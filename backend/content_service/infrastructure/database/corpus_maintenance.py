"""Operator maintenance of the document store: verification after outages, deletion and statistics.

Deletion is limited to generated `load-cs` documents; only `reset` touches the factual corpus, and it drops
everything. Batch receipts survive a partial deletion on purpose: a redelivered batch is answered from its receipt
and cannot bring deleted documents back.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from content_service.infrastructure.database.corpus_repository import MongoCorpusRepository, counter_id, counters_by_scope
from contracts.load_ids import LOAD_SCOPE, MAX_INDEX, load_document_id

CHUNK = 2000
PARALLEL = 4
SAMPLE = 20
COLLECTIONS = ('source_documents', 'committed_batches', 'outbox', 'corpus_counters')
CHUNKS_PER_SHARD = 4  # same pre-split as deploy/mongo-sharded-init.sh


@dataclass(frozen=True)
class LoadJob:
    """Identity of a generated job: enough to recompute the ID of each of its documents."""

    job_id: UUID
    created_at: datetime
    strategy: str

    def identifiers(self, start: int, end: int) -> list[str]:
        return [str(load_document_id(self.job_id, self.created_at, index, self.strategy)) for index in range(start, end)]

    @property
    def bounds(self) -> tuple[str, str] | None:
        if self.strategy != 'ordered':
            return None
        return self.identifiers(0, 1)[0], self.identifiers(MAX_INDEX, MAX_INDEX + 1)[0]


class CorpusMaintenance:
    def __init__(self, client, database: str = 'content'):
        self.client, self.name = client, database
        self.db = client.get_database(database)
        self.documents = self.db.source_documents

    # ----------------------------------------------------------------- verification

    async def verify(self, job: LoadJob, confirmed: int, produced: int) -> dict:
        """Look up every expected ID. Documents below `confirmed` must exist; up to `produced` they may be in flight."""
        if not 0 <= confirmed <= produced:
            raise ValueError('Expected 0 <= confirmed <= produced')
        limit, found, in_flight, missing = asyncio.Semaphore(PARALLEL), 0, 0, []

        async def check(start: int, end: int):
            nonlocal found, in_flight
            async with limit:
                identifiers = job.identifiers(start, end)
                present = {row['_id'] async for row in self.documents.find({'_id': {'$in': identifiers}}, {'_id': 1})}
            for offset, identifier in enumerate(identifiers, start):
                if identifier in present:
                    found, in_flight = found + (offset < confirmed), in_flight + (offset >= confirmed)
                elif offset < confirmed:
                    missing.append((offset, identifier))
        # One group of chunks at a time: millions of IDs are never in memory together.
        for group in range(0, produced, CHUNK * PARALLEL):
            await asyncio.gather(*(check(start, min(start + CHUNK, produced))
                                   for start in range(group, min(group + CHUNK * PARALLEL, produced), CHUNK)))
        missing.sort()
        unexpected = None
        if job.bounds:
            first, last = job.bounds
            unexpected = await self.documents.count_documents({'_id': {'$gte': first, '$lte': last}}) - found - in_flight
        return {'job_id': str(job.job_id), 'confirmed': confirmed, 'found': found, 'missing': len(missing),
                'missing_sample': [{'index': index, 'id': identifier} for index, identifier in missing[:SAMPLE]],
                'in_flight_found': in_flight, 'unexpected': unexpected, 'ok': not missing and not unexpected}

    # ----------------------------------------------------------------- statistics

    async def stats(self, *, exact: bool = True) -> dict:
        counters = counters_by_scope([row async for row in self.db.corpus_counters.find({})])
        shards = []
        async for row in await self.documents.aggregate([{'$collStats': {'storageStats': {}}}]):
            storage = row['storageStats']
            # `count` and `size` are metadata and stay too low after an unclean stop of a shard, until `validate`.
            shards.append({'shard': row.get('shard', 'single'), 'documents_estimate': storage['count'], 'data_bytes': storage['size'],
                           'storage_bytes': storage['storageSize'], 'index_bytes': storage['totalIndexSize'],
                           'reusable_bytes': storage.get('freeStorageSize', 0)})
        shards.sort(key=lambda row: row['shard'])
        return {'counters': counters, 'documents_exact': await self.documents.count_documents({}) if exact else None,
                'documents_estimate': sum(row['documents_estimate'] for row in shards), 'shards': shards,
                'receipts': await self.db.committed_batches.estimated_document_count(),
                'outbox': await self.db.outbox.estimated_document_count()}

    # ----------------------------------------------------------------- partial deletion

    async def _delete(self, identifiers: list[str]) -> int:
        """Documents and their counter change in one transaction, so the dashboard total stays exact."""
        slot = counter_id(LOAD_SCOPE, str(uuid4()))

        async def transaction(session):
            result = await self.documents.delete_many({'_id': {'$in': identifiers}, 'corpus_scope': LOAD_SCOPE}, session=session)
            if result.deleted_count:
                await self.db.corpus_counters.update_one({'_id': slot}, {'$inc': {'stored_documents': -result.deleted_count}},
                                                         upsert=True, session=session)
            return result.deleted_count
        async with self.client.start_session() as session:
            return await session.with_transaction(transaction, read_concern=ReadConcern('snapshot'),
                                                  write_concern=WriteConcern('majority'))

    async def _pages(self, total: int):
        """Load document IDs in ID order (for ordered IDs: the oldest first)."""
        last, remaining = '', total
        while remaining > 0:
            rows = self.documents.find({'corpus_scope': LOAD_SCOPE, 'publication_status': 'published', '_id': {'$gt': last}},
                                       {'_id': 1}).sort('_id', 1).limit(min(CHUNK * PARALLEL, remaining))
            page = [row['_id'] async for row in rows]
            if not page:
                return
            last, remaining = page[-1], remaining - len(page)
            yield page

    async def _job_pages(self, job: LoadJob, produced: int):
        for start in range(0, produced, CHUNK * PARALLEL):
            yield job.identifiers(start, min(start + CHUNK * PARALLEL, produced))

    async def stored_load_documents(self) -> int:
        return counters_by_scope([row async for row in self.db.corpus_counters.find({})]).get(LOAD_SCOPE, 0)

    async def purge(self, *, percent: float | None = None, limit: int | None = None, job: LoadJob | None = None,
                    produced: int = 0, dry_run: bool = False, pause: float = 0, progress=None) -> dict:
        """Delete a share, a number or one job of the load documents; everything in the scope by default."""
        if sum(value is not None for value in (percent, limit, job)) > 1:
            raise ValueError('Choose one of percent, limit and job')
        if percent is not None and not 0 < percent <= 100 or limit is not None and limit < 1 or job and produced < 1:
            raise ValueError('Invalid deletion size')
        before = await self.stored_load_documents()
        target = produced if job else min(before, limit if limit is not None else round(before * (percent or 100) / 100))
        # A complete purge is not limited by the counter: whatever is in the scope goes.
        bounded = target if limit is not None or (percent is not None and percent < 100) else 2**63
        report = {'scope': LOAD_SCOPE, 'stored_before': before, 'target': target, 'deleted': 0, 'dry_run': dry_run}
        if dry_run:
            return report
        async for page in (self._job_pages(job, produced) if job else self._pages(bounded)):
            deleted = await asyncio.gather(*(self._delete(page[start:start + CHUNK]) for start in range(0, len(page), CHUNK)))
            report['deleted'] += sum(deleted)
            if progress:
                progress(report['deleted'], target)
            if pause:
                await asyncio.sleep(pause)
        report['stored_after'] = await self.stored_load_documents()
        return report

    # ----------------------------------------------------------------- full deletion

    async def reset(self, *, lean_indexes: bool = False) -> dict:
        """Drop all corpus collections (disk space returns at once) and recreate them, sharded behind mongos."""
        before = await self.stats()
        for name in COLLECTIONS:
            await self.db.drop_collection(name)
        shards = 0
        if (await self.client.admin.command('hello')).get('msg') == 'isdbgrid':
            shards = len((await self.client.admin.command('listShards'))['shards'])
            await self.client.admin.command('enableSharding', self.name)
            await self.documents.create_index([('_id', 'hashed')])
            await self.client.admin.command({'shardCollection': f'{self.name}.source_documents', 'key': {'_id': 'hashed'},
                                             'numInitialChunks': CHUNKS_PER_SHARD * shards})
        await MongoCorpusRepository(self.db).initialize(lean_indexes=lean_indexes)
        return {'dropped_documents': before['documents_exact'], 'shards': shards, 'after': await self.stats()}

    async def compact(self) -> list[dict]:
        """Return freed file space to the OS after a partial deletion; runs on one shard member at a time."""
        hello = await self.client.admin.command('hello')
        if hello.get('msg') == 'isdbgrid':
            shards = (await self.client.admin.command('listShards'))['shards']
            members = [(shard['_id'], address) for shard in shards for address in shard['host'].split('/', 1)[1].split(',')]
        else:
            members = [('single', hello['me'])] if hello.get('me') else []
        results = []
        for shard, address in members:
            direct = AsyncMongoClient(f'mongodb://{address}/', directConnection=True, serverSelectionTimeoutMS=5000)
            try:
                reply = await direct.get_database(self.name).command('compact', 'source_documents')
                results.append({'shard': shard, 'member': address, 'bytes_freed': reply.get('bytesFreed')})
            except PyMongoError as exc:
                results.append({'shard': shard, 'member': address, 'error': str(exc)[:200]})
            finally:
                await direct.close()
        return results
