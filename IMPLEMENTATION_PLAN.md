# NFL Game Explainer: Live Dashboard Implementation Plan

## Overview

Transform the existing Python-based NFL game analysis tool into a live web application with:
- Real-time auto-refresh (1 minute) for active games
- Directory page showing all games for current NFL week
- Game detail pages with sidebar navigation
- Vercel deployment with hybrid Python API + Next.js frontend

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Vercel Deployment                     │
├─────────────────────────────────────────────────────────┤
│  Next.js Frontend (TypeScript)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  Directory  │  │  Game Page  │  │  Sidebar Nav    │ │
│  │    Page     │──│  + Stats    │──│  (all games)    │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
│         │                │                              │
│         └────────────────┼──────────────────────────────│
│                          ▼                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Python API Routes                    │  │
│  │  /api/scoreboard  │  /api/game/[id]  │  /api/ai  │  │
│  └──────────────────────────────────────────────────┘  │
│         │                │                              │
└─────────┼────────────────┼──────────────────────────────┘
          ▼                ▼
    ┌───────────┐    ┌───────────┐
    │ ESPN API  │    │ OpenAI API│
    └───────────┘    └───────────┘
```

## Existing Design System (from game_summary_template.html)

The current template uses:
- **Fonts**: Bebas Neue (display), Barlow/Barlow Condensed (body)
- **Colors**: Dark theme with `--bg-deep: #0a0a0f`, `--bg-card: #12121a`
- **Team colors**: Dynamic CSS variables for home/away
- **Pattern**: Subtle grid overlay on background
- **Components**: Hero scoreboard, tug-of-war stat bars, expandable play lists

---

## Phase 1: Project Foundation

### Step 1.1: Initialize Next.js Project

```text
Create a new Next.js 14 project for the NFL Game Explainer live dashboard.

Project requirements:
- Next.js 14 with App Router
- TypeScript
- Tailwind CSS (we'll customize it to match existing design)
- Project name: nfl-game-explainer-live

Initial setup tasks:
1. Initialize the Next.js project with: npx create-next-app@latest nfl-game-explainer-live --typescript --tailwind --app --src-dir --no-eslint
2. Navigate into the project directory
3. Update tailwind.config.ts to include the design tokens from the existing template:
   - Add custom colors matching the CSS variables (bg-deep, bg-card, bg-elevated, etc.)
   - Add the font families (Bebas Neue, Barlow, Barlow Condensed)
4. Update src/app/globals.css to:
   - Import Google Fonts (Bebas Neue, Barlow, Barlow Condensed)
   - Add CSS variables matching the existing template
   - Add the subtle grid pattern background
5. Update src/app/layout.tsx to apply the base dark theme styling
6. Update src/app/page.tsx with a simple "NFL Game Explainer" heading to verify fonts and colors work
7. Test by running npm run dev and verifying the page renders with correct fonts and dark theme

The design should match the existing template's aesthetic:
- Dark background (#0a0a0f)
- Subtle grid pattern overlay
- Bebas Neue for headlines
- Barlow for body text
```

**Checklist:**
- [x] Next.js project initialized with TypeScript and Tailwind
- [x] tailwind.config.ts updated with custom colors and fonts
- [x] globals.css has CSS variables and grid pattern
- [x] layout.tsx applies dark theme
- [x] page.tsx renders with correct fonts
- [x] Dev server runs successfully

---

### Step 1.2: Set Up Python API Structure

```text
Set up the Python API route structure for Vercel serverless functions.

The project already has game_compare.py with all the game analysis logic. We need to:

1. Create the api/ directory structure in the project root (NOT in src/):
   - api/
     - scoreboard.py (will return all games for current week)
     - game/
       - [gameId].py (will return full game analysis)

2. Create a minimal api/health.py endpoint to verify Python runtime works:
   ```python
   from http.server import BaseHTTPRequestHandler
   import json

   class handler(BaseHTTPRequestHandler):
       def do_GET(self):
           self.send_response(200)
           self.send_header('Content-type', 'application/json')
           self.end_headers()
           self.wfile.write(json.dumps({"status": "ok", "runtime": "python"}).encode())
   ```

3. Create vercel.json in project root to configure:
   - Python runtime for /api routes
   - Rewrites for Next.js
   ```json
   {
     "functions": {
       "api/**/*.py": {
         "runtime": "python3.12"
       }
     }
   }
   ```

4. Create requirements.txt with dependencies from the existing project:
   - requests
   - pandas
   - openai
   - python-dotenv

5. Test locally using vercel dev (install Vercel CLI if needed: npm i -g vercel)
   - Verify /api/health returns {"status": "ok", "runtime": "python"}

Note: The Vercel Python runtime uses a specific handler format. Each API file exports a handler class.
```

