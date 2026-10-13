"""Second-round predictive experiments; never changes first-round artifacts.

All feature/model selection uses rolling-origin validation in 2018..2023.
2024..2025 is an already-inspected follow-up sample, NOT a fresh holdout.
"""
import argparse
from itertools import combinations
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from api.lib.team_season import FACTORS
from research.team_power_model import KEYS, load_records, metrics, bootstrap_delta
from research.build_team_seasons import save_json

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_YEARS = tuple(range(2018, 2024))
FOLLOWUP_YEARS = (2024, 2025)
ALPHAS = (10, 100, 1000)
CS = (.001, .01, .1, 1)
SIGNS = np.array([1 if f['higherIsBetter'] else -1 for f in FACTORS])
FEATURE_NAMES = KEYS + ['own_'+k for k in KEYS] + ['prevention_'+k for k in KEYS] + ['point_margin']
PROFILES = {'uniform': [2]*8, 'factor_specific': [2, 2, 2, 6, 8, 2, 6, 8]}
BASE = {'priorGames': 4, 'profile': 'uniform', 'halfLife': None}


def decay(age, half_life):
    if age < 0:
        raise ValueError('Future observation in rating inputs')
    return 1. if half_life is None else 2.**(-age/half_life)


def ratings(games, ids, cutoff, prior, old_points, config, *, adjust_opponents=True):
    """Fit production/allowed effects with opportunity and optional age weights."""
    if any(g['week'] >= cutoff for g in games):
        raise ValueError('Cutoff requires strictly earlier weeks')
    n=len(ids); index={t:i for i,t in enumerate(ids)}
    effects=np.zeros((n,8,2)); prior=np.zeros_like(effects) if prior is None else prior
    pg=config['priorGames']; neutral=PROFILES[config['profile']]
    for k,key in enumerate(KEYS):
        obs=[]
        for g in games:
            a,b=g['teams']; age_weight=decay(cutoff-1-g['week'],config['halfLife'])
            for own,opp in ((a,b),(b,a)):
                f=own['factors'][key]
                if f['usable'] and f['denominator']>0:
                    obs.append((index[own['id']],index[opp['id']],f['numerator'],f['denominator'],age_weight))
        target=np.r_[prior[:,k,0],prior[:,k,1]]*.5
        lhs=(pg+neutral[k])*np.eye(2*n); rhs=pg*target
        if obs:
            league=sum(num*w for _,_,num,den,w in obs)/sum(den*w for _,_,num,den,w in obs)
            typical=np.mean([den for _,_,num,den,w in obs])
            for own,opp,num,den,w in obs:
                weight=den/typical*w
                j=n+opp
                lhs[own,own]+=weight;lhs[j,j]+=weight
                if adjust_opponents:
                    lhs[own,j]+=weight;lhs[j,own]+=weight
                residual=weight*(num/den-league);rhs[own]+=residual;rhs[j]+=residual
        beta=np.linalg.solve(lhs,rhs)
        effects[:,k,0]=beta[:n]-beta[:n].mean()
        effects[:,k,1]=beta[n:]-beta[n:].mean()
    # Point baseline receives the same prior and age treatment. The factor-
    # specific profile changes only factor estimates, not this baseline.
    lhs=(pg+2)*np.eye(n);rhs=np.zeros(n) if old_points is None else pg*.5*old_points
    for g in games:
        h=next(t for t in g['teams'] if t['homeAway']=='home')
        a=next(t for t in g['teams'] if t['homeAway']=='away')
        x=np.zeros(n);x[index[h['id']]]=1;x[index[a['id']]]=-1
        w=decay(cutoff-1-g['week'],config['halfLife'])
        lhs+=w*(np.outer(x,x) if adjust_opponents else np.diag(x*x));rhs+=w*x*(h['score']-a['score'])
    points=np.linalg.solve(lhs,rhs);points-=points.mean()
    own=effects[:,:,0]*SIGNS;prevention=-effects[:,:,1]*SIGNS
    return effects,points,np.c_[own+prevention,own,prevention,points]


