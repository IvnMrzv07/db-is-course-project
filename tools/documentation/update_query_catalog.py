from pathlib import Path
import ast
root=Path(__file__).resolve().parents[2]
path=root/'docs/stages9-12-queries.md'
old=path.read_text(encoding='utf-8')
intro=old.split('### content_service/')[0]
footer=old[old.index('## Outcomes and indexes'):]
chunks=[intro]
for filename in ['content_service/infrastructure/database/corpus_repository.py','content_service/infrastructure/database/cluster_status.py','content_service/infrastructure/database/corpus_maintenance.py','content_service/worker.py']:
    source=(root/'backend'/filename).read_text(encoding='utf-8')
    for item in ast.walk(ast.parse(source)):
        if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and item.name in ('mongo_filter','initialize','browse','_total','_counters','read','statistics','persist_batch','unsent','mark_sent','status','verify','stats','_delete','_pages','reset','dispatch_once'):
            chunks.append(f'### {filename} — {item.name}\n\n```python\n{ast.get_source_segment(source,item)}\n```\n')
distributed='content_service/infrastructure/database/distributed_aggregation.py'
source=(root/'backend'/distributed).read_text(encoding='utf-8')
for top in ast.parse(source).body:
    for node in [top]+(list(top.body) if isinstance(top,ast.ClassDef) else []):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in ('build_match','build_pipeline','build_map_reduce','count','execute','topology'):
            chunks.append(f'### {distributed} — {node.name}\n\n```python\n{ast.get_source_segment(source,node)}\n```\n')
chunks.append('## Elasticsearch queries (cs-sharded only)\n\n'
    'Search owns alias `cs-documents` -> index `cs-documents-v1` (`INDEX_DEFINITION`: 1 shard, 0 replicas, `dynamic: strict`, analyzer `cs_text` = standard + lowercase + asciifolding; `metadata` kept in `_source` with `enabled: false`). '
    'Writes: one `POST /_bulk` per `search.index` event, `index` actions with `_id = document_id`, `version = document version`, `version_type = external_gte` (409 = stale, skipped). '
    'Reads: `POST /cs-documents/_search` built by `build_search_body` (scoring `multi_match` + non-scoring `filter`, map filter as `post_filter`, highlight with U+E000/U+E001 markers, facets, `timeout: 3s`, `track_total_hits`); '
    '`GET /_cluster/health`, `GET /cs-documents/_count` and a `size: 0` terms aggregation for `/search/status`. '
    'Modes: `all` = `cross_fields` AND, `any` = `best_fields` OR, `phrase` = `phrase`, `fuzzy` = `best_fields` AND with `fuzziness: AUTO:5,9` on name fields only. '
    'Backfill source (Content, MongoDB): `find(backfill_filter(scope)).sort(_id)` in `content_service/reindex.py`.\n')
search='search_service/infrastructure/search/elasticsearch_documents.py'
source=(root/'backend'/search).read_text(encoding='utf-8')
for node in ast.parse(source).body:
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in ('text_query','scope_filters','build_search_body','bulk_payload','summarize_bulk'):
        chunks.append(f'### {search} — {node.name}\n\n```python\n{ast.get_source_segment(source,node)}\n```\n')
reindex='content_service/reindex.py'
source=(root/'backend'/reindex).read_text(encoding='utf-8')
for node in ast.parse(source).body:
    if isinstance(node,ast.FunctionDef) and node.name=='backfill_filter':
        chunks.append(f'### {reindex} — {node.name}\n\n```python\n{ast.get_source_segment(source,node)}\n```\n')
chunks.append('## PostgreSQL queries\n\nDDL and constraints: `ingestion_service/infrastructure/database/migrations/001_replay.sql` (`replay_jobs`) and `003_high_load.sql` (rate and status constraints), `002_partitioning.sql` (`replay_batches`, `replay_outbox`: `PARTITION BY RANGE (created_at)`, daily UTC partitions `<table>_pYYYYMMDD` plus a `DEFAULT` partition; keys `(id, created_at)`; composite FK `replay_outbox(id, created_at) -> replay_batches(id, created_at)`). Parameters are bound by asyncpg.\n\n'
    'Partition DDL is issued by `ingestion_service/infrastructure/database/partitioning.py`; identifiers are built only from the fixed table names and dates. '
    'Creation: `CREATE TABLE <table>_pYYYYMMDD PARTITION OF <table> FOR VALUES FROM (day 00:00 UTC) TO (next day 00:00 UTC)`; rows stranded in `DEFAULT` are moved with `CREATE TABLE ... (LIKE ...)`, `INSERT ... SELECT`, `DELETE` and `ALTER TABLE ... ATTACH PARTITION`. '
    "Retention: `LOCK TABLE replay_batches, replay_outbox IN ACCESS EXCLUSIVE MODE` (with `lock_timeout`), `count(*)` of `NOT sent` / `status = 'pending'` rows in the expired partitions, then `DROP TABLE replay_outbox_pD`, `ALTER TABLE replay_batches DETACH PARTITION replay_batches_pD`, `DROP TABLE replay_batches_pD`.\n")
for filename in ['ingestion_service/infrastructure/database/replay_store.py','ingestion_service/worker.py','ingestion_service/presentation/api/app.py','ingestion_service/infrastructure/database/partitioning.py']:
    for item in ast.walk(ast.parse((root/'backend'/filename).read_text(encoding='utf-8'))):
        if isinstance(item,ast.Constant) and isinstance(item.value,str) and item.value.strip().upper().startswith(('SELECT ','INSERT INTO ','UPDATE ','DELETE ')):
            chunks.append(f'### {filename}:{item.lineno}\n\n```sql\n{item.value.strip()}\n```\n')
path.write_text('\n'.join(chunks)+footer,encoding='utf-8')
