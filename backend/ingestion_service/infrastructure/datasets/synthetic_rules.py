"""Pure domain rules for the synthetic load corpus (no pandas/SDV imports).

The SDV models learn two flat tables extracted from the factual CSV:

* ``series`` — one row per series (`is_total=True`): tournament, teams, best-of, series score,
  date and whether per-map detail exists;
* ``maps`` — one row per fully recorded map, oriented winner/loser: map name, round score and
  the 5+5 player statistic lines.

Cross-row relations that a single-table model cannot learn are enforced here, when the
validated samples are assembled into rows of the source CSV schema: the number of map rows
equals the series score sum, map winners reproduce the series score (the series winner takes
the last map), map names do not repeat inside a series, series player totals are the sums of
the map lines and every team keeps one fixed five-player roster.

All names are pseudonyms (D38, report section 2.2): fabricated results are never attached to
real teams, players or tournaments.
"""
from __future__ import annotations

import csv
import gzip
import io
import math
import random
from collections import Counter, defaultdict
from datetime import datetime

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
COUNT_STATS = ("kills", "deaths", "assists")
RATE_STATS = ("adr", "kast")
PLAYER_STATS = COUNT_STATS + RATE_STATS
SIDES = ("w", "l")  # map winner / loser in the training table
SERIES_COLUMNS = ("tournament", "team1", "team2", "best_of", "score1", "score2", "played_at", "detail")
MAP_COLUMNS = ("map_name", "win_score", "lose_score") + tuple(
    f"{side}{slot}_{stat}" for side in SIDES for slot in range(1, 6) for stat in PLAYER_STATS)
GENERATOR = "sdv-tvae"


def _int(value) -> int | None:
    """Integral, finite, non-negative number or None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not number.is_integer() or number < 0:
        return None
    return int(number)


def _float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


# --------------------------------------------------------------------------- training tables

def training_tables(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Extract the two SDV training tables from rows of ``cs2_all_tiers_games.csv``."""
    with_maps = {r["match_id"] for r in rows if r.get("is_total") == "False"}
    series, maps = [], []
    for r in rows:
        if r.get("is_total") == "True":
            s1, s2 = _int(r.get("score1_match")), _int(r.get("score2_match"))
            if s1 is None or s2 is None or not r.get("team1") or not r.get("team2") or r["team1"] == r["team2"]:
                continue
            bo = _int(r.get("bestOf"))
            series.append({"tournament": r["tournament"], "team1": r["team1"], "team2": r["team2"],
                "best_of": str(bo) if bo in (1, 3, 5) else "unknown", "score1": s1, "score2": s2,
                "played_at": r["datetime"], "detail": "maps" if r["match_id"] in with_maps else "none"})
        elif r.get("is_total") == "False":
            a, b = _int(r.get("score1_game")), _int(r.get("score2_game"))
            if a is None or b is None or a == b or not valid_map_score(max(a, b), min(a, b)):
                continue
            winner, loser = (1, 2) if a > b else (2, 1)
            record = {"map_name": r.get("map_name"), "win_score": max(a, b), "lose_score": min(a, b)}
            complete = bool(record["map_name"])
            for side, team in zip(SIDES, (winner, loser)):
                for slot in range(1, 6):
                    prefix = f"team{team}_player{slot}"
                    if not r.get(prefix):
                        complete = False
                    for stat in PLAYER_STATS:
                        value = (_int if stat in COUNT_STATS else _float)(r.get(f"{prefix}_{stat}"))
                        complete &= value is not None
                        record[f"{side}{slot}_{stat}"] = value
            if complete:
                maps.append(record)
    return series, maps


# --------------------------------------------------------------------------- domain checks

def valid_map_score(win: int, lose: int) -> bool:
    """CS2 MR12: regulation ends 13–0..11; each MR3 overtime adds 3 and ends with a 2–4 round margin."""
    if win == 13:
        return 0 <= lose <= 11
    return win > 13 and (win - 13) % 3 == 0 and win - 4 <= lose <= win - 2


