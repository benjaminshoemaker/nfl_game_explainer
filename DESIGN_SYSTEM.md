# Sunday edition design system

Sunday edition is the visual direction for the whole public site. Lead with the
game story, then let readers investigate the evidence. The interface should feel
like a clear sports publication: white reading surfaces, serif headlines, quiet
rules, and readable data. Avoid turning it into a wall of dashboard cards.

This guide is the shared design contract. It covers both the Next.js application
and the standalone team publication; they do **not** share a component library or
stylesheet. A change to one implementation does not automatically reach the other.
Keep this guide and both implementations aligned when changing shared conventions.
The original reskin proposals are historical explorations, not implementation specs.

## Where to work

| Surface | Implementation |
| --- | --- |
| Shared Next.js colors and type scale | `src/app/globals.css` |
| Next.js font loading and licensed font files | `src/app/layout.tsx`, `src/app/fonts/` |
| Games directory (`/`) | `src/app/Directory.module.css`, `src/components/GameCard.module.css`, `src/components/WeekPicker.tsx` |
| Game report (`/game/[gameId]`) | `src/components/GameExplorer.tsx`, `src/components/GameExplorer.module.css` |
| Game navigation and status controls | `src/components/GameSidebar.tsx`, its CSS module, and CSS modules in `src/app/game/[gameId]/` |
| Evidence charts and play cards | `src/components/FactorVisuals.tsx`, `src/components/CanonicalPlayCard.tsx` |
| How it works (`/how-it-works`) | `src/app/how-it-works/page.tsx` and its CSS module |
| Loading, error, and not-found states | `src/components/StateScreens.module.css` and the corresponding route components |
| Teams, team detail, power rankings, prediction results, team methodology | `prototypes/team-seasons.html` is the maintained HTML/CSS/JS template |
| Published team interface | `public/team-seasons.html`; route rewrites live in `next.config.mjs` |
| Team publication generation | `research/render_team_prototype.py`, `research/publish_team_site.py` |
| Standalone fonts and publication provenance | `public/fonts/`, `public/team-data/publication.json` |

The standalone routes are `/teams`, `/teams/:team`, `/power-rankings`,
`/prediction-results`, and `/team-methodology`. Their navigation also supports
hash routes within the same document. Include all five when reviewing a shared
site change; reviewing only Next.js pages misses them.

## Color and typography

Use semantic tokens in Next.js instead of new hardcoded equivalents. The
standalone template has its own variables: match these values and roles there.
Legacy `--mf-*` names in the app are compatibility aliases, not a separate teal theme.

| Role | Next.js token / value | Use |
| --- | --- | --- |
| Primary ink | `--text-primary`: `#17212a` | Headlines, reading text, strong rules |
| Secondary ink | `--text-secondary`, `--text-muted`: `#535d66` | Explanations and metadata; keep readable |
| Outer page | `--bg-deep`: `#eeefed` | Space outside the white reading surface |
| Reading surface | `--bg-card`: `#ffffff` | Main content, including team pages |
| Quiet evidence fill | `#f6f6f3` | Table headers and neutral supporting panels |
| Fine / strong rule | `--border-subtle`: `#d5d7d4`; `--border-medium`: `#acb0ac` | Rows and section boundaries |
| Editorial accent | `--editorial-accent`: `#9e3325` | Links, actions, selection, masthead slash |
| Accent fill | `--editorial-soft`: `#f5eeea` | Selected controls and explanatory notices |
| Away / home data | `--data-away`: `#205273`; `--data-home`: `#805f2b` | Consistent comparison colors in game evidence |

Source Serif 4, weight 700, is for the masthead, story headlines, section titles,
and prominent scores. Public Sans is for prose, controls, labels, and tables;
use its supplied 400, 600, and 800 weights. Load fonts locally, retain OFL license
files, and never reference a generated Next.js font URL from the standalone page.

| Element | Default treatment |
| --- | --- |
| Body | 16px; line height roughly 1.5–1.7; prose generally no wider than 75ch |
| Metadata | 13–14px; reserve smaller type for short labels, not explanations |
| Story headline | Roughly 32px on phones to 50px on wide report pages; serif, 1.1 line height, `-.025em` tracking |
| Section title | Roughly 28–30px; serif; clear space above |
| Masthead | 27px desktop, 23px phone; compact game navigation can use a smaller mark |
| Tables | Public Sans, usually 14–16px; tabular numerals; readable row labels |
| Eyebrow | Short, muted, uppercase label; about 14px, moderate tracking |

Use the existing `--type-*` and `--font-family-*` tokens where appropriate.
Report headlines use container-relative sizing; the reading guide can have a
larger hero. These are deliberate hierarchy differences, not reasons to invent
another type scale. Let long headlines wrap; do not ellipsize the story.

## Page and component patterns

- **Masthead:** `GAME/EXPLAINED`, ink lettering with the red slash and a 4px
  double ink rule below. Show one masthead per visible page composition. On mobile
  game pages the shell already provides it; the inner report keeps only week metadata.
- **Reading surface:** white, generally up to 1320px wide with 32px desktop and
  about 20px phone gutters. The prose-focused how-it-works page is intentionally
  narrower. Use whitespace and rules rather than shadows or rounded card stacks.
