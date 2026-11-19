"""Offline SDV generation of the isolated ``synthetic-cs`` load corpus (D38).

Requires the optional tooling in ``requirements-synthetic.txt`` (SDV, SDMetrics, CPU torch);
the runtime services never import SDV. pandas/SDV are imported lazily so that the module still
imports in the normal test environment.

    python -m ingestion_service.infrastructure.datasets.synthesize_corpus \
        --archive counter-strike-pro-matches.zip --output data/synthetic

Writes ``synthetic-cs.csv.gz`` (immutable snapshot in the source CSV schema plus
``is_synthetic``/``synthetic_generator``) and ``synthetic-cs.quality.json`` (SDMetrics + domain
checks). ``prepare_corpus`` then converts the snapshot with the same validation as kaggle-cs.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import time
import zipfile
from collections import Counter
from pathlib import Path

from ingestion_service.infrastructure.datasets.synthetic_rules import (
    COUNT_STATS, DATE_FORMAT, MAP_COLUMNS, PLAYER_STATS, SERIES_COLUMNS, Pseudonyms, assemble,
    kill_gap, map_issue, numeric_bounds, relation_report, series_issue, training_tables, write_csv_gz)

BASE_DOCUMENTS = 20_675  # accepted kaggle-cs documents (20,676 CSV rows, 1 rejected)
DEFAULT_TOTAL = 100_000 - BASE_DOCUMENTS


def _metadata(table: str, frame):
    """Explicit column types (no auto-detection, so the model input is reproducible)."""
    from sdv.metadata import Metadata
    columns = {}
    for column in frame.columns:
        if column in ("tournament", "team1", "team2", "best_of", "detail", "map_name"):
            columns[column] = {"sdtype": "categorical"}
        elif column == "played_at":
            columns[column] = {"sdtype": "datetime", "datetime_format": DATE_FORMAT}
        else:
            integral = column in ("score1", "score2", "win_score", "lose_score") or column.endswith(COUNT_STATS)
            columns[column] = {"sdtype": "numerical", "decimal_places": 0 if integral else 1}
    return Metadata.load_from_dict({"METADATA_SPEC_VERSION": "V2", "tables": {table: {"columns": columns}}})


def _fit(table: str, frame, *, kind: str, epochs: int, seed: int):
    import numpy
    import torch
    from sdv.single_table import CTGANSynthesizer, TVAESynthesizer
    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)
    metadata = _metadata(table, frame)
    synthesizer = {"tvae": TVAESynthesizer, "ctgan": CTGANSynthesizer}[kind]
    model = synthesizer(metadata, epochs=epochs, batch_size=500, enforce_min_max_values=True,
                        enforce_rounding=True, enable_gpu=False)
    started = time.perf_counter()
    model.fit({table: frame})  # SDV 2.x takes {table_name: DataFrame}
    return model, metadata, round(time.perf_counter() - started, 1)


def _sample_valid(model, needed: int, check, *, chunk: int, limit: int) -> tuple[list[dict], Counter, int]:
    """Rejection sampling: keep only rows that satisfy the domain rules."""
    valid, issues, drawn = [], Counter(), 0
    while len(valid) < needed:
        if drawn >= limit:
            raise RuntimeError(f"Only {len(valid)}/{needed} valid rows after {drawn} samples: {issues.most_common(5)}")
        frame = next(iter(model.sample(num_rows=chunk, batch_size=chunk).values()))
        drawn += len(frame)
        for record in frame.to_dict("records"):
            if "played_at" in record:
                record["played_at"] = record["played_at"].strftime(DATE_FORMAT) if hasattr(record["played_at"], "strftime") else str(record["played_at"])
            issue = check(record)
            issues[issue or "valid"] += 1
            if issue is None:
                valid.append(record)
    return valid[:needed], issues, drawn


def _quality(real, synthetic, metadata) -> dict:
    from sdv.evaluation import evaluate_quality, run_diagnostic
    quality = evaluate_quality(real, synthetic, metadata, verbose=False)
    diagnostic = run_diagnostic(real, synthetic, metadata, verbose=False)
    shapes = quality.get_details("Column Shapes")
    return {"quality_score": round(quality.get_score(), 4),
        "properties": {r["Property"]: round(r["Score"], 4) for r in quality.get_properties().to_dict("records")},
        "diagnostic_score": round(diagnostic.get_score(), 4),
        "diagnostic_properties": {r["Property"]: round(r["Score"], 4) for r in diagnostic.get_properties().to_dict("records")},
        "worst_column_shapes": [{"column": r["Column"], "metric": r["Metric"], "score": round(r["Score"], 4)}
                                for r in shapes.sort_values("Score").head(5).to_dict("records")]}


def generate(archive: Path, output: Path, *, total: int = DEFAULT_TOTAL, seed: int = 2026,
             series_epochs: int = 300, map_epochs: int = 300, series_model: str = "tvae",
             map_model: str = "tvae") -> dict:
    import pandas
    started = time.perf_counter()
    raw = zipfile.ZipFile(archive).read("cs2_all_tiers_games.csv")
    source_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    columns = list(source_rows[0].keys())
    series_rows, map_rows = training_tables(source_rows)
    series_real = pandas.DataFrame(series_rows, columns=SERIES_COLUMNS)
    maps_real = pandas.DataFrame(map_rows, columns=MAP_COLUMNS)

    date_bounds = (series_real["played_at"].min(), series_real["played_at"].max())
    bounds = numeric_bounds(map_rows)
    gaps = sorted(kill_gap(r) for r in map_rows)
    max_gap = gaps[int(len(gaps) * 0.99)]  # tolerance = real 99th percentile

    series_model, series_meta, series_fit = _fit("series", series_real, kind=series_model, epochs=series_epochs, seed=seed)
    maps_model, maps_meta, maps_fit = _fit("maps", maps_real, kind=map_model, epochs=map_epochs, seed=seed + 1)

    # Expected rows per series in the real table: 1 + share_with_maps * mean(score sum).
    with_maps = series_real[series_real["detail"] == "maps"]
    per_series = 1 + len(with_maps) / len(series_real) * (with_maps["score1"] + with_maps["score2"]).mean()
    series_needed = int(total / per_series * 1.1) + 100
    series_valid, series_issues, series_drawn = _sample_valid(
        series_model, series_needed, lambda r: series_issue(r, date_bounds), chunk=20_000, limit=series_needed * 20)
    maps_needed = sum(int(r["score1"]) + int(r["score2"]) for r in series_valid if r["detail"] == "maps")
    maps_valid, maps_issues, maps_drawn = _sample_valid(
        maps_model, maps_needed, lambda r: map_issue(r, bounds, max_gap), chunk=20_000, limit=maps_needed * 40)

    teams = Pseudonyms(list(series_real["team1"]) + list(series_real["team2"]), "Team", "ST")
    tournaments = Pseudonyms(series_real["tournament"], "Tournament", "TT")
    generator = f"sdv-{series_model}+{map_model}"
    rows, assembly = assemble(series_valid, maps_valid, total=total, columns=columns, seed=seed,
                              teams=teams, tournaments=tournaments, generator=generator)
    used_series = series_valid[:assembly["series_rows"]]
    used_maps = maps_valid[:assembly["map_rows"]]
    csv_bytes, packed = write_csv_gz(rows, columns)
    output.mkdir(parents=True, exist_ok=True)
    (output / "synthetic-cs.csv.gz").write_bytes(packed)

    report = {
        "snapshot_id": "synthetic-cs", "generator": generator,
        "synthesizers": {"series": f"sdv.single_table.{series_model.upper()}Synthesizer",
                         "maps": f"sdv.single_table.{map_model.upper()}Synthesizer"},
        "seed": seed, "epochs": {"series": series_epochs, "maps": map_epochs},
        "fit_seconds": {"series": series_fit, "maps": maps_fit},
        "total_seconds": round(time.perf_counter() - started, 1),
        "training_rows": {"series": len(series_real), "maps": len(maps_real)},
        "rows": assembly, "base_documents": BASE_DOCUMENTS, "combined_documents": BASE_DOCUMENTS + len(rows),
        "snapshot_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "snapshot_gzip_sha256": hashlib.sha256(packed).hexdigest(),
        "rejection_sampling": {
            "series": {"drawn": series_drawn, "issues": dict(series_issues)},
            "maps": {"drawn": maps_drawn, "issues": dict(maps_issues),
                     "team_kill_death_gap_tolerance": max_gap}},
        "relations": relation_report(rows),
        "sdmetrics": {
            "series": _quality(series_real, pandas.DataFrame(used_series, columns=SERIES_COLUMNS), series_meta),
            "maps": _quality(maps_real, pandas.DataFrame(used_maps, columns=MAP_COLUMNS), maps_meta)},
        "real_reference": {
            "series_detail_share": round(len(with_maps) / len(series_real), 4),
            "synthetic_detail_share": round(assembly.get("series_with_maps", 0) / assembly["series_rows"], 4),
            "map_name_share_real": _shares(maps_real["map_name"]),
            "map_name_share_synthetic": _shares(pandas.Series([r["map_name"] for r in used_maps]))},
        "privacy": "teams, players and tournaments are frequency-ranked pseudonyms; no real names are emitted",
    }
    (output / "synthetic-cs.quality.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _shares(series) -> dict:
    return {k: round(v, 4) for k, v in series.value_counts(normalize=True).sort_index().items()}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", type=Path, default=Path("counter-strike-pro-matches.zip"))
    parser.add_argument("--output", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--total", type=int, default=DEFAULT_TOTAL, help="synthetic rows (series + map documents)")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--series-epochs", type=int, default=300)
    parser.add_argument("--map-epochs", type=int, default=300)
    parser.add_argument("--series-model", choices=("ctgan", "tvae"), default="tvae")
    parser.add_argument("--map-model", choices=("ctgan", "tvae"), default="tvae")
    args = parser.parse_args()
    result = generate(args.archive, args.output, total=args.total, seed=args.seed,
                      series_epochs=args.series_epochs, map_epochs=args.map_epochs,
                      series_model=args.series_model, map_model=args.map_model)
    print(json.dumps({k: result[k] for k in ("rows", "combined_documents", "fit_seconds", "total_seconds", "relations")}
                     | {"quality": {t: q["quality_score"] for t, q in result["sdmetrics"].items()}}, indent=2))