def series_issue(row: dict, date_bounds: tuple[str, str]) -> str | None:
    """Reason a sampled series row violates the domain rules, or None when it is valid."""
    s1, s2 = _int(row.get("score1")), _int(row.get("score2"))
    if s1 is None or s2 is None:
        return "score_not_non_negative_int"
    if row.get("team1") == row.get("team2"):
        return "same_team"
    high, low = max(s1, s2), min(s1, s2)
    bo = row.get("best_of")
    need = {"1": 1, "3": 2, "5": 3}.get(str(bo))
    if need is None and bo != "unknown":
        return "unknown_best_of"
    if high == low or (need is not None and high != need) or (need is None and high not in (1, 2, 3)):
        return "score_inconsistent_with_best_of"
    played = str(row.get("played_at"))[:19]
    try:
        datetime.strptime(played, DATE_FORMAT)
    except ValueError:
        return "invalid_datetime"
    if not date_bounds[0] <= played <= date_bounds[1]:
        return "datetime_out_of_range"
    if row.get("detail") not in ("maps", "none"):
        return "unknown_detail"
    return None


def map_issue(row: dict, bounds: dict[str, tuple[float, float]], max_kill_gap: int) -> str | None:
    """Reason a sampled map row violates the domain rules, or None when it is valid."""
    win, lose = _int(row.get("win_score")), _int(row.get("lose_score"))
    if win is None or lose is None:
        return "score_not_non_negative_int"
    if not valid_map_score(win, lose):
        return "invalid_round_score"
    if not row.get("map_name"):
        return "missing_map_name"
    rounds = win + lose
    team = {side: Counter() for side in SIDES}
    for side in SIDES:
        for slot in range(1, 6):
            for stat in PLAYER_STATS:
                column = f"{side}{slot}_{stat}"
                value = (_int if stat in COUNT_STATS else _float)(row.get(column))
                if value is None:
                    return "stat_not_non_negative" + ("_int" if stat in COUNT_STATS else "")
                low, high = bounds.get(column, (0, math.inf))
                if not low <= value <= high:
                    return "stat_out_of_observed_range"
                team[side][stat] += value
            if _int(row[f"{side}{slot}_deaths"]) > rounds:
                return "deaths_exceed_rounds"
            if _float(row[f"{side}{slot}_kast"]) > 100:
                return "kast_above_100"
    # Every kill is somebody's death: a team's kills track the opponent's deaths.
    if any(abs(team[a]["kills"] - team[b]["deaths"]) > max_kill_gap for a, b in (("w", "l"), ("l", "w"))):
        return "team_kills_deaths_mismatch"
    return None


def kill_gap(row: dict) -> int:
    """Largest |team kills - opponent deaths| of one training/sample map row."""
    sums = {side: [sum(int(row[f"{side}{slot}_{stat}"]) for slot in range(1, 6)) for stat in ("kills", "deaths")]
            for side in SIDES}
    return max(abs(sums["w"][0] - sums["l"][1]), abs(sums["l"][0] - sums["w"][1]))


def numeric_bounds(maps: list[dict]) -> dict[str, tuple[float, float]]:
    columns = [c for c in MAP_COLUMNS if c != "map_name"]
    return {c: (min(float(r[c]) for r in maps), max(float(r[c]) for r in maps)) for c in columns}


# --------------------------------------------------------------------------- assembly

class Pseudonyms:
    """Frequency-ranked, deterministic pseudonyms: rank 1 is the most frequent real value."""

    def __init__(self, values, label: str, code: str):
        ranked = [value for value, _ in sorted(Counter(values).items(), key=lambda item: (-item[1], item[0]))]
        width = max(3, len(str(len(ranked))))
        self.names = {value: f"Synthetic {label} {rank:0{width}d}" for rank, value in enumerate(ranked, 1)}
        self.codes = {value: f"{code}{rank:0{width}d}" for rank, value in enumerate(ranked, 1)}


