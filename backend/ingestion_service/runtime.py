import os
import asyncpg
from ingestion_service.infrastructure.database.replay_store import PostgresReplayStore
from ingestion_service.infrastructure.database.partitioning import PartitionPolicy
from ingestion_service.application.services.commands.replay_operations import ReplayOperations
from ingestion_service.application.services.queries.replay_monitor import ReplayMonitor
from ingestion_service.presentation.api.controllers.replay_controller import ReplayController

async def build_runtime():
    pool = await asyncpg.create_pool(os.environ['INGESTION_DATABASE_URL'], min_size=1, max_size=5, command_timeout=10)
    store = PostgresReplayStore(pool, os.getenv('CORPUS_DIR','data/prepared'), PartitionPolicy.from_env())
    await store.initialize()
    return pool, store, ReplayController(ReplayOperations(store), ReplayMonitor(store))
