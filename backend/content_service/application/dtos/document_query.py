from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True, kw_only=True)
class DocumentQuery:
    q: str = ""
    document_type: str | None = None
    tournament: str | None = None
    team: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    page: int = 1
    page_size: int = 20
    corpus_scope: str = "kaggle-cs"

    def __post_init__(self):
        if len(self.q) > 200 or self.page < 1 or not 1 <= self.page_size <= 100 or self.page > 10000:
            raise ValueError("Invalid query length or pagination")
        if self.document_type not in (None, "series", "map"):
            raise ValueError("Unknown document type")
        for value in (self.date_from, self.date_to):
            if value:
                date.fromisoformat(value)
        if self.date_to == '9999-12-31':
            raise ValueError('End date is outside supported range')
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Start date must precede end date")
        if self.corpus_scope not in ("kaggle-cs", "synthetic-cs"):
            raise ValueError("Unknown corpus scope")
        if any(len(v) > 200 for v in (self.tournament or "", self.team or "")):
            raise ValueError("Filter too long")