def _number(value) -> str:
    """Source CSV style: counts and scores as ``16.0``, rates with one decimal."""
    return f"{float(value):.1f}"


def _empty_row(columns: list[str]) -> dict:
    return dict.fromkeys(columns, "")


def assemble(series: list[dict], maps: list[dict], *, total: int, columns: list[str], seed: int,
             teams: Pseudonyms, tournaments: Pseudonyms, generator: str = GENERATOR) -> tuple[list[dict], dict]:
    """Build exactly ``total`` CSV rows (series + map rows) from validated samples."""
    rng = random.Random(seed)
    columns = list(columns) + [c for c in ("is_synthetic", "synthetic_generator") if c not in columns]
    pool = list(maps)
    rng.shuffle(pool)
    output, stats = [], Counter()
    remaining = total
    for number, source in enumerate(series, 1):
        if remaining <= 0:
            break
        s1, s2 = int(source["score1"]), int(source["score2"])
        detail = source["detail"] == "maps" and 1 + s1 + s2 <= remaining
        if source["detail"] == "maps" and not detail:
            stats["series_detail_trimmed_to_budget"] += 1
        match_id = f"S{number:06d}"
        team_names = {1: source["team1"], 2: source["team2"]}
        base = _empty_row(columns) | {"match_id": match_id, "is_total": "True", "tournament": tournaments.names[source["tournament"]],
            "datetime": str(source["played_at"])[:19], "is_synthetic": "True", "synthetic_generator": generator,
            "bestOf": "" if source["best_of"] == "unknown" else _number(source["best_of"]),
            "score1_match": _number(s1), "score2_match": _number(s2), "games_played": _number(s1 + s2),
            "team1_win": "1" if s1 > s2 else "0"}
        for team in (1, 2):
            base[f"team{team}"] = teams.names[team_names[team]]
            base[f"team{team}_id"] = teams.codes[team_names[team]]
        map_rows = []
        if detail:
            series_winner = 1 if s1 > s2 else 2
            winners = [1] * s1 + [2] * s2
            winners.remove(series_winner)
            rng.shuffle(winners)
            winners.append(series_winner)  # the series ends on the winner's last map
            used_names = set()
            for game, winner in enumerate(winners, 1):
                sample = _take_map(pool, used_names)
                used_names.add(sample["map_name"])
                map_rows.append(_map_row(base, sample, winner, game, columns, teams, team_names))
            _series_totals(base, map_rows, teams, team_names)
            stats["series_with_maps"] += 1
        else:
            stats["series_without_maps"] += 1
        output.append(base)
        output.extend(map_rows)
        stats["map_rows"] += len(map_rows)
        remaining -= 1 + len(map_rows)
    if remaining:
        raise ValueError(f"Not enough validated series samples: {remaining} rows missing")
    stats["series_rows"] = stats["series_with_maps"] + stats["series_without_maps"]
    stats["rows"] = len(output)
    return output, dict(stats)


def _take_map(pool: list[dict], used_names: set, lookahead: int = 500) -> dict:
    """Pop the next unused map sample whose name is new in this series (each sample used once)."""
    for index in range(len(pool) - 1, max(-1, len(pool) - 1 - lookahead), -1):
        if pool[index]["map_name"] not in used_names:
            return pool.pop(index)
    raise ValueError("Validated map samples exhausted or lack distinct map names")


def _player(team_label: str, slot: int, teams: Pseudonyms) -> tuple[str, str]:
    code = teams.codes[team_label]
    return f"Synthetic Player {code[2:]}-{slot}", f"SP{code[2:]}{slot}"


