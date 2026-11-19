#!/usr/bin/env bash
# Idempotent initialisation of the sharded MongoDB cluster used by deploy/docker-compose.sharded.yml.
# cfgRS (config server) + shard1RS/shard2RS/shard3RS (single-member replica sets) + mongos.
set -euo pipefail

CHUNK_SIZE_MB="${CHUNK_SIZE_MB:-2}"
INITIAL_CHUNKS="${INITIAL_CHUNKS:-12}"

wait_ping() {
  until mongosh --host "$1" --quiet --eval 'db.adminCommand({ping:1}).ok' >/dev/null 2>&1; do sleep 1; done
}

init_rs() { # host:port rsName configsvr(true|false)
  local host="$1" rs="$2" cfg="$3"
  wait_ping "$host"
  mongosh --host "$host" --quiet --eval "
    try { rs.status(); print('$rs already initiated') }
    catch (e) { rs.initiate({_id: '$rs', configsvr: $cfg, members: [{_id: 0, host: '$host'}]}); print('$rs initiated') }"
  until mongosh --host "$host" --quiet --eval 'quit(db.hello().isWritablePrimary ? 0 : 1)' >/dev/null 2>&1; do sleep 1; done
}

init_rs cfg1:27019 cfgRS true
init_rs shard1:27018 shard1RS false
init_rs shard2:27018 shard2RS false
init_rs shard3:27018 shard3RS false

wait_ping mongos:27017
mongosh --host mongos:27017 --quiet --eval "
  const existing = db.adminCommand({listShards: 1}).shards.map(s => s._id);
  for (const [id, host] of [['shard1RS', 'shard1RS/shard1:27018'], ['shard2RS', 'shard2RS/shard2:27018'], ['shard3RS', 'shard3RS/shard3:27018']]) {
    if (!existing.includes(id)) printjson(sh.addShard(host));
  }
  // Small chunks so that 100k documents (~350 MB) span many chunks on every shard.
  db.getSiblingDB('config').settings.updateOne({_id: 'chunksize'}, {\$set: {value: $CHUNK_SIZE_MB}}, {upsert: true});
  sh.enableSharding('content');
  const content = db.getSiblingDB('content');
  const coll = db.getSiblingDB('config').collections.findOne({_id: 'content.source_documents'});
  if (!coll) {
    content.source_documents.createIndex({_id: 'hashed'});
    // Hashed key on an empty collection: chunks are pre-split and spread over all 3 shards before any insert.
    printjson(db.adminCommand({shardCollection: 'content.source_documents', key: {_id: 'hashed'}, numInitialChunks: $INITIAL_CHUNKS}));
  } else {
    print('content.source_documents already sharded');
  }
  sh.startBalancer();
  printjson(db.getSiblingDB('config').chunks.aggregate([
    {\$lookup: {from: 'collections', localField: 'uuid', foreignField: 'uuid', as: 'c'}},
    {\$match: {'c._id': 'content.source_documents'}},
    {\$group: {_id: '\$shard', chunks: {\$sum: 1}}}, {\$sort: {_id: 1}}]).toArray());
"
