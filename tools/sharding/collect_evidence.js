// Collects sharding evidence through mongos and prints one relaxed-EJSON document. Run:
//   docker compose -f deploy/docker-compose.sharded.yml --env-file .env exec -T mongos //     mongosh content --quiet --eval "$(cat tools/sharding/collect_evidence.js)" > evidence.json
const db_ = db.getSiblingDB('content');
const coll = db_.source_documents;
const cfg = db.getSiblingDB('config');
const meta = cfg.collections.findOne({_id: 'content.source_documents'});

const chunks = cfg.chunks.aggregate([{$match: {uuid: meta.uuid}}, {$group: {_id: '$shard', chunks: {$sum: 1}}}, {$sort: {_id: 1}}]).toArray();
const perShard = coll.aggregate([{$collStats: {storageStats: {}}}]).toArray().map(s => ({
  shard: s.shard, documents: s.storageStats.count, data_bytes: s.storageStats.size,
  storage_bytes: s.storageStats.storageSize, index_bytes: s.storageStats.totalIndexSize,
})).sort((a, b) => a.shard.localeCompare(b.shard));
const total = coll.countDocuments({});

function planPath(stage) { // e.g. LIMIT > SHARDING_FILTER > FETCH > IXSCAN(index)
  const parts = [];
  for (let s = stage; s; s = s.inputStage) parts.push(s.indexName ? `${s.stage}(${s.indexName})` : s.stage);
  return parts.join(' > ');
}
function summarize(explain) {
  const wp = explain.queryPlanner.winningPlan;
  const es = explain.executionStats;
  return {
    mongos_stage: wp.stage,
    shards_targeted: (wp.shards || []).map(s => s.shardName),
    per_shard: (es.executionStages.shards || []).map(s => ({
      shard: s.shardName, plan: planPath(s.executionStages),
      returned: s.nReturned, keys_examined: s.totalKeysExamined, docs_examined: s.totalDocsExamined,
      ms: s.executionTimeMillis,
    })),
    n_returned: es.nReturned, total_keys_examined: es.totalKeysExamined,
    total_docs_examined: es.totalDocsExamined, execution_ms: es.executionTimeMillis,
  };
}
const sample = coll.findOne({corpus_scope: 'kaggle-cs', 'metadata.document_type': 'series'}, {_id: 1});
const pointFilter = {_id: sample._id};
const scatterFilter = {corpus_scope: 'synthetic-cs', 'metadata.document_type': 'map'};
const point = coll.find(pointFilter).explain('executionStats');
const scatter = coll.find(scatterFilter, {text: 0}).sort({_id: 1}).limit(20).explain('executionStats');
const scatterCount = coll.explain('executionStats').count(scatterFilter);

print(EJSON.stringify({
  collected_at: new Date().toISOString(),
  mongodb_version: db.version(),
  shards: db.adminCommand({listShards: 1}).shards.map(s => ({_id: s._id, host: s.host})),
  shard_key: meta.key, chunk_size_mb: (cfg.settings.findOne({_id: 'chunksize'}) || {}).value,
  balancer: (({mode, inBalancerRound, numBalancerRounds}) => ({enabled: sh.getBalancerState(), mode, inBalancerRound, numBalancerRounds}))(sh.isBalancerRunning()),
  total_documents: total,
  by_scope: coll.aggregate([{$group: {_id: '$corpus_scope', n: {$sum: 1}}}, {$sort: {_id: 1}}]).toArray(),
  by_scope_and_type: coll.aggregate([{$group: {_id: {scope: '$corpus_scope', type: '$metadata.document_type'}, n: {$sum: 1}}}, {$sort: {'_id.scope': 1, '_id.type': 1}}]).toArray(),
  template_versions: coll.distinct('metadata.template_version'),
  corpus_counters: db_.corpus_counters.find().sort({_id: 1}).toArray(),
  chunks_per_shard: chunks,
  storage_per_shard: perShard,
  explain_point_by_id: {filter: pointFilter, summary: summarize(point), raw: point},
  explain_scatter_scope_type: {filter: scatterFilter, sort: {_id: 1}, limit: 20, summary: summarize(scatter), raw: scatter},
  explain_scatter_count: {filter: scatterFilter, summary: summarize(scatterCount)},
}, null, 1, {relaxed: true}));
