"""Reduce-side logic shared by both engines: derived indicators, engine comparison, coverage check."""
import math
from dataclasses import dataclass
from content_service.application.dtos.distributed_query import DistributedAggregationQuery
from content_service.application.ports.distributed_aggregation import DistributedAggregationReader

# Field that counts source documents in each group; summing it over all groups must give the matched count.
DOCUMENT_COUNTER = {"map_pool": "maps", "document_types": "documents", "series_scores": "documents"}


def _ratio(numerator, denominator, digits=3):
    return round(numerator / denominator, digits) if denominator else None


def derive_rows(metric: str, rows: list[dict]) -> list[dict]:
    """Add averages and shares computed from the raw sums; raw sums are kept for verification."""
    result = []
    if metric == "map_pool":
        total = sum(row["maps"] for row in rows)
        for row in rows:
            decided = row["team1_wins"] + row["team2_wins"]
            result.append({**row, "share": _ratio(row["maps"], total, 4),
                           "avg_rounds": _ratio(row["rounds"], row["scored"], 2),
                           "avg_margin": _ratio(row["margin"], row["scored"], 2),
                           "team1_win_share": _ratio(row["team1_wins"], decided)})
    elif metric == "document_types":
        for row in rows:
            decided = row["team1_wins"] + row["team2_wins"]
            result.append({**row, "avg_players": _ratio(row["player_rows"], row["documents"], 2),
                           "team1_win_share": _ratio(row["team1_wins"], decided)})
    elif metric == "series_scores":
        total = sum(row["documents"] for row in rows)
        result = [{**row, "share": _ratio(row["documents"], total, 4)} for row in rows]
    elif metric == "top_players":
        for row in rows:
            result.append({**row, "kd": _ratio(row["kills"], row["deaths"], 2),
                           "kills_per_document": _ratio(row["kills"], row["documents"], 2),
                           "avg_adr": _ratio(row["adr_sum"], row["adr_n"], 1),
                           "avg_kast": _ratio(row["kast_sum"], row["kast_n"], 1)})
    else:
        raise ValueError("Unknown metric")
    return result


def _same(left, right) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)) \
            and not isinstance(left, bool) and not isinstance(right, bool):
        # Floating sums (ADR/KAST) are added in a different order by each engine and shard.
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-6)
    return left == right


def compare_rows(left: list[dict], right: list[dict]) -> dict:
    differences = []
    if len(left) != len(right):
        differences.append({"row": None, "field": "row_count", "aggregate": len(left), "mapreduce": len(right)})
    for index, (a, b) in enumerate(zip(left, right)):
        for field in sorted(set(a) | set(b)):
            if not _same(a.get(field), b.get(field)):
                differences.append({"row": index, "field": field, "aggregate": a.get(field), "mapreduce": b.get(field)})
    return {"equal": not differences, "rows_compared": min(len(left), len(right)), "differences": differences[:10]}


@dataclass
class DistributedAggregationQueryService:
    reader: DistributedAggregationReader

    async def run(self, query: DistributedAggregationQuery) -> dict:
        matched = await self.reader.count(query)
        engines = ("aggregate", "mapreduce") if query.engine == "both" else (query.engine,)
        # Sequential on purpose: concurrent runs would distort each other's timings on the same shards.
        executions = [await self.reader.execute(query, engine) for engine in engines]
        counter = DOCUMENT_COUNTER.get(query.metric)
        covered = sum(row[counter] for row in executions[0]["rows"]) if counter else None
        return {
            "metric": query.metric,
            "corpus_scope": query.corpus_scope,
            "document_type": query.resolved_document_type,
            "template_version": "2",
            "engine": query.engine,
            "limit": query.limit if query.metric == "top_players" else None,
            "matched_documents": matched,
            "rows": derive_rows(query.metric, executions[0]["rows"]),
            "coverage": None if counter is None else {
                "field": counter, "grouped_documents": covered, "matched_documents": matched,
                "consistent": covered == matched},
            "executions": [{key: execution[key] for key in ("engine", "elapsed_ms", "groups_returned", "plan")}
                           for execution in executions],
            "comparison": compare_rows(executions[0]["rows"], executions[1]["rows"]) if len(executions) == 2 else None,
            "topology": await self.reader.topology(),
        }
