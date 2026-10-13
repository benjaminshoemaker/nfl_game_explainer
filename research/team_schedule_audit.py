"""Bounded retrospective schedule-adjustment audit; never replaces frozen model."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from research.team_power_experiments import ratings, make_features
from research.team_power_model import load_records
from research.team_power_flexible import rolling,loss
from research.team_power_nested import select_candidate,paired_intervals
from research.team_power_baseline_audit import fit_strength
from research.team_schedule_strength import schedule_strength
from research.build_team_seasons import save_json
ROOT=Path(__file__).resolve().parents[1]


def schedule_features(records, ids, venues):
    prior=None;home=2.5;rows={};contexts={}
    for year in sorted({g['season'] for g in records}):
        games=[g for g in records if g['season']==year]
        for week in sorted({g['week'] for g in games}):
            sos=schedule_strength([g for g in games if g['week']<week],ids,week,prior,home,venues)
            for g in games:
                if g['week']!=week:continue
                h=next(t['id'] for t in g['teams'] if t['homeAway']=='home')
                a=next(t['id'] for t in g['teams'] if t['homeAway']=='away')
                hs,vs=sos[h],sos[a]
                rows[g['gameId']]=[(hs['value'] or 0)-(vs['value'] or 0),float(hs['value'] is None)-float(vs['value'] is None)]
                contexts[g['gameId']]={'home':hs['rank'],'away':vs['rank'],'pool':hs['rankPool']}
        prior,home=fit_strength(games,ids,max(g['week'] for g in games)+1,prior,home,8,8,venues)
        print('Schedule features',year,flush=True)
    return rows,contexts


def opponent_off_features(records,ids):
    prior=points=None;rows={};ix={t:i for i,t in enumerate(ids)}
    cfg={'priorGames':8,'profile':'uniform','halfLife':8}
    for year in sorted({g['season'] for g in records}):
        games=[g for g in records if g['season']==year]
        for week in sorted({g['week'] for g in games}):
            _,_,values=ratings([g for g in games if g['week']<week],ids,week,prior,points,cfg,adjust_opponents=False)
            for g in games:
                if g['week']!=week:continue
                h=next(t['id'] for t in g['teams'] if t['homeAway']=='home');a=next(t['id'] for t in g['teams'] if t['homeAway']=='away')
                rows[g['gameId']]=(values[ix[h]]-values[ix[a]]).tolist()
        prior,points,_=ratings(games,ids,max(g['week'] for g in games)+1,prior,points,cfg)
    return rows


def run(base):
    out=base/'model-v8-schedule';out.mkdir(exist_ok=True)
    protocol={'status':'Retrospective exploratory audit; all evaluation years previously inspected',
        'outerSeasons':list(range(2018,2026)),'selection':'Previous three seasons rolling validation; candidates include incumbent',
        'training':'2012 through preceding season only; all features strictly earlier NFL weeks',
        'alternatives':['priorGames 2 and 4, half-life 8','current-opponent effect amplified 1.5x and 2x','explicit leave-focal-team-out schedule strength'],
        'ridgeStrengths':[10,100,1000],'incumbent':'Frozen recipe p8 h8 QB-history Ridge1000, refit chronologically (not final 2026 coefficients applied backward)',
        'subgroups':'Weeks 1–5 and 6+; team-games with prior schedule rank 1–8 or bottom 8, excluding no-history schedules',
        'promotionRule':'No automatic deployment. Require selected procedure to improve incumbent with season-block interval below zero, beat strong point baseline, and improve in at least 6/8 seasons. Then freeze and test prospectively.',
        'codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save_json(out/'protocol.json',protocol)
    records,inputs=load_records(base);records=[g for g in records if g['season']<=2025]
    meta=json.loads((base/'model-v6-situation/features.json').read_text())
    with np.load(base/'model-v6-situation/features.npz') as data:
        full=data['x'];y=data['y'];seasons=data['season'];weeks=data['week']
    model=json.loads((ROOT/'research/models/frozen-margin-model.json').read_text())
    x=full[:,model['spec']['columns']];ids=sorted({t['id'] for g in records for t in g['teams']})
    venues={r['game_id']:float(r['location']!='Neutral') for r in csv.DictReader((base/'sources/games.csv').open())}
    cache=out/'diagnostic-features.npz';cache_meta=out/'diagnostic-features.json'
    source_hashes={item['path']:hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() for item in inputs}
    source_hashes['schedule']=hashlib.sha256((base/'sources/games.csv').read_bytes()).hexdigest()
    source_hashes['source_matrix']=hashlib.sha256((base/'model-v6-situation/features.npz').read_bytes()).hexdigest()
    source_hashes['builder']=protocol['codeSha256']
    source_hashes['schedule_code']=hashlib.sha256((ROOT/'research/team_schedule_strength.py').read_bytes()).hexdigest()
    if cache.exists() and cache_meta.exists() and json.loads(cache_meta.read_text())['hashes']==source_hashes:
        d=np.load(cache);schedule=d['schedule'];off=d['off'];low2=d['low2'];low4=d['low4'];contexts=json.loads(cache_meta.read_text())['contexts']
    else:
        sf,contexts=schedule_features(records,ids,venues)
        schedule=np.array([sf[g] for g in meta['games']])
        off_rows=opponent_off_features(records,ids);off=np.array([off_rows[g] for g in meta['games']])
        reduced=[]
        for pg in (2,4):
            rows=make_features(records,{'priorGames':pg,'profile':'uniform','halfLife':8})
            assert [r['gameId'] for r in rows]==meta['games']
            reduced.append(np.array([r['x'] for r in rows]));print('Lower-prior features',pg,flush=True)
        low2,low4=reduced
        np.savez_compressed(cache,schedule=schedule,off=off,low2=low2,low4=low4)
        save_json(cache_meta,{'hashes':source_hashes,'contexts':contexts,'gameIds':meta['games']})
    matrices={'incumbent':x,'prior2':np.c_[low2,x[:,25:]],'prior4':np.c_[low4,x[:,25:]],
              'opponent1.5':np.c_[off+1.5*(x[:,:25]-off),x[:,25:]],
              'opponent2':np.c_[off+2*(x[:,:25]-off),x[:,25:]],'explicit_schedule':np.c_[x,schedule]}
    specs=[];pred=[]
    for name,xx in matrices.items():
        for alpha in ([1000] if name=='incumbent' else [10,100,1000]):
            spec={'family':name,'columns':list(range(xx.shape[1])),'kind':'ridge','strength':alpha}
            idx,p=rolling(xx,y,seasons,spec,'margin',range(2015,2026));pred.append(p);specs.append(spec)
    pred=np.array(pred);yy=y[idx];ss=seasons[idx];ww=weeks[idx];selected=np.full(len(yy),np.nan);choices={}
    for year in range(2018,2026):
        i=select_candidate(pred,yy,ss,year,'margin',range(len(specs)));mask=ss==year
        selected[mask]=pred[i,mask];choices[str(year)]=specs[i]
    keep=ss>=2018;test_ids=[meta['games'][i] for i in idx[keep]];yy=yy[keep];ss=ss[keep];ww=ww[keep]
    forecasts={'incumbent_recipe':pred[0,keep],'selected_schedule_procedure':selected[keep]}
    saved={r['gameId']:r for r in json.loads((base/'model-v5-baseline/predictions.json').read_text())}
    forecasts['strong_point_baseline']=np.array([saved[g]['baselines']['fixed_v2'] for g in test_ids])
    old={r['gameId']:r for r in json.loads((base/'model-v6-situation/nested/margin-predictions.json').read_text())}
    forecasts['previous_annual_selection']=np.array([old[g]['predictions']['selected_nonbaseline'] for g in test_ids])
    # Team-oriented residuals permit an easy-schedule overrating diagnostic.
    team_ix=[];signs=[];difficult=[]
    for i,g in enumerate(test_ids):
        c=contexts[g]
        for side,sign in [('home',1),('away',-1)]:
            if c[side] is None or c['pool']!=32:continue
            team_ix.append(i);signs.append(sign);difficult.append('hard' if c[side]<=8 else 'easy' if c[side]>24 else 'middle')
    ti=np.array(team_ix);sign=np.array(signs);difficulty=np.array(difficult)
    result={'protocol':protocol,'selections':choices,'models':{},'candidateScores':[]}
    for name,p in forecasts.items():
        subgroups={}
        for label,mask in [('early',ww<=5),('later',ww>5)]:
            subgroups[label]={'games':int(mask.sum()),'rmse':loss(yy[mask],p[mask],'margin')}
        for label in ('easy','hard'):
            m=difficulty==label;error=sign[m]*(p[ti[m]]-yy[ti[m]])
            subgroups[label]={'teamGames':int(m.sum()),'rmse':float(np.sqrt(np.mean(error**2))),
                'meanOverpredictionPoints':float(np.mean(error))}
        result['models'][name]={'rmse':loss(yy,p,'margin'),'subgroups':subgroups,
            'byYear':{str(year):loss(yy[ss==year],p[ss==year],'margin') for year in range(2018,2026)}}
    candidate=forecasts['selected_schedule_procedure']
    result['comparisons']={name:paired_intervals(yy,candidate,p,ss,'margin') for name,p in forecasts.items() if name!='selected_schedule_procedure'}
    for i,spec in enumerate(specs):
        result['candidateScores'].append({'family':spec['family'],'alpha':spec['strength'],
            'rmse':loss(yy,pred[i,keep],'margin'),'status':'descriptive only; not valid for post-hoc winner selection'})
    wins=sum(result['models']['selected_schedule_procedure']['byYear'][str(y)]<result['models']['incumbent_recipe']['byYear'][str(y)] for y in range(2018,2026))
    result['seasonsImprovedVsIncumbent']=wins
    result['promotionGatePassed']=bool(result['comparisons']['incumbent_recipe']['upper']<0 and result['comparisons']['strong_point_baseline']['difference']<0 and wins>=6)
    result['decision']='Keep frozen model unchanged; prospective validation required for any replacement.'
    save_json(out/'results.json',result)
    save_json(out/'predictions.json',[{'gameId':g,'season':int(ss[i]),'week':int(ww[i]),'margin':float(yy[i]),'predictions':{k:float(v[i]) for k,v in forecasts.items()}} for i,g in enumerate(test_ids)])
    lines=['# Schedule adjustment audit','',protocol['status'],'',
           'Final 2026 coefficients are never evaluated backward. Incumbent means its fixed recipe, refitted on earlier seasons. Alternative settings/families are chosen on the previous three validation seasons.','',
           '| Procedure | All games RMSE | Weeks 1–5 | Weeks 6+ | Easy-schedule team-games | Hard-schedule team-games |',
           '|---|---:|---:|---:|---:|---:|']
    for name,r in result['models'].items():
        sg=r['subgroups'];lines.append(f"| {name} | {r['rmse']:.4f} | {sg['early']['rmse']:.4f} | {sg['later']['rmse']:.4f} | {sg['easy']['rmse']:.4f} | {sg['hard']['rmse']:.4f} |")
    lines+=['','Easy/hard groups are bottom/top eight schedules using strictly prior-week leave-focal-team-out opponent strength. Team-games are not independent observations; intervals resample seasons. No-history weeks are excluded from schedule groups.',f'','## Selected procedure versus comparators']
    for name,ci in result['comparisons'].items():lines.append(f"- {name}: RMSE difference {ci['difference']:+.4f}, exploratory 95% season-block interval [{ci['lower']:+.4f}, {ci['upper']:+.4f}].")
    lines += ['',f'Improved versus incumbent recipe in {wins}/8 seasons. Promotion gate passed: {result["promotionGatePassed"]}.',result['decision'],'',
        'Current-season focal games are excluded from schedule fits; prior-season ratings still include historical meetings. Schedule estimates have uncertainty and are conservative early. The search and intervals are exploratory, not multiplicity-adjusted or prospective proof. No FPI/DVOA comparison.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines),flush=True)

if __name__=='__main__':run(ROOT/'game_summaries/nflverse')