def _map_row(base: dict, sample: dict, winner: int, game: int, columns: list[str], teams: Pseudonyms,
             team_names: dict) -> dict:
    row = {k: base[k] for k in ("match_id", "tournament", "datetime", "bestOf", "is_synthetic", "synthetic_generator",
                                "team1", "team1_id", "team2", "team2_id", "score1_match", "score2_match")}
    row = _empty_row(columns) | row | {"is_total": "False", "game_id": f"{base['match_id']}-M{game}",
        "map_name": sample["map_name"], "games_played": base["games_played"]}
    side_of = {winner: "w", 3 - winner: "l"}
    row["score1_game"] = _number(sample["win_score"] if winner == 1 else sample["lose_score"])
    row["score2_game"] = _number(sample["lose_score"] if winner == 1 else sample["win_score"])
    row["team1_win"] = "1" if winner == 1 else "0"
    row["_rounds"] = int(sample["win_score"]) + int(sample["lose_score"])
    for team in (1, 2):
        for slot in range(1, 6):
            prefix = f"team{team}_player{slot}"
            row[prefix], row[prefix + "_id"] = _player(team_names[team], slot, teams)
            for stat in PLAYER_STATS:
                row[f"{prefix}_{stat}"] = _number(sample[f"{side_of[team]}{slot}_{stat}"])
            row[prefix + "_kddiff"] = _number(int(float(row[prefix + "_kills"])) - int(float(row[prefix + "_deaths"])))
    return row


def _series_totals(base: dict, map_rows: list[dict], teams: Pseudonyms, team_names: dict) -> None:
    """Series player lines: summed counts, round-weighted ADR/KAST (as in the factual corpus)."""
    rounds = sum(m["_rounds"] for m in map_rows)
    for team in (1, 2):
        for slot in range(1, 6):
            prefix = f"team{team}_player{slot}"
            base[prefix], base[prefix + "_id"] = _player(team_names[team], slot, teams)
            for stat in COUNT_STATS:
                base[f"{prefix}_{stat}"] = _number(sum(int(float(m[f"{prefix}_{stat}"])) for m in map_rows))
            for stat in RATE_STATS:
                weighted = sum(float(m[f"{prefix}_{stat}"]) * m["_rounds"] for m in map_rows) / rounds
                base[f"{prefix}_{stat}"] = _number(round(weighted, 1))
            base[prefix + "_kddiff"] = _number(int(float(base[prefix + "_kills"])) - int(float(base[prefix + "_deaths"])))
    for m in map_rows:
        m.pop("_rounds")


def write_csv_gz(rows: list[dict], columns: list[str]) -> tuple[bytes, bytes]:
    """Return (csv bytes, reproducible gzip bytes with mtime=0)."""
    columns = list(columns) + [c for c in ("is_synthetic", "synthetic_generator") if c not in columns]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    raw = buffer.getvalue().encode("utf-8")
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", mtime=0, compresslevel=9) as target:
        target.write(raw)
    return raw, packed.getvalue()


def relation_report(rows: list[dict]) -> dict:
    """Cross-row checks on the assembled CSV rows (must all hold by construction)."""
    by_match, series = defaultdict(list), {}
    for row in rows:
        if row["is_total"] == "True":
            series[row["match_id"]] = row
        else:
            by_match[row["match_id"]].append(row)
    checks = Counter()
    for match_id, maps in by_match.items():
        s = series[match_id]
        w1 = sum(float(m["score1_game"]) > float(m["score2_game"]) for m in maps)
        checks["map_winners_match_series_score"] += (w1, len(maps) - w1) == (int(float(s["score1_match"])), int(float(s["score2_match"])))
        checks["map_names_unique_in_series"] += len({m["map_name"] for m in maps}) == len(maps)
        checks["series_kills_equal_map_sum"] += all(
            int(float(s[f"team{t}_player{p}_kills"])) == sum(int(float(m[f"team{t}_player{p}_kills"])) for m in maps)
            for t in (1, 2) for p in range(1, 6))
        checks["series_with_maps"] += 1
    checks["map_rows_without_series"] = sum(1 for match_id in by_match if match_id not in series)
    return dict(checks)
