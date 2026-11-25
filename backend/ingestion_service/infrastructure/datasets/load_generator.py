"""Unbounded `load-cs` source: Counter-Strike texts generated on the fly for high-load runs.

Every document is a variation of a row of the generated `synthetic-cs` snapshot (pseudonymous teams and players),
converted by the same `convert()` as the prepared snapshots. It is a pure function of (job, index): nothing is
stored on disk, and a batch rebuilt after a crash is byte-for-byte the batch that was staged.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from contracts.load_ids import LOAD_SCOPE, LOAD_SNAPSHOTS, load_document_id
from ingestion_service.infrastructure.datasets.prepare_corpus import CorpusSource, SYNTHETIC, convert

GENERATOR_VERSION = 'load-generator-v1'
LOAD = CorpusSource(LOAD_SCOPE, 'cs_load_generator', None, True)
BASE_ROWS = 4000
BASE_FILE, MANIFEST_FILE = 'load-cs.base.jsonl', 'load-cs.manifest.json'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
_SLOTS = tuple(f'team{team}_player{slot}' for team in (1, 2) for slot in range(1, 6))


def prepare_load_base(snapshot: Path, output: Path, rows: int = BASE_ROWS) -> dict:
    """Keep the first valid rows of the synthetic snapshot (non-empty columns only) as generator input."""
    output.mkdir(parents=True, exist_ok=True)
    text = gzip.decompress(snapshot.read_bytes()).decode('utf-8-sig')
    digest, count = hashlib.sha256(), 0
    with (output / BASE_FILE).open('w', encoding='utf-8', newline='\n') as target:
        for row in csv.DictReader(io.StringIO(text)):
            if count == rows:
                break
            try:
                convert(row, 'base', SYNTHETIC)
            except ValueError:
                continue
            line = json.dumps({key: value for key, value in row.items() if value}, ensure_ascii=False) + '\n'
            target.write(line)
            digest.update(line.encode('utf-8'))
            count += 1
    if not count:
        raise ValueError('Synthetic snapshot has no valid rows')
    manifest = {'snapshot_id': LOAD_SCOPE, 'generator_version': GENERATOR_VERSION, 'base_rows': count,
                'base_sha256': digest.hexdigest(), 'is_synthetic': True}
    (output / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def _shift(row: dict, field: str, delta: float) -> None:
    if row.get(field):
        row[field] = f'{max(0.0, float(row[field]) + delta):.1f}'


def vary(base: dict, job_id: UUID, index: int) -> dict:
    """Deterministic variation: own match identity, date within 23 days and slightly different player statistics."""
    bits = int.from_bytes(hashlib.blake2b(f'{job_id}:{index}'.encode(), digest_size=24).digest(), 'big')
    row = dict(base)
    row['match_id'] = f'L{job_id.hex[:8]}-{index:010d}'
    if row['is_total'] == 'False':
        row['game_id'] = row['match_id'] + '-M1'
    minutes, bits = bits & 0x7FFF, bits >> 15
    row['datetime'] = (datetime.strptime(base['datetime'], DATE_FORMAT) + timedelta(minutes=minutes)).strftime(DATE_FORMAT)
    for slot in _SLOTS:
        if not row.get(slot):
            continue
        _shift(row, slot + '_kills', (bits & 7) - 3)
        _shift(row, slot + '_assists', ((bits >> 3) & 3) - 1)
        _shift(row, slot + '_adr', (((bits >> 5) & 127) - 64) / 10)
        bits >>= 12
        if row.get(slot + '_kills') and row.get(slot + '_deaths'):
            row[slot + '_kddiff'] = f"{float(row[slot + '_kills']) - float(row[slot + '_deaths']):.1f}"
    row['synthetic_generator'] = GENERATOR_VERSION
    return row


class LoadSnapshot:
    """Same interface as a prepared snapshot; `total` only limits one job."""

    def __init__(self, base: list[dict], snapshot_hash: str, strategy: str, total: int):
        self.base, self.snapshot_hash, self.strategy, self.total = base, snapshot_hash, strategy, total

    def __len__(self):
        return self.total

    def document(self, job_id: UUID, job_created_at: datetime, index: int) -> dict:
        document = convert(vary(self.base[index % len(self.base)], job_id, index), self.snapshot_hash, LOAD)
        document['id'] = str(load_document_id(job_id, job_created_at, index, self.strategy))
        return document

    def window(self, job_id: UUID, job_created_at: datetime, start: int, end: int) -> list[dict]:
        return [self.document(job_id, job_created_at, index) for index in range(start, end)]


def load_snapshots(data_dir: Path, total: int) -> dict:
    """Catalog entries `snapshot id -> (manifest, LoadSnapshot)`; empty when the base was not prepared."""
    manifest_path = data_dir / MANIFEST_FILE
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    raw = (data_dir / BASE_FILE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['base_sha256'] or manifest['generator_version'] != GENERATOR_VERSION:
        raise ValueError('Load generator base does not match its manifest')
    base = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    if len(base) != manifest['base_rows']:
        raise ValueError('Load generator base count mismatch')
    entries = {}
    for name, strategy in LOAD_SNAPSHOTS.items():
        digest = hashlib.sha256(f"{manifest['base_sha256']}:{GENERATOR_VERSION}:{strategy}".encode()).hexdigest()
        entries[name] = ({'snapshot_id': name, 'jsonl_sha256': digest, 'accepted': total, 'rejected': 0,
                          'is_synthetic': True}, LoadSnapshot(base, digest, strategy, total))
    return entries
