# NFL category explorer prototype

Serve this directory and open `nfl-category-explorer.html` to review the standalone game design:

```bash
python3 -m http.server 8765 --directory prototypes
```

The JSON is a local snapshot for ESPN game `401872955` (Seattle at Washington, Week 3, 2026). League WP ranks use the 16 final Week 3 ESPN win-probability sequences captured in `audits/`; 2,976 adjacent changes were measured. The cards only highlight a top-ten league-week rank. EPA is available for 168 of the 197 displayed source plays.

Run the focused checks with `node --test prototypes/nfl-category-explorer.test.cjs`.
