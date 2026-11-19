"""Synthetic load corpus (synthetic-cs): domain rules, assembly, conversion and isolation.

SDV itself is optional tooling (requirements-synthetic.txt); these tests exercise everything
around the model without it, and validate the committed snapshot when it is present.
"""
import asyncio
import csv
import gzip
import io
import json
import random
from pathlib import Path
from uuid import uuid4

import pytest
from content_service.application.dtos.document_query import DocumentQuery
from content_service.application.services.commands.corpus_command_service import CorpusCommandService
from content_service.infrastructure.database.corpus_repository import MongoCorpusRepository
from ingestion_service.infrastructure.database.replay_store import PreparedSnapshot
from ingestion_service.infrastructure.datasets.prepare_corpus import KAGGLE, SYNTHETIC, convert, prepare, prepare_synthetic
from ingestion_service.infrastructure.datasets.synthetic_rules import (
    MAP_COLUMNS, Pseudonyms, assemble, map_issue, relation_report, series_issue, valid_map_score,
    write_csv_gz)
from tests.test_corpus_runtime import Database

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "synthetic" / "synthetic-cs.csv.gz"
BOUNDS = ("2023-01-01 00:00:00", "2026-12-31 23:59:59")


def series_sample(**changes):
    return {"tournament": "Cup A", "team1": "Alpha", "team2": "Beta", "best_of": "3", "score1": 2, "score2": 1,
            "played_at": "2025-03-01 18:00:00", "detail": "maps", **changes}


def map_sample(name="Mirage", win=13, lose=9, **changes):
    row = {"map_name": name, "win_score": win, "lose_score": lose}
    for side, kills, deaths in (("w", 18, 9), ("l", 9, 18)):  # 5 x 18 = 90 kills vs 5 x 18 = 90 deaths
        for slot in range(1, 6):
            row |= {f"{side}{slot}_kills": kills, f"{side}{slot}_deaths": deaths, f"{side}{slot}_assists": 3,
                    f"{side}{slot}_adr": 80.5, f"{side}{slot}_kast": 70.0}
    return row | changes


@pytest.mark.parametrize("win,lose,ok", [(13, 11, True), (13, 0, True), (13, 12, False), (16, 14, True),
                                         (16, 12, True), (16, 11, False), (19, 17, True), (14, 12, False), (1, 0, False)])
def test_cs2_round_score_rule(win, lose, ok):
    assert valid_map_score(win, lose) is ok


@pytest.mark.parametrize("changes,issue", [({}, None), ({"team2": "Alpha"}, "same_team"),
    ({"score1": -1}, "score_not_non_negative_int"), ({"score1": 1.5}, "score_not_non_negative_int"),
    ({"score1": 1, "score2": 0}, "score_inconsistent_with_best_of"), ({"score2": 2}, "score_inconsistent_with_best_of"),
    ({"best_of": "1", "score1": 1, "score2": 0}, None), ({"best_of": "7"}, "unknown_best_of"),
    ({"played_at": "2030-01-01 00:00:00"}, "datetime_out_of_range")])
def test_series_domain_rules(changes, issue):
    assert series_issue(series_sample(**changes), BOUNDS) == issue


def test_map_domain_rules():
    bounds = {c: (0, 1000) for c in MAP_COLUMNS if c != "map_name"}
    assert map_issue(map_sample(), bounds, 4) is None
    assert map_issue(map_sample(w1_kills=-1), bounds, 4) == "stat_not_non_negative_int"
    assert map_issue(map_sample(w1_kills=1.5), bounds, 4) == "stat_not_non_negative_int"
    assert map_issue(map_sample(w1_kast=101.0), bounds, 4) == "kast_above_100"
    assert map_issue(map_sample(w1_deaths=30), bounds, 4) == "deaths_exceed_rounds"
    assert map_issue(map_sample(w1_kills=30), bounds, 4) == "team_kills_deaths_mismatch"
    assert map_issue(map_sample(win=13, lose=12), bounds, 4) == "invalid_round_score"
    assert map_issue(map_sample(w1_adr=900.0), bounds | {"w1_adr": (10, 200)}, 4) == "stat_out_of_observed_range"


