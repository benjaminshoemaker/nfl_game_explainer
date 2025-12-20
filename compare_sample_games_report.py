#!/usr/bin/env python3
"""
Generate an overall comparison report for a list of ESPN game IDs.

Compares:
  - ESPN official team totals from the summary endpoint (Total Yards, Turnovers)
  - windelta.app totals computed from the same summary payload via nfl_core.process_game_stats

Default input is sample_games.txt.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# Add api/ to path for shared imports, matching game_compare.py's approach.
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from lib.game_analysis import get_game_data  # noqa: E402
from lib.nfl_core import process_game_stats  # noqa: E402


@dataclass(frozen=True)
class TeamLine:
    game_id: str
    team: str
    home_away: str
    opponent: str
    espn_total_yards: Optional[int]
    windelta_total_yards: Optional[int]
    yards_delta: Optional[int]
    espn_turnovers: Optional[int]
    windelta_turnovers: Optional[int]
    turnovers_delta: Optional[int]
    espn_penalty_yards: Optional[int]
    windelta_penalty_yards: Optional[int]
    penalty_yards_delta: Optional[int]
    windelta_source: str


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_game_ids(path: Path) -> List[str]:
    ids: List[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line.split(",")[0].strip())
    # De-dup, preserve order.
    seen = set()
    out: List[str] = []
    for gid in ids:
        if gid and gid not in seen:
            out.append(gid)
            seen.add(gid)
    return out


def extract_espn_official_team_stats(raw_data: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Optional[int]]], Dict[str, str]]:
    comps = raw_data.get("header", {}).get("competitions", [])
    away_abbr = home_abbr = None
    away_score = home_score = None
    if comps:
        for competitor in comps[0].get("competitors", []):
            abbr = competitor.get("team", {}).get("abbreviation")
            score = _parse_int(competitor.get("score"))
            if competitor.get("homeAway") == "away":
                away_abbr, away_score = abbr, score
            elif competitor.get("homeAway") == "home":
                home_abbr, home_score = abbr, score

    espn_by_abbr: Dict[str, Dict[str, Optional[int]]] = {}
    box = raw_data.get("boxscore", {}) or {}
    for team_data in box.get("teams", []) or []:
        abbr = (team_data.get("team", {}) or {}).get("abbreviation")
        if not abbr:
            continue
        stats = {s.get("name"): s.get("displayValue") for s in (team_data.get("statistics") or [])}
        penalty_yards = None
        penalties_raw = stats.get("totalPenaltiesYards")
        if isinstance(penalties_raw, str) and "-" in penalties_raw:
            parts = penalties_raw.split("-", 1)
            if len(parts) == 2:
                penalty_yards = _parse_int(parts[1])
        espn_by_abbr[abbr] = {
            "Score": away_score if abbr == away_abbr else home_score,
            "Total Yards": _parse_int(stats.get("totalYards")),
            "Turnovers": _parse_int(stats.get("turnovers")),
            "Penalty Yards": penalty_yards,
        }

    meta = {
        "away": away_abbr or "",
        "home": home_abbr or "",
    }
    return espn_by_abbr, meta


def load_raw_game_data(game_id: str, *, source: str, cache_dir: Path) -> Tuple[Dict[str, Any], str]:
    if source not in {"auto", "cache", "network"}:
        raise ValueError(f"Invalid source: {source}")

    cache_path = cache_dir / f"{game_id}.json"
    if source in {"auto", "cache"} and cache_path.exists():
        return json.loads(cache_path.read_text()), "cache"

    if source == "cache":
        raise FileNotFoundError(f"Missing cached game JSON: {cache_path}")

    return get_game_data(game_id), "network"


def build_report_lines(game_ids: Iterable[str], *, source: str, cache_dir: Path) -> Tuple[List[TeamLine], List[str]]:
    lines: List[TeamLine] = []
    failures: List[str] = []

    for game_id in game_ids:
        try:
            raw_data, raw_source = load_raw_game_data(game_id, source=source, cache_dir=cache_dir)
            espn_stats, espn_meta = extract_espn_official_team_stats(raw_data)

            stats_rows, _details = process_game_stats(
                raw_data,
                expanded=False,
                probability_map=None,
                pregame_probabilities=None,
                wp_threshold=1.0,
            )
            windelta_stats: Dict[str, Dict[str, Optional[int]]] = {
                row.get("Team"): {
                    "Total Yards": _parse_int(row.get("Total Yards")),
                    "Turnovers": _parse_int(row.get("Turnovers")),
                    "Penalty Yards": _parse_int(row.get("Penalty Yards")),
                }
                for row in stats_rows
                if row.get("Team")
            }

            away = espn_meta.get("away") or ""
            home = espn_meta.get("home") or ""

            for team, home_away, opponent in [
                (away, "away", home),
                (home, "home", away),
            ]:
                if not team:
                    continue
                e = espn_stats.get(team, {})
                w = windelta_stats.get(team, {})

                e_y = e.get("Total Yards")
                w_y = w.get("Total Yards")
                e_to = e.get("Turnovers")
                w_to = w.get("Turnovers")
                e_py = e.get("Penalty Yards")
                w_py = w.get("Penalty Yards")

                lines.append(
                    TeamLine(
                        game_id=game_id,
                        team=team,
                        home_away=home_away,
                        opponent=opponent,
                        espn_total_yards=e_y,
                        windelta_total_yards=w_y,
                        yards_delta=(w_y - e_y) if (w_y is not None and e_y is not None) else None,
                        espn_turnovers=e_to,
                        windelta_turnovers=w_to,
                        turnovers_delta=(w_to - e_to) if (w_to is not None and e_to is not None) else None,
                        espn_penalty_yards=e_py,
                        windelta_penalty_yards=w_py,
                        penalty_yards_delta=(w_py - e_py) if (w_py is not None and e_py is not None) else None,
                        windelta_source=f"nfl_core.process_game_stats (full, wp_threshold=1.0, raw={raw_source})",
                    )
                )
        except Exception as exc:
            failures.append(f"{game_id}: {exc}")

    return lines, failures


def write_csv(path: Path, lines: List[TeamLine]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "game_id",
                "team",
                "home_away",
                "opponent",
                "espn_total_yards",
                "windelta_total_yards",
                "yards_delta",
                "espn_turnovers",
                "windelta_turnovers",
                "turnovers_delta",
                "espn_penalty_yards",
                "windelta_penalty_yards",
                "penalty_yards_delta",
                "windelta_source",
            ],
        )
        writer.writeheader()
        for line in lines:
            writer.writerow(
                {
                    "game_id": line.game_id,
                    "team": line.team,
                    "home_away": line.home_away,
                    "opponent": line.opponent,
                    "espn_total_yards": line.espn_total_yards,
                    "windelta_total_yards": line.windelta_total_yards,
                    "yards_delta": line.yards_delta,
                    "espn_turnovers": line.espn_turnovers,
                    "windelta_turnovers": line.windelta_turnovers,
                    "turnovers_delta": line.turnovers_delta,
                    "espn_penalty_yards": line.espn_penalty_yards,
                    "windelta_penalty_yards": line.windelta_penalty_yards,
                    "penalty_yards_delta": line.penalty_yards_delta,
                    "windelta_source": line.windelta_source,
                }
            )


def _fmt_val(val: Optional[int]) -> str:
    return "N/A" if val is None else str(val)


def _fmt_delta(delta: Optional[int]) -> str:
    return "N/A" if delta is None else f"{delta:+d}"


def _print_table(headers: List[str], rows: List[List[str]], *, right_align_cols: Optional[set[int]] = None) -> None:
    if not rows:
        return

    right_align_cols = right_align_cols or set()
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(row: List[str]) -> str:
        parts: List[str] = []
        for i, cell in enumerate(row):
            parts.append(cell.rjust(widths[i]) if i in right_align_cols else cell.ljust(widths[i]))
        return " | ".join(parts)

    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))


def print_terminal_report(lines: List[TeamLine], mode: str, *, fmt: str = "table") -> None:
    if mode == "none":
        return

    by_game: Dict[str, List[TeamLine]] = {}
    for line in lines:
        by_game.setdefault(line.game_id, []).append(line)

    def row_mismatch(row: TeamLine) -> bool:
        return (row.yards_delta or 0) != 0 or (row.turnovers_delta or 0) != 0 or (row.penalty_yards_delta or 0) != 0

    if fmt not in {"table", "line"}:
        raise ValueError(f"Invalid fmt: {fmt}")

    if fmt == "line":
        for game_id in sorted(by_game.keys()):
            game_rows = by_game[game_id]
            away = next((r for r in game_rows if r.home_away == "away"), None)
            home = next((r for r in game_rows if r.home_away == "home"), None)

            any_mismatch = any(row_mismatch(r) for r in game_rows)
            if mode == "mismatches" and not any_mismatch:
                continue

            away_team = away.team if away else "AWAY"
            home_team = home.team if home else "HOME"

            def seg(r: Optional[TeamLine]) -> str:
                if not r:
                    return "N/A"
                return (
                    f"{r.team} yd {_fmt_val(r.windelta_total_yards)}/{_fmt_val(r.espn_total_yards)}"
                    f"({_fmt_delta(r.yards_delta)})"
                    f" TO {_fmt_val(r.windelta_turnovers)}/{_fmt_val(r.espn_turnovers)}"
                    f"({_fmt_delta(r.turnovers_delta)})"
                    f" PEN {_fmt_val(r.windelta_penalty_yards)}/{_fmt_val(r.espn_penalty_yards)}"
                    f"({_fmt_delta(r.penalty_yards_delta)})"
                )

            status = "MISMATCH" if any_mismatch else "MATCH"
            print(f"{game_id} {away_team} @ {home_team} | {seg(away)} | {seg(home)} | {status}")
        return

    headers = [
        "game_id",
        "matchup",
        "away_yards",
        "away_yards_delta",
        "away_turnovers",
        "away_turnovers_delta",
        "away_penalty_yards",
        "away_penalty_yards_delta",
        "home_yards",
        "home_yards_delta",
        "home_turnovers",
        "home_turnovers_delta",
        "home_penalty_yards",
        "home_penalty_yards_delta",
        "status",
    ]
    rows: List[List[str]] = []
    for game_id in sorted(by_game.keys()):
        game_rows = by_game[game_id]
        away = next((r for r in game_rows if r.home_away == "away"), None)
        home = next((r for r in game_rows if r.home_away == "home"), None)

        any_mismatch = any(row_mismatch(r) for r in game_rows)
        if mode == "mismatches" and not any_mismatch:
            continue

        away_team = away.team if away else "AWAY"
        home_team = home.team if home else "HOME"

        def pair(w: Optional[int], e: Optional[int]) -> str:
            return f"{_fmt_val(w)}/{_fmt_val(e)}"

        status = "MISMATCH" if any_mismatch else "MATCH"
        rows.append(
            [
                game_id,
                f"{away_team} @ {home_team}",
                pair(away.windelta_total_yards if away else None, away.espn_total_yards if away else None),
                _fmt_delta(away.yards_delta if away else None),
                pair(away.windelta_turnovers if away else None, away.espn_turnovers if away else None),
                _fmt_delta(away.turnovers_delta if away else None),
                pair(away.windelta_penalty_yards if away else None, away.espn_penalty_yards if away else None),
                _fmt_delta(away.penalty_yards_delta if away else None),
                pair(home.windelta_total_yards if home else None, home.espn_total_yards if home else None),
                _fmt_delta(home.yards_delta if home else None),
                pair(home.windelta_turnovers if home else None, home.espn_turnovers if home else None),
                _fmt_delta(home.turnovers_delta if home else None),
                pair(home.windelta_penalty_yards if home else None, home.espn_penalty_yards if home else None),
                _fmt_delta(home.penalty_yards_delta if home else None),
                status,
            ]
        )
    _print_table(headers, rows, right_align_cols={3, 5, 7, 9, 11, 13})


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare ESPN official yards/turnovers vs windelta.app logic for many games."
    )
    parser.add_argument(
        "--input",
        default="sample_games.txt",
        help="Path to a file containing ESPN game IDs (one per line; CSV ok, first column used).",
    )
    parser.add_argument(
        "--out",
        default=os.path.join("audits", "sample_games_comparison.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "cache", "network"],
        default="auto",
        help="Where to load raw ESPN summary payloads (default: auto, uses pbp_cache first).",
    )
    parser.add_argument(
        "--cache-dir",
        default="pbp_cache",
        help="Directory containing cached summary JSON files (default: pbp_cache).",
    )
    parser.add_argument(
        "--print",
        choices=["mismatches", "all", "none"],
        default="mismatches",
        help="Terminal output mode (default: mismatches).",
    )
    parser.add_argument(
        "--print-format",
        choices=["table", "line"],
        default="table",
        help="Terminal output format (default: table). Use 'line' for the legacy one-line-per-game output.",
    )
    args = parser.parse_args()

    input_path = (REPO_ROOT / args.input).resolve() if not os.path.isabs(args.input) else Path(args.input)
    game_ids = load_game_ids(input_path)
    if not game_ids:
        print(f"No game IDs found in {input_path}", file=sys.stderr)
        return 2

    cache_dir = (REPO_ROOT / args.cache_dir).resolve() if not os.path.isabs(args.cache_dir) else Path(args.cache_dir)
    lines, failures = build_report_lines(game_ids, source=args.source, cache_dir=cache_dir)
    write_csv(Path(args.out), lines)

    mismatches = [
        l
        for l in lines
        if (l.yards_delta or 0) != 0 or (l.turnovers_delta or 0) != 0 or (l.penalty_yards_delta or 0) != 0
    ]
    print_terminal_report(lines, args.print, fmt=args.print_format)
    print(f"Wrote {len(lines)} team rows to {args.out}")
    print(f"Mismatches: {len(mismatches)} rows")
    if failures:
        print(f"Failures: {len(failures)} games", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