**Checklist:**
- [x] api/ directory created with health.py
- [x] vercel.json configured for Python runtime
- [x] requirements.txt created with dependencies
- [x] Vercel CLI installed
- [x] vercel dev runs successfully (Next.js frontend works; Python API testing requires deployment)
- [x] /api/health endpoint returns expected JSON (verified syntax; full test in production)

---

### Step 1.3: Create Scoreboard API Endpoint

```text
Create the /api/scoreboard endpoint that returns all games for the current NFL week.

ESPN provides a scoreboard endpoint that returns all games for a given week. We need to:

1. Create api/scoreboard.py that:
   - Fetches the current NFL scoreboard from ESPN: https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
   - Extracts key information for each game:
     - gameId
     - status (pregame, in-progress, final)
     - home team (abbreviation, name, score, logo)
     - away team (abbreviation, name, score, logo)
     - quarter/time remaining (if in progress)
     - start time (if pregame)
   - Returns as JSON array

2. The response format should be:
   ```json
   {
     "week": {
       "number": 14,
       "label": "Week 14"
     },
     "games": [
       {
         "gameId": "401772896",
         "status": "in-progress",
         "statusDetail": "Q3 5:42",
         "homeTeam": {
           "abbr": "SEA",
           "name": "Seattle Seahawks", 
           "score": 21,
           "logo": "https://..."
         },
         "awayTeam": {
           "abbr": "MIN",
           "name": "Minnesota Vikings",
           "score": 17,
           "logo": "https://..."
         },
         "startTime": null,
         "isActive": true
       }
     ]
   }
   ```

3. The isActive flag should be true if:
   - status.type.state === "in" (game in progress)
   - This determines which games get auto-refreshed

4. Handle errors gracefully - return empty games array with error message if ESPN fails

5. Test by calling http://localhost:3000/api/scoreboard and verifying it returns current week's games
```

**Checklist:**
- [x] api/scoreboard.py created
- [x] Fetches from ESPN scoreboard API
- [x] Extracts all required fields per game
- [x] Returns properly formatted JSON
- [x] isActive flag correctly identifies in-progress games
- [x] Error handling works
- [x] Manual test returns expected data

---

### Step 1.4: Create Game Detail API Endpoint

```text
Create the /api/game/[gameId] endpoint that returns full game analysis.

This endpoint ports the core logic from game_compare.py to a serverless function.

1. Copy the existing game_compare.py to a new file: api/lib/game_analysis.py
   - This will be a module imported by the API route
   - Keep all the existing functions (get_game_data, get_play_probabilities, process_game_stats, etc.)
   - Remove the main() function and CLI argument parsing
   - Export the key functions we need

2. Create api/game/[gameId].py that:
   - Parses gameId from the URL path
   - Calls the game analysis functions from api/lib/game_analysis.py
   - Returns the same payload structure that currently gets written to JSON:
     - gameId, label
     - team_meta
     - summary_table, summary_table_full
     - advanced_table, advanced_table_full
     - expanded_details, expanded_details_full
     - wp_filter
     - analysis (the current build_analysis_text output)
     - status (pregame/in-progress/final)
   - Does NOT generate AI summary yet (that comes in a later step)

3. Create api/lib/__init__.py (empty file to make it a Python package)

4. Update api/lib/game_analysis.py to:
   - Remove file I/O operations (no writing CSV/JSON/HTML)
   - Return data structures directly
   - Accept wp_threshold as parameter (default 0.975)

5. Test by calling http://localhost:3000/api/game/401772896 and verifying:
   - Returns full game analysis JSON
   - summary_table has both teams
   - advanced_table has all metrics
   - expanded_details has play lists

Note: This is the largest step - take care to preserve all the existing logic. The goal is wrapping existing code, not rewriting it.
```

**Checklist:**
- [x] api/lib/game_analysis.py created with ported functions
- [x] api/lib/__init__.py created
- [x] api/game/[gameId].py created and calls analysis functions
- [x] File I/O removed from analysis module
- [x] Returns proper JSON payload
- [x] Manual test with real gameId works
- [x] Both filtered and full stats included

---

## Phase 2: Frontend Components

### Step 2.1: Create Type Definitions

```text
Create TypeScript type definitions for the API responses.

1. Create src/types/index.ts with interfaces matching the API responses:

```typescript
// Team info
export interface Team {
  abbr: string;
  name: string;
  score: number;
  logo: string;
  id?: string;
}

