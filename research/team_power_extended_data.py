"""V3 research matrices. Whitelisted, non-market, strict earlier-week inputs."""
import copy
import csv
import hashlib
import json
from pathlib import Path

import duckdb
import numpy as np

from api.lib.nflverse_season import team_key
from api.lib.team_season import measure
from research.team_power_model import load_records
from research.team_power_experiments import make_features, FEATURE_NAMES
from research.build_team_seasons import save_json

ROOT=Path(__file__).resolve().parents[1]


def split_efficiency(path, season):
    # Reuse the app's 40/60/100 success and 20/10 explosive definitions.
    with duckdb.connect() as conn:
        rows=conn.execute('''with plays as (
            select game_id,posteam,down,ydstogo,
              case when lateral_reception=1 and passing_yards is not null then passing_yards else yards_gained end yards,
              case when qb_dropback=1 or qb_scramble=1 or sack=1 or play_type='pass' then 'pass' else 'rush' end kind
            from read_parquet(?) where season=? and season_type='REG'
              and play_type in ('run','pass') and coalesce(play_deleted,0)<>1 and coalesce(two_point_attempt,0)<>1)
            select game_id,posteam,kind,count(*),sum(yards),
              sum(case when yards >= ydstogo*(case when down=1 then .4 when down=2 then .6 else 1 end) then 1 else 0 end),
              sum(case when yards >= (case when kind='pass' then 20 else 10 end) then 1 else 0 end),
              count(*) filter(where yards is null or down not in (1,2,3,4) or down is null or ydstogo is null)
            from plays group by game_id,posteam,kind''',[str(path),season]).fetchall()
    return {(g,team_key(t),kind):{'plays':n,'yards':yards,'success':success,'explosives':explosives,'missing':missing}
            for g,t,kind,n,yards,success,explosives,missing in rows}


def revised_records(records, splits, variant):
    output=copy.deepcopy(records)
    for g in output:
        for t in g['teams']:
            f=t['factors'];c=t['counters']
            if variant in ('pass','rush'):
                row=splits.get((g['gameId'],t['id'],variant))
                for key,count in [('success_rate','success'),('yards_per_play','yards'),('explosive_rate','explosives')]:
                    f[key]=measure(row[count] or 0,row['plays'],['missing_split_inputs'] if row['missing'] else []) if row else measure(0,0)
            elif variant=='opportunity':
                # Retain source reliability gates rather than filling gaps.
                for key,den in [('turnovers','Drives Count'),('penalties','Plays'),('non_offensive_points','Drives Count')]:
                    reasons=list(f[key]['reasons'])
                    if den=='Drives Count' and not f['field_position']['usable']:
                        reasons.append('unreliable_drive_denominator')
                    f[key]=measure(f[key]['numerator'],c[den],reasons)
    return output


def schedule_context(path):
    # Actual starting QB, actual weather, and all odds columns are excluded.
    output={}
    for r in csv.DictReader(path.open()):
        if r['game_type']!='REG':continue
        rest=[]
        for side in ('home','away'):
            v=r.get(side+'_rest','')
            rest.append(float(v) if v else None)
        output[r['game_id']]={'neutral':float(r['location']=='Neutral'),
                            'restDifference':min(rest[0],21)-min(rest[1],21) if all(v is not None for v in rest) else 0.,
                            'restMissing':float(any(v is None for v in rest))}
    return output


def build(directory):
    records,inputs=load_records(directory)
    # Do not inspect/use 2026 outcomes during development in this builder.
    records=[g for g in records if g['season']<=2025]
    output=directory/'model-v3';output.mkdir(exist_ok=True)
    splits={}
    for year in range(2011,2026):
        path=Path(f'/tmp/nfl_game_explainer_pbp_{year}.parquet')
        splits.update(split_efficiency(path,year))
        inputs.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    schedule=directory/'sources/games.csv';context=schedule_context(schedule)
    inputs.append({'path':str(schedule),'sha256':hashlib.sha256(schedule.read_bytes()).hexdigest()})
    columns=[];arrays=[];reference=None;groups={}
    # Multiple stabilization strengths permit regularized models to learn
    # factor-specific mixtures instead of enforcing one reliability profile.
    configs=[{'priorGames':p,'profile':'uniform','halfLife':h} for p,h in [(2,None),(8,None),(32,None),(8,4),(8,8)]]
    for variant in ('original','pass','rush','opportunity'):
        source=records if variant=='original' else revised_records(records,splits,variant)
        for config in configs:
            rows=make_features(source,config)
            identity=[r['gameId'] for r in rows]
            if reference is None:reference=rows
            assert identity==[r['gameId'] for r in reference]
            if variant=='original':selected=list(range(25))
            elif variant in ('pass','rush'):selected=[0,1,2,8,9,10,16,17,18]
            else:selected=[4,6,7,12,14,15,20,22,23]
            tag=f"{variant}_p{config['priorGames']}_h{config['halfLife']}"
            groups[tag]=list(range(len(columns),len(columns)+len(selected)))
            columns.extend(tag+'_'+FEATURE_NAMES[i] for i in selected)
            arrays.append(np.array([r['x'] for r in rows])[:,selected])
            print('Built '+tag,flush=True)
    groups['context']=list(range(len(columns),len(columns)+3))
    columns+=['restDifference','neutral','restMissing']
    arrays.append(np.array([[context[r['gameId']][k] for k in ('restDifference','neutral','restMissing')] for r in reference]))
    x=np.column_stack(arrays)
    if not np.isfinite(x).all():raise ValueError('Non-finite features')
    np.savez_compressed(output/'features.npz',x=x,y=np.array([r['margin'] for r in reference]),season=np.array([r['season'] for r in reference]),week=np.array([r['week'] for r in reference]))
    save_json(output/'features.json',{'columns':columns,'groups':groups,'games':[r['gameId'] for r in reference],
               'inputs':inputs,'codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'latestInputWeeks':[r['latestInputWeek'] for r in reference],
               'limitations':['retrospective corrected snapshots','no odds/WP/QB starters/weather','per-drive turnovers include return turnovers as a team rate, not offensive turnover probability',
                              'drive denominator conservatively gated by drive-start coverage']})
    print(f'Saved {x.shape}',flush=True)


if __name__=='__main__':build(ROOT/'game_summaries/nflverse')
