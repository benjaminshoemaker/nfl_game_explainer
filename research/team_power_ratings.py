"""Publish frozen-model strength snapshots; never fit on new outcomes.

Run: PYTHONPATH=. .venv/bin/python research/team_power_ratings.py
The default output is a dated retrospective review, not a pregame archive.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from research.team_power_experiments import FEATURE_NAMES, KEYS, ratings
from research.team_power_model import load_records
from research.team_power_situation import QB_NAMES, qb_features, source_rows
from research.build_team_seasons import save_json
from research.team_schedule_strength import schedule_strength, prior_schedule_state

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / 'research/models/frozen-margin-model.json'
CONTEXT = ('restDifference', 'neutral', 'restMissing')
PREFIX = 'original_p8_h8_'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component_indices():
    return {**{key:[i,i+8,i+16] for i,key in enumerate(KEYS)},
            'point_margin':[24], 'quarterback':list(range(28,34))}


def component_weights(training_x, model):
    """Comparable, fixed reference weights; not literal percentage coefficients.

    Compute SD of each grouped contribution on the original training matchup
    rows, then normalize those SDs. Group before measuring spread so redundant
    net/own/prevention terms and their covariance are handled together.
    This is not variance attribution or an independent measure of importance.
    """
    x=np.asarray(training_x,dtype=float)
    if x.ndim!=2 or x.shape[1]!=len(model['featureNames']) or not np.isfinite(x).all() or len(x)<2:
        raise ValueError('Invalid reference matrix')
    weighted=x*np.asarray(model['coefficients'])
    spreads={k:float(np.std(weighted[:,ix].sum(axis=1))) for k,ix in component_indices().items()}
    total=sum(spreads.values())
    return {k:{'weightPercent':100*v/total if total else 0., 'referenceSdPoints':v,
               'terms':[{'feature':model['featureNames'][i], 'coefficient':model['coefficients'][i]}
                        for i in component_indices()[k]]} for k,v in spreads.items()}


def rank_components(teams):
    """Competition ranks and midpoint percentiles; higher contribution is better."""
    n=len(teams)
    for team in teams:
        team['componentRanks']={}
        for key,value in team['contributions'].items():
            peers=[other['contributions'][key] for other in teams]
            above=sum(v>value for v in peers)
            tied=sum(v==value for v in peers)
            percentile=100*(n-1-above-(tied-1)/2)/(n-1) if n>1 else 50.
            team['componentRanks'][key]={'rank':above+1, 'tied':tied>1,
                                          'percentile':percentile, 'rankPool':n}
    return teams


def contributions(values, model):
    """Center every contribution on the same league, excluding game context.

