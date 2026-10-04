import Link from 'next/link';
import type { DebugPlayRow, GameResponse } from '@/types';
import { DebugGamePicker } from './DebugGamePicker';

function valueText(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function StatsTable({ title, rows }: {
  title: string;
  rows: Record<string, string | number | null>[];
}) {
  const teams = rows.map((row, index) => String(row.Team ?? `Team ${index + 1}`));
  const metrics = Array.from(new Set(rows.flatMap((row) => Object.keys(row).filter((key) => key !== 'Team'))));
  return (
    <section className="min-w-0 space-y-1">
      <h2 className="text-sm font-semibold">{title}</h2>
      {rows.length === 0 ? <p className="text-slate-600">No calculated rows.</p> : (
        <div className="min-w-0 border border-slate-300">
          <table aria-label={title} className="w-full table-fixed border-collapse text-left text-xs leading-tight">
            <thead className="bg-slate-100 text-slate-700">
              <tr>
                <th scope="col" className="w-1/2 border-b border-slate-300 px-2 py-1">Metric</th>
                {teams.map((team, index) => <th key={`${team}-${index}`} scope="col" className="border-b border-slate-300 px-2 py-1 break-words">{team}</th>)}
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric) => (
                <tr key={metric} className="border-t border-slate-200 align-top">
                  <th scope="row" className="px-2 py-1 font-normal break-words">{metric}</th>
                  {rows.map((row, index) => <td key={`${teams[index]}-${index}`} className="px-2 py-1 break-words">{valueText(row[metric])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function RawJSON({ label, data }: { label: string; data: unknown }) {
  return (
    <details className="border border-slate-300 p-2">
      <summary className="cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-600">{label}</summary>
      <pre className="mt-2 max-h-[34rem] overflow-auto whitespace-pre-wrap break-all text-xs text-slate-700">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}

function contributionText(row: DebugPlayRow): string {
  return Object.entries(row.statDeltas)
    .flatMap(([team, changes]) => Object.entries(changes).map(([metric, value]) => `${team} ${metric}: ${value > 0 ? '+' : ''}${value}`))
    .join('; ') || '—';
}

function fieldPosition(row: DebugPlayRow, boundary: 'start' | 'end'): string {
  if (row.kind !== 'play') return '—';
  const source = row.raw[boundary];
  if (!source || typeof source !== 'object') return '—';
  const position = (source as Record<string, unknown>).possessionText;
  return typeof position === 'string' && position.trim() ? position.trim() : '—';
}

function downDistance(row: DebugPlayRow): string {
  if (row.kind !== 'play' || row.down == null || row.down < 1 || row.distance == null || row.distance < 0) return '—';
  return `${row.down} & ${row.distance}`;
}

function winProbability(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${(value * 100).toFixed(2)}%`
    : '—';
}

function winProbabilityChange(row: DebugPlayRow): string {
  if (typeof row.startHomeWP !== 'number' || typeof row.endHomeWP !== 'number') return '—';
  return `${((row.endHomeWP - row.startHomeWP) * 100).toFixed(2)} pp`;
}

function calculationFlag(row: DebugPlayRow, metric: 'Successful Plays' | 'Explosive Plays'): string {
  if (row.kind !== 'play' || row.excludedReason || !['run', 'pass'].includes(row.classification ?? '')) return '—';
  return Object.values(row.statDeltas).some((changes) => (changes[metric] ?? 0) > 0) ? 'Yes' : 'No';
}

export function GameDebugView({ gameData }: { gameData: GameResponse }) {
  const debug = gameData.debug;
  const rawPayload = { ...gameData, debug: undefined };

  return (
    <div className="min-h-screen min-w-0 bg-white px-3 py-3 font-mono text-xs text-slate-900">
      <div className="min-w-0 space-y-4">
        <header className="space-y-2 border-b border-slate-300 pb-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h1 className="text-base font-semibold">Debug data: {gameData.label}</h1>
            <DebugGamePicker gameId={gameData.gameId} label={gameData.label} week={gameData.week} />
            <Link href={`/game/${gameData.gameId}`} className="text-blue-700 underline hover:text-blue-900">Game view</Link>
          </div>
          <p className="text-xs text-slate-600">
            ESPN source data and the calculations currently used by this app. Competitive rows use the
            {' '}{gameData.wp_filter.threshold * 100}% win-probability cutoff; full-game rows do not.
            {' '}Success Rate uses 40% of yards to go on first down, 60% on second, and 100% on third or fourth.
          </p>
        </header>

        {!debug ? (
          <p role="alert" className="border border-slate-300 p-3">
            Debug data was not returned by the API. Open /api/game/{gameData.gameId}?debug=true to inspect the response.
          </p>
        ) : (
          <>
            <StatsTable title="Calculated stats — competitive plays" rows={debug.statsCompetitive} />
            <StatsTable title="Calculated stats — full game" rows={debug.statsFull} />

            <section className="min-w-0 space-y-1">
              <h2 className="text-sm font-semibold">Source plays and calculated contributions</h2>
              <p className="text-xs text-slate-600">
                Each row comes from an ESPN drive play. Contributions show changes to the calculation counters
                in the full-game pass. Drive totals are finalized on separate rows. Score comes from the ESPN
                game header, penalty yards from its box score, and non-offensive points from scoring plays.
                WP is home-team win probability, with change in percentage points. Success and explosive
                flags reflect the full-game calculation; — means not applicable.
              </p>
              <div className="min-w-0 border border-slate-300">
                <table aria-label="Source plays and calculated contributions" className="block w-full text-left text-xs leading-snug lg:table lg:table-fixed lg:border-collapse">
                  <colgroup>
                    <col className="lg:w-[4%]" />
                    <col className="lg:w-[7%]" />
                    <col className="lg:w-[4%]" />
                    <col className="lg:w-[5%]" />
                    <col className="lg:w-[6%]" />
                    <col className="lg:w-[6%]" />
                    <col className="lg:w-[4%]" />
                    <col className="lg:w-[6%]" />
                    <col className="lg:w-[6%]" />
                    <col className="lg:w-[6%]" />
                    <col className="lg:w-[5%]" />
                    <col className="lg:w-[6%]" />
                    <col className="lg:w-[29%]" />
                    <col className="lg:w-[6%]" />
                  </colgroup>
                  <thead className="hidden bg-slate-100 text-slate-700 lg:table-header-group">
                    <tr>
                      {['Drive', 'Time', 'Team', 'Down & distance', 'Start', 'End', 'Yards', 'WP before', 'WP after', 'WP change', 'Success', 'Explosive', 'Play and contributions', 'Details'].map((heading) => (
                        <th key={heading} scope="col" className="border-b border-slate-300 px-1 py-1 break-words">{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="block lg:table-row-group">
                    {debug.plays.map((row, index) => (
                      <tr key={`${row.kind}-${row.playId ?? row.drive}-${index}`} className="block border-t border-slate-200 p-1 align-top lg:table-row lg:p-0">
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Drive: </span>{row.drive}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Time: </span>{row.quarter ? `Q${row.quarter} ` : ''}{valueText(row.clock)}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Team: </span>{valueText(row.team)}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Down & distance: </span>{downDistance(row)}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Start: </span>{fieldPosition(row, 'start')}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">End: </span>{fieldPosition(row, 'end')}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Yards: </span>{valueText(row.sourceYards)}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">WP before: </span>{winProbability(row.startHomeWP)}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">WP after: </span>{winProbability(row.endHomeWP)}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">WP change: </span>{winProbabilityChange(row)}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Success: </span>{calculationFlag(row, 'Successful Plays')}</td>
                        <td className="inline-block p-1 lg:table-cell"><span className="text-slate-600 lg:hidden">Explosive: </span>{calculationFlag(row, 'Explosive Plays')}</td>
                        <td className="block min-w-0 p-1 lg:table-cell">
                          <span className="text-slate-600">{valueText(row.type ?? row.kind)} · {valueText(row.classification)}</span>
                          <div className="break-words">{row.text}{row.excludedReason ? ` [${row.excludedReason}]` : ''}</div>
                          <div className="break-words text-slate-600">{contributionText(row)}</div>
                        </td>
                        <td className="block min-w-0 p-1 lg:table-cell">
                          <details className="min-w-0 border border-slate-300 p-1">
                            <summary className="cursor-pointer text-blue-700 focus-visible:outline-2 focus-visible:outline-blue-600">Inspect</summary>
                            <div className="mt-2 min-w-0 space-y-1 break-words text-slate-700">
                              <div>Play ID: {valueText(row.playId)}</div>
                              <div>Down / to go: {valueText(row.down)} / {valueText(row.distance)}</div>
                              <div>Competitive: {row.competitive === undefined ? '—' : row.competitive ? 'Yes' : 'No'}</div>
                              <div>Home WP: {valueText(row.startHomeWP)} → {valueText(row.endHomeWP)}</div>
                              <pre className="max-h-96 max-w-full overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(row.raw, null, 2)}</pre>
                            </div>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="space-y-1">
              <h2 className="text-sm font-semibold">Underlying responses</h2>
              <RawJSON label="Full ESPN game payload" data={debug.sources.espnSummary} />
              <RawJSON label="ESPN play win probabilities" data={debug.sources.playProbabilities} />
              <RawJSON label="Pregame win probabilities" data={debug.sources.pregameProbabilities} />
              <RawJSON label="Calculated API payload" data={rawPayload} />
            </section>
          </>
        )}
      </div>
    </div>
  );
}
