# NFL category explorer prototype

Serve this directory and open `nfl-category-explorer.html` to review the standalone game design:

```bash
python3 -m http.server 8765 --directory prototypes
```

The JSON is a local snapshot for ESPN game `401872955` (Seattle at Washington, Week 3, 2026). The play browser has three replay checkpoints: early game, the Q4 3:57 pick-six, and final. The middle checkpoint reconstructs the 12 started games from archived ESPN feeds through `2026-09-27T20:08:43Z`; the pick-six ranks provisionally #4 of 1,411 eligible plays at that moment. Across all 16 final games it ranks #6 of 2,352 eligible plays. These are retrospective snapshots for the prototype, not a live data connection.

A play with a WP swing of at least 25 percentage points can show historical rarity immediately. The reference is 215 complete 2025 regular-season game snapshots (Weeks 1–15): 91 of 30,866 eligible plays met the threshold. A weekly rank replaces that label only when the week snapshot has complete coverage; the prototype falls back to historical rarity when ranks are unavailable. EPA is available for 168 of the 197 displayed source plays.

Run the focused checks with `node --test prototypes/nfl-category-explorer.test.cjs`.
