"""Nested chronological replay of v3 candidates. Development evidence only.

For each 2018..2025 outer season, select on preceding three seasons' rolling
predictions. Those predictions were themselves fitted on strictly earlier
seasons. Model families were designed after inspecting recent years: this
repairs parameter-selection leakage, not research-design hindsight.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning

from research.team_power_flexible import rolling, loss
from research.build_team_seasons import save_json

ROOT=Path(__file__).resolve().parents[1]


def select_candidate(predictions,y,seasons,year,objective,eligible):
    mask=(seasons>=year-3)&(seasons<year)
    if not mask.any():raise ValueError('No prior validation seasons')
    return min(eligible,key=lambda i:loss(y[mask],predictions[i,mask],objective))


def paired_intervals(y,a,b,seasons,objective,seed=20261005):
    rng=np.random.default_rng(seed);years=np.unique(seasons);groups=[np.flatnonzero(seasons==s) for s in years]
    ds=[]
    for _ in range(4000):
        ix=np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))])
        ds.append(loss(y[ix],a[ix],objective)-loss(y[ix],b[ix],objective))
    return {'difference':loss(y,a,objective)-loss(y,b,objective),'lower':float(np.quantile(ds,.025)),
            'upper':float(np.quantile(ds,.975)),'method':'paired season-block bootstrap, 4000 draws; exploratory, eight seasons'}


def run(source, output=None):
    output=output or source.parent/'model-v4-nested';output.mkdir(exist_ok=True)
    protocol=json.loads((source/'protocol.json').read_text());meta=json.loads((source/'features.json').read_text())
    d=np.load(source/'features.npz');x,y,seasons,week=(d[k] for k in ('x','y','season','week'))
    plan={'outerYears':list(range(2018,2026)),'innerLookbackSeasons':3,'trainingStarts':2012,
          'candidateProtocolSha256':hashlib.sha256((source/'protocol.json').read_bytes()).hexdigest(),
          'featureSha256':hashlib.sha256((source/'features.npz').read_bytes()).hexdigest(),
          'codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'warning':'Retrospective development; candidate families designed after inspecting outcomes. NOT an untouched experiment.'}
    save_json(output/'protocol.json',plan)
    results={};exports={};selections={}
    for objective,key in [('margin','marginCandidates'),('probability','probabilityCandidates')]:
        specs=protocol[key];preds=[];valid=[];failures=[]
        for i,spec in enumerate(specs):
            try:idx,p=rolling(x,y,seasons,spec,objective,range(2015,2026))
            except ConvergenceWarning as error:
                failures.append({'candidate':i,'error':str(error)});continue
            preds.append(p);valid.append(spec)
            if i%15==0:print(objective,i,len(specs),flush=True)
        preds=np.array(preds);yy=y[idx];ss=seasons[idx];ww=week[idx]
        if failures:save_json(output/f'{objective}-failures.json',failures)
        families=sorted({s['family'] for s in valid})+['selected_nonbaseline']
        family_predictions={};choices={}
        for family in families:
            eligible=[i for i,s in enumerate(valid) if s['family']==family or
                      (family=='selected_nonbaseline' and s['family'] not in ('point_baseline','point_context'))]
            forecast=np.full(len(yy),np.nan);choices[family]={}
            for year in range(2018,2026):
                best=select_candidate(preds,yy,ss,year,objective,eligible);mask=ss==year
                forecast[mask]=preds[best,mask]
                choices[family][str(year)]={'spec':valid[best],'lastValidationSeason':year-1}
            family_predictions[family]=forecast[ss>=2018]
        mask=ss>=2018;yy=yy[mask];ss=ss[mask];ii=idx[mask]
        results[objective]={}
        for family,p in family_predictions.items():
            r={'loss':loss(yy,p,objective),'byYear':{str(year):loss(yy[ss==year],p[ss==year],objective) for year in range(2018,2026)}}
            r['differenceVsPoint']=paired_intervals(yy,p,family_predictions['point_baseline'],ss,objective)
            r['differenceVsPointWithContext']=paired_intervals(yy,p,family_predictions['point_context'],ss,objective)
            results[objective][family]=r
        selections[objective]=choices
        exports[objective]=[{'gameId':meta['games'][i],'season':int(seasons[i]),'week':int(week[i]),'margin':float(y[i]),
                             'predictions':{f:float(p[j]) for f,p in family_predictions.items()}} for j,i in enumerate(ii)]
        save_json(output/f'{objective}-predictions.json',exports[objective]);save_json(output/'results.json',results)
        save_json(output/'selections.json',selections)
    lines=['# Nested chronological replay','',plan['warning'],'',
           'For each season 2018–2025, select settings using only the preceding three seasons. Each validation forecast trains only on preceding seasons.','']
    for objective,rs in results.items():
        lines += [f'## {objective}','','| Family | Loss | Difference vs point | Season-block 95% interval | Seasons better |','|---|---:|---:|---|---:|']
        base=rs['point_baseline']['byYear']
        for f,r in rs.items():
            ci=r['differenceVsPoint'];wins=sum(v<base[k] for k,v in r['byYear'].items())
            lines.append(f"| {f} | {r['loss']:.4f} | {ci['difference']:+.4f} | [{ci['lower']:+.4f}, {ci['upper']:+.4f}] | {wins}/8 |")
    lines+=['','Lower is better. Margin loss is RMSE; probability loss is decisive-game log loss.',
            'selected_nonbaseline chooses the model family as well as its settings using earlier validation seasons.',
            'These intervals do not correct for research-design hindsight or repeated model-family exploration.',
            'Individual-family wins must not replace the outcome of the predeclared family-selection procedure.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines),flush=True)


if __name__=='__main__':run(ROOT/'game_summaries/nflverse/model-v3')
