"""Shard availability as the router sees it. Read-only; never opens connections to shards directly."""
from datetime import datetime, timezone
from pymongo.errors import PyMongoError

COUNT_TIMEOUT_MS = 1000


def shard_view(shard: dict, replica_sets: dict) -> dict:
    members = [{'address': host['addr'], 'reachable': bool(host['ok']), 'primary': bool(host['ismaster'])}
               for host in replica_sets.get(shard['_id'], {}).get('hosts', [])]
    return {'id': shard['_id'], 'members': members, 'available': any(m['reachable'] and m['primary'] for m in members)}


class MongoClusterStatus:
    def __init__(self, client, database='content'):
        self.client, self.database = client, database

    async def status(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        hello = await self.client.admin.command('hello')
        if hello.get('msg') != 'isdbgrid':
            return {'topology': 'single', 'shards': [], 'available': bool(hello.get('isWritablePrimary')), 'sampled_at': now}
        shards = (await self.client.admin.command('listShards'))['shards']
        pools = (await self.client.admin.command('connPoolStats')).get('replicaSets', {})
        views = [shard_view(shard, pools) for shard in sorted(shards, key=lambda shard: shard['_id'])]
        primary = await self.client.config.databases.find_one({'_id': self.database}, {'primary': 1})
        available = all(view['available'] for view in views)
        counts = {}
        if available:  # $collStats needs every shard; during an outage only availability is reported
            try:
                cursor = await self.client[self.database].source_documents.aggregate(
                    [{'$collStats': {'count': {}}}], maxTimeMS=COUNT_TIMEOUT_MS)
                counts = {row['shard']: row['count'] async for row in cursor}
            except PyMongoError:
                pass
        for view in views:
            # Collection metadata: after an unclean stop (SIGKILL) WiredTiger reports too few documents until
            # `validate` runs, although nothing is lost. Never use it as proof; `content_service.manage verify` is.
            view['documents_estimate'] = counts.get(view['id'])
            # Receipts, counters and the outbox are unsharded: without this shard nothing can commit.
            view['database_primary'] = bool(primary) and primary['primary'] == view['id']
        return {'topology': 'sharded', 'shards': views, 'available': available, 'sampled_at': now}