// Scoreboard game (from /api/scoreboard)
export interface ScoreboardGame {
  gameId: string;
  status: 'pregame' | 'in-progress' | 'final';
  statusDetail: string;
  homeTeam: Team;
  awayTeam: Team;
  startTime: string | null;
  isActive: boolean;
}

export interface ScoreboardResponse {
  week: {
    number: number;
    label: string;
  };
  games: ScoreboardGame[];
}

// Team meta for game detail
export interface TeamMeta {
  id: string;
  abbr: string;
  name: string;
  homeAway: 'home' | 'away';
}

// Stats row
export interface SummaryStats {
  Team: string;
  Score: number;
  'Total Yards': number;
  Drives: number;
}

export interface AdvancedStats {
  Team: string;
  Score: number;
  Turnovers: number;
  'Total Yards': number;
  'Yards Per Play': number;
  'Success Rate': number;
  'Explosive Plays': number;
  'Explosive Play Rate': number;
  'Points Per Trip (Inside 40)': number;
  'Ave Start Field Pos': string;
  'Penalty Yards': number;
  'Non-Offensive Points': number;
}

// Play detail
export interface PlayDetail {
  type: string;
  text: string;
  yards?: number;
  points?: number;
  quarter?: number;
  clock?: string;
  probability?: {
    homeWinPercentage: number;
    awayWinPercentage: number;
    homeDelta: number;
    awayDelta: number;
  };
}

// Full game response
export interface GameResponse {
  gameId: string;
  label: string;
  status: 'pregame' | 'in-progress' | 'final';
  team_meta: TeamMeta[];
  summary_table: SummaryStats[];
  summary_table_full: SummaryStats[];
  advanced_table: AdvancedStats[];
  advanced_table_full: AdvancedStats[];
  expanded_details: Record<string, Record<string, PlayDetail[]>>;
  expanded_details_full: Record<string, Record<string, PlayDetail[]>>;
  wp_filter: {
    enabled: boolean;
    threshold: number;
    description: string;
  };
  analysis: string;
  ai_summary?: string | null;
}
```

2. Create src/lib/api.ts with typed fetch functions:
   - fetchScoreboard(): Promise<ScoreboardResponse>
   - fetchGame(gameId: string): Promise<GameResponse>

These should call the API routes and handle errors.

3. Test by importing types in a component and verifying TypeScript compiles.
```

**Checklist:**
- [ ] src/types/index.ts created with all interfaces
- [ ] Types match API response structure
- [ ] src/lib/api.ts created with fetch functions
- [ ] TypeScript compiles without errors
- [ ] Types are exported and importable

---

### Step 2.2: Build Scoreboard Component

```text
Build the scoreboard/hero component that displays the two teams and score.

Reference the existing template's hero section for design. Key elements:
- Split background with team colors
- Team logos (large)
- Team abbreviations
- Scores in large display font (Bebas Neue)
- Game status (quarter/time or "Final")
- Winner indicator (subtle glow on winning team's side)

1. Create src/components/Scoreboard.tsx:
   - Accept props: homeTeam, awayTeam, status, statusDetail
   - Use dynamic CSS variables for team colors (we'll add a team colors utility)
   - Match the existing template's hero layout:
     - Full-width hero section
     - Diagonal split background using team primary colors
     - Away team on left, home team on right
     - Centered score display

2. Create src/lib/teamColors.ts:
   - Port the TEAM_COLORS object from the existing template
   - Export a getTeamColors(abbr: string) function
   - Include primary, secondary, and accent colors for each NFL team

3. Style requirements (matching existing template):
   - Hero min-height: 320px
   - Diagonal gradient split at ~50% using team colors
   - Score font: Bebas Neue, ~5rem size
   - Team abbrev: Bebas Neue, ~1.5rem, letter-spacing
   - Subtle glow/shadow behind winning team's score
   - Status pill showing game state

4. Test by creating a test page that renders the Scoreboard with mock data.
   - Verify team colors apply correctly
   - Verify layout matches existing template
   - Test with various score states (tie, blowout, close)
```

**Checklist:**
- [ ] src/components/Scoreboard.tsx created
- [ ] src/lib/teamColors.ts created with all NFL teams
- [ ] Component accepts required props with types
- [ ] Team colors apply dynamically via CSS variables
- [ ] Layout matches existing template hero section
- [ ] Winner glow effect works
- [ ] Status displays correctly for all states

---

### Step 2.3: Build Stat Row Component (Tug-of-War Bars)

