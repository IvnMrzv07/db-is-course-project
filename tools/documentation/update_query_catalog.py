from pathlib import Path
import ast
root=Path(__file__).resolve().parents[2]
path=root/'docs/stages9-12-queries.md'
old=path.read_text(encoding='utf-8')
intro=old.split('### content_service/')[0]
footer=old[old.index('## Outcomes and indexes'):]
chunks=[intro]
for filename in ['content_service/infrastructure/database/corpus_repository.py','content_service/worker.py']:
    source=(root/'backend'/filename).read_text(encoding='utf-8')
    for item in ast.walk(ast.parse(source)):
        if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and item.name in ('mongo_filter','initialize','browse','read','statistics','persist_batch','dispatch'):
            chunks.append(f'### {filename} — {item.name}\n\n```python\n{ast.get_source_segment(source,item)}\n```\n')
chunks.append('## PostgreSQL queries\n\nDDL and constraints: `ingestion_service/infrastructure/database/migrations/001_replay.sql`. Parameters are bound by asyncpg.\n')
for filename in ['ingestion_service/infrastructure/database/replay_store.py','ingestion_service/worker.py','ingestion_service/presentation/api/app.py']:
    for item in ast.walk(ast.parse((root/'backend'/filename).read_text(encoding='utf-8'))):
        if isinstance(item,ast.Constant) and isinstance(item.value,str) and item.value.strip().upper().startswith(('SELECT ','INSERT INTO ','UPDATE ','DELETE ')):
            chunks.append(f'### {filename}:{item.lineno}\n\n```sql\n{item.value.strip()}\n```\n')
path.write_text('\n'.join(chunks)+footer,encoding='utf-8')
