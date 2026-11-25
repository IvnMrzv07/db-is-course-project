#!/usr/bin/env bash
# Idempotent initialisation of the sharded MongoDB cluster used by deploy/docker-compose.sharded.yml.
# cfgRS (config server) + <shard>RS single-member replica sets (SHARDS, default three) + mongos.
set -euo pipefail

read -r -a SHARD_NAMES <<< "${SHARDS:-shard1 shard2 shard3}"
CHUNK_SIZE_MB="${CHUNK_SIZE_MB:-128}"
INITIAL_CHUNKS="${INITIAL_CHUNKS:-$((4 * ${#SHARD_NAMES[@]}))}"

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
SHARD_LIST=""
for name in "${SHARD_NAMES[@]}"; do
  init_rs "$name:27018" "${name}RS" false
  SHARD_LIST="$SHARD_LIST['${name}RS', '${name}RS/$name:27018'],"
done

wait_ping mongos:27017
mongosh --host mongos:27017 --quiet --eval "
  const existing = db.adminCommand({listShards: 1}).shards.map(s => s._id);
  for (const [id, host] of [$SHARD_LIST]) {
    if (!existing.includes(id)) printjson(sh.addShard(host));
  }
  // Data is spread by the pre-split below; the chunk size only decides when the balancer starts migrations.
  db.getSiblingDB('config').settings.updateOne({_id: 'chunksize'}, {\$set: {value: $CHUNK_SIZE_MB}}, {upsert: true});
  sh.enableSharding('content');
  const content = db.getSiblingDB('content');
  const coll = db.getSiblingDB('config').collections.findOne({_id: 'content.source_documents'});
  if (!coll) {
    content.source_documents.createIndex({_id: 'hashed'});
    // Hashed key on an empty collection: chunks are pre-split and spread over all shards before any insert.
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