- **Story hierarchy:** title and short introduction precede detailed evidence.
  Game reports lead with the outcome and score, then reasons, factors, and plays.
  Team pages lead with their title and introduction, followed by publication notices
  before the evidence. Do not place a large administrative notice above the title.
- **Navigation and actions:** recognizable text links with underlines, red actions,
  visible selected states, and a clear return path. Keep control labels in sentence
  case. Use real links for navigation and buttons for actions.
- **Sections:** serif title, optional short explanation, then evidence. Use neutral
  panel fills and thin borders when grouping aids reading; keep statistical labels
  and controls in sans serif.
- **Tables:** align like quantities, use tabular numerals, and retain explicit
  team and unit labels. Row headings are reading content, not tiny uppercase metadata.
  Keep ranks, estimates, observed results, and forecasts clearly distinguished.
- **Charts:** use labels as well as color. Keep away/home colors stable within game
  reports. Multi-team profiles may use additional distinguishable colors and line
  styles with a legend. Preserve readable axes; game charts use HTML axis labels
  where scaling an SVG would make its text too small.
- **Notices and states:** preserve explicit live, pregame, final, stale-data,
  missing-data, and coverage labels. A visual cleanup must not hide uncertainty or
  imply that dated ratings are live. Keep loading, empty, error, and not-found
  screens in the same typography and surface language.

For example, a new factor section should follow the existing `GameExplorer`
section heading, explanation, chart/table, and contributing-play pattern. A new
team analysis section should use the template's heading, notice, `.scroll` table,
and `.calculation` patterns rather than introducing a separate card theme.

## Team Rating drivers

The approved team-detail composition is a story headline with power rating beside
it, followed by the source disclosure and Rating drivers. Use the same Source
Serif/Public Sans typography, white surface and double-rule masthead as game
reports. Keep contribution bars blue for positive and ochre for negative, and
model influence neutral gray with large percentages and a clearly separate axis.
Use unfilled column headers, a fine baseline rule, and secondary scale labels
aligned to their bar tracks; avoid a shaded table-header band.
On phones, influence gets a full-width row below each component.

Default to absolute team contribution order; offer Model influence sorting in
place. Preserve the sort selection across team/season navigation. Keep missing
influence explicit and last in influence order. The data, rating total and source
notices must survive sorting. Retain calculations, comparisons and raw statistics
in expandable sections. `prototypes/team-rating-drivers.test.mjs` verifies both
sorts and exact template/published presentation parity through `npm test`.

## Mobile and accessibility

Game evidence responds to its available container width, including the space
taken by the desktop sidebar. Preserve the report's container queries rather
than replacing them with viewport-only rules. The game sidebar gives way to
mobile navigation below 1024px. The standalone template uses viewport queries;
match the resulting behavior rather than blindly copying breakpoint numbers.

Stack supporting sections on phones, keep the scoreboard understandable with both
teams visible, and allow controls and long labels to wrap. Avoid page-level
horizontal scrolling. Dense team tables and wide profile/scatter charts may scroll
inside their own focusable, labeled regions; include a visible horizontal-scroll
hint. Do not shrink an entire chart until its labels become unreadable.

Preserve visible keyboard focus, semantic headings, table headers, accessible
control names, and selected/expanded states. Aim for at least 44px touch targets
for primary controls. Never rely only on color to communicate a leader, warning,
or selection. Respect reduced motion when adding animation.

## Updating both implementations

1. Find the owning files above and reuse their patterns. For a shared visual
   change, check both the Next.js tokens/components and the standalone template.
2. Edit `prototypes/team-seasons.html` for durable team-page changes; despite the
   directory name, it is the production generator's template. Editing only
   `public/team-seasons.html` will lose the change on the next publication.
3. Regenerate with the documented publisher when the audited source archive is
   available. For a presentation-only update to an existing publication, apply
   the matching template change to the published HTML and update its SHA-256 in
   `public/team-data/publication.json`. Preserve embedded data, model calculations,
   forecast archives, source checksums, and the original data publication time.
4. Keep standalone font assets in `public/fonts/` consistent with `src/app/fonts/`.
   Do not assume Next.js layout styles or font loading reach standalone HTML.
5. Update this guide when intentionally changing a shared convention. The README
   owns setup and publishing commands; metric definitions remain in
   `documentation.txt` and `FAQ.txt`.

## Visual verification

For a site-wide change, inspect the directory, completed and upcoming game
reports, expanded factor evidence and plays, all five standalone route types,
how-it-works, and state screens. Review the top and lower evidence sections;
checking only the first screen misses charts, tables, and calculation details.

Use a narrow 320px stress check, a representative phone around 390px, and desktop
widths around 1280–1440px. Exercise long headlines, long team names, season changes,
route navigation, matchup selectors, chart controls, and expanded details. Check
that data notices survive rerenders and mobile scrolling stays inside the evidence
region. Verify live behavior with fixtures when no game is currently live; do not
claim that a simulated state was observed in production.

Run checks proportionate to the change using `AGENTS.md`. Unit tests use mocks or
fixtures, never real ESPN or OpenAI calls. For a release, inspect the deployed
pages as well as local screenshots and confirm fonts load. Documentation-only
changes need link/path checks, not an application rebuild.
