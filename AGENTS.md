# AGENTS.md

Guidance for coding agents working in NFL Game Explainer. User-facing setup
and usage belong in `README.md`; metric definitions belong in
`documentation.txt` and `FAQ.txt`.

## Repository orientation

- `src/`: Next.js App Router dashboard.
- `api/`: Python serverless endpoints and shared analytics modules.
- `game_compare.py`: original command-line report generator.
- `tests/` and `src/**/*.test.*`: Python and frontend regression suites.
- `IMPLEMENTATION_PLAN.md`: historical build context, not a mandatory workflow.

## Working rules

- Keep Python and TypeScript implementations of shared metrics aligned.
- Treat scrambles and sacks as pass dropbacks, not runs.
- Detect turnovers consistently with the existing parsing rules.
- Never make real OpenAI or ESPN calls from unit tests; use mocks or fixtures.
- Preserve optional OpenAI behavior when `OPENAI_API_KEY` is absent.
- Do not disable functionality or tests to conceal failures.
- Update durable documentation when behavior or metric definitions change.

## Verification

Run checks proportionate to the change. For repository-wide changes, use:

```bash
.venv/bin/python -m pytest tests/ -q
npm run test
npm run typecheck
npm run lint
npm run build
```

Generated reports belong in `game_summaries/`, which is gitignored.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
