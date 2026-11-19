"""Collect evidence for the distributed map-reduce endpoint from a running stack (cs-sharded by default).

    python tools/sharding/collect_map_reduce_evidence.py [--base-url http://localhost:8082] [--output DIR]

Writes one JSON per query (full API response with engine=both and per-shard explain summaries) and
timings.json (median of 3 runs per engine with explain=false, measured server-side).
"""
import argparse
import json
import statistics
import urllib.parse
import urllib.request
from pathlib import Path

QUERIES = {
    "document-types-all": {"metric": "document_types", "corpus_scope": "all"},
    "map-pool-all": {"metric": "map_pool", "corpus_scope": "all"},
    "series-scores-all": {"metric": "series_scores", "corpus_scope": "all"},
    "top-players-map-all": {"metric": "top_players", "document_type": "map", "corpus_scope": "all", "limit": 10},
    "top-players-series-kaggle": {"metric": "top_players", "document_type": "series", "corpus_scope": "kaggle-cs", "limit": 10},
}


def fetch(base_url: str, params: dict) -> dict:
    url = base_url.rstrip("/") + "/api/v1/distributed/map-reduce?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8082")
    parser.add_argument("--output", default="docs/coursework/stages/map-reduce-summary")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    timings = {}
    for name, params in QUERIES.items():
        result = fetch(args.base_url, {**params, "engine": "both", "explain": "true"})
        (output / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        runs = {engine: [fetch(args.base_url, {**params, "engine": engine, "explain": "false"})["executions"][0]["elapsed_ms"]
                         for _ in range(args.runs)] for engine in ("aggregate", "mapreduce")}
        timings[name] = {
            "params": params, "matched_documents": result["matched_documents"], "rows": len(result["rows"]),
            "comparison_equal": result["comparison"]["equal"],
            "coverage_consistent": None if result["coverage"] is None else result["coverage"]["consistent"],
            "groups_returned": {e["engine"]: e["groups_returned"] for e in result["executions"]},
            "partial_groups_per_shard": {e["engine"]: {s["shard"]: s["partial_groups"] for s in e["plan"]["shards"]}
                                         for e in result["executions"]},
            "merge_type": {e["engine"]: e["plan"]["merge_type"] for e in result["executions"]},
            "runs_ms": runs, "median_ms": {engine: statistics.median(values) for engine, values in runs.items()},
        }
        print(name, json.dumps(timings[name]["median_ms"]), "equal" if result["comparison"]["equal"] else "DIFFERENT")
    (output / "timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
