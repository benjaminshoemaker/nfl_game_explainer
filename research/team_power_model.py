"""Chronological eight-factor forecasting experiment. No network or market inputs.

Run after build_nflverse_seasons.py for 2011..2026. Predictions for a week use
only earlier weeks; 2011 initializes priors, 2012..2021 train, 2022..2023 select,
and 2024..2025 evaluate the frozen selection. Corrected historical inputs mean
this is a retrospective backtest, not an as-published betting simulation.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from api.lib.team_season import FACTORS
from research.build_team_seasons import save_json

ROOT = Path(__file__).resolve().parents[1]
KEYS = [f['id'] for f in FACTORS]
TRAIN = (2012, 2021)
VALIDATION = (2022, 2023)
TEST = (2024, 2025)
PRIOR_RETENTION = .5
RIDGE_TEAM_GAMES = 2.0


def load_records(directory):
    records, files = [], []
    for year in range(2011, 2027):
        paths = sorted(directory.glob(f'{year}-week-*-games.json'))
        if not paths:
            raise ValueError(f'Missing season {year}')
        path = max(paths, key=lambda p: int(p.name.split('-')[2]))
        games = json.loads(path.read_text())
        if not games or len({g['gameId'] for g in games}) != len(games):
            raise ValueError(f'Empty/duplicate season {year}')
        audit_path = path.with_name(path.name.replace('-games.json', '-audit.json'))
        audit = json.loads(audit_path.read_text())
        if audit['errors'] or audit['games'] != audit['expected'] or len(games) != audit['expected']:
            raise ValueError(f'Incomplete scheduled-game coverage for {year}')
        if any(g['season'] != year or g['source'] != 'nflverse' for g in games):
            raise ValueError(f'Incorrect source/season in {path}')
        records.extend(games)
        files.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest_path = path.with_name(path.name.replace('-games.json', '-manifest.json'))
        files.append({'path': str(manifest_path), 'sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest()})
    return records, files


def estimate(games, ids, prior=None, prior_games=2, adjusted=True):
    """Joint offense/allowed effects; each factor retains its own missingness.

    y = league level + own effect + opponent allowed effect. Observation weights
    equal opportunities / average opportunities per team-game. Prior values are
    previous-season effects regressed halfway to zero. Two neutral team-games
    also regularize every estimate, including when prior_games is zero.
    """
    n = len(ids)
    ix = {t: i for i, t in enumerate(ids)}
    old = np.zeros((n, len(KEYS), 2)) if prior is None else prior
    result = np.zeros_like(old)
    exposure = np.zeros((n, len(KEYS)))
    for k, key in enumerate(KEYS):
        rows = []
        for g in games:
            a, b = g['teams']
            for own, opp in ((a, b), (b, a)):
                f = own['factors'][key]
                if f['usable'] and f['denominator'] > 0:
                    rows.append((ix[own['id']], ix[opp['id']], f['numerator'], f['denominator']))
        if not rows:
            result[:, k, :] = old[:, k, :] * PRIOR_RETENTION * prior_games / (prior_games + RIDGE_TEAM_GAMES)
            continue
        league = sum(r[2] for r in rows) / sum(r[3] for r in rows)
        avg_denom = np.mean([r[3] for r in rows])
        design = np.zeros((len(rows), 2*n))
        response, weights = [], []
        for j, (own, opp, num, den) in enumerate(rows):
            design[j, own] = 1
            design[j, n+opp] = 1
            response.append(num/den-league)
            weights.append(den/avg_denom)
            exposure[own, k] += 1
        weights = np.array(weights)
        target = np.concatenate([old[:, k, 0], old[:, k, 1]]) * PRIOR_RETENTION
        penalty = RIDGE_TEAM_GAMES + prior_games
        if adjusted:
            lhs = design.T @ (weights[:, None] * design) + penalty*np.eye(2*n)
            rhs = design.T @ (weights*np.array(response)) + prior_games*target
            beta = np.linalg.solve(lhs, rhs)
        else:
            # Independent own/allowed averages with identical shrinkage.
            beta = (design.T @ (weights*np.array(response)) + prior_games*target) / (design.T @ weights + penalty)
        beta[:n] -= beta[:n].mean()
        beta[n:] -= beta[n:].mean()
        result[:, k, 0], result[:, k, 1] = beta[:n], beta[n:]
    signs = np.array([1 if f['higherIsBetter'] else -1 for f in FACTORS])
    net = (result[:, :, 0] - result[:, :, 1]) * signs
    return result, net, exposure


def point_strength(games, ids, old=None, prior_games=2, adjusted=True):
    n = len(ids); ix = {t:i for i,t in enumerate(ids)}
    target = np.zeros(n) if old is None else old*PRIOR_RETENTION
    lhs = (prior_games+RIDGE_TEAM_GAMES)*np.eye(n)
    rhs = prior_games*target
    for g in games:
        home = next(t for t in g['teams'] if t['homeAway']=='home')
        away = next(t for t in g['teams'] if t['homeAway']=='away')
        x = np.zeros(n); x[ix[home['id']]]=1; x[ix[away['id']]]=-1
        # Home advantage is learned in the downstream training model; source
        # schedule venue effects are a declared limitation of this first model.
        margin = home['score']-away['score']
        lhs += np.outer(x,x) if adjusted else np.diag(x*x)
        rhs += x*margin
    result = np.linalg.solve(lhs,rhs)
    return result-result.mean()


def make_features(records, prior_games=2, adjusted=True):
    ids = sorted({t['id'] for g in records for t in g['teams']})
    if len(ids)!=32: raise ValueError('Expected 32 canonical franchises')
    ix = {t:i for i,t in enumerate(ids)}
    rows=[]; prior=None; prior_points=None; latest=None
    for season in sorted({g['season'] for g in records}):
        gs = [g for g in records if g['season']==season]
        for week in sorted({g['week'] for g in gs}):
            earlier = [g for g in gs if g['week']<week]
            effects, net, exposure = estimate(earlier,ids,prior,prior_games,adjusted)
            ps = point_strength(earlier,ids,prior_points,prior_games,adjusted)
            for g in gs:
                if g['week']!=week: continue
                home = next(t for t in g['teams'] if t['homeAway']=='home')
                away = next(t for t in g['teams'] if t['homeAway']=='away')
                hi, ai = ix[home['id']], ix[away['id']]
                rows.append({'gameId':g['gameId'],'season':season,'week':week,
                             'home':home['id'],'away':away['id'],
                             'margin':home['score']-away['score'],
                             'x':(net[hi]-net[ai]).tolist(), 'pointX':[float(ps[hi]-ps[ai])],
                             'latestInputWeek':max([r['week'] for r in earlier],default=0)})
        prior,net,exposure = estimate(gs,ids,prior,prior_games,adjusted)
        prior_points = point_strength(gs,ids,prior_points,prior_games,adjusted)
        latest={'season':season,'throughWeek':max(g['week'] for g in gs),'ids':ids,
                'net':net.tolist(),'exposure':exposure.tolist()}
    return rows,latest


def matrix(rows, key='x'):
    return np.array([r[key] for r in rows]),np.array([r['margin'] for r in rows])


def subset(rows, bounds):
    return [r for r in rows if bounds[0]<=r['season']<=bounds[1]]


def fit(rows, alpha, key='x'):
    x,y=matrix(rows,key)
    model=make_pipeline(StandardScaler(),Ridge(alpha=alpha)).fit(x,y)
    # Separate logistic model gives probabilities; ties are excluded and this
    # is explicitly a conditional home-win probability among decisive games.
    decisive=y!=0
    probability=make_pipeline(StandardScaler(),LogisticRegression(C=1/alpha,max_iter=2000)).fit(x[decisive],y[decisive]>0)
    return model,probability


def metrics(rows, pred, prob):
    y=np.array([r['margin'] for r in rows]); decisive=y!=0
    p=np.clip(prob[decisive],1e-9,1-1e-9); win=y[decisive]>0
    bins=[]
    for lo in (0,.2,.4,.6,.8):
        mask=(p>=lo)&(p<lo+.2+1e-12)
        if mask.any(): bins.append({'low':lo,'n':int(mask.sum()),'predicted':float(p[mask].mean()),'observed':float(win[mask].mean())})
    return {'games':len(y),'rmse':float(np.sqrt(np.mean((pred-y)**2))),
            'mae':float(np.mean(abs(pred-y))),'decisiveGames':int(decisive.sum()),
            'brier':float(np.mean((p-win)**2)),
            'logLoss':float(-np.mean(win*np.log(p)+(1-win)*np.log(1-p))),
            'winnerAccuracy':float(np.mean((p>=.5)==win)), 'calibration':bins}


def evaluate(rows, models, key='x'):
    x,_=matrix(rows,key); pred=models[0].predict(x); prob=models[1].predict_proba(x)[:,1]
    return metrics(rows,pred,prob),pred,prob


def bootstrap_delta(rows, candidate, baseline):
    """Paired week-block bootstrap; negative RMSE difference favors candidate."""
    y=np.array([r['margin'] for r in rows]); groups=sorted({(r['season'],r['week']) for r in rows})
    masks=[np.array([i for i,r in enumerate(rows) if (r['season'],r['week'])==g]) for g in groups]
    rng=np.random.default_rng(20261004); deltas=[]
    for _ in range(2000):
        ix=np.concatenate([masks[j] for j in rng.integers(0,len(masks),len(masks))])
        deltas.append(np.sqrt(np.mean((candidate[ix]-y[ix])**2))-np.sqrt(np.mean((baseline[ix]-y[ix])**2)))
    return {'lower':float(np.quantile(deltas,.025)),'upper':float(np.quantile(deltas,.975)),
            'method':'paired season-week block bootstrap, 2000 draws; not season-level certainty'}


def run(directory):
    records,inputs=load_records(directory)
    output=directory/'model'; output.mkdir(exist_ok=True)
    # Freeze the protocol before inspecting test scores. Do not select or refit
    # hyperparameters on 2024/25. Development remains distinct from evaluation.
    protocol={'train':TRAIN,'validation':VALIDATION,'test':TEST,'initialization':2011,
              'priorGames':[0,2,4],'priorRetention':PRIOR_RETENTION,'teamRidgeGames':RIDGE_TEAM_GAMES,
              'alphas':[10,100,1000],'selection':'validation margin RMSE only',
              'features':KEYS,'marketInputs':False,'cutoff':'strictly earlier NFL weeks',
              'sourceVintage':'retrospective corrected files','inputs':inputs,
              'codeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save_json(output/'protocol.json',protocol)
    candidates=[]; bundles={}
    for adjusted in (False,True):
        for prior_games in (0,2,4):
            rows,latest=make_features(records,prior_games,adjusted)
            bundles[(adjusted,prior_games)]=(rows,latest)
            for alpha in (10,100,1000):
                models=fit(subset(rows,TRAIN),alpha)
                m,_,_=evaluate(subset(rows,VALIDATION),models)
                candidates.append({'adjusted':adjusted,'priorGames':prior_games,'alpha':alpha,'validation':m})
            print(f'Features built: adjusted={adjusted}, priorGames={prior_games}',flush=True)
    # Opponent-adjusted and unadjusted variants selected separately so the
    # cost/benefit of schedule adjustment stays visible on the untouched test.
    winners={name:min([c for c in candidates if c['adjusted']==adjusted],key=lambda c:c['validation']['rmse'])
             for name,adjusted in [('eight_factor',True),('unadjusted_eight_factor',False)]}
    all_predictions={}; results={}; fitted={}
    for name,choice in winners.items():
        rows,latest=bundles[(choice['adjusted'],choice['priorGames'])]
        models=fit(subset(rows,TRAIN),choice['alpha'])
        test=subset(rows,TEST); score,pred,prob=evaluate(test,models)
        results[name]={'selection':choice,'test':score}
        all_predictions[name]=(pred,prob); fitted[name]=(models,rows,latest)
    # Point-differential baselines also get fair validation tuning.
    for name,adjusted in [('opponent_adjusted_point_margin',True),('raw_point_margin',False)]:
        options=[]
        for pg in (0,2,4):
            rows,_=bundles[(adjusted,pg)]
            for alpha in (10,100,1000):
                models=fit(subset(rows,TRAIN),alpha,'pointX')
                score,_,_=evaluate(subset(rows,VALIDATION),models,'pointX')
                options.append((score['rmse'],pg,alpha))
        _,pg,alpha=min(options)
        rows,_=bundles[(adjusted,pg)];models=fit(subset(rows,TRAIN),alpha,'pointX')
        test=subset(rows,TEST);score,pred,prob=evaluate(test,models,'pointX')
        results[name]={'selection':{'priorGames':pg,'alpha':alpha},'test':score}
        all_predictions[name]=(pred,prob)
    train=subset(rows,TRAIN); test=subset(rows,TEST)
    mean_margin=float(np.mean([r['margin'] for r in train])); decisive=[r for r in train if r['margin']!=0]
    win_rate=np.mean([r['margin']>0 for r in decisive])
    pred=np.full(len(test),mean_margin);prob=np.full(len(test),win_rate)
    results['home_only']={'test':metrics(test,pred,prob)};all_predictions['home_only']=(pred,prob)
    candidate=all_predictions['eight_factor'][0]
    for name,(pred,prob) in all_predictions.items():
        results[name]['candidateRmseDifference95']=bootstrap_delta(test,candidate,pred)
        results[name]['bySeason']={str(y):metrics([r for r in test if r['season']==y],pred[np.array([r['season']==y for r in test])],prob[np.array([r['season']==y for r in test])]) for y in TEST}
        for label,mask in [('early',np.array([r['week']<=4 for r in test])),('later',np.array([r['week']>4 for r in test]))]:
            results[name][label]=metrics([r for r,m in zip(test,mask) if m],pred[mask],prob[mask])
    save_json(output/'results.json',{'protocol':protocol,'candidates':candidates,'models':results})
    prediction_rows=[{k:r[k] for k in ('gameId','season','week','home','away','margin','latestInputWeek')} for r in test]
    for i,r in enumerate(prediction_rows):
        r['models']={name:{'margin':float(p[i]),'homeWinProbability':float(q[i])} for name,(p,q) in all_predictions.items()}
    save_json(output/'test-predictions.json',prediction_rows)
    models,rows,latest=fitted['eight_factor'];scaler=models[0].named_steps['standardscaler'];reg=models[0].named_steps['ridge']
    beta=reg.coef_/scaler.scale_; net=np.array(latest['net']);contributions=net*beta;rating=contributions.sum(axis=1)
    ranking=[]
    for i in np.argsort(-rating):
        ranking.append({'team':latest['ids'][i],'rank':len(ranking)+1,'rating':float(rating[i]),
                        'contributions':{k:float(v) for k,v in zip(KEYS,contributions[i])},
                        'currentSeasonGamesByFactor':dict(zip(KEYS,latest['exposure'][i]))})
    save_json(output/'experimental-ratings.json',{'status':'experimental_not_validated_for_publication',
             'season':latest['season'],'throughWeek':latest['throughWeek'],'trainedThrough':TRAIN[1],
             'selection':winners['eight_factor'],'unit':'points above average on neutral field',
             'coefficients':dict(zip(KEYS,beta.tolist())),'teams':ranking})
    lines=['# Eight-factor predictive experiment','',
           'Retrospective research. Train 2012–2021; select 2022–2023; frozen test 2024–2025.',
           '2011 initializes prior-season effects. No odds, WP, EPA, or third-party ratings enter features.','',
           '| Model | Test RMSE | MAE | Brier | Log loss |','|---|---:|---:|---:|---:|']
    for name,r in results.items():
        m=r['test'];lines.append(f"| {name} | {m['rmse']:.3f} | {m['mae']:.3f} | {m['brier']:.4f} | {m['logLoss']:.4f} |")
    lines+=['','## Interpretation','']
    base=results['opponent_adjusted_point_margin']['test']['rmse']; ours=results['eight_factor']['test']['rmse']
    lines.append(f'Eight factors change test RMSE by {ours-base:+.3f} points versus opponent-adjusted point margin (negative is better).')
    ci=results['opponent_adjusted_point_margin']['candidateRmseDifference95']
    lines.append(f"Paired week-block 95% interval: {ci['lower']:+.3f} to {ci['upper']:+.3f}. This does not establish performance across future seasons.")
    lines+=['','## Limitations','',
            '- Corrected historical files are not point-in-time archived publications.',
            '- No FPI, DVOA, Elo, or EPA benchmark is claimed in this run.',
            '- Home designation is used; neutral-site games are not separately modeled.',
            '- No injury/QB/roster inputs or in-season recency weighting.',
            '- Missing factor observations shrink toward the prior/league; missingness is recorded, not observed zero.',
            '- Probability metrics exclude tied games and estimate the winner conditional on a decisive result.',
            '- A good scoring reconciliation does not independently validate every factor definition.',
            '- Correlated-factor coefficients are model contributions, not causal importance.',
            '- Experimental current ratings keep training frozen through 2021; no production forecast is published.',
            '', 'See protocol.json, results.json, test-predictions.json, and experimental-ratings.json for reproducible detail.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=ROOT/'game_summaries/nflverse')
    run(parser.parse_args().data)
