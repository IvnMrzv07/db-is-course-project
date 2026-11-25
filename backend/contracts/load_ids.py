"""Deterministic identifiers of generated load documents, shared by Ingestion (producing) and Content (verifying).

An ID depends only on the job and the document's index in that job. Redelivery and re-generation therefore give
the same ID, and "was anything lost?" can be answered by recomputing every expected ID instead of storing a list.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5

LOAD_SCOPE = 'load-cs'
# Two replay snapshots write the same corpus scope and differ only in the order of their document IDs.
LOAD_SNAPSHOTS = {'load-cs': 'ordered', 'load-cs-random': 'random'}
MAX_INDEX = 2**32 - 1
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def load_document_id(job_id: UUID, job_created_at: datetime, index: int, strategy: str = 'ordered') -> UUID:
    """`ordered`: UUIDv8 that grows with the job start and the index, so inserts append to the `_id` B-tree.
    `random`: UUIDv5, uniformly distributed (the ID order of the prepared snapshots)."""
    if not 0 <= index <= MAX_INDEX:
        raise ValueError('Load document index out of range')
    if strategy == 'random':
        return uuid5(job_id, f'load:{index}')
    if strategy != 'ordered':
        raise ValueError('Unknown load ID strategy')
    # 48-bit start in ms | version 8 | 12 job bits | variant | 32-bit index | 30 job bits (RFC 9562 UUIDv8)
    milliseconds = (job_created_at - _EPOCH) // timedelta(milliseconds=1)
    return UUID(int=(milliseconds << 80) | (0x8 << 76) | ((job_id.int & 0xFFF) << 64) | (0b10 << 62)
                | (index << 30) | ((job_id.int >> 12) & 0x3FFFFFFF))
