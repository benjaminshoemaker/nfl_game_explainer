#!/usr/bin/env python3
"""
Generate a season-wide reconciliation report for windelta vs ESPN official stats.

This script:
  1) Fetches all ESPN game IDs for a season and writes them to a txt file.
  2) Runs the yards/turnovers comparison for every game.
  3) Sorts games by priority: abs(turnovers delta) desc, then abs(yards delta) desc.
  4) Writes a comprehensive markdown report with suspected reconciliation work items.

Notes:
  - Network calls are required unless you run with --source cache and have pbp_cache populated.
  - The comparison uses windelta's core logic (api/lib/nfl_core.process_game_stats) with wp_threshold=1.0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import re


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from lib.game_analysis import get_game_data  # noqa: E402
from lib.nfl_core import (  # noqa: E402
    classify_offense_play,
    final_play_text,
    is_nullified_play,
    is_penalty_play,
    is_special_teams_play,
    is_spike_or_kneel,
    process_game_stats,
)


ESPN_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.espn.com/",
    "Origin": "https://www.espn.com",
}

CORE_WEEK_EVENTS_URL = (
    "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
    "seasons/{season}/types/{season_type}/weeks/{week}/events"
)


def _decompress_response(data: bytes) -> bytes:
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data


def _fetch_json(url: str, *, timeout_s: int = 15) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=ESPN_REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = _decompress_response(resp.read())
        return json.loads(raw.decode())


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
    seen = set()
    out: List[str] = []
    for gid in ids:
        if gid and gid not in seen:
            out.append(gid)
            seen.add(gid)
    return out


def extract_event_ids_from_core_schedule(payload: Dict[str, Any]) -> List[str]:
    items = payload.get("items") or []
    out: List[str] = []
    for item in items:
        if isinstance(item, dict):
            if item.get("id"):
                out.append(str(item["id"]))
                continue
            ref = item.get("$ref")
            if not ref or not isinstance(ref, str):
                continue
            # .../events/<id>?lang=en&region=us
            path = ref.split("?", 1)[0]
            parts = path.rstrip("/").split("/")
            if parts:
                out.append(parts[-1])
    return [gid for gid in out if gid]


def fetch_week_game_ids_core(season: int, season_type: int, week: int) -> List[str]:
    url = f"{CORE_WEEK_EVENTS_URL.format(season=season, season_type=season_type, week=week)}?limit=1000"
    payload = _fetch_json(url, timeout_s=20)
    return extract_event_ids_from_core_schedule(payload)


def fetch_season_game_ids(
    season: int,
    *,
    season_types: Sequence[int] = (2, 3),
    max_weeks_by_type: Optional[Dict[int, int]] = None,
    max_week: Optional[int] = None,
    fetch_week_ids: Optional[Callable[[int, int, int], List[str]]] = None,
) -> List[str]:
    max_weeks_by_type = max_weeks_by_type or {1: 4, 2: 18, 3: 5}
    fetch_week_ids = fetch_week_ids or fetch_week_game_ids_core

    ids: List[str] = []
    for st in season_types:
        max_weeks = max_weeks_by_type.get(st, 18)
        if st == 2 and max_week is not None:
            max_weeks = min(max_weeks, max(1, max_week))
        for week in range(1, max_weeks + 1):
            try:
                week_ids = fetch_week_ids(season, st, week)
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
                week_ids = []
            if not week_ids:
                continue
            ids.extend(week_ids)

    # De-dup, preserve order.
    seen = set()
    out: List[str] = []
    for gid in ids:
        if gid not in seen:
            out.append(gid)
            seen.add(gid)
    return out


def write_game_ids_txt(path: Path, game_ids: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(game_ids) + ("\n" if game_ids else ""))


def extract_espn_official_team_stats(
    raw_data: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Optional[int]]], Dict[str, str]]:
    comps = raw_data.get("header", {}).get("competitions", [])
    away_abbr = home_abbr = None
    away_score = home_score = None
    if comps:
        for competitor in (comps[0].get("competitors") or []):
            abbr = competitor.get("team", {}).get("abbreviation")
            score = _parse_int(competitor.get("score"))
            if competitor.get("homeAway") == "away":
                away_abbr, away_score = abbr, score
            elif competitor.get("homeAway") == "home":
                home_abbr, home_score = abbr, score

    espn_by_abbr: Dict[str, Dict[str, Optional[int]]] = {}
    box = raw_data.get("boxscore", {}) or {}
    for team_data in (box.get("teams") or []):
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

    meta = {"away": away_abbr or "", "home": home_abbr or ""}
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


@dataclass(frozen=True)
class PlayBlurb:
    quarter: Any
    clock: str
    play_type: str
    text: str
    yards: Optional[int] = None
    reason: Optional[str] = None

    def format_line(self) -> str:
        q = f"Q{self.quarter}" if self.quarter not in (None, "", "?") else "Q?"
        clk = self.clock or "?"
        y = "" if self.yards is None else f" ({self.yards} yds)"
        r = "" if not self.reason else f" [{self.reason}]"
        return f"- {q} {clk}{y} {self.play_type}: {self.text}{r}"


@dataclass(frozen=True)
class GameRecon:
    game_id: str
    away: str
    home: str
    raw_source: str
    team_lines: Tuple[TeamLine, TeamLine]
    turnover_plays_by_team: Dict[str, List[PlayBlurb]]
    potential_turnover_keyword_plays: Dict[str, List[PlayBlurb]]
    excluded_yardage_plays: Dict[str, List[PlayBlurb]]

    @property
    def max_abs_turnovers_delta(self) -> int:
        vals = [abs(l.turnovers_delta or 0) for l in self.team_lines]
        return max(vals) if vals else 0

    @property
    def max_abs_yards_delta(self) -> int:
        vals = [abs(l.yards_delta or 0) for l in self.team_lines]
        return max(vals) if vals else 0

    @property
    def any_mismatch(self) -> bool:
        return any(
            (l.yards_delta or 0) != 0 or (l.turnovers_delta or 0) != 0 or (l.penalty_yards_delta or 0) != 0
            for l in self.team_lines
        )

    def priority_key(self) -> Tuple[int, int, str]:
        return (-self.max_abs_turnovers_delta, -self.max_abs_yards_delta, self.game_id)


Number = Union[int, float]


def _pct_delta(delta: Number, denom: Number) -> Optional[float]:
    try:
        denom_f = float(denom)
        if denom_f == 0.0:
            return None
        return (float(delta) / denom_f) * 100.0
    except Exception:
        return None


def compute_aggregate_deltas(recon: Sequence[GameRecon]) -> Dict[str, Dict[str, Optional[Number]]]:
    """
    Aggregate totals across all team rows and compute overall percent deltas:
      pct_delta = (sum(windelta) - sum(espn)) / sum(espn) * 100
    """
    lines: List[TeamLine] = []
    for g in recon:
        lines.extend(list(g.team_lines))

    def agg(field_espn: str, field_windelta: str) -> Dict[str, Optional[Number]]:
        espn_sum = 0
        windelta_sum = 0
        used = 0
        for line in lines:
            e = getattr(line, field_espn)
            w = getattr(line, field_windelta)
            if e is None or w is None:
                continue
            espn_sum += int(e)
            windelta_sum += int(w)
            used += 1
        delta = windelta_sum - espn_sum
        return {
            "rows_used": used,
            "espn_sum": espn_sum,
            "windelta_sum": windelta_sum,
            "delta": delta,
            "pct_delta": _pct_delta(delta, espn_sum),
        }

    def mismatch_count(field_delta: str) -> int:
        return sum(1 for line in lines if (getattr(line, field_delta) or 0) != 0)

    return {
        "total_yards": {
            **agg("espn_total_yards", "windelta_total_yards"),
            "mismatch_rows": mismatch_count("yards_delta"),
        },
        "turnovers": {
            **agg("espn_turnovers", "windelta_turnovers"),
            "mismatch_rows": mismatch_count("turnovers_delta"),
        },
        "penalty_yards": {
            **agg("espn_penalty_yards", "windelta_penalty_yards"),
            "mismatch_rows": mismatch_count("penalty_yards_delta"),
        },
    }


def print_aggregate_report(recon: Sequence[GameRecon]) -> None:
    agg = compute_aggregate_deltas(recon)

    def fmt_pct(val: Optional[Number]) -> str:
        if val is None:
            return "N/A"
        return f"{float(val):+.3f}%"

    def line(label: str, key: str) -> str:
        a = agg[key]
        return (
            f"{label}: {a['windelta_sum']}/{a['espn_sum']} (Δ {int(a['delta']):+d}, {fmt_pct(a['pct_delta'])})"
            f" | mismatched rows: {a['mismatch_rows']}/{a['rows_used']}"
        )

    print("\n=== AGGREGATE DELTAS (windelta vs ESPN) ===")
    print(line("Total Yards", "total_yards"))
    print(line("Turnovers", "turnovers"))
    print(line("Penalty Yards", "penalty_yards"))


_FOR_YARDS_RE = re.compile(r"\bfor (-?\d+) yards\b", re.IGNORECASE)


def _credited_yards_before_fumble(event_text: str) -> Optional[int]:
    if not event_text:
        return None
    lower = event_text.lower()
    if "fumble" not in lower:
        return None
    prefix = lower.split("fumble", 1)[0]
    matches = list(_FOR_YARDS_RE.finditer(prefix))
    if matches:
        try:
            return int(matches[-1].group(1))
        except ValueError:
            return None
    if "for no gain" in prefix or "for no loss" in prefix:
        return 0
    m = re.search(r"\bfor loss of (\d+) yards\b", prefix)
    if m:
        try:
            return -int(m.group(1))
        except ValueError:
            return None
    return None


def write_logic_recommendations(
    path: Path,
    recon: Sequence[GameRecon],
    *,
    season: int,
    cache_dir: Path,
) -> None:
    """
    Write a lightweight, data-driven recommendations report based on remaining mismatches.

    This is meant to be regenerated each run as logic changes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[TeamLine] = []
    for g in recon:
        lines.extend(list(g.team_lines))

    mismatch_lines = [
        l for l in lines if (l.yards_delta or 0) != 0 or (l.turnovers_delta or 0) != 0 or (l.penalty_yards_delta or 0) != 0
    ]

    agg = compute_aggregate_deltas(recon)

    # Heuristic residual-analysis on remaining yard deltas.
    kneel_explained = 0
    fumble_credit_explained = 0
    analyzed = 0

    # Build quick map: game_id -> raw payload.
    raw_by_game: Dict[str, Dict[str, Any]] = {}
    for g in recon:
        cache_path = cache_dir / f"{g.game_id}.json"
        if not cache_path.exists():
            continue
        try:
            raw_by_game[g.game_id] = json.loads(cache_path.read_text())
        except Exception:
            continue

    # Precompute team ids per game.
    abbr_to_id_by_game: Dict[str, Dict[str, str]] = {}
    for gid, raw in raw_by_game.items():
        abbr_to_id: Dict[str, str] = {}
        for t in (raw.get("boxscore", {}) or {}).get("teams", []) or []:
            abbr = (t.get("team", {}) or {}).get("abbreviation")
            tid = (t.get("team", {}) or {}).get("id")
            if abbr and tid:
                abbr_to_id[abbr] = str(tid)
        abbr_to_id_by_game[gid] = abbr_to_id

    for l in mismatch_lines:
        if (l.yards_delta or 0) == 0:
            continue
        raw = raw_by_game.get(l.game_id)
        if not raw:
            continue
        team_id = abbr_to_id_by_game.get(l.game_id, {}).get(l.team)
        if not team_id:
            continue

        drives = (raw.get("drives", {}) or {}).get("previous", []) or []
        kneel_sum = 0
        fumble_adj = 0

        for drive in drives:
            if str(((drive.get("team") or {}).get("id") or "")) != team_id:
                continue
            for play in (drive.get("plays") or []):
                text = play.get("text") or ""
                text_lower = text.lower()
                play_type = ((play.get("type") or {}).get("text") or "").lower()
                stat_yards = _parse_int(play.get("statYardage")) or 0

                if is_spike_or_kneel(text_lower, play_type):
                    kneel_sum += stat_yards

                event_text = final_play_text(text) or ""
                credited = _credited_yards_before_fumble(event_text)
                if credited is not None and "fumble" in (event_text or "").lower():
                    fumble_adj += (credited - stat_yards)

        analyzed += 1
        if (l.yards_delta or 0) == -kneel_sum:
            kneel_explained += 1
        if (l.yards_delta or 0) == fumble_adj:
            fumble_credit_explained += 1

    # Top remaining mismatches for human review.
    top_yards = sorted([l for l in mismatch_lines if (l.yards_delta or 0) != 0], key=lambda x: abs(x.yards_delta or 0), reverse=True)[:25]
    top_turnovers = sorted([l for l in mismatch_lines if (l.turnovers_delta or 0) != 0], key=lambda x: abs(x.turnovers_delta or 0), reverse=True)[:25]

    out: List[str] = []
    out.append(f"# Season {season} Logic Recommendations (Auto)")
    out.append("")
    out.append("Generated from cached `pbp_cache/*.json` plus `audits/season_*_team_comparison.csv`-equivalent data.")
    out.append("")
    out.append("## Aggregate Percent Deltas")
    out.append("- Percent deltas are computed as `(sum(windelta) - sum(espn)) / sum(espn) * 100`.")

    def fmt_pct(val: Optional[Number]) -> str:
        if val is None:
            return "N/A"
        return f"{float(val):+.3f}%"

    out.append(f"- Total Yards: {fmt_pct(agg['total_yards']['pct_delta'])} (Δ {int(agg['total_yards']['delta']):+d})")
    out.append(f"- Turnovers: {fmt_pct(agg['turnovers']['pct_delta'])} (Δ {int(agg['turnovers']['delta']):+d})")
    out.append(f"- Penalty Yards: {fmt_pct(agg['penalty_yards']['pct_delta'])} (Δ {int(agg['penalty_yards']['delta']):+d})")
    out.append("")
    out.append("## Remaining Mismatch Counts (Team Rows)")
    out.append(f"- Yards mismatches: {agg['total_yards']['mismatch_rows']}/{agg['total_yards']['rows_used']}")  # type: ignore[index]
    out.append(f"- Turnover mismatches: {agg['turnovers']['mismatch_rows']}/{agg['turnovers']['rows_used']}")  # type: ignore[index]
    out.append(f"- Penalty-yards mismatches: {agg['penalty_yards']['mismatch_rows']}/{agg['penalty_yards']['rows_used']}")  # type: ignore[index]
    out.append("")

    out.append("## Heuristic Attribution (Yards)")
    out.append(f"- Rows analyzed (with cache available): {analyzed}")
    out.append(f"- Rows exactly explained by kneel/spike exclusion: {kneel_explained}")
    out.append(f"- Rows exactly explained by fumble credited-yards mismatch: {fumble_credit_explained}")
    out.append("")

    out.append("## Recommendations")
    if agg["total_yards"]["mismatch_rows"]:
        out.append("- Inspect top remaining yards deltas; remaining issues are likely edge cases (special teams attribution, rare replay phrasing, unusual play types).")
    if agg["turnovers"]["mismatch_rows"]:
        out.append("- Inspect turnover mismatches; remaining issues are likely muffed-kick or touchback corner cases.")
    if not agg["total_yards"]["mismatch_rows"] and not agg["turnovers"]["mismatch_rows"]:
        out.append("- Core reconciliation looks clean for the compared stats; add new stat categories to extend coverage.")
    out.append("")

    def fmt_row(l: TeamLine) -> str:
        return (
            f"- {l.game_id} {l.team}: YdsΔ {_fmt_delta(l.yards_delta)} "
            f"TOΔ {_fmt_delta(l.turnovers_delta)} PenYdsΔ {_fmt_delta(l.penalty_yards_delta)}"
        )

    if top_yards:
        out.append("## Top Remaining Yard Deltas (Team Rows)")
        out.extend(fmt_row(l) for l in top_yards)
        out.append("")

    if top_turnovers:
        out.append("## Remaining Turnover Deltas (Team Rows)")
        out.extend(fmt_row(l) for l in top_turnovers)
        out.append("")

    out.append("## Suggested Deep-Dive Command")
    out.append("- For any game above: `python diagnose_game_discrepancies.py <game_id>`")
    out.append("")

    path.write_text("\n".join(out).rstrip() + "\n")


