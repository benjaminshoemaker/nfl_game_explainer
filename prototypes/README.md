# NFL category explorer prototype

Serve this directory and open `nfl-category-explorer.html` to review the standalone game design:

```bash
python3 -m http.server 8765 --directory prototypes
```

Open `nfl-category-explorer-map-five.html` on the same server to review the
interactive duplicate with Map Five styling. It uses the same snapshot data and
controls as the original; its presentation overrides live in
`nfl-category-explorer-map-five.css`.

The JSON files are local snapshots for ESPN game `401872955` (Seattle at Washington, Week 3, 2026). `nfl-category-prototype-data.json` supplies plays and factor events; `play-card-context.json` supplies pre-play score, ball spot, and WP context for all 197 source plays. The play browser has three replay checkpoints: early game, the Q4 3:57 pick-six, and final. These are retrospective snapshots for the prototype, not a live data connection.

The same source-play card appears in factor lists, Most impactful plays, and All plays. Drive and trip facts stay outside the card. The older weekly WP-rank and rarity labels are withheld pending the separate backtest of the notable-play provider. EPA is available for 168 of the 197 displayed source plays.

Run the focused checks with `node --test prototypes/nfl-category-explorer.test.cjs`.