def build(total, seed=7):
    rng = random.Random(seed)
    teams_real = [f"Team{i}" for i in range(12)]
    series = []
    for _ in range(total):
        t1, t2 = rng.sample(teams_real, 2)
        bo = rng.choice(["1", "3", "3", "5"])
        need = {"1": 1, "3": 2, "5": 3}[bo]
        lose = rng.randrange(need)
        s1, s2 = (need, lose) if rng.random() < 0.5 else (lose, need)
        series.append(series_sample(team1=t1, team2=t2, best_of=bo, score1=s1, score2=s2,
                                    detail=rng.choice(["maps", "none"]), tournament=f"Cup {rng.randrange(3)}"))
    names = ["Ancient", "Mirage", "Nuke", "Dust2", "Inferno", "Anubis", "Train"]
    maps = [map_sample(name=names[i % len(names)], win=13, lose=i % 12) for i in range(total * 5)]
    columns = list(csv.DictReader(io.StringIO(_header())).fieldnames)
    teams = Pseudonyms([s["team1"] for s in series] + [s["team2"] for s in series], "Team", "ST")
    tournaments = Pseudonyms([s["tournament"] for s in series], "Tournament", "TT")
    return assemble(series, maps, total=total, columns=columns, seed=seed, teams=teams, tournaments=tournaments), columns


def _header():
    import zipfile
    with zipfile.ZipFile(ROOT / "counter-strike-pro-matches.zip") as archive:
        with archive.open("cs2_all_tiers_games.csv") as source:
            return source.readline().decode("utf-8-sig")


def test_assembly_exact_volume_relations_and_pseudonyms():
    (rows, stats), columns = build(500)
    assert len(rows) == stats["rows"] == 500
    assert stats["series_rows"] + stats["map_rows"] == 500
    relations = relation_report(rows)
    assert relations["series_with_maps"] == stats["series_with_maps"] > 0
    for check in ("map_winners_match_series_score", "map_names_unique_in_series", "series_kills_equal_map_sum"):
        assert relations[check] == relations["series_with_maps"]
    assert relations["map_rows_without_series"] == 0
    assert all(r["is_synthetic"] == "True" and r["team1"].startswith("Synthetic Team ") for r in rows)
    assert not any("Team" + str(i) in r["team1"] + r["team2"] for r in rows for i in range(12))
    rosters = {}
    for r in rows:
        for t in (1, 2):
            if r[f"team{t}_player1"]:
                rosters.setdefault(r[f"team{t}"], set()).add(tuple(r[f"team{t}_player{p}"] for p in range(1, 6)))
    assert rosters and all(len(v) == 1 for v in rosters.values())  # one fixed five-player roster per team
    docs = [convert(r, "digest", SYNTHETIC) for r in rows]
    assert len({d["id"] for d in docs}) == 500
    for d in docs:
        m = d["metadata"]
        assert d["corpus_scope"] == "synthetic-cs" and d["is_synthetic"] is True and d["source_url"] is None
        assert m["generated_from_dataset"] == "false" and m["synthetic_generator"].startswith("sdv-")
        assert d["text"].startswith("Synthetic load-test record")
        assert m["score1"] >= 0 and m["score2"] >= 0 and m["winner"] in ("team1", "team2")
        for p in m["players"]:
            assert p["kddiff"] == p["kills"] - p["deaths"] and 0 <= p["kast"] <= 100
    raw, packed = write_csv_gz(rows, columns)
    assert gzip.decompress(packed) == raw and write_csv_gz(rows, columns)[1] == packed  # reproducible bytes


def test_assembly_trims_last_series_to_budget():
    (rows, stats), _ = build(37, seed=3)
    assert len(rows) == 37


def test_synthetic_ids_never_collide_with_factual_ids():
    row = {"match_id": "1", "game_id": "2", "is_total": "False", "team1": "A", "team2": "B", "tournament": "C",
           "datetime": "2024-02-29 12:00:00", "map_name": "Dust2", "score1_game": "13.0", "score2_game": "7.0"}
    assert convert(row, "d", KAGGLE)["id"] != convert(row, "d", SYNTHETIC)["id"]
    assert convert(row, "d", KAGGLE)["is_synthetic"] is False