```text
Build the stat row component with tug-of-war visualization.

This is the core statistical display showing how each team performed on a metric. Reference the existing template's advanced stats section.

1. Create src/components/StatRow.tsx:
   - Props: 
     - label: string (e.g., "Turnovers")
     - sublabel?: string (e.g., "Giveaways")
     - awayValue: number | string
     - homeValue: number | string
     - awayColor: string
     - homeColor: string
     - lowerIsBetter?: boolean (for turnovers, penalties)
     - isPercentage?: boolean
   
2. The tug-of-war bar visualization:
   - Horizontal track (100% width, ~8px height, dark background)
   - Center line indicator
   - Two bars growing from center:
     - Away team bar grows left
     - Home team bar grows right
   - Bar lengths proportional to values
   - Winning team's bar is full opacity team color
   - Losing team's bar is muted (rgba white overlay)
   
3. Value display:
   - Away value on far left
   - Home value on far right
   - Winning value in white, losing in gray (#666)
   
4. Strength indicators (diamonds):
   - Calculate percentage difference: |away - home| / ((|away| + |home|) / 2)
   - ◆◆◆ Dominant (>30%)
   - ◆◆ Strong (15-30%)
   - ◆ Slight (5-15%)
   - · Minimal (<5%)
   - Position diamonds to the right of the row
   - Diamonds glow with team color of winner

5. Create src/components/AdvancedStats.tsx:
   - Renders all stat rows for a game
   - Maps the advanced_table data to StatRow components
   - Includes card styling matching existing template

6. Test with mock data verifying:
   - Bars grow in correct direction
   - Colors apply correctly
   - Strength indicators show correct symbols
   - lowerIsBetter inverts the winner logic
```

**Checklist:**
- [ ] src/components/StatRow.tsx created
- [ ] Tug-of-war bar visualization works
- [ ] Bar widths proportional to values
- [ ] Winner/loser styling correct
- [ ] Strength indicators (diamonds) display correctly
- [ ] lowerIsBetter prop inverts logic for turnovers/penalties
- [ ] src/components/AdvancedStats.tsx wraps all rows
- [ ] Visual test matches existing template

---

### Step 2.4: Build Play List Component

```text
Build the expandable play list component for turnovers, explosive plays, etc.

Reference the existing template's plays section with tabs and expandable rows.

1. Create src/components/PlayList.tsx:
   - Props:
     - plays: PlayDetail[]
     - teamAbbr: string
     - teamColor: string
   - Each play row shows:
     - Quarter and clock (e.g., "Q2 5:42")
     - Play type
     - Brief description (truncated)
     - WP delta if significant (±X.X%)
   - Rows are expandable on click to show full play text
   - Animation on expand/collapse

2. Create src/components/PlayTabs.tsx:
   - Horizontal tabs for categories: Turnovers, Explosive Plays, Non-Offensive Scores
   - Active tab styling (underline or filled)
   - Shows both teams' plays for selected category
   - Team sections labeled with team abbreviation

3. Styling requirements:
   - Card container matching existing template
   - Tab bar at top
   - Play rows with hover effect
   - Expand animation (height transition)
   - WP delta colored: positive = green, negative = red

4. Create src/components/GamePlays.tsx:
   - Combines PlayTabs and PlayList
   - Accepts expanded_details from game response
   - Handles tab switching
   - Groups plays by team within each tab

5. Test with mock play data:
   - Tabs switch correctly
   - Plays render for both teams
   - Expand/collapse works
   - WP delta displays and colors correctly
```

**Checklist:**
- [ ] src/components/PlayList.tsx created
- [ ] Plays render with all fields
- [ ] Expand/collapse animation works
- [ ] WP delta colored correctly
- [ ] src/components/PlayTabs.tsx created
- [ ] Tab switching works
- [ ] src/components/GamePlays.tsx combines them
- [ ] Both teams' plays display
- [ ] Visual test matches existing template

---

### Step 2.5: Build AI Summary Component

```text
Build the AI summary display component.

This shows the ~280 character AI-generated summary of why the game is the way it is.

1. Create src/components/AISummary.tsx:
   - Props:
     - summary: string | null
     - isLoading?: boolean
   - If summary is null, don't render anything
   - Display in a card with subtle AI indicator icon
   - Text styling: slightly larger, readable line-height

2. Design requirements (matching existing template's analysis card):
   - Card background: var(--bg-card)
   - Left border or icon indicating AI-generated
   - Summary text in body font (Barlow)
   - Subtle "AI Analysis" label above text
   - Optional: animated gradient border or glow

3. Loading state:
   - Show skeleton/shimmer while generating
   - Subtle animation

4. Test with sample summary text and null state
```

