"""Distributed map-reduce over content.source_documents through mongos.

Two engines compute the same raw sums:

* ``aggregate`` - an aggregation pipeline. On a sharded cluster mongos splits it: ``$match`` + a partial
  ``$group`` run on every shard (map + combine), the merging ``$group`` / ``$sort`` / ``$limit`` run on
  the merger (reduce).
* ``mapreduce`` - the legacy ``mapReduce`` command with JavaScript map/reduce functions. Since MongoDB 5.0
  it is executed as ``$_internalJsEmit`` / ``$_internalJsReduce`` stages with the same shard/merger split.
  It cannot sort or limit the reduced output, so ordering and the top-N cut are applied here, after the
  full result has been transferred.

Both engines treat missing values the same way (missing score -> not "scored", missing map name -> null
key, non-numeric player stat -> 0 / not counted), so their rows are directly comparable.
"""
import time
from bson.code import Code
from content_service.application.dtos.distributed_query import DistributedAggregationQuery

SCOPES = ["kaggle-cs", "synthetic-cs"]
MAX_TIME_MS = 60_000

KEY_FIELDS = {"map_pool": "map_name", "top_players": "player_id",
              "document_types": ("corpus_scope", "document_type"), "series_scores": ("best_of", "score")}
# (field, direction); identical for the database $sort and the Python sort of mapReduce output.
SORT = {"map_pool": [("maps", -1), ("map_name", 1)],
        "document_types": [("corpus_scope", 1), ("document_type", 1)],
        "series_scores": [("best_of", 1), ("documents", -1), ("score", 1)],
        "top_players": [("kills", -1), ("player_id", 1)]}


def build_match(query: DistributedAggregationQuery) -> dict:
    # `$in` over both scopes keeps the {corpus_scope, metadata.document_type, _id} index usable for "all".
    match = {"corpus_scope": {"$in": SCOPES} if query.corpus_scope == "all" else query.corpus_scope,
             "publication_status": "published", "metadata.template_version": "2"}
    if query.resolved_document_type:
        match["metadata.document_type"] = query.resolved_document_type
    return match


S1, S2 = "$metadata.score1", "$metadata.score2"
SCORED = {"$and": [{"$isNumber": S1}, {"$isNumber": S2}]}


def _if(condition, then, otherwise=0):
    return {"$cond": [condition, then, otherwise]}


def _winner(value):
    return {"$sum": _if({"$eq": ["$metadata.winner", value]}, 1)}


WINS = {"team1_wins": _winner("team1"), "team2_wins": _winner("team2"), "draws": _winner("draw")}
PLAYERS = {"$cond": [{"$isArray": "$metadata.players"}, "$metadata.players", []]}


def _player_stat(name):
    return {"$sum": _if({"$isNumber": f"$metadata.players.{name}"}, f"$metadata.players.{name}")}


def _sort_stage(metric: str) -> dict:
    key = KEY_FIELDS[metric]
    path = (lambda field: "_id" if field == key else f"_id.{field}" if isinstance(key, tuple) and field in key else field)
    return {"$sort": {path(field): direction for field, direction in SORT[metric]}}


def build_pipeline(query: DistributedAggregationQuery) -> list[dict]:
    metric = query.metric
    pipeline: list[dict] = [{"$match": build_match(query)}]
    if metric == "map_pool":
        pipeline.append({"$group": {
            "_id": {"$ifNull": ["$metadata.map_name", None]}, "maps": {"$sum": 1},
            "scored": {"$sum": _if(SCORED, 1)}, "rounds": {"$sum": _if(SCORED, {"$add": [S1, S2]})},
            "margin": {"$sum": _if(SCORED, {"$abs": {"$subtract": [S1, S2]}})}, **WINS}})
    elif metric == "document_types":
        pipeline.append({"$group": {
            "_id": {"corpus_scope": "$corpus_scope", "document_type": {"$ifNull": ["$metadata.document_type", None]}},
            "documents": {"$sum": 1}, "with_players": {"$sum": _if({"$gt": [{"$size": PLAYERS}, 0]}, 1)},
            "player_rows": {"$sum": {"$size": PLAYERS}}, **WINS}})
    elif metric == "series_scores":
        score = {"$concat": [{"$toString": {"$toLong": {"$floor": {"$max": [S1, S2]}}}}, ":",
                             {"$toString": {"$toLong": {"$floor": {"$min": [S1, S2]}}}}]}
        pipeline.append({"$group": {
            "_id": {"best_of": {"$ifNull": ["$metadata.best_of", None]}, "score": _if(SCORED, score, None)},
            "documents": {"$sum": 1}, **WINS}})
    elif metric == "top_players":
        pipeline += [{"$unwind": "$metadata.players"},
                     {"$match": {"metadata.players.player_id": {"$ne": None}}},
                     {"$group": {"_id": "$metadata.players.player_id", "name": {"$max": "$metadata.players.name"},
                                 "documents": {"$sum": 1}, "kills": _player_stat("kills"),
                                 "deaths": _player_stat("deaths"), "assists": _player_stat("assists"),
                                 "adr_sum": _player_stat("adr"), "adr_n": {"$sum": _if({"$isNumber": "$metadata.players.adr"}, 1)},
                                 "kast_sum": _player_stat("kast"), "kast_n": {"$sum": _if({"$isNumber": "$metadata.players.kast"}, 1)}}}]
    pipeline.append(_sort_stage(metric))
    if metric == "top_players":
        pipeline.append({"$limit": query.limit})
    return pipeline


