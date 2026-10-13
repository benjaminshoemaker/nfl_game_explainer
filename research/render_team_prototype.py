"""Build the review from the last successful publication, preserving old snapshots."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text()) if path.exists() else None


def public_payload(value):
    """Keep public provenance without exposing the operator's local directories."""
    if isinstance(value, dict):
        return {k:public_payload(v) for k,v in value.items()}
    if isinstance(value, list):
        return [public_payload(v) for v in value]
    if isinstance(value, str) and value.startswith(('/Users/', '/tmp/', '/private/')):
        return Path(value).name
    return value


def render(source=ROOT/'game_summaries/nflverse', output=None, current_archive=None, public_mode=False):
    def link(path):
        if public_mode:
            return '/team-data/' + str(path.relative_to(source/'weekly-archive'))
        return os.path.relpath(path, output.parent)

    output = output or source/'team-seasons-review.html'
    data = {}
    for year, week in [(2024,18), (2025,18), (2026,3)]:
        value = load(source/f'{year}-week-{week}.json')
        if value:
            data[str(year)] = value
    latest = load(current_archive/'manifest.json') if current_archive else load(source/'weekly-latest.json')
    active = source/latest['archive'] if latest else None
    if active:
        year, week = latest['season'], latest['throughWeek']
        data[str(year)] = load(active/'snapshots'/f'{year}-week-{week}.json')
    if not data:
        raise ValueError('Build nflverse season snapshots first')
    power = {}
    for year, snapshot in data.items():
        location = active/'snapshots' if active and int(year)==latest['season'] else source
        value = load(location/f"{year}-week-{snapshot['throughWeek']}-power.json")
        if value:
            power[year] = value
    model = load(source/'model/results.json')
    evidence = None
    a = load(source/'model-v7-audit/ablation.json')
    comparison = load(source/'model-v6-situation/stronger-baseline-audit.json')
    if a and comparison:
        c = comparison['selected_nonbaseline']['fixed_v2']
        evidence = {'full':a['fullRmse'], 'baseline':a['fullRmse']-c['difference'],
                    'pointQb':a['pointQbRmse'], 'interval':c}
    weekly = None
    if active:
        replay_paths = sorted((source/'weekly-archive').glob('*/manifest.json'))
        replays = []
        for p in replay_paths:
            m = load(p)
            if m['mode']=='replay' and (p.parent/'checksums.json').exists():
                replays.append({'season':m['season'], 'week':m['throughWeek']+1,
                    'evaluation':load(p.parent/'evaluation.json'),
                    'report':link(p.parent/'REPORT.md')})
        weekly = {'manifest':latest, 'status':{'status':'ok'} if current_archive else load(source/'weekly-status.json'),
            'predictions':load(active/'predictions.json'),
            'prospective':load(active/'prospective-results.json'),
            'replay':replays[-1] if replays else None,
            'archive':link(active/'predictions.json')}
    html = (ROOT/'prototypes/team-seasons.html').read_text()
    if public_mode:
        html = html.replace('Season research prototype', 'Teams &amp; power rankings')
        html = html.replace('<nav>', '<nav><a href="/">Games</a>', 1)
    for marker, payload in [('/*SNAPSHOTS*/{}',data), ('/*MODEL*/null',model),
        ('/*POWER*/{}',power), ('/*EVIDENCE*/null',evidence),
        ('/*SCHEDULE_AUDIT*/null',load(source/'model-v8-schedule/results.json')), ('/*WEEKLY*/null',weekly)]:
        html = html.replace(marker,json.dumps(public_payload(payload) if public_mode else payload,separators=(',',':'),allow_nan=False).replace('</','<\\/'))
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary = output.with_suffix('.html.tmp')
    temporary.write_text(html)
    temporary.replace(output)
    return output


if __name__ == '__main__':
    print(render())
