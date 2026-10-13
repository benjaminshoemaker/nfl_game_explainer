"""V3 bounded model search; separate margin and probability selection."""
import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.linear_model import Ridge, ElasticNet, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning

from research.build_team_seasons import save_json
from research.team_power_model import metrics, bootstrap_delta

ROOT=Path(__file__).resolve().parents[1]


def estimator(spec, objective):
    kind=spec['kind'];strength=spec['strength']
    if kind=='tree':
        cls=HistGradientBoostingRegressor if objective=='margin' else HistGradientBoostingClassifier
        return cls(max_iter=150,max_leaf_nodes=strength,min_samples_leaf=50,l2_regularization=10,learning_rate=.04,early_stopping=False,random_state=19)
    if objective=='margin':
        model=Ridge(alpha=strength) if kind=='ridge' else ElasticNet(alpha=strength,l1_ratio=.5,max_iter=100000,tol=1e-5,selection='random',random_state=19)
    else:
        model=LogisticRegression(C=strength,max_iter=10000,solver='lbfgs')
    return make_pipeline(StandardScaler(),model)


def rolling(x,y,seasons,spec,objective,years):
    pred=[];indices=[]
    for year in years:
        train=(seasons>=2012)&(seasons<year);test=seasons==year
        if objective=='probability':train &= y!=0
        model=estimator(spec,objective)
        xx=x[:,spec['columns']]
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            model.fit(xx[train],y[train] if objective=='margin' else y[train]>0)
        p=model.predict(xx[test]) if objective=='margin' else model.predict_proba(xx[test])[:,1]
        pred.extend(p);indices.extend(np.flatnonzero(test))
    return np.array(indices),np.array(pred)


def loss(y,p,objective):
    if objective=='margin':return float(np.sqrt(np.mean((y-p)**2)))
    mask=y!=0;p=np.clip(p[mask],1e-9,1-1e-9);win=y[mask]>0
    return float(-np.mean(win*np.log(p)+(1-win)*np.log(1-p)))


def run(directory):
    metadata=json.loads((directory/'features.json').read_text());data=np.load(directory/'features.npz')
    x,y,seasons,week=(data[k] for k in ('x','y','season','week'))
    groups=metadata['groups'];context=groups['context']
    original=groups['original_p8_h8'];points=[cols[-1] for name,cols in groups.items() if name.startswith('original')]
    measured=original+groups['pass_p8_h8']+groups['rush_p8_h8']+groups['opportunity_p8_h8']
    sets={'eight_plus_points':original,'revised_measurements':measured,'with_context':measured+context,
          'learned_stabilization':list(range(x.shape[1]))}
    specs=[]
    for col in points:
        for name,cols in [('point_baseline',[col]),('point_context',[col]+context)]:
            for a in (10,100,1000):specs.append({'family':name,'columns':cols,'kind':'ridge','strength':a})
    for name,cols in sets.items():
        for a in (10,100,1000):specs.append({'family':name,'columns':cols,'kind':'ridge','strength':a})
        for a in (.01,.1,1):specs.append({'family':name+'_elastic','columns':cols,'kind':'elastic','strength':a})
    for name,cols in [('nonlinear',measured+context)]:
        for leaves in (3,7,15):specs.append({'family':name,'columns':cols,'kind':'tree','strength':leaves})
    probspecs=[]
    # Independently choose probability features and settings, rather than
    # recycling margin-selected columns. Elastic net is margin-only here.
    unique={(s['family'],tuple(s['columns'])) for s in specs if s['kind']=='ridge'}
    for family,cols in sorted(unique):
        for c in (.001,.01,.1,1):probspecs.append({'family':family,'columns':list(cols),'kind':'ridge','strength':c})
    probspecs += [s for s in specs if s['kind']=='tree']
    protocol={'marginCandidates':specs,'probabilityCandidates':probspecs,'validation':list(range(2018,2024)),
              'followup':[2024,2025],'followupStatus':'previously inspected, development only','randomSeed':19,
              'featureSha256':hashlib.sha256((directory/'features.npz').read_bytes()).hexdigest(),
              'codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'selection':'separate validation RMSE and log loss; chronological annual refits'}
    save_json(directory/'protocol.json',protocol)
    selections={};all_candidates={}
    for objective,candidates in [('margin',specs),('probability',probspecs)]:
        winners={};scores=[]
        for n,spec in enumerate(candidates):
            try:
                idx,p=rolling(x,y,seasons,spec,objective,range(2018,2024));score=loss(y[idx],p,objective)
            except ConvergenceWarning as error:
                scores.append({**spec,'status':'failed_convergence','error':str(error)})
                print('Rejected unconverged candidate '+str(spec['family'])+' '+str(spec['strength']),flush=True)
                continue
            result={**spec,'validationLoss':score};scores.append(result)
            if spec['family'] not in winners or score<winners[spec['family']]['validationLoss']:winners[spec['family']]=result
            if n%15==0:print(objective,n,len(candidates),flush=True)
        selections[objective]=winners;all_candidates[objective]=scores
    save_json(directory/'locked-selection.json',selections);save_json(directory/'candidates.json',all_candidates)
    print('Selections locked before follow-up',flush=True)
    results={};predictions={}
    for objective,winners in selections.items():
        results[objective]={};predictions[objective]={}
        for family,spec in winners.items():
            idx,p=rolling(x,y,seasons,spec,objective,[2024,2025]);predictions[objective][family]=p
            results[objective][family]={'selection':spec,'followupLoss':loss(y[idx],p,objective),
                'yearLoss':{str(year):loss(y[idx][seasons[idx]==year],p[seasons[idx]==year],objective) for year in (2024,2025)}}
    rows=[{'gameId':metadata['games'][i],'season':int(seasons[i]),'week':int(week[i]),'margin':float(y[i])} for i in idx]
    for family,p in predictions['margin'].items():
        results['margin'][family]['difference95VsPoint']=bootstrap_delta(rows,p,predictions['margin']['point_baseline'])
    save_json(directory/'results.json',results)
    save_json(directory/'followup-predictions.json',[{**r,'predictions':{o:{k:float(v[j]) for k,v in models.items()} for o,models in predictions.items()}} for j,r in enumerate(rows)])
    lines=['# Flexible predictive models — round three','','Retrospective development, not new untouched evaluation. All choices selected using 2018–2023; follow-up 2024–2025 was previously inspected.','']
    for objective,models in results.items():
        lines += [f'## {objective}','','| Model family | Validation loss | Follow-up loss | 2024 | 2025 |','|---|---:|---:|---:|---:|']
        for family,r in models.items():lines.append(f"| {family} | {r['selection']['validationLoss']:.4f} | {r['followupLoss']:.4f} | {r['yearLoss']['2024']:.4f} | {r['yearLoss']['2025']:.4f} |")
    lines+=['','Margin loss is RMSE in points; probability loss is log loss on decisive games. Lower is better.',
            'Learned stabilization stacks multiple prior/recency estimates and learns regularized combinations; it is not a fitted generative reliability model.',
            'Elastic net is tested for margin. Probability features are selected independently; probability models include logistic and nonlinear boosting.',
            'Rest and neutral-site context are pregame schedule fields. Starting QB labels, actual weather, odds, and WP are excluded.',
            'All earlier source limitations remain. Model-search uncertainty is not removed by a week-block interval. No superiority is claimed automatically.']
    (directory/'REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines),flush=True)


if __name__=='__main__':run(ROOT/'game_summaries/nflverse/model-v3')
