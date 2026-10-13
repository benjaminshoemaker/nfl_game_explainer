"""Refresh audited season ratings and append pregame forecasts without refitting.

Use --replay-week only for explicitly retrospective checks. Market data is read
by evaluation, never by the frozen prediction function. Archives are local,
write-once by this program, checksum sealed, not an external timestamp service.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from api.lib.nflverse_season import team_key
from research.build_nflverse_seasons import build_season, ensure_file, SCHEDULE_URL, TEAMS_URL
from research.team_power_extended_data import schedule_context
from research.team_power_ratings import build, digest, predict_matchup, MODEL_PATH, ROOT
from research.render_team_prototype import render

BASELINE_PATH = ROOT / 'research/models/frozen-point-baseline.json'
DEFAULT_BASE = ROOT / 'game_summaries/nflverse'


def now_utc():
    return datetime.now(timezone.utc)


def read(path):
    return json.loads(path.read_text())


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def replace_json(path, value):
    temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    write_new(temp, value)
    temp.replace(path)


def kickoff(row):
    # nflverse schedule gametime is US Eastern, including DST transitions.
    if not row['gametime'] or not row['gameday']:
        raise ValueError(f"Missing kickoff: {row['game_id']}")
    return datetime.fromisoformat(row['gameday'] + 'T' + row['gametime']).replace(
        tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)


def final(row, at):
    return row['home_score'] != '' and row['away_score'] != '' and kickoff(row) < at


def completed_week(rows, at):
    weeks = sorted({int(r['week']) for r in rows})
    cutoff = 0
    for week in weeks:
        games = [r for r in rows if int(r['week']) == week]
        if week != cutoff + 1 or not all(final(r, at) for r in games):
            break
        cutoff = week
    if not cutoff:
        raise ValueError('No fully completed regular-season week; retain previous publication')
    return cutoff


def validate_coverage(snapshot, audit, rows, cutoff, at):
    expected = {r['game_id'] for r in rows if int(r['week']) <= cutoff}
    if not expected or not all(final(r, at) for r in rows if r['game_id'] in expected):
        raise ValueError('Requested cutoff includes unfinished games')
    if (snapshot['throughWeek'] != cutoff or audit['errors'] or
            audit['games'] != len(expected) or audit['expected'] != len(expected) or
            audit['scoring'] != len(expected) or audit['teams'] != 32):
        raise ValueError(f'Incomplete/scoring-invalid source coverage: {audit}')
    return expected


def forecasts(power, rows, contexts, model, baseline, at, retrospective=False):
    teams = {t['id']: t['features'] for t in power['teams']}
    output = []
    for row in rows:
        start = kickoff(row)
        if not retrospective and (start <= at or row['home_score'] != '' or row['away_score'] != ''):
            raise ValueError(f"Pregame cutoff missed: {row['game_id']}; use an explicit retrospective replay")
        if int(row['week']) != power['throughWeek'] + 1:
            raise ValueError('Forecast must use strictly previous-week inputs')
        home, away = (teams[team_key(row[k])] for k in ('home_team', 'away_team'))
        context = contexts[row['game_id']]
        margin = predict_matchup(home, away, model, rest_difference=context['restDifference'],
                                 neutral=context['neutral'], rest_missing=context['restMissing'])
        baseline_margin = baseline['intercept'] + sum(
            (home[k] - away[k]) * c for k, c in zip(baseline['featureNames'], baseline['coefficients']))
        values = {k: home[k] - away[k] for k in model['featureNames']}
        values.update(context)
        output.append({'gameId': row['game_id'], 'season': int(row['season']), 'week': int(row['week']),
                       'home': team_key(row['home_team']), 'away': team_key(row['away_team']),
                       'kickoff': start.isoformat(), 'model': margin, 'pointBaseline': baseline_margin,
                       'features': values})
    if not output:
        raise ValueError('No target games')
    if len({r['gameId'] for r in output}) != len(output):
        raise ValueError('Duplicate target games')
    return output


def score_predictions(predictions, schedule, at):
    by_id = {r['game_id']: r for r in schedule}
    scored, pending, missing_line = [], [], []
    for p in predictions:
        row = by_id.get(p['gameId'])
        if row is None or not final(row, at):
            pending.append(p['gameId'])
            continue
        actual = float(row['home_score']) - float(row['away_score'])
        try:
            line = float(row['spread_line']) if row.get('spread_line', '') else None
        except (TypeError, ValueError):
            line = None
        if line is None or not math.isfinite(line):
            missing_line.append(p['gameId'])
            line = None
        scored.append({**{k:p[k] for k in ('gameId','home','away','model','pointBaseline')},
                       **{k:p[k] for k in ('archive','publishedAt','modelSha256','baselineSha256') if k in p},
                       'actual':actual, 'vegas':line})
    matched = [r for r in scored if r['vegas'] is not None]
    metrics = {}
    for name in ('model', 'pointBaseline', 'vegas'):
        errors = [r[name] - r['actual'] for r in matched]
        decisive = [r for r in matched if r['actual'] != 0]
        metrics[name] = {'games':len(errors),
            'rmse':math.sqrt(sum(e*e for e in errors)/len(errors)) if errors else None,
            'mae':sum(abs(e) for e in errors)/len(errors) if errors else None,
            'winnerCorrect':sum(r[name]*r['actual']>0 for r in decisive),
            'winnerGames':len(decisive), 'tiesExcluded':len(matched)-len(decisive)}
    return {'metrics':metrics, 'games':scored, 'pending':pending, 'missingClosingLine':missing_line,
            'totalForecasts':len(predictions),
            'comparison':'Identical completed games with finite nflverse closing spread_line; positive = home favored. Winner accuracy excludes tied outcomes; a pick-em predicts neither winner.'}


def seed_history(base, work, season):
    for year in range(2011, season):
        candidates = list(base.glob(f'{year}-week-*-games.json'))
        if not candidates:
            raise ValueError(f'Missing audited historical season {year}')
        selected = max(candidates, key=lambda p:int(p.name.split('-')[2]))
        stem = selected.name.removesuffix('-games.json')
        for suffix in ('.json', '-games.json', '-audit.json', '-manifest.json'):
            shutil.copy2(base / (stem + suffix), work / (stem + suffix))
    (work / 'model-v6-situation').mkdir()
    shutil.copy2(base / 'model-v6-situation/features.npz', work / 'model-v6-situation/features.npz')


def seal(run):
    hashes = {str(p.relative_to(run)):digest(p) for p in sorted(run.rglob('*')) if p.is_file()}
    write_new(run / 'checksums.json', hashes)


def verify_archive(run):
    for name, expected in read(run / 'checksums.json').items():
        if digest(run / name) != expected:
            raise ValueError(f'Archive changed: {run / name}')


def earlier_forecasts(base, exclude=None):
    # First sealed pregame publication per game. Replays never enter the ledger.
    chosen = {}
    for path in sorted((base / 'weekly-archive').glob('*/predictions.json')):
        if path.parent == exclude or not (path.parent/'checksums.json').exists():
            continue
        data = read(path)
        if data['status'] != 'pregame':
            continue
        verify_archive(path.parent)
        for row in data['games']:
            if datetime.fromisoformat(data['publishedAt']) >= datetime.fromisoformat(row['kickoff']):
                raise ValueError(f'Invalid pregame timestamp in {path}')
            key = row['gameId']
            candidate = {**row, 'archive':str(path.relative_to(base)), 'publishedAt':data['publishedAt'],
                         **{k:data[k] for k in ('modelSha256','baselineSha256') if k in data}}
            if key not in chosen or candidate['publishedAt'] < chosen[key]['publishedAt']:
                chosen[key] = candidate
    return list(chosen.values())


def report_text(evaluation, status, season, week, cutoff):
    lines = [f'# {season} Week {week}: {status}', '', f'Inputs through Week {cutoff}. All margins are home minus away, in points.', '',
             'This model predicts scoring margin, not betting returns. nflverse closing spreads are the market benchmark; odds do not enter the model.', '',
             '| Predictor | RMSE ↓ | MAE ↓ | Winners (ties excluded) |', '|---|---:|---:|---:|']
    for name, m in evaluation['metrics'].items():
        rmse = f"{m['rmse']:.3f}" if m['rmse'] is not None else 'Pending'
        mae = f"{m['mae']:.3f}" if m['mae'] is not None else 'Pending'
        lines.append(f"| {name} | {rmse} | {mae} | {m['winnerCorrect']}/{m['winnerGames']} |")
    lines += ['', f"{len(evaluation['games'])}/{evaluation['totalForecasts']} finished; {len(evaluation['missingClosingLine'])} missing closing lines.", '',
              '| Game (away @ home) | Actual | Model | Point baseline | Closing line |', '|---|---:|---:|---:|---:|']
    for r in evaluation['games']:
        line = f"{r['vegas']:+.1f}" if r['vegas'] is not None else 'Missing'
        lines.append(f"| {r['away']} @ {r['home']} | {r['actual']:+.0f} | {r['model']:+.2f} | {r['pointBaseline']:+.2f} | {line} |")
    lines += ['', 'A single week is a small sample. A replay uses corrected data available now, strictly filtered to earlier weeks; it was not published before those games. The frozen coefficients were fit only through 2025. Past QB usage is not confirmed starter knowledge.', '',
              '[nflverse schedule definitions](https://nflreadr.nflverse.com/articles/dictionary_schedules.html)', '']
    return '\n'.join(lines)


def run_weekly(base=DEFAULT_BASE, season=2026, replay_week=None, input_dir=None):
    base = Path(base).resolve()
    at = now_utc()
    mode = 'replay' if replay_week else 'weekly'
    run = base / 'weekly-archive' / (at.strftime('%Y%m%dT%H%M%S%fZ') + '-' + mode)
    run.mkdir(parents=True, exist_ok=False)
    source = run / 'sources'
    source.mkdir()
    work = run / 'snapshots'
    work.mkdir()
    try:
        model, baseline = read(MODEL_PATH), read(BASELINE_PATH)
        if season != model['intendedFirstSeason'] or baseline['trainingSeasons'] != model['trainingSeasons']:
            raise ValueError('Only the frozen 2026 protocol is authorized; do not silently reuse in a later season')
        inputs = []
        files = [('games.csv', SCHEDULE_URL), ('teams.csv', TEAMS_URL)] + [
            (f'pbp_{y}.parquet', f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.parquet')
            for y in range(season-2, season+1)]
        for name, url in files:
            destination = source / name
            if input_dir is not None and (Path(input_dir) / name).exists():
                shutil.copy2(Path(input_dir) / name, destination)
            inputs.append({**ensure_file(destination, url, True), 'archivedAt':now_utc().isoformat(),
                           'acquisition':'local supplied snapshot' if input_dir is not None and (Path(input_dir)/name).exists() else 'download'})
        schedule = list(csv.DictReader((source / 'games.csv').open()))
        rows = [r for r in schedule if int(r['season']) == season and r['game_type'] == 'REG']
        cutoff = replay_week - 1 if replay_week else completed_week(rows, at)
        if cutoff < 1 or cutoff > 18:
            raise ValueError('Unsupported completed-week cutoff')
        targets = [r for r in rows if int(r['week']) == cutoff+1]
        if not replay_week and not targets and cutoff != 18:
            raise ValueError('Next week schedule unavailable')
        seed_history(base, work, season)
        (work / 'sources').mkdir()
        shutil.copy2(source / 'games.csv', work / 'sources/games.csv')
        pattern = str(source / 'pbp_{season}.parquet')
        snapshot = build_season(season, SimpleNamespace(output=work, schedule=source/'games.csv',
            teams=source/'teams.csv', pbp_pattern=pattern, fetch=False, through_week=cutoff))
        audit = read(work/f"{season}-week-{snapshot['throughWeek']}-audit.json")
        expected = validate_coverage(snapshot, audit, rows, cutoff, at)
        records = read(work/f'{season}-week-{cutoff}-games.json')
        if {g['gameId'] for g in records} != expected:
            raise ValueError('Extracted game IDs differ from completed schedule')
        power = build(work, season, cutoff, pbp_pattern=pattern)
        # Inputs, code, and both frozen formulas travel with each publication.
        shutil.copy2(MODEL_PATH, run/'frozen-margin-model.json')
        shutil.copy2(BASELINE_PATH, run/'frozen-point-baseline.json')
        for folder, paths in [('research', list((ROOT/'research').glob('*.py'))),
                              ('api/lib', list((ROOT/'api/lib').glob('*.py')))]:
            destination = run/'code'/folder
            destination.mkdir(parents=True)
            for path in paths:
                shutil.copy2(path, destination/path.name)
        published = now_utc()
        games = forecasts(power, targets, schedule_context(source/'games.csv'), model, baseline,
                          published, retrospective=bool(replay_week)) if targets else []
        predictions = {'status':'retrospective replay' if replay_week else 'pregame',
            'publishedAt':published.isoformat(), 'season':season, 'week':cutoff+1,
            'inputThroughWeek':cutoff, 'modelSha256':digest(MODEL_PATH),
            'baselineSha256':digest(BASELINE_PATH), 'games':games,
            'limits':['Local timestamped checksum archive, not externally attested publication',
                      'Only earlier-week outcomes enter features; no market inputs',
                      'Prior QB usage is not confirmed upcoming starter information']}
        write_new(run/'predictions.json', predictions)
        evaluation = score_predictions(games, schedule, published)
        write_new(run/'evaluation.json', evaluation)
        (run/'REPORT.md').write_text(report_text(evaluation, predictions['status'], season, cutoff+1, cutoff))
        previous = earlier_forecasts(base, exclude=run)
        write_new(run/'prospective-results.json', score_predictions(previous, schedule, published))
        manifest = {'status':'complete', 'mode':mode, 'season':season, 'throughWeek':cutoff,
            'createdAt':at.isoformat(), 'publishedAt':published.isoformat(), 'inputs':inputs,
            'coverage':audit, 'archive':str(run.relative_to(base)),
            'predictionCount':len(games), 'featurePolicy':'Completed games through prior week only; no odds, future outcomes or confirmed target-game QB'}
        write_new(run/'manifest.json', manifest)
        if not replay_week:
            # Keep a portable review with the exact publication, as well as the
            # JSON needed to reproduce all calculations.
            shutil.copy2(ROOT/'prototypes/team-seasons.html', run/'code/team-seasons.html')
            render(base, run/'review.html', current_archive=run)
        seal(run)
        verify_archive(run)
        if not replay_week:
            existing_review = base/'team-seasons-review.html'
            if existing_review.exists():
                history = base/'review-history'
                history.mkdir(exist_ok=True)
                shutil.copy2(existing_review, history/(run.name+'.html'))
            # Only small pointers change. All previously published artifacts remain.
            replace_json(base/'weekly-latest.json', manifest)
            replace_json(base/'weekly-status.json', {'status':'ok', 'checkedAt':now_utc().isoformat(),
                         'throughWeek':cutoff, 'archive':manifest['archive']})
            render(base)
        return run
    except Exception as error:
        failure = {'status':'failed', 'checkedAt':now_utc().isoformat(),
                   'error':f'{type(error).__name__}: {error}', 'archive':str(run.relative_to(base)),
                   'previousPublicationPreserved':True}
        write_new(run/'failure.json', failure)
        if not replay_week:
            replace_json(base/'weekly-status.json', failure)
            if (base/'weekly-latest.json').exists():
                try:
                    render(base)
                except (OSError, ValueError, KeyError):
                    pass  # The JSON failure remains visible to the scheduler.
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=DEFAULT_BASE)
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--replay-week', type=int, choices=range(2,19))
    parser.add_argument('--input-dir', type=Path, help='Optional existing source snapshot; never implies pregame availability for a replay')
    args = parser.parse_args()
    print(run_weekly(args.base, args.season, args.replay_week, args.input_dir))
