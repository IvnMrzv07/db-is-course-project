"""Request for a distributed (map-reduce style) aggregation over template_version = "2" documents."""
from dataclasses import dataclass

METRICS = ("map_pool", "document_types", "series_scores", "top_players")
ENGINES = ("aggregate", "mapreduce", "both")
SCOPES = ("all", "kaggle-cs", "synthetic-cs")
DOCUMENT_TYPES = ("series", "map")

# Series and map documents describe the same match at different granularity: a series already contains
# the totals of its maps. A metric is therefore always computed over exactly one document type, except
# `document_types`, which only counts documents per (scope, type) and never sums values across types.
FIXED_DOCUMENT_TYPE = {"map_pool": "map", "series_scores": "series"}


@dataclass(frozen=True, kw_only=True)
class DistributedAggregationQuery:
    metric: str = "map_pool"
    corpus_scope: str = "all"
    document_type: str | None = None
    engine: str = "aggregate"
    limit: int = 20
    explain: bool = True

    def __post_init__(self):
        if self.metric not in METRICS:
            raise ValueError("Unknown metric")
        if self.engine not in ENGINES:
            raise ValueError("Unknown engine")
        if self.corpus_scope not in SCOPES:
            raise ValueError("Unknown corpus scope")
        if self.document_type not in (None, *DOCUMENT_TYPES):
            raise ValueError("Unknown document type")
        if not 1 <= self.limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        fixed = FIXED_DOCUMENT_TYPE.get(self.metric)
        if fixed and self.document_type not in (None, fixed):
            raise ValueError(f"Metric {self.metric} is defined only for {fixed} documents")
        if self.metric == "top_players" and self.document_type is None:
            raise ValueError("top_players requires document_type: series and map statistics must not be summed")

    @property
    def resolved_document_type(self) -> str | None:
        return FIXED_DOCUMENT_TYPE.get(self.metric, self.document_type)