def make_features(records, config):
    ids=sorted({t['id'] for g in records for t in g['teams']});index={t:i for i,t in enumerate(ids)}
    rows=[];prior=None;old_points=None
    for year in sorted({g['season'] for g in records}):
        gs=[g for g in records if g['season']==year]
        for week in sorted({g['week'] for g in gs}):
            earlier=[g for g in gs if g['week']<week]
            _,_,values=ratings(earlier,ids,week,prior,old_points,config)
            for g in gs:
                if g['week']!=week:continue
                h=next(t for t in g['teams'] if t['homeAway']=='home')
                a=next(t for t in g['teams'] if t['homeAway']=='away')
                rows.append({'gameId':g['gameId'],'season':year,'week':week,
                             'margin':h['score']-a['score'],'x':(values[index[h['id']]]-values[index[a['id']]]).tolist(),
                             'latestInputWeek':max((g['week'] for g in earlier),default=0)})
        prior,old_points,_=ratings(gs,ids,max(g['week'] for g in gs)+1,prior,old_points,config)
    return rows


def specifications():
    result=[{'family':'point_baseline','columns':[24]}, {'family':'all_eight','columns':list(range(8))},
            {'family':'separate_sides','columns':list(range(8,24))}]
    subsets=[list(c) for size in (1,2,3) for c in combinations(range(8),size)]
    subsets += [[i for i in range(8) if i!=drop] for drop in range(8)]
    result += [{'family':'fewer_factors','columns':c} for c in subsets]
    hybrid=[[]]+[list(c) for size in (1,2,3) for c in combinations(range(8),size)]+[list(range(8))]
    result += [{'family':'point_plus_factors','columns':[24]+c} for c in hybrid if c]
    return result


def predict_rolling(rows, columns, years, alpha=100, probability_c=None):
    """Refit each year using 2012 onward and strictly earlier seasons."""
    all_x=np.array([r['x'] for r in rows])[:,columns]; y=np.array([r['margin'] for r in rows])
    seasons=np.array([r['season'] for r in rows]);out=[];predictions=[]
    for year in years:
        tr=(seasons>=2012)&(seasons<year);te=seasons==year
        if not tr.any() or not te.any():raise ValueError('Empty train/evaluation fold')
        if probability_c is None:
            model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
            model.fit(all_x[tr],y[tr]);pred=model.predict(all_x[te])
        else:
            tr &= y!=0
            model=make_pipeline(StandardScaler(),LogisticRegression(C=probability_c,max_iter=2000))
            model.fit(all_x[tr],y[tr]>0);pred=model.predict_proba(all_x[te])[:,1]
        out.extend(r for r,keep in zip(rows,te) if keep);predictions.extend(pred)
    return out,np.array(predictions)


def margin_score(rows,pred):
    y=np.array([r['margin'] for r in rows])
    return float(np.sqrt(np.mean((pred-y)**2)))


def choose_alpha(rows,spec,config):
    options=[]
    for alpha in ALPHAS:
        ev,pred=predict_rolling(rows,spec['columns'],VALIDATION_YEARS,alpha)
        options.append({**spec,'config':config,'alpha':alpha,'validationRmse':margin_score(ev,pred),
                        'validationByYear':{str(y):margin_score([r for r in ev if r['season']==y],pred[np.array([r['season']==y for r in ev])]) for y in VALIDATION_YEARS}})
    return min(options,key=lambda o:(o['validationRmse'],len(o['columns']))), options