**Checklist:**
- [ ] src/components/AISummary.tsx created
- [ ] Renders summary text when provided
- [ ] Hidden when summary is null
- [ ] AI indicator/label present
- [ ] Loading state with skeleton
- [ ] Styling matches existing template

---

### Step 2.6: Build View Toggle Component

```text
Build the Competitive/Full Game toggle component.

This allows switching between competitive-time-only stats and full game stats.

1. Create src/components/ViewToggle.tsx:
   - Props:
     - value: 'competitive' | 'full'
     - onChange: (value: 'competitive' | 'full') => void
   - Two buttons: "Competitive" and "Full Game"
   - Active button has filled/highlighted style
   - Inactive button is ghost/outline style

2. Design requirements:
   - Compact horizontal toggle
   - Fits in card header
   - Uses pill/segment style buttons
   - Active state clearly distinguished

3. Create associated filter indicator:
   - When "Competitive" is active, show small text: "Stats reflect competitive plays only (WP < 97.5%)"
   - Hidden when "Full Game" is selected

4. Test toggle interaction and state changes
```

**Checklist:**
- [ ] src/components/ViewToggle.tsx created
- [ ] Toggle switches between competitive/full
- [ ] Active state clearly visible
- [ ] onChange callback fires correctly
- [ ] Filter indicator text shows/hides appropriately

---

## Phase 3: Page Assembly

### Step 3.1: Build Game Detail Page

```text
Assemble all components into the game detail page.

1. Create src/app/game/[gameId]/page.tsx:
   - Server component that fetches initial data
   - Renders loading state while fetching
   - Passes data to client components

2. Create src/app/game/[gameId]/GamePageClient.tsx:
   - Client component ("use client")
   - Manages state: current view (competitive/full), expanded plays, etc.
   - Composes all components:
     - Scoreboard (top)
     - AISummary (below scoreboard)
     - AdvancedStats with ViewToggle
     - GamePlays

3. Layout structure:
   ```
   ┌────────────────────────────────────────┐
   │           SCOREBOARD                   │
   ├────────────────────────────────────────┤
   │         AI SUMMARY                     │
   ├────────────────────────────────────────┤
   │  ADVANCED STATS    [Competitive|Full]  │
   │  ┌─────────────────────────────────┐   │
   │  │ Stat Row (tug of war)           │   │
   │  │ Stat Row                        │   │
   │  │ ...                             │   │
   │  └─────────────────────────────────┘   │
   ├────────────────────────────────────────┤
   │  PLAYS [Turnovers|Explosives|ST TDs]   │
   │  ┌─────────────────────────────────┐   │
   │  │ Play list...                    │   │
   │  └─────────────────────────────────┘   │
   └────────────────────────────────────────┘
   ```

4. View toggle should switch data source between:
   - advanced_table vs advanced_table_full
   - expanded_details vs expanded_details_full

5. Test by navigating to /game/401772896 with dev server running:
   - Verify all sections render
   - Verify data displays correctly
   - Verify toggle switches stats
   - Verify plays expand
```

**Checklist:**
- [ ] src/app/game/[gameId]/page.tsx created (server component)
- [ ] src/app/game/[gameId]/GamePageClient.tsx created (client component)
- [ ] All components composed correctly
- [ ] View toggle switches data sources
- [ ] Loading state displays
- [ ] Page renders with real API data
- [ ] All interactions work (toggle, play expand)

---

### Step 3.2: Build Directory Page

```text
Build the directory/home page showing all games for the current week.

1. Update src/app/page.tsx to be the directory page:
   - Fetches scoreboard data
   - Displays all games in a grid/list

2. Create src/components/GameCard.tsx:
   - Compact card showing one game
   - Team logos (smaller than game page)
   - Team abbreviations
   - Scores
   - Status indicator (Q2 5:42, Final, etc.)
   - Clickable - links to /game/[gameId]
   - Active games have subtle pulse/glow animation

3. Directory layout:
   ```
   ┌────────────────────────────────────────┐
   │  NFL WEEK 14                           │
   │  Sunday, December 14, 2025             │
   ├────────────────────────────────────────┤
   │  ┌──────────┐  ┌──────────┐  ┌──────┐ │
   │  │ MIN @ SEA│  │ DET @ GB │  │ ...  │ │
   │  │  17  21  │  │  24  21  │  │      │ │
   │  │  Q3 5:42 │  │  Final   │  │      │ │
   │  └──────────┘  └──────────┘  └──────┘ │
   │  ┌──────────┐  ┌──────────┐           │
   │  │  ...     │  │  ...     │           │
   │  └──────────┘  └──────────┘           │
   └────────────────────────────────────────┘
   ```

4. Game cards should:
   - Use team colors for subtle accents
   - Show clear visual distinction between pregame/active/final
   - Pregame: Show start time
   - Active: Show quarter and time, pulse animation
   - Final: Show "Final", winning team highlighted

5. Sort games by status: in-progress first, then pregame by time, then final

6. Test by visiting home page:
   - Verify all games display
   - Verify clicking navigates to game page
   - Verify status displays correctly
```

