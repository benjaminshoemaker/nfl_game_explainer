"""Export an audited weekly publication into the deployable public directory.

Only explicit public artifacts are copied. Raw PBP, source CSVs, private paths,
code snapshots and development files stay in the research archive.
"""
import argparse
import json
from pathlib import Path
import shutil
from research.render_team_prototype import render, public_payload
from research.weekly_team_ratings import read, verify_archive, digest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = ('predictions.json', 'evaluation.json', 'prospective-results.json',
                'frozen-margin-model.json', 'frozen-point-baseline.json', 'REPORT.md')


def export(source, output):
    source, output = source.resolve(), output.resolve()
    latest = read(source/'weekly-latest.json')
    active = source/latest['archive']
    verify_archive(active)
    output.mkdir(parents=True, exist_ok=True)
    for manifest in sorted((source/'weekly-archive').glob('*/manifest.json')):
        run = manifest.parent
        if not (run/'checksums.json').exists():
            continue
        verify_archive(run)
        destination = output/'team-data'/run.name
        destination.mkdir(parents=True, exist_ok=True)
        for name in PUBLIC_FILES:
            path = run/name
            if path.exists():
                target = destination/name
                if target.exists() and target.read_bytes() != path.read_bytes():
                    raise ValueError(f'Refuse to replace published archive: {target}')
                shutil.copy2(path, target)
        # Original inputs remain local; names/checksums/source URLs are public.
        (destination/'manifest.json').write_text(json.dumps(public_payload(read(manifest)), indent=2)+'\n')
        checksums = {p.name:digest(p) for p in sorted(destination.iterdir())
                     if p.is_file() and p.name!='checksums.json'}
        (destination/'checksums.json').write_text(json.dumps(checksums,indent=2)+'\n')
    render(source, output/'team-seasons.html', public_mode=True)
    provenance = {'season':latest['season'], 'throughWeek':latest['throughWeek'],
                  'archive':latest['archive'].replace('weekly-archive/','/team-data/'),
                  'publishedAt':latest['publishedAt'],
                  'htmlSha256':digest(output/'team-seasons.html'),
                  'modelSha256':read(active/'predictions.json')['modelSha256'],
                  'sourceArchiveChecksumsSha256':digest(active/'checksums.json')}
    (output/'team-data/publication.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return provenance


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'game_summaries/nflverse')
    parser.add_argument('--output',type=Path,default=ROOT/'public')
    args=parser.parse_args()
    print(json.dumps(export(args.source,args.output),indent=2))
