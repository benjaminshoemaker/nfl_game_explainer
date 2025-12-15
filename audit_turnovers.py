import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any

import game_compare


def load_game_ids(args: argparse.Namespace) -> List[str]:
    ids: List[str] = []
    if args.game_ids:
        ids.extend(args.game_ids)
    file_inputs = [args.file, args.sample_file]
    for file_path in file_inputs:
        if not file_path:
            continue
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                ids.append(line.split(",")[0])
    # De-dup while preserving order
    seen = set()
    uniq_ids = []
    for gid in ids:
        if gid not in seen:
            uniq_ids.append(gid)
            seen.add(gid)
    if args.max_games:
        uniq_ids = uniq_ids[: args.max_games]
    return uniq_ids


def classify_turnover_events(
    play: Dict[str, Any], id_to_abbr: Dict[str, str], drive_team_id: str
) -> List[Tuple[str, str]]:
    """
    Approximate the turnover detection logic in game_compare and return a list of
    (team_id, reason) events. Supports multiple turnovers in one play.
    """
    text = play.get("text", "")
    text_lower = text.lower()
    play_type_lower = play.get("type", {}).get("text", "unknown").lower()
    start_team_id = play.get("start", {}).get("team", {}).get("id") or drive_team_id
    end_team_id = play.get("end", {}).get("team", {}).get("id")
    team_abbrev = play.get("team", {}).get("abbreviation", "").lower()
    offense_abbrev = team_abbrev or id_to_abbr.get(drive_team_id, "").lower()
    opponent_id = None
    if len(id_to_abbr) == 2 and start_team_id in id_to_abbr:
        opponent_id = next((tid for tid in id_to_abbr if tid != start_team_id), None)

    muffed_punt = "muffed punt" in text_lower or "muff" in play_type_lower
    muffed_kick = (
        muffed_punt
        or ("muffed kick" in text_lower)
        or ("muffed kickoff" in text_lower)
        or ("muff" in text_lower and "kickoff" in text_lower)
    )
    interception = "interception" in play_type_lower or "intercept" in text_lower
    fumble_phrase = "fumble" in text_lower
    overturned = "reversed" in text_lower or "overturned" in text_lower

    events: List[Tuple[str, str]] = []
    current_possessor = start_team_id
    current_off_abbr = offense_abbrev

    if muffed_kick and opponent_id:
        current_possessor = opponent_id
        current_off_abbr = id_to_abbr.get(opponent_id, "").lower()

    if interception and not overturned:
        events.append((current_possessor, "interception"))
        if opponent_id:
            current_possessor = opponent_id
            current_off_abbr = id_to_abbr.get(opponent_id, "").lower()

    recovered_by_def = False
    recovered_team_id = None
    if fumble_phrase:
        if "recovered by" in text_lower:
            if current_off_abbr:
                recovered_by_def = f"recovered by {current_off_abbr}" not in text_lower
            elif "fumble recovery (own)" in play_type_lower:
                recovered_by_def = False
            else:
                recovered_by_def = True
        elif "fumble recovery (own)" in play_type_lower:
            recovered_by_def = False
        if start_team_id and end_team_id and start_team_id != end_team_id:
            recovered_by_def = current_possessor != end_team_id
            recovered_team_id = end_team_id
        elif end_team_id:
            recovered_team_id = end_team_id

    fumble_turnover = fumble_phrase and recovered_by_def and not overturned
    if fumble_turnover and not muffed_kick:
        events.append((current_possessor, "fumble"))
        if recovered_team_id:
            current_possessor = recovered_team_id
            current_off_abbr = id_to_abbr.get(current_possessor, "").lower()

    if muffed_kick and not overturned:
        events.append((current_possessor, "muffed_kick"))
        if end_team_id:
            current_possessor = end_team_id

    if not overturned and "onside" in text_lower and "kick" in text_lower and opponent_id:
        if end_team_id == start_team_id:
            events.append((opponent_id, "onside_recovery"))
            current_possessor = start_team_id

    if (
        not overturned
        and "blocked" in text_lower
        and ("punt" in play_type_lower or "field goal" in play_type_lower or "fg" in play_type_lower)
    ):
        if start_team_id and end_team_id and start_team_id != end_team_id:
            events.append((start_team_id, "blocked_kick"))
            current_possessor = end_team_id

    if overturned:
        # Explicit marker for audit visibility.
        events.append((start_team_id or drive_team_id, "overturned"))

    return events