def run(directory):
    output=directory/'model-v2';output.mkdir(exist_ok=True)
    records,inputs=load_records(directory);records=[g for g in records if g['season']<=2025]
    protocol={'version':2,'inputs':inputs,'codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'initialization':2011,'trainStart':2012,'rollingValidationYears':VALIDATION_YEARS,
              'followupYears':FOLLOWUP_YEARS,'followupStatus':'already inspected; NOT a fresh holdout',
              'annualRefit':'Each year uses only preceding seasons; feature cutoffs use earlier weeks',
              'phase1':specifications(),'baseConfig':BASE,'alphas':ALPHAS,
              'phase2':{'priorGames':[2,4,8],'neutralProfiles':PROFILES},
              'phase3':{'halfLivesWeeks':[None,4,8]},'probabilityCs':CS,
              'selection':'Margin RMSE on pooled 2018-2023 rolling validation; probability C chosen by validation log loss after margin feature selection',
              'limitations':['corrected historical snapshots','no market inputs','no FPI/DVOA comparison','home-designation only; no neutral-site adjustment','selection comparisons are exploratory, not multiplicity-adjusted','no future predictive superiority claim']}
    save_json(output/'protocol.json',protocol)
    bundles={}
    def bundle(config):
        key=json.dumps(config,sort_keys=True)
        if key not in bundles:
            bundles[key]=make_features(records,config)
            print('Built features '+key,flush=True)
        return bundles[key]
    base=bundle(BASE);candidates=[];by_family={}
    for spec in specifications():
        choice,options=choose_alpha(base,spec,BASE);candidates.extend(options)
        family=spec['family']
        if family not in by_family or choice['validationRmse']<by_family[family]['validationRmse']:
            by_family[family]=choice
    save_json(output/'phase1-selection.json',{'winners':by_family,'candidates':candidates})
    print('Phase 1 selected using validation only',flush=True)
    # Preserve the family winners and their ablations. Later phases change
    # shrinkage and recency, not the factor subset selected in phase 1.
    phases={'structure':by_family};stabilized={};stability_candidates=[]
    for family,spec in by_family.items():
        options=[]
        for pg in (2,4,8):
            for profile in ('uniform','factor_specific'):
                if family=='point_baseline' and profile!='uniform':continue
                config={'priorGames':pg,'profile':profile,'halfLife':None}
                choice,attempts=choose_alpha(bundle(config),{'family':family,'columns':spec['columns']},config)
                options.append(choice);stability_candidates.extend(attempts)
        stabilized[family]=min(options,key=lambda o:o['validationRmse'])
    phases['stabilization']=stabilized;recent={};recency_candidates=[]
    save_json(output/'phase2-selection.json',{'winners':stabilized,'candidates':stability_candidates})
    print('Phase 2 selected using validation only',flush=True)
    for family,spec in stabilized.items():
        options=[spec]
        for half in (4,8):
            config={**spec['config'],'halfLife':half}
            choice,attempts=choose_alpha(bundle(config),{'family':family,'columns':spec['columns']},config)
            options.append(choice);recency_candidates.extend(attempts)
        recent[family]=min(options,key=lambda o:o['validationRmse'])
    phases['recency']=recent
    # Freeze final choices, including independently selected probability
    # regularization, before generating any 2024/25 follow-up predictions.
    for spec in recent.values():
        rows=bundle(spec['config']);options=[]
        for c in CS:
            ev,p=predict_rolling(rows,spec['columns'],VALIDATION_YEARS,probability_c=c)
            loss=metrics(ev,np.zeros(len(p)),p)['logLoss'];options.append((loss,c))
        spec['probabilityC']=min(options)[1]
    winner=min(recent,key=lambda name:recent[name]['validationRmse'])
    save_json(output/'locked-selection.json',{'winner':winner,'phases':phases,'recencyCandidates':recency_candidates})
    print('All selections locked; evaluating historical follow-up now',flush=True)
    results={};followup_predictions={};validation_predictions={};phase_results={}
    for phase,choices in phases.items():
        phase_results[phase]={}
        for name,spec in choices.items():
            rows=bundle(spec['config']);ev,pred=predict_rolling(rows,spec['columns'],FOLLOWUP_YEARS,spec['alpha'])
            phase_results[phase][name]={'validationRmse':spec['validationRmse'],'followupRmse':margin_score(ev,pred)}
    for name,spec in recent.items():
        rows=bundle(spec['config']);ev,pred=predict_rolling(rows,spec['columns'],FOLLOWUP_YEARS,spec['alpha'])
        _,prob=predict_rolling(rows,spec['columns'],FOLLOWUP_YEARS,probability_c=spec['probabilityC'])
        score=metrics(ev,pred,prob);followup_predictions[name]=(pred,prob)
        val,vpred=predict_rolling(rows,spec['columns'],VALIDATION_YEARS,spec['alpha']);validation_predictions[name]=vpred
        results[name]={'selection':spec,'featureNames':[FEATURE_NAMES[i] for i in spec['columns']],
                       'followup':score,'byYear':{},'byStage':{}}
        for y in FOLLOWUP_YEARS:
            mask=np.array([r['season']==y for r in ev]);results[name]['byYear'][str(y)]=metrics([r for r,m in zip(ev,mask) if m],pred[mask],prob[mask])
        for label,mask in [('early',np.array([r['week']<=4 for r in ev])),('later',np.array([r['week']>4 for r in ev]))]:
            results[name]['byStage'][label]=metrics([r for r,m in zip(ev,mask) if m],pred[mask],prob[mask])
    for name,(pred,_) in followup_predictions.items():
        results[name]['followupRmseDifference95VsPoint']=bootstrap_delta(ev,pred,followup_predictions['point_baseline'][0])
    prediction_rows=[{k:r[k] for k in ('gameId','season','week','margin','latestInputWeek')} for r in ev]
    for i,r in enumerate(prediction_rows):
        r['models']={name:{'margin':float(p[i]),'probability':float(q[i])} for name,(p,q) in followup_predictions.items()}
    save_json(output/'followup-predictions.json',prediction_rows)
    save_json(output/'validation-predictions.json',[{'gameId':r['gameId'],'season':r['season'],'week':r['week'],'margin':r['margin'],
              'predictions':{name:float(p[i]) for name,p in validation_predictions.items()}} for i,r in enumerate(val)])
    save_json(output/'results.json',{'protocol':protocol,'selectedFamily':winner,'models':results,'phaseComparison':phase_results})
    lines=['# Predictive experiments: round two','',
           '**Development research, not a new untouched test.** Select on rolling 2018–2023; inspect 2024–2025 only after all choices are locked.',
           'Every fold retrains from 2012 through the preceding season. Weekly inputs exclude the predicted week. 2011 initializes priors.','',
           f'Validation-selected family: **{winner}**.','',
           '| Family | Validation RMSE | Follow-up RMSE | Follow-up MAE | Brier | Log loss |',
           '|---|---:|---:|---:|---:|---:|']
    for name,r in results.items():
        m=r['followup'];lines.append(f"| {name} | {r['selection']['validationRmse']:.3f} | {m['rmse']:.3f} | {m['mae']:.3f} | {m['brier']:.4f} | {m['logLoss']:.4f} |")
    lines+=['','## What each family selected','']
    for name,r in results.items():
        s=r['selection'];ci=r['followupRmseDifference95VsPoint']
        lines += [f"- **{name}**: {', '.join(r['featureNames'])}. Prior games {s['config']['priorGames']}; neutral profile {s['config']['profile']}; recency half-life {s['config']['halfLife']} weeks; ridge {s['alpha']}; logistic C {s['probabilityC']}.",
                  f"  Follow-up RMSE difference interval versus point baseline: [{ci['lower']:+.3f}, {ci['upper']:+.3f}] (negative favors this family)."]
    lines+=['','## Structure → stabilization → recency','',
            'Entries are validation RMSE / follow-up RMSE. Only validation selected settings.','',
            '| Family | Structure only | Stabilization | Recency |','|---|---:|---:|---:|']
    for name in results:
        vals=[phase_results[p][name] for p in phases]
        lines.append('| '+name+' | '+' | '.join(f"{v['validationRmse']:.3f} / {v['followupRmse']:.3f}" for v in vals)+' |')
    lines+=['','## Limits and next decisions','',
            '- These are forecast associations, not weights for explaining a completed game.',
            '- All-eight, point-only and the alternatives use the same rolling evaluation and fair stabilization/recency searches.',
            '- Net factors already existed in v1. Separate sides removes the equal-weight constraint between production and prevention.',
            '- Factor-specific stabilization is a predefined hypothesis, not an established reliability measurement: neutral pseudo-games [2,2,2,6,8,2,6,8] in factor order.',
            '- Recency decays by NFL weeks. The prior stays fixed within a season; this is one specific shrinkage/recency design.',
            '- Probability regularization is tuned separately on validation log loss, conditional on decisive games. Factor choices still target margin RMSE.',
            '- Selecting many variants can overfit validation; bootstrap intervals are paired week-block diagnostics, not adjusted for model search.',
            '- 2024–2025 has already been inspected. Annual retraining uses 2024 to fit 2025 coefficients, with hyperparameters frozen before follow-up evaluation.',
            '- Missing factor observations are omitted and regularized, not replaced by observed zero. Corrected historical files are not publication archives.',
            '- No market inputs, injury/QB inputs, neutral-site adjustment, or FPI/DVOA comparison. No production ratings changed.',
            '- Version 1 is preserved; its frozen-2021 scores are not directly interchangeable with these annually retrained scores.',
            '', 'Machine-readable artifacts include the full candidate search, locked selections, hashes, per-game predictions, calibration, season splits, and early/late splits.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,default=ROOT/'game_summaries/nflverse')
    run(parser.parse_args().data)
