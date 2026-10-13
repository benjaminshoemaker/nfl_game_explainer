"""Situation-specific factor rates and past-only QB continuity (round six).

No expected-next-starter information is assumed. QB features describe recent
observed usage, not injury reports or confirmation of the next starter.
"""
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import duckdb
import numpy as np
from api.lib.nflverse_season import team_key
from api.lib.team_season import measure
from research.team_power_experiments import make_features,FEATURE_NAMES
from research.team_power_model import load_records
from research.build_team_seasons import save_json

ROOT=Path(__file__).resolve().parents[1]
FILTERS={'early':'down in (1,2)','close':'qtr<=3 and abs(score_differential)<=14',
         'close_pass':"qtr<=3 and abs(score_differential)<=14 and dropback=1",
         'close_rush':"qtr<=3 and abs(score_differential)<=14 and dropback=0"}
QB_NAMES=['recent_qb_change','recent_qb_share','recent_qb_yards_per_dropback','recent_qb_interception_rate','recent_qb_history_games','recent_qb_missing']


def source_rows(path,year):
    with duckdb.connect() as c:
        c.execute('''create temp table p as select game_id,posteam,down,ydstogo,qtr,score_differential,
             case when lateral_reception=1 and passing_yards is not null then passing_yards else yards_gained end yards,
             case when qb_dropback=1 or qb_scramble=1 or sack=1 or play_type='pass' then 1 else 0 end dropback,
             coalesce(passer_player_id,case when qb_scramble=1 then rusher_player_id end) qb,interception
             from read_parquet(?) where season=? and season_type='REG' and play_type in ('run','pass')
             and coalesce(play_deleted,0)<>1 and coalesce(two_point_attempt,0)<>1''',[str(path),year])
        splits={}
        for name,condition in FILTERS.items():
            rows=c.execute(f'''select game_id,posteam,count(*),sum(yards),
              sum(case when yards >= ydstogo*(case when down=1 then .4 when down=2 then .6 else 1 end) then 1 else 0 end),
              sum(case when yards >= (case when dropback=1 then 20 else 10 end) then 1 else 0 end),
              count(*) filter(where yards is null or down is null or ydstogo is null)
              from p where {condition} group by game_id,posteam''').fetchall()
            splits[name]={(g,team_key(t)):(n,y,s,e,missing) for g,t,n,y,s,e,missing in rows}
        qbs=c.execute('''select game_id,posteam,qb,count(*),sum(yards),sum(coalesce(interception,0))
                    from p where dropback=1 group by game_id,posteam,qb''').fetchall()
    return splits,[(g,team_key(t),qb,n,y,ints) for g,t,qb,n,y,ints in qbs]


def qb_features(records,qbrows, *, by_team=False):
    by_game=defaultdict(list)
    for g,t,q,n,y,ints in qbrows:by_game[(g,t)].append((q,n,y,ints))
    history=defaultdict(list);team_history=defaultdict(list);result={}
    for year,week in sorted({(g['season'],g['week']) for g in records}):
        games=[g for g in records if (g['season'],g['week'])==(year,week)]
        # Score all games in a week BEFORE observing any game in that week.
        for g in games:
            vals={}
            for t in g['teams']:
                past=team_history[t['id']];recent=past[-1] if past else None
                if recent is None or recent['qb'] is None:
                    vals[t['homeAway']]=[0,0,0,0,0,1];continue
                qb=recent['qb'];rows=[r for r in history[qb] if r['season']>=year-2]
                n=sum(r['n'] for r in rows);yards=sum(r['yards'] for r in rows);ints=sum(r['ints'] for r in rows)
                # Plain historical rates + sample size, no fitted EPA or
                # future roster identity. Regress small samples in the model.
                vals[t['homeAway']]=[float(len(past)>1 and qb!=past[-2]['qb']),recent['share'],yards/n if n else 0,
                                      ints/n if n else 0,len(rows),float(n==0)]
            result[g['gameId']]=({t['id']: vals[t['homeAway']] for t in g['teams']} if by_team else (np.array(vals['home'])-vals['away']).tolist())
        for g in games:
            for t in g['teams']:
                rows=by_game.get((g['gameId'],t['id']),[]);known=[r for r in rows if r[0] and r[2] is not None]
                total=sum(r[1] for r in rows);lead=max(known,key=lambda r:r[1]) if known else None
                team_history[t['id']].append({'qb':lead[0] if lead else None,'share':lead[1]/total if lead and total else 0})
                for qb,n,yards,ints in known:history[qb].append({'season':year,'n':n,'yards':yards,'ints':ints})
    return result


def build(base):
    out=base/'model-v6-situation';out.mkdir(exist_ok=True)
    records,inputs=load_records(base);records=[g for g in records if g['season']<=2025]
    all_splits={k:{} for k in FILTERS};qbs=[]
    for year in range(2011,2026):
        path=Path(f'/tmp/nfl_game_explainer_pbp_{year}.parquet');splits,rows=source_rows(path,year)
        qbs+=rows
        for k in FILTERS:all_splits[k].update(splits[k])
        inputs.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    meta=json.loads((base/'model-v3/features.json').read_text());d=np.load(base/'model-v3/features.npz')
    arrays=[d['x']];columns=list(meta['columns']);groups=dict(meta['groups'])
    for name,split in all_splits.items():
        modified=copy.deepcopy(records)
        for g in modified:
            for t in g['teams']:
                row=split.get((g['gameId'],t['id']))
                for k,j in [('success_rate',2),('yards_per_play',1),('explosive_rate',3)]:
                    t['factors'][k]=measure(row[j] or 0,row[0],['missing_state_inputs'] if row[4] else []) if row else measure(0,0)
        rows=make_features(modified,{'priorGames':8,'profile':'uniform','halfLife':8})
        assert [r['gameId'] for r in rows]==meta['games']
        selected=[0,1,2,8,9,10,16,17,18]
        groups[name]=list(range(len(columns),len(columns)+len(selected)))
        columns.extend(name+'_'+FEATURE_NAMES[i] for i in selected);arrays.append(np.array([r['x'] for r in rows])[:,selected])
        print('Built '+name,flush=True)
    qb=qb_features(records,qbs);groups['qb_history']=list(range(len(columns),len(columns)+len(QB_NAMES)))
    columns+=QB_NAMES;arrays.append(np.array([qb[g] for g in meta['games']]))
    x=np.column_stack(arrays)
    assert np.isfinite(x).all()
    np.savez_compressed(out/'features.npz',x=x,y=d['y'],season=d['season'],week=d['week'])
    save_json(out/'features.json',{'columns':columns,'groups':groups,'games':meta['games'],'inputs':inputs,
               'codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'limits':['historical usage is not next-start confirmation','no injuries/odds/WP/EPA','situation filters are descriptive, not an expected-points model']})
    print(x.shape,flush=True)


if __name__=='__main__':build(ROOT/'game_summaries/nflverse')