**Checklist:**
- [ ] src/app/page.tsx updated as directory
- [ ] src/components/GameCard.tsx created
- [ ] All games from scoreboard display
- [ ] Team colors applied to cards
- [ ] Status displays correctly (pregame/active/final)
- [ ] Clicking card navigates to game page
- [ ] Games sorted by status
- [ ] Active games have visual distinction

---

### Step 3.3: Build Sidebar Navigation

```text
Add sidebar navigation to the game page showing all games for quick switching.

1. Create src/components/GameSidebar.tsx:
   - Fetches scoreboard data (or receives as prop)
   - Lists all games in compact format
   - Highlights current game
   - Clicking navigates to different game
   - Shows live scores that update

2. Compact game row format:
   - Team abbrevs: "MIN @ SEA"
   - Scores: "17-21"
   - Status badge
   - Active game indicator (pulsing dot)

3. Update the game page layout to include sidebar:
   ```
   ┌─────────┬────────────────────────────────┐
   │ SIDEBAR │         MAIN CONTENT           │
   │         │                                │
   │ MIN@SEA │  SCOREBOARD                    │
   │  17-21● │  AI SUMMARY                    │
   │         │  ADVANCED STATS                │
   │ DET@GB  │  PLAYS                         │
   │  24-21  │                                │
   │  Final  │                                │
   │         │                                │
   │ ...     │                                │
   │         │                                │
   └─────────┴────────────────────────────────┘
   ```

4. Update src/app/game/[gameId]/layout.tsx:
   - Create layout that includes sidebar
   - Sidebar fixed on left
   - Main content scrollable

5. Mobile considerations:
   - Sidebar hidden on mobile by default
   - Hamburger menu to toggle
   - Or: horizontal scrollable bar at top on mobile

6. Test navigation:
   - Sidebar shows all games
   - Current game highlighted
   - Clicking different game navigates
   - Scores display correctly
```

**Checklist:**
- [ ] src/components/GameSidebar.tsx created
- [ ] Shows all games in compact format
- [ ] Current game highlighted
- [ ] Clicking navigates to different game
- [ ] Layout updated to include sidebar
- [ ] Mobile responsive (hidden or horizontal)
- [ ] Active games have indicator

---

## Phase 4: Real-Time Features

### Step 4.1: Add Auto-Refresh for Active Games

```text
Implement automatic data refresh every 60 seconds for active (in-progress) games.

1. Create src/hooks/useAutoRefresh.ts:
   - Custom hook that polls an endpoint at specified interval
   - Only runs when enabled (game is active)
   - Returns current data, loading state, last updated time
   - Handles cleanup on unmount

2. Update GamePageClient.tsx:
   - Use the auto-refresh hook
   - Pass isActive from game status
   - When data refreshes, update all components
   - Show "Last updated: X seconds ago" indicator

3. Refresh logic:
   - Only fetch if game status is "in-progress"
   - Stop polling once game becomes "final"
   - If fetch fails, retry after 30 seconds
   - Don't show loading state on refresh (just update data)

4. Create src/components/UpdateIndicator.tsx:
   - Shows last update time
   - Subtle countdown to next refresh
   - Appears only for active games
   - "Live" badge with pulse animation

5. Update sidebar to also refresh:
   - Sidebar scores should update alongside main content
   - Use same refresh mechanism or separate hook

6. Test with an active game:
   - Verify data updates every 60 seconds
   - Verify no loading flash on update
   - Verify updates stop after game ends
   - Verify last updated time displays
```

**Checklist:**
- [ ] src/hooks/useAutoRefresh.ts created
- [ ] Hook handles polling interval
- [ ] Hook only runs when game is active
- [ ] GamePageClient uses hook
- [ ] Data updates without loading flash
- [ ] src/components/UpdateIndicator.tsx created
- [ ] Last updated time displays
- [ ] Polling stops when game ends
- [ ] Sidebar scores update too

---

### Step 4.2: Add AI Summary Generation with Caching

