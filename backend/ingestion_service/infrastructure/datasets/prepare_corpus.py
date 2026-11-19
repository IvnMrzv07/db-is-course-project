"""Deterministic, offline conversion of the bundled dataset. No provider calls."""
import csv
import gzip
import hashlib
import io
import json
import math
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

TEMPLATE_VERSION = "2"
PROVIDER = "kaggle_counter_strike_pro_matches"
SOURCE_URL = "https://www.kaggle.com/datasets/ektarr/counter-strike-pro-matches"
COUNT_STATS = ("kills", "deaths", "assists")
RATE_STATS = ("adr", "kast")
TEXT_STATS = COUNT_STATS + RATE_STATS  # order used by the v1/v2 English text


@dataclass(frozen=True)
class CorpusSource:
    """Provenance of one prepared snapshot; the provider is part of every UUIDv5 name."""

    snapshot_id: str
    provider: str
    source_url: str | None
    is_synthetic: bool


KAGGLE = CorpusSource("kaggle-cs", PROVIDER, SOURCE_URL, False)
# D38 / report 2.2: generated load data lives only in its own corpus scope and provider namespace.
SYNTHETIC = CorpusSource("synthetic-cs", "sdv_synthetic_counter_strike", None, True)
SYNTHETIC_NOTICE = "Synthetic load-test record generated with SDV; it does not describe a real match."


def _number(value: str, field: str, *, integer: bool = False, non_negative: bool = False) -> float:
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"Invalid {field}") from None
    if not math.isfinite(number) or (integer and not number.is_integer()) or (non_negative and number < 0):
        raise ValueError(f"Invalid {field}")
    return number


def _optional_int(row: dict, field: str) -> int | None:
    value = row.get(field)
    return int(_number(value, field, integer=True, non_negative=True)) if value else None


def _players(row: dict) -> list[dict]:
    """Structured per-player statistics; only slots that the source names (same as the text)."""
    players = []
    for team in (1, 2):
        for slot in range(1, 6):
            prefix = f"team{team}_player{slot}"
            name = row.get(prefix)
            if not name:
                continue
            record = {"team": team, "slot": slot, "player_id": row.get(prefix + "_id") or None, "name": name}
            for stat in COUNT_STATS:
                value = row.get(f"{prefix}_{stat}")
                record[stat] = int(_number(value, f"{prefix}_{stat}", integer=True, non_negative=True)) if value else None
            for stat in RATE_STATS:
                value = row.get(f"{prefix}_{stat}")
                record[stat] = _number(value, f"{prefix}_{stat}", non_negative=True) if value else None
            value = row.get(prefix + "_kddiff")
            record["kddiff"] = int(_number(value, prefix + "_kddiff", integer=True)) if value else None
            players.append(record)
    return players


def convert(row: dict, snapshot_hash: str, source: CorpusSource = KAGGLE) -> dict:
    for field in ("match_id", "is_total", "team1", "team2", "tournament", "datetime"):
        if not row.get(field):
            raise ValueError(f"Missing {field}")
    if row["is_total"] not in ("True", "False"):
        raise ValueError("Invalid is_total")
    kind = "series" if row["is_total"] == "True" else "map"
    if kind == "map" and not row.get("game_id"):
        raise ValueError("Missing game_id")
    date = datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S").isoformat()
    key = f"{row['match_id']}:{kind}" + (f":{row['game_id']}" if kind == "map" else "")
    title = f"{row['team1']} vs {row['team2']} — {row['tournament']}"
    sentences = [SYNTHETIC_NOTICE] if source.is_synthetic else []
    sentences.append(f"{row['team1']} played {row['team2']} at {row['tournament']} on {date[:10]}.")
    if kind == "map" and row.get("map_name"):
        title += f" — {row['map_name']}"
        sentences.append(f"Map: {row['map_name']}.")
    score_fields = ("score1_match", "score2_match") if kind == "series" else ("score1_game", "score2_game")
    score1 = score2 = None
    if all(row.get(f) for f in score_fields):
        try:
            scores = [float(row[f]) for f in score_fields]
        except ValueError:
            raise ValueError("Invalid score") from None
        if any(not math.isfinite(s) or not s.is_integer() or s < 0 for s in scores):
            raise ValueError("Invalid score")
        score1, score2 = int(scores[0]), int(scores[1])
        sentences.append(f"{'Series' if kind == 'series' else 'Map'} score: {score1}-{score2}.")
    players = _players(row)
    for player in players:
        prefix = f"team{player['team']}_player{player['slot']}"
        stats = [f"{row[prefix + '_' + stat]} {stat}" for stat in TEXT_STATS if row.get(prefix + "_" + stat)]
        sentences.append(player["name"] + (": " + ", ".join(stats) if stats else "") + ".")
    # Winner is derived from the recorded score only: the source `team1_win` flag contradicts
    # the series score in about half of the series rows, so it is not trusted.
    winner = None if score1 is None else "draw" if score1 == score2 else "team1" if score1 > score2 else "team2"
    metadata = {"document_type": kind, "match_id": row["match_id"], "game_id": row.get("game_id", ""),
        "tournament": row["tournament"], "team1": row["team1"], "team2": row["team2"],
        "played_at": date, "source_timezone": "unspecified", "snapshot_sha256": snapshot_hash,
        "template_version": TEMPLATE_VERSION,
        "generated_from_dataset": "false" if source.is_synthetic else "true",
        # v2 structured fields (JSON-typed; null means "not recorded in the source").
        "team1_id": row.get("team1_id") or None, "team2_id": row.get("team2_id") or None,
        "best_of": _optional_int(row, "bestOf"),
        "score1": score1, "score2": score2, "winner": winner,
        "winner_team": row[winner] if winner in ("team1", "team2") else None,
        "players": players}
    if kind == "map":
        # Series rows sometimes carry one map's name/id; they are not map observations.
        metadata["map_name"] = row.get("map_name") or None
        metadata["map_id"] = row.get("map_id") or None
    else:
        metadata["games_played"] = _optional_int(row, "games_played")
    if source.is_synthetic:
        metadata["synthetic_generator"] = row.get("synthetic_generator") or "sdv"
    return {"id": str(uuid5(NAMESPACE_URL, source.provider + ":" + key)), "version": 1,
        "title": title, "text": " ".join(sentences), "language": "en", "provider": source.provider,
        "source_id": key, "source_url": source.source_url, "corpus_scope": source.snapshot_id,
        "is_synthetic": source.is_synthetic, "publication_status": "published", "related_entity_ids": [],
        "metadata": metadata}