# ---------------------------------------------------------------- mapReduce (server-side JavaScript)
_JS_PRELUDE = """
  function num(v) {
    if (typeof v === 'number') return v;
    if (v !== null && v !== undefined && typeof v.toNumber === 'function') return v.toNumber();
    return null;
  }
  function nz(v) { return v === undefined ? null : v; }
  var m = this.metadata || {};
  var wins = {team1_wins: m.winner === 'team1' ? 1 : 0, team2_wins: m.winner === 'team2' ? 1 : 0,
              draws: m.winner === 'draw' ? 1 : 0};
  var s1 = num(m.score1), s2 = num(m.score2), scored = s1 !== null && s2 !== null;
  var players = Array.isArray(m.players) ? m.players : [];
"""

MAP_FUNCTIONS = {
    "map_pool": """
      emit(nz(m.map_name), {maps: 1, scored: scored ? 1 : 0, rounds: scored ? s1 + s2 : 0,
        margin: scored ? Math.abs(s1 - s2) : 0, team1_wins: wins.team1_wins, team2_wins: wins.team2_wins,
        draws: wins.draws});""",
    "document_types": """
      emit({corpus_scope: this.corpus_scope, document_type: nz(m.document_type)},
        {documents: 1, with_players: players.length > 0 ? 1 : 0, player_rows: players.length,
         team1_wins: wins.team1_wins, team2_wins: wins.team2_wins, draws: wins.draws});""",
    "series_scores": """
      var score = scored ? Math.floor(Math.max(s1, s2)) + ':' + Math.floor(Math.min(s1, s2)) : null;
      emit({best_of: num(m.best_of), score: score},
        {documents: 1, team1_wins: wins.team1_wins, team2_wins: wins.team2_wins, draws: wins.draws});""",
    "top_players": """
      for (var i = 0; i < players.length; i++) {
        var p = players[i];
        if (!p || p.player_id === null || p.player_id === undefined) continue;
        var k = num(p.kills), d = num(p.deaths), a = num(p.assists), adr = num(p.adr), kast = num(p.kast);
        emit(p.player_id, {name: nz(p.name), documents: 1, kills: k === null ? 0 : k,
          deaths: d === null ? 0 : d, assists: a === null ? 0 : a,
          adr_sum: adr === null ? 0 : adr, adr_n: adr === null ? 0 : 1,
          kast_sum: kast === null ? 0 : kast, kast_n: kast === null ? 0 : 1});
      }""",
}

# Associative and idempotent: sums every counter, keeps the greatest non-null name (same as $max).
REDUCE_FUNCTION = """function (key, values) {
  var out = {};
  values.forEach(function (v) {
    for (var f in v) {
      if (f === 'name') {
        if (v.name !== null && v.name !== undefined && (out.name === undefined || out.name === null || v.name > out.name)) out.name = v.name;
        else if (out.name === undefined) out.name = null;
      } else {
        out[f] = (out[f] || 0) + v[f];
      }
    }
  });
  return out;
}"""


def map_function(metric: str) -> str:
    return "function () {" + _JS_PRELUDE + MAP_FUNCTIONS[metric] + "\n}"


def build_map_reduce(query: DistributedAggregationQuery) -> dict:
    return {"mapReduce": "source_documents", "map": Code(map_function(query.metric)),
            "reduce": Code(REDUCE_FUNCTION), "query": build_match(query), "out": {"inline": 1}}


# ---------------------------------------------------------------- normalisation and ordering
def _clean(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)  # bson.Int64 -> int
    return value


def normalize(metric: str, key, values: dict) -> dict:
    fields = KEY_FIELDS[metric]
    if isinstance(fields, tuple):
        key = key if isinstance(key, dict) else {}
        head = {field: _clean(key.get(field)) for field in fields}
    else:
        head = {fields: _clean(key)}
    return {**head, **{name: _clean(value) for name, value in values.items()}}


def _mongo_order(value):
    """BSON comparison order for the scalar types used as keys: null < numbers < strings."""
    if value is None:
        return (0, 0)
    if isinstance(value, (int, float)):
        return (1, value)
    return (2, str(value))


def sort_rows(metric: str, rows: list[dict]) -> list[dict]:
    def key(row):
        return tuple((-row[field],) if direction < 0 else _mongo_order(row[field]) for field, direction in SORT[metric])
    return sorted(rows, key=key)