```text
Implement AI summary generation that only regenerates when score changes.

1. Create api/ai/summary.py endpoint:
   - Accepts gameId and current scores as parameters
   - Port the AI generation logic from game_compare.py
   - Calls OpenAI API
   - Returns summary text

2. Create simple cache mechanism:
   - Use Vercel KV (Redis) or a simple in-memory cache
   - For MVP: file-based cache in /tmp (works on Vercel)
   - Cache key: gameId_homeScore_awayScore
   - Cache value: generated summary
   - TTL: 24 hours (or until score changes)

3. Update api/game/[gameId].py:
   - After getting game data, check if AI summary is cached
   - If cached for current score, return cached summary
   - If not cached (or score changed), generate new summary
   - Store new summary in cache
   - Include ai_summary in response

4. Cache logic:
   ```python
   cache_key = f"{game_id}_{home_score}_{away_score}"
   cached = get_cache(cache_key)
   if cached:
       return cached
   summary = generate_ai_summary(...)
   set_cache(cache_key, summary, ttl=86400)
   return summary
   ```

5. Handle OpenAI failures gracefully:
   - If API fails, return null for ai_summary
   - Don't block game data response
   - Log error for debugging

6. Test:
   - First load generates summary
   - Refresh with same score returns cached
   - Score change generates new summary
   - API failure returns null gracefully
```

**Checklist:**
- [ ] api/ai/summary.py created (or integrated into game endpoint)
- [ ] AI generation logic ported
- [ ] Cache mechanism implemented
- [ ] Cache key includes scores
- [ ] New summary generated on score change
- [ ] Cached summary returned when scores unchanged
- [ ] OpenAI failures handled gracefully
- [ ] ai_summary included in game response

---

### Step 4.3: Directory Page Auto-Refresh

```text
Add auto-refresh to the directory page for live score updates.

1. Create src/app/DirectoryClient.tsx:
   - Client component for directory page
   - Uses auto-refresh hook
   - Always refreshes every 60 seconds during game days
   - Updates all game cards with new scores

2. Update src/app/page.tsx:
   - Server component fetches initial data
   - Passes to DirectoryClient for client-side updates

3. Smart refresh logic:
   - Only auto-refresh if any game is active
   - If all games are final or pregame, disable refresh
   - Re-enable when a game goes active

4. Visual feedback:
   - Score changes should briefly highlight (flash animation)
   - Status changes (e.g., halftime -> Q3) should update smoothly
   - "Scores update automatically" indicator

5. Test:
   - Directory refreshes every 60 seconds
   - Score changes visible
   - Highlight animation on score change
   - Stops refreshing when all games final
```

**Checklist:**
- [ ] src/app/DirectoryClient.tsx created
- [ ] Auto-refresh hook integrated
- [ ] Refreshes only when games active
- [ ] Scores update in place
- [ ] Score change highlight animation
- [ ] Refresh disabled when all games final/pregame

---

## Phase 5: Polish & Deploy

### Step 5.1: Loading States and Error Handling

```text
Add proper loading states and error handling throughout the app.

1. Create src/components/LoadingStates.tsx:
   - ScoreboardSkeleton: placeholder for hero section
   - StatRowSkeleton: placeholder for stat rows
   - PlayListSkeleton: placeholder for plays
   - GameCardSkeleton: placeholder for directory cards

2. Implement loading UI:
   - Skeletons should match layout of actual components
   - Use shimmer animation
   - Show skeleton while fetching

3. Create src/components/ErrorState.tsx:
   - Friendly error message
   - Retry button
   - Different messages for different error types

4. Add error boundaries:
   - Create error.tsx files in app directories
   - Handle component-level errors gracefully

5. Handle specific error cases:
   - Game not found (404)
   - ESPN API down
   - OpenAI API failure (graceful degradation)
   - Network errors

6. Test error states:
   - Invalid gameId shows error
   - Network disconnect shows retry option
   - Partial failures still show available data
```

**Checklist:**
- [ ] Loading skeleton components created
- [ ] Skeletons match actual component layouts
- [ ] Error state component created
- [ ] error.tsx files in app directories
- [ ] 404 handling for invalid gameId
- [ ] Network error handling with retry
- [ ] Partial failure handling

---

### Step 5.2: Mobile Responsiveness

```text
Ensure all components are fully responsive on mobile devices.

1. Review and update each component for mobile:
   - Scoreboard: Stack teams vertically on mobile
   - StatRows: Smaller fonts, full width
   - PlayList: Full width, larger touch targets
   - GameCards: 2 columns on tablet, 1 on mobile
   - Sidebar: Bottom drawer on mobile

2. Breakpoints (Tailwind defaults):
   - sm: 640px
   - md: 768px
   - lg: 1024px

3. Key mobile adjustments:
   - Scoreboard: 
     - Reduce score font size
     - Stack layout on <640px
   - Sidebar:
     - Fixed bottom bar on mobile showing current game
     - Tap to open full game list as bottom sheet
   - Touch targets:
     - Minimum 44px height for tappable elements
   - Text sizing:
     - Base 16px, scale appropriately

4. Test on multiple viewport sizes:
   - Mobile (375px, 390px)
   - Tablet (768px)
   - Desktop (1024px+)

5. Use Chrome DevTools device toolbar to verify layouts
```