def _team_id_maps(raw_data: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    id_to_abbr: Dict[str, str] = {}
    abbr_to_id: Dict[str, str] = {}
    for t in (raw_data.get("boxscore", {}) or {}).get("teams", []) or []:
        tid = (t.get("team", {}) or {}).get("id")
        abbr = (t.get("team", {}) or {}).get("abbreviation")
        if tid and abbr:
            id_to_abbr[str(tid)] = abbr
            abbr_to_id[abbr] = str(tid)
    return id_to_abbr, abbr_to_id


def _detect_exclusion_reason(play: Dict[str, Any]) -> Optional[str]:
    text_lower = (play.get("text") or "").lower()
    type_lower = ((play.get("type") or {}).get("text") or "").lower()
    if "timeout" in type_lower or "end of" in type_lower:
        return "marker"
    if ("kickoff" in type_lower or "punt" in type_lower) and "return" in type_lower:
        return "special_teams_return"
    if "interception return" in type_lower or "fumble return" in type_lower:
        return "turnover_return"
    if is_nullified_play(text_lower):
        return "nullified"
    if is_penalty_play(play, text_lower, type_lower):
        return "penalty_no_play"
    if is_spike_or_kneel(text_lower, type_lower):
        return "spike_kneel"
    if is_special_teams_play(text_lower, type_lower):
        return "special_teams"
    return None


def _build_play_blurb(play: Dict[str, Any], *, reason: Optional[str] = None) -> PlayBlurb:
    return PlayBlurb(
        quarter=(play.get("period") or {}).get("number"),
        clock=((play.get("clock") or {}).get("displayValue") or ""),
        play_type=((play.get("type") or {}).get("text") or "Unknown"),
        text=(play.get("text") or ""),
        yards=_parse_int(play.get("statYardage")),
        reason=reason,
    )


def analyze_reconciliation_clues(
    raw_data: Dict[str, Any],
    details: Dict[str, Any],
) -> Tuple[Dict[str, List[PlayBlurb]], Dict[str, List[PlayBlurb]], Dict[str, List[PlayBlurb]]]:
    id_to_abbr, _abbr_to_id = _team_id_maps(raw_data)
    drives = (raw_data.get("drives", {}) or {}).get("previous", []) or []

    team_abbrs = sorted(set(id_to_abbr.values()))
    turnover_keywords = ("interception", "intercept", "fumble", "muffed", "blocked", "onside")

    # 1) Windelta turnover plays (from expanded details)
    turnover_plays_by_team: Dict[str, List[PlayBlurb]] = {abbr: [] for abbr in team_abbrs}
    for tid, cats in (details or {}).items():
        abbr = id_to_abbr.get(str(tid))
        if not abbr:
            continue
        for to_play in (cats or {}).get("Turnovers", []) or []:
            turnover_plays_by_team.setdefault(abbr, []).append(
                PlayBlurb(
                    quarter=to_play.get("quarter"),
                    clock=to_play.get("clock") or "",
                    play_type=to_play.get("type") or "Turnover",
                    text=to_play.get("text") or "",
                    yards=_parse_int(to_play.get("yards")),
                    reason=to_play.get("reason"),
                )
            )

    # Build a coarse "already tracked" set by (quarter, clock, final_play_text).
    tracked_keys = set()
    for plays in turnover_plays_by_team.values():
        for p in plays:
            tracked_keys.add((p.quarter, p.clock, final_play_text(p.text).strip().lower()))

    # 2) Potential turnover keyword plays not counted by windelta
    potential_turnover_keyword_plays: Dict[str, List[PlayBlurb]] = {abbr: [] for abbr in team_abbrs}
    # 3) Excluded non-zero yardage plays (classification mismatch candidates)
    excluded_yardage_plays: Dict[str, List[PlayBlurb]] = {abbr: [] for abbr in team_abbrs}

    opponent_id_by_team: Dict[str, Optional[str]] = {}
    if len(id_to_abbr) == 2:
        tids = list(id_to_abbr.keys())
        opponent_id_by_team[tids[0]] = tids[1]
        opponent_id_by_team[tids[1]] = tids[0]

    for drive in drives:
        drive_team_id = str(((drive.get("team") or {}).get("id") or "")).strip()
        drive_team_abbr = id_to_abbr.get(drive_team_id, "")
        opponent_id = opponent_id_by_team.get(drive_team_id)
        opponent_abbr = id_to_abbr.get(opponent_id, "") if opponent_id else ""

        for play in (drive.get("plays") or []):
            text = play.get("text") or ""
            text_final_lower = final_play_text(text).strip().lower()
            type_text = ((play.get("type") or {}).get("text") or "")
            type_lower = type_text.lower()

            # Attribute return plays to the receiving team (opponent) when it's clear.
            play_abbr = drive_team_abbr
            if ("kickoff" in type_lower or "punt" in type_lower) and "return" in type_lower and opponent_abbr:
                play_abbr = opponent_abbr

            if not play_abbr:
                continue

            # Potential missed turnovers: keyword plays not in windelta's counted turnover list.
            if any(k in text_final_lower for k in turnover_keywords) or any(k in type_lower for k in turnover_keywords):
                key = ((play.get("period") or {}).get("number"), ((play.get("clock") or {}).get("displayValue") or ""), text_final_lower)
                if key not in tracked_keys:
                    potential_turnover_keyword_plays.setdefault(play_abbr, []).append(_build_play_blurb(play))

            # Excluded plays with non-zero yards: useful for yards reconciliation.
            yards = _parse_int(play.get("statYardage")) or 0
            if yards != 0:
                is_offense, is_run, is_pass = classify_offense_play(play)
                if not (is_offense and (is_run or is_pass)):
                    reason = _detect_exclusion_reason(play)
                    if reason and reason != "marker":
                        excluded_yardage_plays.setdefault(play_abbr, []).append(_build_play_blurb(play, reason=reason))

    # Keep output focused: sort by quarter/clock as strings.
    def sort_key(p: PlayBlurb) -> Tuple[int, str]:
        q = p.quarter if isinstance(p.quarter, int) else 99
        return q, p.clock or ""

    for d in (turnover_plays_by_team, potential_turnover_keyword_plays, excluded_yardage_plays):
        for abbr in list(d.keys()):
            d[abbr] = sorted(d[abbr], key=sort_key)[:25]

    return turnover_plays_by_team, potential_turnover_keyword_plays, excluded_yardage_plays


def build_season_recon(
    game_ids: Iterable[str],
    *,
    source: str,
    cache_dir: Path,
    cache_write: bool,
    espn_stats_cache: Optional[Dict[str, Any]] = None,
) -> Tuple[List[GameRecon], List[str]]:
    recon: List[GameRecon] = []
    failures: List[str] = []
    if espn_stats_cache is None:
        espn_stats_cache = {}

    for game_id in game_ids:
        try:
            raw_data, raw_source = load_raw_game_data(game_id, source=source, cache_dir=cache_dir)
            if raw_source == "network" and cache_write:
                cache_dir.mkdir(parents=True, exist_ok=True)
                (cache_dir / f"{game_id}.json").write_text(json.dumps(raw_data))

            cached = espn_stats_cache.get(game_id)
            if isinstance(cached, dict) and isinstance(cached.get("espn_stats"), dict) and isinstance(cached.get("meta"), dict):
                espn_stats = cached["espn_stats"]
                meta = cached["meta"]
            else:
                espn_stats, meta = extract_espn_official_team_stats(raw_data)
                espn_stats_cache[game_id] = {"espn_stats": espn_stats, "meta": meta}
            away = meta.get("away") or ""
            home = meta.get("home") or ""
            if not (away and home):
                raise ValueError("Missing away/home team abbreviations in payload")

            stats_rows, details = process_game_stats(
                raw_data,
                expanded=True,
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

            def team_line(team: str, home_away: str, opponent: str) -> TeamLine:
                e = espn_stats.get(team, {})
                w = windelta_stats.get(team, {})
                e_y = e.get("Total Yards")
                w_y = w.get("Total Yards")
                e_to = e.get("Turnovers")
                w_to = w.get("Turnovers")
                e_py = e.get("Penalty Yards")
                w_py = w.get("Penalty Yards")
                return TeamLine(
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

            away_line = team_line(away, "away", home)
            home_line = team_line(home, "home", away)

            turnover_plays_by_team, potential_keyword, excluded_yards = analyze_reconciliation_clues(raw_data, details)

            recon.append(
                GameRecon(
                    game_id=game_id,
                    away=away,
                    home=home,
                    raw_source=raw_source,
                    team_lines=(away_line, home_line),
                    turnover_plays_by_team=turnover_plays_by_team,
                    potential_turnover_keyword_plays=potential_keyword,
                    excluded_yardage_plays=excluded_yards,
                )
            )
        except Exception as exc:
            failures.append(f"{game_id}: {exc}")

    return recon, failures


def write_team_csv(path: Path, recon: Sequence[GameRecon]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for g in recon:
        for line in g.team_lines:
            rows.append(
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

    # Avoid importing csv in hot paths; output is small enough for JSON->CSV style.
    import csv

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)


def write_game_priority_csv(path: Path, recon: Sequence[GameRecon]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "game_id",
                "away",
                "home",
                "max_abs_turnovers_delta",
                "max_abs_yards_delta",
                "raw_source",
                "status",
            ],
        )
        writer.writeheader()
        for g in sorted(recon, key=lambda x: x.priority_key()):
            writer.writerow(
                {
                    "game_id": g.game_id,
                    "away": g.away,
                    "home": g.home,
                    "max_abs_turnovers_delta": g.max_abs_turnovers_delta,
                    "max_abs_yards_delta": g.max_abs_yards_delta,
                    "raw_source": g.raw_source,
                    "status": "MISMATCH" if g.any_mismatch else "MATCH",
                }
            )


def _fmt_val(val: Optional[int]) -> str:
    return "N/A" if val is None else str(val)


def _fmt_delta(delta: Optional[int]) -> str:
    return "N/A" if delta is None else f"{delta:+d}"


def write_markdown_report(path: Path, recon: Sequence[GameRecon], failures: Sequence[str], *, season: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    mismatches = [g for g in recon if g.any_mismatch]
    mismatch_turnovers = [g for g in mismatches if g.max_abs_turnovers_delta != 0]
    mismatch_yards = [g for g in mismatches if g.max_abs_yards_delta != 0]
    mismatch_penalties = [
        g for g in mismatches if any((l.penalty_yards_delta or 0) != 0 for l in g.team_lines)
    ]

    # Heuristic "issue buckets"
    turnover_keyword_hits = 0
    excluded_yardage_hits = 0
    for g in mismatches:
        for plays in g.potential_turnover_keyword_plays.values():
            turnover_keyword_hits += len(plays)
        for plays in g.excluded_yardage_plays.values():
            excluded_yardage_hits += len(plays)

    lines: List[str] = []
    lines.append(f"# Season {season} Reconciliation Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Games analyzed: {len(recon)}")
    lines.append(f"- Mismatch games: {len(mismatches)}")
    lines.append(f"- Games with turnover mismatches: {len(mismatch_turnovers)}")
    lines.append(f"- Games with yards mismatches: {len(mismatch_yards)}")
    lines.append(f"- Games with penalty-yards mismatches: {len(mismatch_penalties)}")
    if failures:
        lines.append(f"- Fetch/process failures: {len(failures)}")
    lines.append("")
    lines.append("## Priority Sort")
    lines.append("Sorted by `max(|turnovers_delta|) desc`, then `max(|yards_delta|) desc` per game.")
    lines.append("")
    lines.append("## Suggested Reconciliation Work Items (Heuristic)")
    lines.append(
        "- Turnover deltas: review turnover classification (muffed kicks, onside recoveries, replay reversals)."
    )
    lines.append(
        "- Yards deltas: review how yards are attributed on turnover plays (interceptions/fumbles with returns) vs offensive yards."
    )
    lines.append("- Penalty deltas: review how penalties are attributed (defensive/offensive, accepted vs no-play).")
    lines.append(
        "- Excluded plays with non-zero yards can indicate classification mismatches (penalty/no-play, special teams returns)."
    )
    lines.append("")
    lines.append("Heuristic counts across mismatch games:")
    lines.append(f"- Potential missed turnover-keyword plays (not counted by windelta): {turnover_keyword_hits}")
    lines.append(f"- Excluded non-zero-yard plays (not counted as offense by windelta): {excluded_yardage_hits}")
    lines.append("")

    lines.append("## Games (Prioritized)")
    for g in sorted(recon, key=lambda x: x.priority_key()):
        away_line, home_line = g.team_lines
        if not g.any_mismatch:
            continue
        lines.append("")
        lines.append(
            f"### {g.game_id} {g.away} @ {g.home} "
            f"(TOΔ max {g.max_abs_turnovers_delta}, YdsΔ max {g.max_abs_yards_delta}, raw={g.raw_source})"
        )
        lines.append("")
        lines.append("| Team | ESPN Yds | windelta Yds | Δ | ESPN TO | windelta TO | Δ | ESPN PenYds | windelta PenYds | Δ |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

        def row(line: TeamLine) -> str:
            return (
                f"| {line.team} | {_fmt_val(line.espn_total_yards)} | {_fmt_val(line.windelta_total_yards)}"
                f" | {_fmt_delta(line.yards_delta)} | {_fmt_val(line.espn_turnovers)} | {_fmt_val(line.windelta_turnovers)}"
                f" | {_fmt_delta(line.turnovers_delta)} | {_fmt_val(line.espn_penalty_yards)} | {_fmt_val(line.windelta_penalty_yards)}"
                f" | {_fmt_delta(line.penalty_yards_delta)} |"
            )

        lines.append(row(away_line))
        lines.append(row(home_line))

        # Keep per-game details compact but actionable.
        for team in (g.away, g.home):
            to_plays = g.turnover_plays_by_team.get(team) or []
            kw_plays = g.potential_turnover_keyword_plays.get(team) or []
            ex_plays = g.excluded_yardage_plays.get(team) or []

            if not to_plays and not kw_plays and not ex_plays:
                continue

            lines.append("")
            lines.append(f"**{team} Reconciliation Clues**")

            if to_plays:
                lines.append("")
                lines.append(f"- Windelta counted turnovers ({len(to_plays)}):")
                for p in to_plays:
                    lines.append(p.format_line())

            if kw_plays:
                lines.append("")
                lines.append(f"- Turnover-keyword plays not counted as turnovers (up to {len(kw_plays)} shown):")
                for p in kw_plays:
                    lines.append(p.format_line())

            if ex_plays:
                lines.append("")
                lines.append(f"- Excluded non-zero-yard plays (up to {len(ex_plays)} shown):")
                for p in ex_plays:
                    lines.append(p.format_line())

    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    path.write_text("\n".join(lines).rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a season-wide reconciliation report (game IDs + yards/turnovers deltas + prioritized markdown)."
    )
    parser.add_argument("--season", type=int, default=2025, help="Season year (default: 2025).")
    parser.add_argument(
        "--season-types",
        default="2,3",
        help="Comma-separated season types to include (1=pre, 2=regular, 3=post). Default: 2,3",
    )
    parser.add_argument(
        "--max-week",
        type=int,
        default=None,
        help="Max regular-season week to include (season_type=2 only). Example: --max-week 12",
    )
    parser.add_argument(
        "--ids-input",
        default=None,
        help="Optional path to a game IDs file; if provided, skips fetching IDs from ESPN schedule endpoints.",
    )
    parser.add_argument(
        "--out-ids",
        default=None,
        help="Output txt path for game IDs.",
    )
    parser.add_argument(
        "--out-team-csv",
        default=None,
        help="Output CSV path for per-team rows.",
    )
    parser.add_argument(
        "--out-game-csv",
        default=None,
        help="Output CSV path for per-game priority rows.",
    )
    parser.add_argument(
        "--out-md",
        default=None,
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--write-recommendations",
        action="store_true",
        help="Also write an auto-generated logic recommendations markdown report based on remaining mismatches.",
    )
    parser.add_argument(
        "--out-recommendations",
        default=None,
        help="Output path for logic recommendations markdown (used with --write-recommendations).",
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
        "--cache-write",
        action="store_true",
        help="When fetching from network, write raw ESPN summary payloads to --cache-dir (so you can re-run with --source cache).",
    )
    parser.add_argument(
        "--espn-stats-cache",
        default=None,
        help="Optional JSON file to persist extracted ESPN official team stats (used to avoid re-parsing when iterating).",
    )
    args = parser.parse_args()

    try:
        season_types = [int(x.strip()) for x in args.season_types.split(",") if x.strip()]
    except ValueError:
        print(f"Invalid --season-types: {args.season_types}", file=sys.stderr)
        return 2

    if args.ids_input:
        input_path = (REPO_ROOT / args.ids_input).resolve() if not os.path.isabs(args.ids_input) else Path(args.ids_input)
        game_ids = load_game_ids(input_path)
        if not game_ids:
            print(f"No game IDs found in {input_path}", file=sys.stderr)
            return 2
    else:
        try:
            game_ids = fetch_season_game_ids(args.season, season_types=season_types, max_week=args.max_week)
        except Exception as exc:
            print(f"Failed to fetch season game IDs: {exc}", file=sys.stderr)
            return 1

    out_ids = Path(args.out_ids or os.path.join("audits", f"season_{args.season}_game_ids.txt"))
    write_game_ids_txt(out_ids, game_ids)
    print(f"Wrote {len(game_ids)} game IDs to {out_ids}")

    espn_stats_cache_path = Path(args.espn_stats_cache) if args.espn_stats_cache else None
    if not espn_stats_cache_path:
        espn_stats_cache_path = Path(os.path.join("audits", f"season_{args.season}_espn_official_stats.json"))
    espn_stats_cache: Dict[str, Any] = {}
    if espn_stats_cache_path.exists():
        try:
            espn_stats_cache = json.loads(espn_stats_cache_path.read_text())
        except Exception:
            espn_stats_cache = {}

    cache_dir = (REPO_ROOT / args.cache_dir).resolve() if not os.path.isabs(args.cache_dir) else Path(args.cache_dir)
    recon, failures = build_season_recon(
        game_ids,
        source=args.source,
        cache_dir=cache_dir,
        cache_write=args.cache_write,
        espn_stats_cache=espn_stats_cache,
    )

    try:
        espn_stats_cache_path.parent.mkdir(parents=True, exist_ok=True)
        espn_stats_cache_path.write_text(json.dumps(espn_stats_cache, indent=2))
    except Exception:
        pass

    # Sort for outputs.
    recon_sorted = sorted(recon, key=lambda x: x.priority_key())

    out_team_csv = Path(args.out_team_csv or os.path.join("audits", f"season_{args.season}_team_comparison.csv"))
    out_game_csv = Path(args.out_game_csv or os.path.join("audits", f"season_{args.season}_game_priority.csv"))
    out_md = Path(args.out_md or os.path.join("audits", f"season_{args.season}_reconciliation.md"))

    write_team_csv(out_team_csv, recon_sorted)
    write_game_priority_csv(out_game_csv, recon_sorted)
    write_markdown_report(out_md, recon_sorted, failures, season=args.season)

    mismatch_games = len([g for g in recon_sorted if g.any_mismatch])
    print(
        textwrap.dedent(
            f"""
            Wrote:
              - Team rows: {out_team_csv}
              - Game priority: {out_game_csv}
              - Markdown report: {out_md}
            Summary:
              - Games analyzed: {len(recon_sorted)}
              - Mismatch games: {mismatch_games}
              - Failures: {len(failures)}
            """
        ).strip()
    )
    print_aggregate_report(recon_sorted)

    if args.write_recommendations:
        out_recs = Path(
            args.out_recommendations or os.path.join("audits", f"season_{args.season}_logic_recommendations.md")
        )
        write_logic_recommendations(out_recs, recon_sorted, season=args.season, cache_dir=cache_dir)
        print(f"Wrote logic recommendations: {out_recs}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
