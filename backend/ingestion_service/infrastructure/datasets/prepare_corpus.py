"""Deterministic, offline conversion of the bundled dataset. No provider calls."""
import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

TEMPLATE_VERSION = "1"
PROVIDER = "kaggle_counter_strike_pro_matches"
SOURCE_URL = "https://www.kaggle.com/datasets/ektarr/counter-strike-pro-matches"

def convert(row: dict, snapshot_hash: str) -> dict:
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
    sentences = [f"{row['team1']} played {row['team2']} at {row['tournament']} on {date[:10]}."]
    if kind == "map" and row.get("map_name"):
        title += f" — {row['map_name']}"
        sentences.append(f"Map: {row['map_name']}.")
    score_fields = ("score1_match", "score2_match") if kind == "series" else ("score1_game", "score2_game")
    if all(row.get(f) for f in score_fields):
        scores = [float(row[f]) for f in score_fields]
        if any(not s.is_integer() or s < 0 for s in scores):
            raise ValueError("Invalid score")
        sentences.append(f"{'Series' if kind == 'series' else 'Map'} score: {int(scores[0])}-{int(scores[1])}.")
    for team in (1, 2):
        for player in range(1, 6):
            prefix = f"team{team}_player{player}"
            name = row.get(prefix)
            if name:
                stats = [f"{row[prefix + '_' + stat]} {stat}" for stat in ("kills", "deaths", "assists", "adr", "kast") if row.get(prefix + "_" + stat)]
                sentences.append(name + (": " + ", ".join(stats) if stats else "") + ".")
    return {"id": str(uuid5(NAMESPACE_URL, PROVIDER + ":" + key)), "version": 1,
        "title": title, "text": " ".join(sentences), "language": "en", "provider": PROVIDER,
        "source_id": key, "source_url": SOURCE_URL, "corpus_scope": "kaggle-cs",
        "is_synthetic": False, "publication_status": "published", "related_entity_ids": [],
        "metadata": {"document_type": kind, "match_id": row["match_id"], "game_id": row.get("game_id", ""),
            "tournament": row["tournament"], "team1": row["team1"], "team2": row["team2"],
            "played_at": date, "source_timezone": "unspecified", "snapshot_sha256": snapshot_hash,
            "template_version": TEMPLATE_VERSION, "generated_from_dataset": "true"}}

def prepare(archive: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        raw = z.read("cs2_all_tiers_games.csv")
    digest = hashlib.sha256(raw).hexdigest()
    seen, rejected, count = set(), [], 0
    with (output / "kaggle-cs.jsonl").open("w", encoding="utf-8", newline="\n") as target:
        for line, row in enumerate(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))), 2):
            try:
                doc = convert(row, digest)
                if doc["id"] in seen:
                    raise ValueError("Duplicate source key")
                seen.add(doc["id"])
                target.write(json.dumps(doc, ensure_ascii=False) + "\n")
                count += 1
            except (ValueError, KeyError) as exc:
                rejected.append({"line": line, "reason": str(exc)})
    report = {"snapshot_id": "kaggle-cs", "snapshot_sha256": digest, "template_version": TEMPLATE_VERSION,
        "accepted": count, "rejected": len(rejected), "issues": rejected,
        "jsonl_sha256": hashlib.sha256((output / "kaggle-cs.jsonl").read_bytes()).hexdigest()}
    (output / "kaggle-cs.manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("counter-strike-pro-matches.zip"))
    parser.add_argument("--output", type=Path, default=Path("data/prepared"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.output), indent=2))