# ---------------------------------------------------------------- explain("executionStats") summary
def _find(node, wanted):
    if isinstance(node, dict):
        if wanted in node:
            return node[wanted]
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        found = _find(child, wanted)
        if found is not None:
            return found
    return None


def _stage_name(stage: dict) -> str:
    name = next(iter(stage), "?")
    text = repr(stage.get(name))
    for internal in ("$_internalJsEmit", "$_internalJsReduce"):
        if internal in text:
            name += f" ({internal})"
    body = stage.get(name.split(" ")[0])
    if name == "$sort" and isinstance(body, dict) and body.get("limit") is not None:
        name += f" (limit {_clean(body['limit'])})"  # mongos coalesces $sort + $limit into a top-k sort
    return name


def _plan_text(plan) -> str | None:
    parts = []
    while isinstance(plan, dict) and plan.get("stage"):
        part = plan["stage"]
        if plan.get("indexName"):
            part += f"({plan['indexName']})"
        parts.append(part)
        plan = plan.get("inputStage") or (plan.get("inputStages") or [None])[0]
    return " → ".join(parts) or None


def _number(value):
    return None if value is None else _clean(value)


def _shard_summary(name: str, body: dict) -> dict:
    stats = _find(body, "executionStats") or {}
    planner = _find(body, "queryPlanner") or {}
    winning = planner.get("winningPlan") or {}
    winning = winning.get("queryPlan", winning)
    stages = body.get("stages") if isinstance(body.get("stages"), list) else []
    last = stages[-1] if stages else None
    partial = last.get("nReturned") if last and "$cursor" not in last else stats.get("nReturned")
    times = [stage.get("executionTimeMillisEstimate") for stage in stages if stage.get("executionTimeMillisEstimate") is not None]
    return {"shard": name, "host": body.get("host"), "plan": _plan_text(winning),
            "pipeline": [_stage_name(stage) for stage in stages],
            "keys_examined": _number(stats.get("totalKeysExamined")),
            "docs_examined": _number(stats.get("totalDocsExamined")),
            "matched": _number(stats.get("nReturned")), "partial_groups": _number(partial),
            "time_ms": _number(max(times) if times else stats.get("executionTimeMillis"))}


def summarize_explain(explain: dict) -> dict:
    shards = explain.get("shards")
    sharded = isinstance(shards, dict)
    split = explain.get("splitPipeline") or {}
    return {"topology": "sharded" if sharded else "single",
            "merge_type": explain.get("mergeType"),
            "shards_part": [_stage_name(stage) for stage in split.get("shardsPart") or []],
            "merger_part": [_stage_name(stage) for stage in split.get("mergerPart") or []],
            "shards": [_shard_summary(name, body) for name, body in sorted((shards if sharded else {"local": explain}).items())]}


class MongoDistributedAggregation:
    def __init__(self, database):
        self.db = database
        self.documents = database.source_documents

    async def count(self, query: DistributedAggregationQuery) -> int:
        return await self.documents.count_documents(build_match(query), maxTimeMS=MAX_TIME_MS)

    async def execute(self, query: DistributedAggregationQuery, engine: str) -> dict:
        if engine == "aggregate":
            pipeline = build_pipeline(query)
            command = {"aggregate": "source_documents", "pipeline": pipeline, "cursor": {}, "allowDiskUse": True}
            started = time.perf_counter()
            cursor = await self.documents.aggregate(pipeline, maxTimeMS=MAX_TIME_MS, allowDiskUse=True)
            raw = await cursor.to_list()
            elapsed = time.perf_counter() - started
            rows = [normalize(query.metric, doc["_id"], {k: v for k, v in doc.items() if k != "_id"}) for doc in raw]
        elif engine == "mapreduce":
            command = build_map_reduce(query)
            started = time.perf_counter()
            result = await self.db.command({**command, "maxTimeMS": MAX_TIME_MS})
            elapsed = time.perf_counter() - started
            raw = result["results"]
            rows = [normalize(query.metric, doc["_id"], doc["value"]) for doc in raw]
        else:
            raise ValueError("Unknown engine")
        rows = sort_rows(query.metric, rows)
        if query.metric == "top_players":
            rows = rows[:query.limit]
        plan = None
        if query.explain:
            explain = await self.db.command({"explain": command, "verbosity": "executionStats", "maxTimeMS": MAX_TIME_MS})
            plan = summarize_explain(explain)
        return {"engine": engine, "rows": rows, "elapsed_ms": round(elapsed * 1000, 1),
                "groups_returned": len(raw), "plan": plan}

    async def topology(self) -> dict:
        cursor = await self.documents.aggregate([{"$collStats": {"count": {}}}], maxTimeMS=MAX_TIME_MS)
        stats = await cursor.to_list()
        return {"sharded": any("shard" in row for row in stats),
                "shards": sorted(({"shard": row.get("shard", "local"), "documents": _number(row.get("count", 0))}
                                  for row in stats), key=lambda row: row["shard"])}
