"""Strengthen the comparator without changing the v4 candidate predictions."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from research.team_power_model import load_records
from research.team_power_flexible import rolling,loss
from research.team_power_nested import select_candidate,paired_intervals
from research.build_team_seasons import save_json

ROOT=Path(__file__).resolve().parents[1]


def fit_strength(games,ids,cutoff,prior,prior_home,pg,half,venues):
    if any(g['week']>=cutoff for g in games):raise ValueError('Future game in strength fit')
    n=len(ids);index={t:i for i,t in enumerate(ids)}
    a=np.diag([pg+2.]*n+[16.]);b=np.r_[np.zeros(n) if prior is None else pg*.5*prior,16*prior_home]
    for g in games:
        h=next(t for t in g['teams'] if t['homeAway']=='home');v=next(t for t in g['teams'] if t['homeAway']=='away')
        x=np.zeros(n+1);x[index[h['id']]]=1;x[index[v['id']]]=-1;x[-1]=venues[g['gameId']]
        w=1 if half is None else 2**(-(cutoff-1-g['week'])/half)
        a+=w*np.outer(x,x);b+=w*x*(h['score']-v['score'])
    beta=np.linalg.solve(a,b);beta[:n]-=beta[:n].mean()
    return beta[:n],beta[-1]


def features(records,pg,half,venues,rest):
    ids=sorted({t['id'] for g in records for t in g['teams']});ix={t:i for i,t in enumerate(ids)}
    previous=None;home=2.5;rows=[]
    for year in sorted({g['season'] for g in records}):
        gs=[g for g in records if g['season']==year]
        for week in sorted({g['week'] for g in gs}):
            strength,hfa=fit_strength([g for g in gs if g['week']<week],ids,week,previous,home,pg,half,venues)
            for g in gs:
                if g['week']!=week:continue
                h=next(t for t in g['teams'] if t['homeAway']=='home');a=next(t for t in g['teams'] if t['homeAway']=='away')
                rows.append([strength[ix[h['id']]]-strength[ix[a['id']]],venues[g['gameId']]*hfa,rest[g['gameId']]])
        previous,home=fit_strength(gs,ids,max(g['week'] for g in gs)+1,previous,home,pg,half,venues)
    return np.array(rows)


def predict(x,y,seasons,alpha,use_rest):
    ps=[];indices=[]
    for year in range(2015,2026):
        train=(seasons>=2012)&(seasons<year);test=seasons==year
        # Preserve exact neutral-site symmetry: no arbitrary home intercept.
        xx=x if use_rest else x[:,:2]
        model=make_pipeline(StandardScaler(with_mean=False),Ridge(alpha=alpha,fit_intercept=False))
        model.fit(xx[train],y[train]);ps.extend(model.predict(xx[test]));indices.extend(np.flatnonzero(test))
    return np.array(indices),np.array(ps)


def run(base):
    out=base/'model-v5-baseline';out.mkdir(exist_ok=True)
    records,inputs=load_records(base);records=[g for g in records if g['season']<=2025]
    meta=json.loads((base/'model-v3/features.json').read_text());d=np.load(base/'model-v3/features.npz')
    x,y,seasons=(d[k] for k in ('x','y','season'))
    assert [g['gameId'] for g in sorted(records,key=lambda g:(g['season'],g['week'],records.index(g)))]==meta['games']
    schedule=list(csv.DictReader((base/'sources/games.csv').open()))
    venues={r['game_id']:float(r['location']!='Neutral') for r in schedule}
    rest={r['game_id']:min(float(r['home_rest'] or 7),21)-min(float(r['away_rest'] or 7),21) for r in schedule}
    save_json(out/'protocol.json',{'priorGames':[2,8,32],'halfLife':[None,4,8],'alphas':[1,10,100],
        'venueFit':'joint team strength and home advantage; 16 pseudo-games around previous season HFA, initial 2.5',
        'selection':'preceding three validation seasons only','candidate':'unchanged v4 selected_nonbaseline',
        'warning':'Retrospective exploratory audit, not untouched evidence','codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'inputs':inputs})
    ps=[];specs=[]
    for pg in (2,8,32):
        for half in (None,4,8):
            xx=features(records,pg,half,venues,rest)
            for alpha in (1,10,100):
                for use_rest in (False,True):
                    idx,p=predict(xx,y,seasons,alpha,use_rest);ps.append(p)
                    specs.append({'jointVenue':True,'priorGames':pg,'halfLife':half,'alpha':alpha,'rest':use_rest})
            print('joint baseline',pg,half,flush=True)
    # Include original baseline candidates: the expanded selector can retain
    # one of them if earlier validation favors it.
    original=json.loads((base/'model-v3/protocol.json').read_text())['marginCandidates']
    fixed=None
    for spec in original:
        if spec['family'] not in ('point_baseline','point_context'):continue
        idx,p=rolling(x,y,seasons,spec,'margin',range(2015,2026));ps.append(p);specs.append(spec)
        if spec['family']=='point_baseline' and spec['columns']==[meta['groups']['original_p8_h8'][-1]] and spec['strength']==10:fixed=p
    ps=np.array(ps);yy=y[idx];ss=seasons[idx];nested=np.full(len(yy),np.nan);choices={}
    for year in range(2018,2026):
        chosen=select_candidate(ps,yy,ss,year,'margin',range(len(ps)));mask=ss==year;nested[mask]=ps[chosen,mask]
        choices[str(year)]=specs[chosen]
    mask=ss>=2018;ii=idx[mask];yy=yy[mask];ss=ss[mask]
    v4=json.loads((base/'model-v4-nested/margin-predictions.json').read_text())
    assert [meta['games'][i] for i in ii]==[r['gameId'] for r in v4]
    candidate=np.array([r['predictions']['selected_nonbaseline'] for r in v4])
    baselines={'expanded_nested':nested[mask],'fixed_v2':fixed[mask],
               'original_nested':np.array([r['predictions']['point_baseline'] for r in v4])}
    result={'candidateRmse':loss(yy,candidate,'margin'),'baselines':{},'selections':choices}
    for name,p in baselines.items():
        result['baselines'][name]={'rmse':loss(yy,p,'margin'),'candidateDifference95':paired_intervals(yy,candidate,p,ss,'margin'),
             'byYear':{str(s):{'baseline':loss(yy[ss==s],p[ss==s],'margin'),'candidate':loss(yy[ss==s],candidate[ss==s],'margin')} for s in range(2018,2026)}}
    save_json(out/'results.json',result)
    save_json(out/'predictions.json',[{'gameId':meta['games'][i],'margin':float(yy[j]),'candidate':float(candidate[j]),
                'baselines':{k:float(p[j]) for k,p in baselines.items()}} for j,i in enumerate(ii)])
    lines=['# Stronger baseline audit','',f"Unchanged candidate RMSE: {result['candidateRmse']:.4f}",'',
           '| Comparator | RMSE | Candidate difference | Season-block 95% interval |','|---|---:|---:|---|']
    for name,r in result['baselines'].items():
        ci=r['candidateDifference95'];lines.append(f"| {name} | {r['rmse']:.4f} | {ci['difference']:+.4f} | [{ci['lower']:+.4f}, {ci['upper']:+.4f}] |")
    lines += ['', 'Negative difference favors the candidate. Expanded baseline jointly estimates venue advantage and team strengths, handles neutral sites, and may include rest.',
              'Fixed v2 is a deliberately strong sensitivity comparator chosen in earlier research; it is not independent evidence.',
              'This audit remains retrospective and exploratory. No fresh unseen-season superiority claim follows.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines),flush=True)


if __name__=='__main__':run(ROOT/'game_summaries/nflverse')