def test_prepare_synthetic_snapshot_and_collision_guard(tmp_path):
    (rows, _), columns = build(120)
    _, packed = write_csv_gz(rows, columns)
    snapshot = tmp_path / "synthetic-cs.csv.gz"
    snapshot.write_bytes(packed)
    report = prepare_synthetic(snapshot, tmp_path / "out", base_ids=set())
    assert report["snapshot_id"] == "synthetic-cs" and report["is_synthetic"] is True
    assert (report["accepted"], report["rejected"]) == (120, 0)
    first = json.loads((tmp_path / "out" / "synthetic-cs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    with pytest.raises(ValueError, match="collides"):
        prepare_synthetic(snapshot, tmp_path / "out", base_ids={first["id"]})
    unmarked = [dict(r, is_synthetic="") for r in rows[:3]]
    snapshot.write_bytes(write_csv_gz(unmarked, columns)[1])
    assert prepare_synthetic(snapshot, tmp_path / "bad")["accepted"] == 0


def test_prepared_snapshot_reads_offsets_lazily(tmp_path):
    lines = [json.dumps({"n": i}) + "\n" for i in range(5)]
    path = tmp_path / "x.jsonl"
    path.write_text("".join(lines), encoding="utf-8", newline="\n")
    import hashlib
    manifest = {"accepted": 5, "jsonl_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    snapshot = PreparedSnapshot.load(path, manifest)
    assert len(snapshot) == 5 and snapshot[1:3] == [{"n": 1}, {"n": 2}] and snapshot[4:100] == [{"n": 4}]
    assert snapshot[5:6] == []
    with pytest.raises(ValueError, match="checksum"):
        PreparedSnapshot.load(path, manifest | {"jsonl_sha256": "0" * 64})


def test_content_enforces_scope_flag_and_counts_per_scope():
    (rows, _), _ = build(3)
    synthetic = convert(rows[0], "digest", SYNTHETIC)

    async def scenario():
        db = Database()
        service = CorpusCommandService(MongoCorpusRepository(db))
        batch = {"job_id": str(uuid4()), "batch_id": str(uuid4()), "checkpoint": 1,
                 "prepared_at": "2026-01-01T00:00:00+00:00", "documents": [synthetic]}
        assert (await service.store(batch))["inserted"] == 1
        assert db.corpus_counters.rows["synthetic-cs"]["stored_documents"] == 1
        assert db.corpus_counters.rows["kaggle-cs"]["stored_documents"] == 0
        for wrong in ({**synthetic, "is_synthetic": False}, {**synthetic, "corpus_scope": "kaggle-cs"},
                      {**synthetic, "corpus_scope": "other"}):
            with pytest.raises(ValueError):
                await service.store({**batch, "batch_id": str(uuid4()), "documents": [wrong]})
    asyncio.run(scenario())
    assert DocumentQuery(corpus_scope="synthetic-cs").corpus_scope == "synthetic-cs"
    with pytest.raises(ValueError):
        DocumentQuery(corpus_scope="other")


@pytest.mark.skipif(not SNAPSHOT.exists(), reason="generated snapshot not present")
def test_generated_snapshot_volume_and_isolation(tmp_path):
    kaggle = prepare(ROOT / "counter-strike-pro-matches.zip", tmp_path)
    base_ids = {json.loads(line)["id"] for line in (tmp_path / "kaggle-cs.jsonl").open(encoding="utf-8")}
    report = prepare_synthetic(SNAPSHOT, tmp_path, base_ids)
    assert report["rejected"] == 0
    assert kaggle["accepted"] + report["accepted"] == 100_000
    quality = json.loads((SNAPSHOT.parent / "synthetic-cs.quality.json").read_text(encoding="utf-8"))
    assert quality["snapshot_sha256"] == report["snapshot_sha256"]
    docs = [json.loads(line) for line in (tmp_path / "synthetic-cs.jsonl").open(encoding="utf-8")]
    assert all(d["is_synthetic"] and d["corpus_scope"] == "synthetic-cs" for d in docs)
    assert {d["metadata"]["document_type"] for d in docs} == {"series", "map"}
    real_names = set()
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as source:
        for r in csv.DictReader(source):
            real_names |= {r["team1"], r["team2"], r["tournament"]}
    assert all(name.startswith("Synthetic ") for name in real_names)