def _write_snapshot(raw: bytes, output: Path, source: CorpusSource) -> dict:
    """Convert one immutable CSV snapshot into `<snapshot_id>.jsonl` plus its manifest."""
    digest = hashlib.sha256(raw).hexdigest()
    name = source.snapshot_id
    seen, rejected, count = set(), [], 0
    with (output / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as target:
        for line, row in enumerate(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))), 2):
            try:
                if source.is_synthetic and row.get("is_synthetic") != "True":
                    raise ValueError("Synthetic snapshot row is not marked synthetic")
                doc = convert(row, digest, source)
                if doc["id"] in seen:
                    raise ValueError("Duplicate source key")
                seen.add(doc["id"])
                target.write(json.dumps(doc, ensure_ascii=False) + "\n")
                count += 1
            except (ValueError, KeyError) as exc:
                rejected.append({"line": line, "reason": str(exc)})
    report = {"snapshot_id": name, "snapshot_sha256": digest, "template_version": TEMPLATE_VERSION,
        "provider": source.provider, "is_synthetic": source.is_synthetic,
        "accepted": count, "rejected": len(rejected), "issues": rejected,
        "jsonl_sha256": hashlib.sha256((output / f"{name}.jsonl").read_bytes()).hexdigest()}
    (output / f"{name}.manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def prepare(archive: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        raw = z.read("cs2_all_tiers_games.csv")
    return _write_snapshot(raw, output, KAGGLE)



def prepare_synthetic(snapshot: Path, output: Path, base_ids: set[str] | None = None) -> dict:
    """Convert the generated `synthetic-cs.csv.gz` with the same validation as the factual corpus."""
    output.mkdir(parents=True, exist_ok=True)
    report = _write_snapshot(gzip.decompress(snapshot.read_bytes()), output, SYNTHETIC)
    if base_ids is not None:
        with (output / "synthetic-cs.jsonl").open(encoding="utf-8") as lines:
            if any(json.loads(line)["id"] in base_ids for line in lines):
                raise ValueError("Synthetic document ID collides with the factual corpus")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("counter-strike-pro-matches.zip"))
    parser.add_argument("--output", type=Path, default=Path("data/prepared"))
    parser.add_argument("--synthetic", type=Path, default=Path("data/synthetic/synthetic-cs.csv.gz"),
                        help="optional generated snapshot; skipped when the file does not exist")
    args = parser.parse_args()
    reports = [prepare(args.archive, args.output)]
    if args.synthetic.exists():
        with (args.output / "kaggle-cs.jsonl").open(encoding="utf-8") as lines:
            base_ids = {json.loads(line)["id"] for line in lines}
        reports.append(prepare_synthetic(args.synthetic, args.output, base_ids))
    print(json.dumps([{k: v for k, v in r.items() if k != "issues"} | {"issues": r["issues"][:5]} for r in reports], indent=2))