def audit_game(game_id: str, out_dir: Path) -> Dict[str, Any]:
    data = game_compare.get_game_data(game_id)

    # Persist raw play-by-play for manual inspection.
    out_dir.mkdir(parents=True, exist_ok=True)
    pbp_path = out_dir / f"{game_id}.json"
    with pbp_path.open("w") as f:
        json.dump(data, f, indent=2)

    # Build team id -> abbreviation map for fallback usage.
    id_to_abbr: Dict[str, str] = {}
    for team in data.get("boxscore", {}).get("teams", []):
        tid = team.get("team", {}).get("id")
        abbr = team.get("team", {}).get("abbreviation")
        if tid and abbr:
            id_to_abbr[tid] = abbr

    turnovers: Dict[str, List[Dict[str, Any]]] = {}

    drives = data.get("drives", {}).get("previous", [])
    for drive in drives:
        team_id = drive.get("team", {}).get("id")
        if not team_id:
            continue
        team_abbrev = id_to_abbr.get(team_id, "").lower()

        for play in drive.get("plays", []):
            text_lower = play.get("text", "").lower()
            play_type_lower = play.get("type", {}).get("text", "unknown").lower()

            # Skip non-plays consistent with main processing.
            if "timeout" in play_type_lower or "end of" in play_type_lower:
                continue
            if game_compare.is_nullified_play(text_lower):
                continue

            events = classify_turnover_events(play, id_to_abbr, team_id)
            for t_event, reason in events:
                turnovers.setdefault(t_event, []).append(
                    {
                        "reason": reason,
                        "text": play.get("text", ""),
                        "clock": play.get("clock", {}).get("displayValue"),
                        "quarter": play.get("period", {}).get("number"),
                        "down_dist": play.get("start", {}).get("downDistanceText")
                        or play.get("start", {}).get("shortDownDistanceText"),
                        "type": play.get("type", {}).get("text"),
                    }
                )

    return {
        "gameId": game_id,
        "turnovers": turnovers,
        "pbp_path": str(pbp_path),
        "teams": id_to_abbr,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch games, cache play-by-play, and audit turnover classification."
    )
    parser.add_argument(
        "--game-ids",
        nargs="+",
        help="ESPN game IDs to audit (space separated).",
    )
    parser.add_argument(
        "--file",
        help="File containing game IDs (one per line or CSV; first column is used).",
    )
    parser.add_argument(
        "--sample-file",
        default="sample_games.txt",
        help="Convenience flag to read IDs from sample_games.txt (or provide a path).",
    )
    parser.add_argument(
        "--max-games", type=int, help="Limit the number of games to process."
    )
    parser.add_argument(
        "--out-dir",
        default="pbp_cache",
        help="Directory to store raw play-by-play JSON files.",
    )

    args = parser.parse_args()
    game_ids = load_game_ids(args)
    if not game_ids:
        raise SystemExit("No game IDs provided. Use --game-ids or --file.")

    out_dir = Path(args.out_dir)
    results = []
    for gid in game_ids:
        print(f"Fetching {gid} ...")
        try:
            results.append(audit_game(gid, out_dir))
        except Exception as exc:
            print(f"  !! Failed to audit {gid}: {exc}")

    print("\n=== TURNOVER AUDIT ===")
    for res in results:
        teams = res["teams"]
        if not res["turnovers"]:
            print(f"{res['gameId']}: no turnovers detected")
            continue
        print(f"{res['gameId']} (pbp cached at {res['pbp_path']}):")
        for tid, plays in res["turnovers"].items():
            label = teams.get(tid, tid)
            print(f"  {label}: {len(plays)} turnovers")
            for p in plays:
                prefix = f"    Q{p.get('quarter')} {p.get('clock')} | {p.get('down_dist')}"
                print(f"{prefix} | {p.get('reason')} | {p.get('type')}: {p.get('text')}")
        print()


if __name__ == "__main__":
    main()
