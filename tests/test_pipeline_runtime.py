"""Whole write pipeline on real PostgreSQL and MongoDB (opt-in); only RabbitMQ is an in-memory double.

TEST_MONGO_URL must be a replica set or mongos, TEST_POSTGRES_URL an isolated server.
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
from pymongo import AsyncMongoClient

from content_service.application.services.commands.corpus_command_service import CorpusCommandService
from content_service.infrastructure.database.corpus_maintenance import CorpusMaintenance, LoadJob
from content_service.infrastructure.database.corpus_repository import MongoCorpusRepository
from ingestion_service.infrastructure.database.replay_store import PostgresReplayStore, ProductionLimits
from ingestion_service.infrastructure.datasets.load_generator import prepare_load_base
from tests.memory_pipeline import running_pipeline, wait_until

pytestmark = pytest.mark.skipif(not (os.getenv('TEST_MONGO_URL') and os.getenv('TEST_POSTGRES_URL')),
                                reason='Requires isolated MongoDB and PostgreSQL')
SNAPSHOT = Path(__file__).resolve().parents[1] / 'data' / 'synthetic' / 'synthetic-cs.csv.gz'


def pipeline_test(limits, body):
    async def scenario(directory):
        url, name = os.environ['TEST_POSTGRES_URL'], 'test_' + uuid4().hex
        admin = await asyncpg.connect(url)
        await admin.execute(f'CREATE SCHEMA {name}')
        pool = await asyncpg.create_pool(url, min_size=1, max_size=5, server_settings={'search_path': name})
        client = AsyncMongoClient(os.environ['TEST_MONGO_URL'], serverSelectionTimeoutMS=5000, tz_aware=True)
        try:
            store = PostgresReplayStore(pool, directory, limits=limits)
            await store.initialize()
            repository = MongoCorpusRepository(client[name])
            await repository.initialize()
            await body(store, repository, CorpusMaintenance(client, name))
        finally:
            await client.drop_database(name)
            await client.close()
            await pool.close()
            await admin.execute(f'DROP SCHEMA {name} CASCADE')
            await admin.close()
    return scenario


def load_job(state):
    strategy = 'random' if state['snapshot_id'] == 'load-cs-random' else 'ordered'
    return LoadJob(UUID(state['id']), datetime.fromisoformat(state['created_at']), strategy)


@pytest.mark.parametrize('snapshot', ['load-cs', 'load-cs-random'])
def test_load_job_runs_through_outages_and_verifies(tmp_path, snapshot):
    """Every fifth commit fails as if a shard were absent: the job still completes and nothing is lost or repeated."""
    async def body(store, repository, maintenance):
        commands, real, calls = CorpusCommandService(repository), repository.persist_batch, 0

        class Flaky:
            async def persist_batch(self, batch):
                nonlocal calls
                calls += 1
                if calls % 5 == 0:
                    from content_service.application.ports.corpus_store import StoreUnavailable
                    raise StoreUnavailable('shard absent')
                return await real(batch)
        commands.repository = Flaky()
        job = await store.create_job(snapshot, 0, uuid4().hex)
        async with running_pipeline(store, repository, commands) as broker:
            async def completed():
                return (await store.get_job(job['id']))['status'] != 'running'
            await wait_until(completed, 90)
            assert broker.quarantined == 0
        state = await store.get_job(job['id'])
        assert (state['status'], state['inserted'], state['duplicates'], state['backlog']) == ('completed', 6000, 0, 0)
        assert calls > 24 / 2
        report = await maintenance.verify(load_job(state), state['checkpoint'], state['attempted'])
        assert report['ok'] and report['found'] == 6000 and report['missing'] == 0
        assert report['unexpected'] == (0 if snapshot == 'load-cs' else None)
        assert (await repository.statistics())['stored_by_scope']['load-cs'] == 6000
        # verify really detects a loss.
        lost = load_job(state).identifiers(1234, 1235)[0]
        await repository.documents.delete_one({'_id': lost})
        report = await maintenance.verify(load_job(state), 6000, 6000)
        assert not report['ok'] and report['missing_sample'] == [{'index': 1234, 'id': lost}]
    prepare_load_base(SNAPSHOT, tmp_path, rows=200)
    asyncio.run(pipeline_test(ProductionLimits(250, 2000, 6000), body)(tmp_path))


def test_partial_and_full_deletion(tmp_path):
    async def body(store, repository, maintenance):
        commands = CorpusCommandService(repository)
        jobs = [await store.create_job('load-cs', 0, uuid4().hex) for _ in range(2)]
        delivered = []
        real = repository.persist_batch

        async def remember(batch):
            delivered.append(batch)
            return await real(batch)
        repository.persist_batch = remember
        async with running_pipeline(store, repository, commands):
            async def completed():
                return {(await store.get_job(job['id']))['status'] for job in jobs} == {'completed'}
            await wait_until(completed, 90)
        total = repository.documents.count_documents
        assert await total({}) == 12000
        factual = {'_id': str(uuid4()), 'corpus_scope': 'kaggle-cs', 'publication_status': 'published', 'metadata': {}}
        await repository.documents.insert_one(factual)
        assert (await maintenance.purge(percent=25, dry_run=True))['target'] == 3000 and await total({}) == 12001
        report = await maintenance.purge(percent=25)
        assert (report['deleted'], report['stored_after']) == (3000, 9000)
        state = await store.get_job(jobs[1]['id'])
        report = await maintenance.purge(job=load_job(state), produced=state['attempted'])
        assert report['deleted'] == 6000 and report['stored_after'] == 3000
        # A redelivered batch is answered from its receipt and does not resurrect deleted documents.
        again = [batch for batch in delivered if batch['job_id'] == jobs[1]['id']][0]
        assert (await commands.store(again))['inserted'] == len(again['documents'])
        assert await total({'corpus_scope': 'load-cs'}) == 3000
        assert (await maintenance.purge(limit=1))['deleted'] == 1
        report = await maintenance.purge()
        assert (report['deleted'], report['stored_after']) == (2999, 0)
        assert await total({}) == 1 and await repository.documents.find_one({'_id': factual['_id']})
        for arguments in ({'percent': 0}, {'percent': 101}, {'limit': 0}, {'percent': 5, 'limit': 5}, {'job': load_job(state)}):
            with pytest.raises(ValueError):
                await maintenance.purge(**arguments)
        await maintenance.reset()
        assert await total({}) == 0 and (await maintenance.stats())['counters'] == {'kaggle-cs': 0, 'synthetic-cs': 0, 'load-cs': 0}
        repository.persist_batch = real
        assert (await commands.store(again))['inserted'] == len(again['documents'])  # the recreated store accepts writes
    prepare_load_base(SNAPSHOT, tmp_path, rows=200)
    asyncio.run(pipeline_test(ProductionLimits(500, 3000, 6000), body)(tmp_path))


def test_deletion_during_writing_keeps_counters_exact(tmp_path):
    async def body(store, repository, maintenance):
        job = await store.create_job('load-cs', 0, uuid4().hex)
        async with running_pipeline(store, repository, CorpusCommandService(repository)):
            async def started():
                return (await maintenance.stored_load_documents()) >= 4000
            await wait_until(started, 60)
            report = await maintenance.purge(percent=50)
            assert report['deleted'] >= 2000

            async def completed():
                return (await store.get_job(job['id']))['status'] == 'completed'
            await wait_until(completed, 90)
        remaining = await repository.documents.count_documents({'corpus_scope': 'load-cs'})
        assert remaining == 20000 - report['deleted'] == await maintenance.stored_load_documents()
    prepare_load_base(SNAPSHOT, tmp_path, rows=200)
    asyncio.run(pipeline_test(ProductionLimits(500, 2000, 20000), body)(tmp_path))


def test_lean_indexes_skip_load_documents_and_survive_restarts(tmp_path):
    async def body(store, repository, maintenance):
        await maintenance.reset(lean_indexes=True)
        names = set(await repository.documents.index_information())
        await repository.initialize()  # a service start keeps the profile instead of adding the full indexes
        assert set(await repository.documents.index_information()) == names
        assert sum(name.endswith('_factual') for name in names) == 4
        common = {'publication_status': 'published', 'metadata': {'team1': 'A', 'played_at': '2024-01-01'}}
        await repository.documents.insert_many([{**common, '_id': str(uuid4()), 'corpus_scope': scope}
                                                for scope in ('kaggle-cs', 'load-cs', 'load-cs')])
        plan = await repository.db.command('explain', {'find': 'source_documents',
            'filter': {'corpus_scope': 'kaggle-cs', 'metadata.team1': 'A'}}, verbosity='executionStats')
        assert 'metadata.team1_1__id_1_factual' in str(plan['queryPlanner'])  # factual filters still use their index
        found = await repository.documents.find({'corpus_scope': 'kaggle-cs', 'metadata.team1': 'A'}).to_list()
        assert len(found) == 1
    asyncio.run(pipeline_test(ProductionLimits(), body)(tmp_path))
