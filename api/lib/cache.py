"""
Caching layer for game analysis payloads.

This module is used by `api/lib/game_analysis.py` to cache completed games so the
web app can load quickly without re-fetching ESPN on every request.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


CACHE_VERSION = "1.3"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
COMPLETION_DELAY_MINUTES = 30


class RedisClient:
    def __init__(self) -> None:
        self.redis_url = os.environ.get("REDIS_URL")
        self.enabled = bool(self.redis_url)
        self._client = None

    def _get_client(self):
        if self._client is None and self.enabled:
            try:
                import redis  # type: ignore

                self._client = redis.from_url(self.redis_url, decode_responses=True)
            except Exception:
                self.enabled = False
        return self._client

    def get(self, key: str) -> Optional[Dict]:
        client = self._get_client()
        if not client:
            return None
        raw = client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            client.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            return False

    def mget(self, keys: List[str]) -> Dict[str, Any]:
        client = self._get_client()
        if not client or not keys:
            return {}
        try:
            raws = client.mget(keys)
            out: Dict[str, Any] = {}
            for i, k in enumerate(keys):
                raw = raws[i]
                if not raw:
                    out[k] = None
                    continue
                try:
                    out[k] = json.loads(raw)
                except Exception:
                    out[k] = None
            return out
        except Exception:
            return {}

    def mset(self, items: Dict[str, Any], ttl: int = CACHE_TTL_SECONDS) -> bool:
        client = self._get_client()
        if not client or not items:
            return False
        try:
            pipe = client.pipeline()
            for k, v in items.items():
                pipe.setex(k, ttl, json.dumps(v))
            pipe.execute()
            return True
        except Exception:
            return False


class LocalFileCache:
    def __init__(self) -> None:
        self.cache_dir = "/tmp/nfl_kv_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

    def _key_to_path(self, key: str) -> str:
        safe = key.replace(":", "_").replace("/", "_")
        return os.path.join(self.cache_dir, f"{safe}.json")

    def get(self, key: str) -> Optional[Dict]:
        path = self._key_to_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            cached_at = data.get("_cached_at")
            ttl = data.get("_ttl", CACHE_TTL_SECONDS)
            if cached_at:
                cached_dt = datetime.fromisoformat(cached_at)
                if datetime.now() - cached_dt > timedelta(seconds=int(ttl)):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                    return None
            return data.get("_value")
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> bool:
        path = self._key_to_path(key)
        try:
            with open(path, "w") as f:
                json.dump({"_value": value, "_cached_at": datetime.now().isoformat(), "_ttl": ttl}, f)
            return True
        except Exception:
            return False

    def mget(self, keys: List[str]) -> Dict[str, Any]:
        return {k: self.get(k) for k in keys}

    def mset(self, items: Dict[str, Any], ttl: int = CACHE_TTL_SECONDS) -> bool:
        ok = True
        for k, v in items.items():
            ok = self.set(k, v, ttl) and ok
        return ok


def _get_cache_client():
    if os.environ.get("REDIS_URL"):
        return RedisClient()
    return LocalFileCache()


_cache = _get_cache_client()


def get_cached_game(game_id: str) -> Optional[Tuple[Dict, Dict, Dict]]:
    keys = [
        f"nfl:game:{game_id}:meta",
        f"nfl:game:{game_id}:stats",
        f"nfl:game:{game_id}:plays",
    ]
    values = _cache.mget(keys)
    meta = values.get(keys[0])
    stats = values.get(keys[1])
    plays = values.get(keys[2])
    if not meta or not stats or not plays:
        return None
    if meta.get("cache_version") != CACHE_VERSION:
        return None
    if meta.get("status") != "final":
        return None
    return meta, stats, plays


def should_cache_game(is_final: bool, last_play_time: Optional[str]) -> bool:
    if not is_final:
        return False
    if not last_play_time:
        return True
    try:
        ts = last_play_time.replace("Z", "+00:00")
        completion_dt = datetime.fromisoformat(ts)
        if completion_dt.tzinfo is None:
            completion_dt = completion_dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - completion_dt) > timedelta(minutes=COMPLETION_DELAY_MINUTES)
    except Exception:
        return True


def cache_game(game_id: str, meta: Dict, stats: Dict, plays: Dict) -> bool:
    items = {
        f"nfl:game:{game_id}:meta": meta,
        f"nfl:game:{game_id}:stats": stats,
        f"nfl:game:{game_id}:plays": plays,
    }
    return bool(_cache.mset(items, ttl=CACHE_TTL_SECONDS))


def build_cache_meta(
    game_id: str,
    team_meta: List[Dict[str, Any]],
    stats_rows: List[Dict[str, Any]],
    wp_threshold: float,
    last_play_time: Optional[str],
    *,
    week_number: int = 0,
    season_type: int = 2,
) -> Dict[str, Any]:
    home = next((t for t in team_meta if t.get("homeAway") == "home"), {}) or {}
    away = next((t for t in team_meta if t.get("homeAway") == "away"), {}) or {}
    return {
        "cache_version": CACHE_VERSION,
        "status": "final",
        "game_id": game_id,
        "completion_time": last_play_time,
        "wp_threshold": wp_threshold,
        "week": {"number": week_number, "seasonType": season_type},
        "home_team": {"id": home.get("id"), "abbr": home.get("abbr"), "name": home.get("name")},
        "away_team": {"id": away.get("id"), "abbr": away.get("abbr"), "name": away.get("name")},
        "team_meta": team_meta,
    }


def build_cache_stats(stats_rows: List[Dict[str, Any]], _team_meta: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"rows": stats_rows}


def build_cache_plays(raw_data: Dict, probability_map: Dict, pregame_probabilities: Tuple[float, float]) -> Dict[str, Any]:
    from .nfl_core import calculate_success, classify_offense_play, final_play_text

    drives = raw_data.get("drives", {}).get("previous", []) or []
    pregame_home_wp, pregame_away_wp = pregame_probabilities

    teams_info = (raw_data.get("boxscore", {}) or {}).get("teams", []) or []
    id_to_abbr: Dict[str, str] = {}
    for t in teams_info:
        tid = (t.get("team") or {}).get("id")
        abbr = (t.get("team") or {}).get("abbreviation")
        if tid and abbr:
            id_to_abbr[str(tid)] = abbr

    prev_home_wp = pregame_home_wp
    prev_away_wp = pregame_away_wp
    plays_list: List[Dict[str, Any]] = []
    drive_starts: List[Dict[str, Any]] = []

    def normalize_abbr(abbr: str, *, known: set[str]) -> str:
        if not abbr:
            return ""
        a = abbr.upper()
        if a in known:
            return a
        aliases = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX"}
        mapped = aliases.get(a)
        if mapped and mapped in known:
            return mapped
        if len(a) == 2:
            matches = [k for k in known if k.startswith(a)]
            if len(matches) == 1:
                return matches[0]
        return a

    def is_drive_boundary_noise(play_obj: Dict[str, Any]) -> bool:
        ptype = ((play_obj.get("type") or {}) or {}).get("text", "") or ""
        ptype_lower = ptype.lower()
        txt = (play_obj.get("text") or "").lower()
        return ("timeout" in ptype_lower) or ("end of" in ptype_lower) or ("end of" in txt)

    def is_kick_or_punt_start(play_obj: Dict[str, Any]) -> bool:
        ptype = ((play_obj.get("type") or {}) or {}).get("text", "") or ""
        ptype_lower = ptype.lower()
        txt = (play_obj.get("text") or "").lower()
        return ("kickoff" in ptype_lower) or ("kickoff" in txt) or ("punt" in ptype_lower) or ("onside" in txt)

    known_abbrs = set(id_to_abbr.values())

    for drive_index, drive in enumerate(drives):
        drive_team_id = (drive.get("team") or {}).get("id")
        drive_team_abbr = id_to_abbr.get(str(drive_team_id), "")

        drive_plays = drive.get("plays", []) or []
        first_play = drive_plays[0] if drive_plays else None
        drive_start_yte = (drive.get("start") or {}).get("yardsToEndzone", -1)
        drive_start_text = (drive.get("start") or {}).get("text")
        if not isinstance(drive_start_text, str) or not drive_start_text.strip():
            drive_start_text = None

        drive_start_home_wp = prev_home_wp
        drive_start_away_wp = prev_away_wp

        if first_play and drive_start_yte != -1:
            start_pos = drive_start_text
            if not start_pos and isinstance(drive_start_yte, (int, float)):
                start_pos = f"Own {int(100 - drive_start_yte)}"

            cause_play = None
            if is_kick_or_punt_start(first_play):
                cause_play = first_play
            elif drive_index > 0:
                prev_drive = drives[drive_index - 1] or {}
                prev_plays = prev_drive.get("plays", []) or []
                for cand in reversed(prev_plays):
                    if not is_drive_boundary_noise(cand):
                        cause_play = cand
                        break

            drive_starts.append(
                {
                    "drive_team": drive_team_abbr,
                    "quarter": first_play.get("period", {}).get("number"),
                    "clock": first_play.get("clock", {}).get("displayValue"),
                    "text": (cause_play.get("text", "") if cause_play else "Start of game")[:500],
                    "type": ((cause_play.get("type") or {}) or {}).get("text", "Drive Start") if cause_play else "Drive Start",
                    "start_pos": start_pos,
                    "end_pos": start_pos,
                    "start_home_wp": round(drive_start_home_wp, 4) if drive_start_home_wp is not None else None,
                    "start_away_wp": round(drive_start_away_wp, 4) if drive_start_away_wp is not None else None,
                }
            )

        for play in drive_plays:
            play_id = str(play.get("id", "") or "")
            if not play_id:
                continue

            start_home_wp = prev_home_wp
            start_away_wp = prev_away_wp

            prob = probability_map.get(play_id) or {}
            home_wp = prob.get("homeWinPercentage")
            away_wp = prob.get("awayWinPercentage")

            wp_delta = None
            if isinstance(home_wp, (int, float)):
                wp_delta = home_wp - prev_home_wp

            is_offense, is_run, is_pass = classify_offense_play(play)

            raw_text = play.get("text", "") or ""
            event_text = final_play_text(raw_text)
            event_text_lower = event_text.lower()

            is_two_point_conversion_attempt = (
                ("two-point" in event_text_lower)
                or ("2-point" in event_text_lower)
                or ("conversion attempt" in event_text_lower)
            )

            is_interception = (not is_two_point_conversion_attempt) and ("intercept" in event_text_lower)
            is_fumble_turnover = False
            if (not is_two_point_conversion_attempt) and ("fumble" in event_text_lower) and ("recovered by" in event_text_lower):
                m = re.search(r"recovered by\s+([a-z]{2,3})", event_text_lower, flags=re.IGNORECASE)
                recovered_abbr = normalize_abbr(m.group(1), known=known_abbrs) if m else ""
                offense_abbr = normalize_abbr(drive_team_abbr, known=known_abbrs)
                if recovered_abbr and offense_abbr:
                    is_fumble_turnover = recovered_abbr != offense_abbr
                else:
                    is_fumble_turnover = True

            is_turnover = bool(is_interception or is_fumble_turnover)

            yards = play.get("statYardage", 0) or 0
            down = (play.get("start") or {}).get("down", 1)
            distance = (play.get("start") or {}).get("distance", 10)
            is_successful = calculate_success(down, distance, yards) if is_offense else False

            plays_list.append(
                {
                    "play_id": play_id,
                    "quarter": (play.get("period") or {}).get("number"),
                    "clock": (play.get("clock") or {}).get("displayValue"),
                    "text": raw_text[:500],
                    "yards": yards,
                    "end_pos": ((play.get("end") or {}) or {}).get("possessionText") or ((play.get("end") or {}) or {}).get("downDistanceText"),
                    "start_home_wp": round(start_home_wp, 4) if start_home_wp is not None else None,
                    "start_away_wp": round(start_away_wp, 4) if start_away_wp is not None else None,
                    "home_wp": round(home_wp, 4) if isinstance(home_wp, (int, float)) else None,
                    "away_wp": round(away_wp, 4) if isinstance(away_wp, (int, float)) else None,
                    "wp_delta": round(wp_delta, 4) if isinstance(wp_delta, (int, float)) else None,
                    "is_offensive": is_offense,
                    "is_run": is_run,
                    "is_pass": is_pass,
                    "is_successful": is_successful,
                    "is_turnover": is_turnover,
                    "drive_team": drive_team_abbr,
                    "home_score": play.get("homeScore", 0),
                    "away_score": play.get("awayScore", 0),
                    "down": down,
                    "distance": distance,
                }
            )

            if isinstance(home_wp, (int, float)):
                prev_home_wp = home_wp
            if isinstance(away_wp, (int, float)):
                prev_away_wp = away_wp

    return {
        "pregame_home_wp": pregame_home_wp,
        "pregame_away_wp": pregame_away_wp,
        "drive_starts": drive_starts,
        "plays": plays_list,
        "play_count": len(plays_list),
    }


def _rebuild_expanded_details_from_cache(plays: Dict[str, Any], meta: Dict[str, Any], wp_threshold: float) -> Dict[str, Any]:
    home_team = meta.get("home_team") or {}
    away_team = meta.get("away_team") or {}
    home_team_id = str(home_team.get("id", "") or "")
    away_team_id = str(away_team.get("id", "") or "")
    home_abbr = home_team.get("abbr") or ""
    away_abbr = away_team.get("abbr") or ""

    abbr_to_id = {home_abbr: home_team_id, away_abbr: away_team_id}
    expanded: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        home_team_id: {
            "All Plays": [],
            "Turnovers": [],
            "Explosive Plays": [],
            "Non-Offensive Scores": [],
            "Points Per Trip (Inside 40)": [],
            "Drive Starts": [],
            "Penalty Yards": [],
            "Non-Offensive Points": [],
        },
        away_team_id: {
            "All Plays": [],
            "Turnovers": [],
            "Explosive Plays": [],
            "Non-Offensive Scores": [],
            "Points Per Trip (Inside 40)": [],
            "Drive Starts": [],
            "Penalty Yards": [],
            "Non-Offensive Points": [],
        },
    }

    plays_list = plays.get("plays", []) if plays else []
    prev_home_score = 0
    prev_away_score = 0

    for play in plays_list:
        drive_team = play.get("drive_team", "") or ""
        team_id = abbr_to_id.get(drive_team)
        if not team_id:
            continue

        quarter = play.get("quarter") or 0
        if isinstance(quarter, (int, float)) and int(quarter) >= 5:
            competitive = True
        else:
            sh = play.get("start_home_wp")
            sa = play.get("start_away_wp")
            if isinstance(sh, (int, float)) and isinstance(sa, (int, float)):
                competitive = sh < wp_threshold and sa < wp_threshold
            else:
                home_wp = play.get("home_wp")
                away_wp = play.get("away_wp")
                competitive = not (isinstance(home_wp, (int, float)) and home_wp >= wp_threshold) and not (
                    isinstance(away_wp, (int, float)) and away_wp >= wp_threshold
                )

        if not competitive:
            prev_home_score = play.get("home_score", prev_home_score)
            prev_away_score = play.get("away_score", prev_away_score)
            continue

        text = play.get("text", "") or ""
        text_lower = text.lower()
        yards = play.get("yards", 0)
        is_offensive = bool(play.get("is_offensive", False))
        is_run = bool(play.get("is_run", False))
        is_pass = bool(play.get("is_pass", False))
        is_turnover = bool(play.get("is_turnover", False))

        has_penalty = "penalty" in text_lower

        current_home = play.get("home_score", prev_home_score)
        current_away = play.get("away_score", prev_away_score)
        is_scoring = current_home != prev_home_score or current_away != prev_away_score
        points_scored = 0
        if is_scoring:
            if drive_team == home_abbr:
                points_scored = current_home - prev_home_score
            else:
                points_scored = current_away - prev_away_score

        probability = None
        home_wp = play.get("home_wp")
        away_wp = play.get("away_wp")
        if isinstance(home_wp, (int, float)) and isinstance(away_wp, (int, float)):
            wp_delta = play.get("wp_delta", 0) if isinstance(play.get("wp_delta"), (int, float)) else 0
            probability = {
                "homeWinPercentage": home_wp,
                "awayWinPercentage": away_wp,
                "homeDelta": wp_delta,
                "awayDelta": -wp_delta,
            }

        play_type = "Unknown"
        if is_run:
            play_type = "Run"
        elif is_pass:
            play_type = "Pass"
        elif is_turnover:
            play_type = "Turnover"
        elif has_penalty:
            play_type = "Penalty"

        is_meaningful = (is_offensive and (is_run or is_pass)) or is_scoring or is_turnover or has_penalty
        if is_meaningful:
            entry = {
                "type": play_type,
                "text": text,
                "yards": yards,
                "quarter": play.get("quarter"),
                "clock": play.get("clock"),
                "end_pos": play.get("end_pos"),
                "probability": probability,
            }
            if is_scoring and points_scored > 0:
                entry["points"] = points_scored
            expanded[team_id]["All Plays"].append(entry)

        if is_turnover:
            expanded[team_id]["Turnovers"].append(
                {
                    "type": play_type,
                    "text": text,
                    "yards": yards,
                    "quarter": play.get("quarter"),
                    "clock": play.get("clock"),
                    "end_pos": play.get("end_pos"),
                    "probability": probability,
                }
            )

        if is_offensive:
            is_explosive = (is_run and yards >= 10) or (is_pass and yards >= 20)
            if is_explosive:
                expanded[team_id]["Explosive Plays"].append(
                    {
                        "type": "Run" if is_run else "Pass",
                        "text": text,
                        "yards": yards,
                        "quarter": play.get("quarter"),
                        "clock": play.get("clock"),
                        "end_pos": play.get("end_pos"),
                        "probability": probability,
                    }
                )

        if has_penalty:
            expanded[team_id]["Penalty Yards"].append(
                {
                    "type": play_type,
                    "text": text,
                    "yards": yards,
                    "quarter": play.get("quarter"),
                    "clock": play.get("clock"),
                    "end_pos": play.get("end_pos"),
                    "probability": probability,
                }
            )

        prev_home_score = current_home
        prev_away_score = current_away

    for entry in plays.get("drive_starts", []) if plays else []:
        drive_team = entry.get("drive_team", "") or ""
        team_id = abbr_to_id.get(drive_team)
        if not team_id:
            continue

        quarter = entry.get("quarter") or 0
        if isinstance(quarter, (int, float)) and int(quarter) >= 5:
            competitive = True
        else:
            sh = entry.get("start_home_wp")
            sa = entry.get("start_away_wp")
            if isinstance(sh, (int, float)) and isinstance(sa, (int, float)):
                competitive = sh < wp_threshold and sa < wp_threshold
            else:
                competitive = True

        if not competitive:
            continue

        expanded[team_id]["Drive Starts"].append(
            {
                "type": entry.get("type") or "Drive Start",
                "text": entry.get("text") or "",
                "quarter": entry.get("quarter"),
                "clock": entry.get("clock"),
                "start_pos": entry.get("start_pos"),
                "end_pos": entry.get("end_pos") or entry.get("start_pos"),
            }
        )

    return expanded


def build_payload_from_cache(meta: Dict[str, Any], stats: Dict[str, Any], plays: Dict[str, Any], wp_threshold: float) -> Dict[str, Any]:
    from .nfl_core import build_analysis_text

    game_id = str(meta.get("game_id", "") or "")
    team_meta = meta.get("team_meta") or []
    rows = (stats.get("rows") or []) if isinstance(stats, dict) else []

    summary_cols = ["Team", "Score", "Total Yards", "Drives"]
    advanced_cols = [
        "Team",
        "Score",
        "Turnovers",
        "Total Yards",
        "Yards Per Play",
        "Success Rate",
        "Explosive Plays",
        "Explosive Play Rate",
        "Points Per Trip (Inside 40)",
        "Ave Start Field Pos",
        "Penalty Yards",
        "Non-Offensive Points",
    ]

    summary_table = [{k: r.get(k) for k in summary_cols} for r in rows]
    advanced_table = [{k: r.get(k) for k in advanced_cols} for r in rows]

    home = meta.get("home_team") or {}
    away = meta.get("away_team") or {}
    label = f"{away.get('abbr', 'AWAY')}_at_{home.get('abbr', 'HOME')}_{game_id}"

    expanded_details = _rebuild_expanded_details_from_cache(plays, meta, wp_threshold)
    expanded_details_full = _rebuild_expanded_details_from_cache(plays, meta, 1.0)

    payload: Dict[str, Any] = {
        "gameId": game_id,
        "label": label,
        "status": "final",
        "gameClock": None,
        "lastPlayTime": meta.get("completion_time"),
        "week": meta.get("week") or {"number": 0, "seasonType": 2},
        "wp_filter": {
            "enabled": True,
            "threshold": wp_threshold,
            "description": f"Stats reflect competitive plays only (WP < {wp_threshold * 100:.1f}%)",
        },
        "team_meta": team_meta,
        "summary_table": summary_table,
        "advanced_table": advanced_table,
        "summary_table_full": summary_table,
        "advanced_table_full": advanced_table,
        "expanded_details": expanded_details,
        "expanded_details_full": expanded_details_full,
        "from_cache": True,
    }

    payload["analysis"] = build_analysis_text(payload)
    return payload
