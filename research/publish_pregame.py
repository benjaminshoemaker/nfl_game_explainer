"""Package an audited weekly archive for the deployed pregame API (no network)."""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'api/lib/data/pregame.json'


def scoring_margin(team, cutoff):
    """Observed points differential per game, only with complete final scores."""
    rows = [row for row in team['schedule'] if row['week'] <= cutoff and row['final']]
    if not rows or len(rows) != team['gamesExpected']:
        return None
    if any(not isinstance(row.get(k), (int, float)) for row in rows for k in ['score', 'opponentScore']):
        return None
    return sum(row['score'] - row['opponentScore'] for row in rows) / len(rows)


def publish(archive, output=DEFAULT_OUTPUT):
    archive, output = Path(archive), Path(output)
    predictions = json.loads((archive / 'predictions.json').read_text())
    if predictions['status'] != 'pregame':
        raise ValueError('Only pregame publications can be packaged')
    season, week = predictions['season'], predictions['inputThroughWeek']
    if predictions['week'] != week + 1:
        raise ValueError('Preview must use prior-week data')
    snapshot = json.loads((archive / f'snapshots/{season}-week-{week}.json').read_text())
    power = json.loads((archive / f'snapshots/{season}-week-{week}-power.json').read_text())
    if any(x['season'] != season or x['throughWeek'] != week for x in [snapshot, power]):
        raise ValueError('Snapshot cutoff mismatch')
    with (archive / 'sources/games.csv').open() as f:
        schedule = {r['game_id']: r for r in csv.DictReader(f)}
    games = {}
    for game in predictions['games']:
        if datetime.fromisoformat(predictions['publishedAt']) >= datetime.fromisoformat(game['kickoff']):
            raise ValueError('Publication must precede kickoff')
        espn = schedule[game['gameId']]['espn']
        if not espn.isdigit() or espn in games:
            raise ValueError('Missing or duplicate ESPN game ID')
        games[espn] = {k: game[k] for k in ['home', 'away', 'kickoff', 'week', 'model']}
    result = {'season': season, 'throughWeek': week, 'publishedAt': predictions['publishedAt'],
              'modelSha256': predictions['modelSha256'], 'factors': snapshot['factors'],
              'weights': {k: v['weightPercent'] for k, v in power['componentWeights'].items()},
              'teams': [{**{k: t[k] for k in ['id', 'abbr', 'name', 'record', 'gamesAvailable', 'factors']},
                         'scoringMarginPerGame': scoring_margin(t, week)} for t in snapshot['teams']],
              'power': [{k: t[k] for k in ['id', 'rank', 'rating', 'contributions']}
                        for t in power['teams']], 'games': games}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False) + '\n')
    temporary.replace(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    base = ROOT / 'game_summaries/nflverse'
    archive = args.archive or base / json.loads((base / 'weekly-latest.json').read_text())['archive']
    print(publish(archive, args.output))