**Checklist:**
- [ ] Scoreboard responsive (stacked on mobile)
- [ ] StatRows responsive (full width)
- [ ] PlayList touch-friendly
- [ ] GameCards grid responsive
- [ ] Sidebar becomes bottom sheet on mobile
- [ ] Touch targets ≥44px
- [ ] Tested at multiple breakpoints
- [ ] No horizontal scroll on mobile

---

### Step 5.3: Environment Variables and Deployment Setup

```text
Configure environment variables and prepare for Vercel deployment.

1. Create .env.local file (gitignored):
   ```
   OPENAI_API_KEY=sk-...
   ```

2. Create .env.example file (committed):
   ```
   OPENAI_API_KEY=your-api-key-here
   ```

3. Update vercel.json with any additional config:
   - Environment variable references
   - Function timeout settings (Python might need more time)
   - Region selection (for latency)

4. Update .gitignore:
   - .env.local
   - .vercel
   - __pycache__
   - *.pyc

5. Create README.md with:
   - Project description
   - Local development setup
   - Environment variables needed
   - Deployment instructions

6. Test local build:
   - npm run build (should succeed)
   - npm run start (should work)
   - vercel dev (should work with Python APIs)
```

**Checklist:**
- [ ] .env.local created with API keys
- [ ] .env.example created (no secrets)
- [ ] vercel.json fully configured
- [ ] .gitignore updated
- [ ] README.md created
- [ ] npm run build succeeds
- [ ] npm run start works
- [ ] vercel dev works

---

### Step 5.4: Deploy to Vercel

```text
Deploy the application to Vercel.

This is a MANUAL STEP with some verification tasks.

1. Connect repository to Vercel:
   - Go to vercel.com
   - Import the Git repository
   - Vercel should auto-detect Next.js

2. Configure environment variables in Vercel dashboard:
   - Add OPENAI_API_KEY
   - Set to production environment

3. Deploy:
   - Trigger deployment from Vercel dashboard
   - Or push to main branch if auto-deploy is enabled

4. Verify deployment:
   - Visit the deployed URL
   - Check directory page loads with games
   - Check individual game page works
   - Check API routes work (/api/health, /api/scoreboard)
   - Check AI summaries generate
   - Check auto-refresh works on active games

5. Monitor:
   - Check Vercel function logs for errors
   - Monitor OpenAI API usage
   - Check for Python function cold start times

6. Set up custom domain (optional):
   - Add domain in Vercel settings
   - Update DNS records
```

**Checklist:**
- [ ] Repository connected to Vercel
- [ ] Environment variables configured
- [ ] Deployment triggered
- [ ] Directory page works on live URL
- [ ] Game page works on live URL
- [ ] API routes respond
- [ ] AI summaries generate
- [ ] Auto-refresh works for active games
- [ ] No console errors in production
- [ ] Function logs show no critical errors

---

## Summary

### Total Steps: 18

**Phase 1: Foundation (4 steps)**
1.1 Initialize Next.js project
1.2 Set up Python API structure
1.3 Create scoreboard API
1.4 Create game detail API

**Phase 2: Components (6 steps)**
2.1 Create TypeScript types
2.2 Build Scoreboard component
2.3 Build StatRow component
2.4 Build PlayList component
2.5 Build AI Summary component
2.6 Build ViewToggle component

**Phase 3: Pages (3 steps)**
3.1 Build Game Detail page
3.2 Build Directory page
3.3 Build Sidebar navigation

**Phase 4: Real-Time (3 steps)**
4.1 Add auto-refresh for active games
4.2 Add AI summary caching
4.3 Add directory auto-refresh

**Phase 5: Polish & Deploy (4 steps)**
5.1 Loading states and error handling
5.2 Mobile responsiveness
5.3 Environment setup
5.4 Deploy to Vercel (MANUAL)

### Estimated Timeline
- Each step: 15-45 minutes
- Total: 6-12 hours of implementation
- Testing between steps: Add 30%
- **Total estimate: 8-16 hours**

### Dependencies
- Steps must be completed in order within each phase
- Phase 2 depends on Phase 1
- Phase 3 depends on Phase 2
- Phase 4 depends on Phase 3
- Phase 5 can partially overlap with Phase 4