Removing the designation/intercept offset is equivalent to averaging a team's
    neutral margin over both home/away designations. It guarantees antisymmetry.
    """
    names = model['featureNames']
    expected = [PREFIX + k for k in FEATURE_NAMES] + list(CONTEXT) + QB_NAMES
    if names != expected:
        raise ValueError('Unsupported feature contract; do not silently reuse ratings')
    ids = sorted(values)
    x = np.array([values[t] for t in ids], dtype=float)
    if x.shape != (len(ids), len(names)) or not np.isfinite(x).all():
        raise ValueError('Incomplete/non-finite feature vectors')
    weighted = (x - x.mean(axis=0)) * np.array(model['coefficients'])
    weighted[:, [names.index(k) for k in CONTEXT]] = 0
    output = []
    for i, team in enumerate(ids):
        groups = {key: float(weighted[i, [j, j+8, j+16]].sum()) for j,key in enumerate(KEYS)}
        groups['point_margin'] = float(weighted[i,24])
        groups['quarterback'] = float(weighted[i,28:].sum())
        output.append({'id':team, 'rating':sum(groups.values()), 'contributions':groups,
                       'qbHistoryMissing':bool(x[i,-1]), 'features':dict(zip(names,x[i].tolist()))})
    output.sort(key=lambda t:(-t['rating'], t['id']))
    for i,t in enumerate(output):
        t['rank'] = 1 + sum(p['rating'] > t['rating'] for p in output)
    return rank_components(output)


def attach_calculation_trace(teams, unadjusted, ids, current, model):
    """Explain actual contributions and a controlled current-opponent comparison.

    The comparison holds the real prior, decay and penalties fixed; it is not
    an alternate unadjusted historical model and does not change predictions.
    """
    names=model['featureNames']
    means={k:float(np.mean([t['features'][k] for t in teams])) for k in names}
    by_id={team:i for i,team in enumerate(ids)}
    for team in teams:
        trace={}
        for key,columns in component_indices().items():
            terms=[]
            for j in columns:
                name=names[j];value=team['features'][name];centered=value-means[name]
                terms.append({'name':name,'value':value,'leagueMean':means[name],
                              'centeredValue':centered,'coefficient':model['coefficients'][j],
                              'points':centered*model['coefficients'][j]})
            trace[key]={'terms':terms,'contribution':team['contributions'][key]}
            if key!='quarterback':
                j=columns[0]
                trace[key].update(beforeOpponent=float(unadjusted[by_id[team['id']],j]),
                                  afterOpponent=team['features'][names[j]],
                                  opponentDelta=team['features'][names[j]]-float(unadjusted[by_id[team['id']],j]))
        margins=[]
        for game in current:
            own=next((t for t in game['teams'] if t['id']==team['id']),None)
            if own is not None:
                opponent=next(t for t in game['teams'] if t['id']!=team['id'])
                margins.append(own['score']-opponent['score'])
        trace['point_margin']['rawMargin']=float(np.mean(margins)) if margins else None
        team['calculationTrace']=trace
    # Reapply the exact frozen formula to the diagnostic feature vectors, with
    # QB/context unchanged and each feature centered over the same league.
    control_values={t['id']:[float(v) for v in unadjusted[by_id[t['id']]]]+
                    [t['features'][k] for k in names[25:]] for t in teams}
    controls={t['id']:t for t in contributions(control_values,model)}
    for team in teams:
        control=controls[team['id']]
        deltas={k:team['contributions'][k]-control['contributions'][k]
                for k in component_indices()}
        team['opponentAdjustment']={
            'points':team['rating']-control['rating'],
            'ratingWithoutCurrentOpponentTerms':control['rating'],
            'components':deltas,
            'scope':'Current-season opponent terms only; historical prior held fixed'}
    for team in teams:
        value=team['opponentAdjustment']['points']
        peers=[t['opponentAdjustment']['points'] for t in teams]
        above=sum(v>value for v in peers)
        tied=sum(v==value for v in peers)
        team['opponentAdjustment'].update(rank=above+1,rankPool=len(peers),tied=tied>1,
            percentile=100*(len(peers)-1-above-(tied-1)/2)/(len(peers)-1) if len(peers)>1 else 50.)
    return teams


def predict_matchup(home, away, model, *, rest_difference=0, neutral=False, rest_missing=False):
    """Original frozen prediction, retaining its learned designation offset."""
    values = {k:home[k]-away[k] for k in model['featureNames']}
    values.update(restDifference=rest_difference, neutral=float(neutral), restMissing=float(rest_missing))
    return float(model['intercept'] + sum(values[k]*b for k,b in zip(model['featureNames'],model['coefficients'])))


def build(base, season=2026, through_week=3, *, pbp_pattern='/tmp/nfl_game_explainer_pbp_{season}.parquet'):
    model = json.loads(MODEL_PATH.read_text())
    if season < model['intendedFirstSeason']:
        raise ValueError('Frozen model cannot generate honest earlier-season ratings')
    records, inputs = load_records(base)
    records = [g for g in records if g['season'] < season or (g['season']==season and g['week']<=through_week)]
    current = [g for g in records if g['season']==season]
    if not current or max(g['week'] for g in current) != through_week:
        raise ValueError('Requested completed-week snapshot is unavailable')
    ids = sorted({t['id'] for g in records for t in g['teams']})
    if len(ids) != 32:
        raise ValueError('Expected all 32 NFL teams')
    config = {'priorGames':8, 'profile':'uniform', 'halfLife':8}
    prior = old_points = None
    for year in range(2011,season):
        games = [g for g in records if g['season']==year]
        if not games:
            raise ValueError(f'Missing prior season {year}')
        prior, old_points, _ = ratings(games,ids,max(g['week'] for g in games)+1,prior,old_points,config)
    _, _, strength = ratings(current,ids,through_week+1,prior,old_points,config)
    _, _, unadjusted = ratings(current,ids,through_week+1,prior,old_points,config,adjust_opponents=False)
    _, _, current_only = ratings(current,ids,through_week+1,None,None,config)
    qbrows = []
    # The chosen QB's history window is current season and two previous seasons.
    qb_records = [g for g in records if g['season']>=season-2]
    allowed = {g['gameId'] for g in qb_records}
    qb_inputs = []
    for year in range(season-2,season+1):
        path = Path(str(pbp_pattern).format(season=year))
        _, rows = source_rows(path,year)
        qbrows.extend(r for r in rows if r[0] in allowed)
        qb_inputs.append({'path':str(path),'sha256':digest(path)})
    available = {(r[0],r[1]) for r in qbrows}
    if any((g['gameId'],t['id']) not in available for g in qb_records for t in g['teams']):
        raise ValueError('QB source missing games; refuse to silently use stale history')
    probes = [{'gameId':f'probe-{i}', 'season':season,'week':through_week+1,
               'teams':[{'id':ids[i],'homeAway':'home'},{'id':ids[i+1],'homeAway':'away'}]}
              for i in range(0,len(ids),2)]
    qb = qb_features(qb_records+probes,qbrows,by_team=True)
    team_qb = {k:v for g in probes for k,v in qb[g['gameId']].items()}
    values = {t:strength[i].tolist()+[0,1,0]+team_qb[t] for i,t in enumerate(ids)}
    matrix_path=base/'model-v6-situation/features.npz'
    if digest(matrix_path)!=model['inputMatrixSha256']:
        raise ValueError('Training reference matrix differs from frozen artifact')
    with np.load(matrix_path) as matrix:
        lo,hi=model['trainingSeasons']
        mask=(matrix['season']>=lo)&(matrix['season']<=hi)
        weights=component_weights(matrix['x'][mask][:,model['spec']['columns']],model)
    output = {'season':season,'throughWeek':through_week,'generatedAt':datetime.now(timezone.utc).isoformat(),
              'status':'retrospective snapshot; not a pregame publication',
              'target':'Expected upcoming-game scoring margin; team strength in points relative to league average',
              'conditions':'Equal rest; venue/designation offsets excluded; centered on all 32 teams',
              'modelSha256':digest(MODEL_PATH), 'builderSha256':digest(Path(__file__)), 'modelTrainingSeasons':model['trainingSeasons'],
              'inputs':inputs,'qbInputs':qb_inputs,
              'limits':['Past QB usage, not a confirmed next starter',
                        'QB source is a refreshed corrected snapshot; only eligible completed-game IDs are used',
                        'No future-season record or playoff forecast',
                        'Historical team estimates retain the original model feature definitions, including their venue exposure'],
              'componentWeights':weights,
              'weightDefinition':'SD of grouped contribution on 2012–2025 training matchups, normalized to sum to 100%; descriptive scale, not causal importance or literal percentage coefficients',
              'teams':attach_calculation_trace(contributions(values,model),unadjusted,ids,current,model)}
    venues={r['game_id']:float(r['location']!='Neutral') for r in csv.DictReader((base/'sources/games.csv').open())}
    schedule_prior,home=prior_schedule_state(records,ids,season,venues)
    sos=schedule_strength(current,ids,through_week+1,schedule_prior,home,venues)
    # The linear fit decomposes exactly into a current-observation response and
    # a prior response when the same design/penalties/league baseline are held.
    data_values={t:current_only[i].tolist()+[0.]*9 for i,t in enumerate(ids)}
    data_parts={t['id']:t for t in contributions(data_values,model)}
    for team in output['teams']:
        team['scheduleDifficulty']=sos[team['id']]
        team['evidenceContributions']={k:{'currentSeason':data_parts[team['id']]['contributions'][k],
            'priorSeasons':v-data_parts[team['id']]['contributions'][k]}
            for k,v in team['contributions'].items() if k!='quarterback'}
    output['scheduleDefinition']='Mean venue-adjusted scoring strength of completed opponents, each game equally weighted; current-season games involving the focal team excluded from strength fitting; actual historical prior retained. Rank 1 = hardest.'
    save_json(base/f'{season}-week-{through_week}-power.json',output)
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season',type=int,default=2026)
    parser.add_argument('--through-week',type=int,default=3)
    args=parser.parse_args()
    result=build(ROOT/'game_summaries/nflverse',args.season,args.through_week)
    print(f"Built {len(result['teams'])} ratings through {result['season']} Week {result['throughWeek']}")
