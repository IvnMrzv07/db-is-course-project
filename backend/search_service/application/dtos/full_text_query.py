from __future__ import annotations

from dataclasses import dataclass

SEARCH_MODES = ('all', 'any', 'phrase', 'fuzzy')
SCOPES = ('all', 'kaggle-cs', 'synthetic-cs')
MAX_RESULT_WINDOW = 10_000


@dataclass(frozen=True, kw_only=True)
class FullTextQuery:
    """Validated `/api/v1/search` request.

    mode: all = every word in any searchable field (cross-field AND), any = at least one word (OR),
    phrase = exact word sequence, fuzzy = every word with typo tolerance.
    include_synthetic=False excludes `is_synthetic` documents regardless of corpus_scope.
    """

    q: str = ''
    mode: str = 'all'
    corpus_scope: str = 'all'
    document_type: str | None = None
    map_name: str | None = None
    include_synthetic: bool = True
    page: int = 1
    page_size: int = 20

    def __post_init__(self):
        if len(self.q) > 200:
            raise ValueError('Query is too long (max 200 characters)')
        if self.mode not in SEARCH_MODES:
            raise ValueError('Unknown search mode')
        if self.corpus_scope not in SCOPES:
            raise ValueError('Unknown corpus scope')
        if self.document_type not in (None, 'series', 'map'):
            raise ValueError('Unknown document type')
        if self.map_name is not None and not 1 <= len(self.map_name) <= 64:
            raise ValueError('Map name filter is too long')
        if self.page < 1 or not 1 <= self.page_size <= 50:
            raise ValueError('Invalid pagination')
        if self.page * self.page_size > MAX_RESULT_WINDOW:
            raise ValueError('Only the first 10 000 results can be paged; refine the query')

    @property
    def text(self) -> str:
        return ' '.join(self.q.split())

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
