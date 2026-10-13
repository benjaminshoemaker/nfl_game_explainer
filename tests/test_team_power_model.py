"""Research model invariants: temporal isolation, adjustment, missingness."""
import copy

import numpy as np
import pytest

pytest.importorskip('sklearn')
from api.lib.team_season import FACTORS
from research.team_power_model import estimate, make_features, metrics, fit, evaluate


def game(a, b, week=1, value=1, season=2020):
    def team(t, side, v):
        return {'id':t,'homeAway':side,'score':21 if side=='home' else 14,
                'factors':{f['id']:{'usable':True,'numerator':v,'denominator':1} for f in FACTORS}}
    return {'gameId':f'{season}-{week}-{a}-{b}','season':season,'week':week,
            'teams':[team(a,'home',value),team(b,'away',0)]}


def test_future_week_cannot_change_pregame_features():
    games=[game(str(i),str(i+1),week=w) for w in (1,2) for i in range(0,32,2)]
    before,_=make_features(games)
    future=copy.deepcopy(games)
    for g in future:
        if g['week']==2:
            g['teams'][0]['score']=99
            for f in g['teams'][0]['factors'].values(): f['numerator']=999
    after,_=make_features(future)
    assert before[16]['x']==after[16]['x']
    assert [r['x'] for r in before]==[r['x'] for r in after]
    assert all(r['latestInputWeek']<r['week'] for r in after)


def test_missing_observation_is_not_observed_zero():
    g=game('A','B')
    g['teams'][0]['factors']['success_rate']['usable']=False
    _,_,exposure=estimate([g],['A','B'])
    assert exposure[0,0]==0
    assert exposure[1,0]==1


def test_no_games_shrinks_prior_without_future_values():
    old=np.ones((2,8,2))
    effects,_,exposure=estimate([],['A','B'],old,prior_games=2)
    assert np.allclose(effects,.25)
    assert not exposure.any()


def test_opponent_adjustment_accounts_for_difficult_schedule():
    # A and B both record +1, but A faces a defense allowing -2 to others,
    # while B faces a defense allowing +2. A should receive stronger credit.
    gs=[game('A','C',value=1),game('B','D',value=1)]
    for _ in range(10):
        gs.extend([game('E','C',value=-2),game('E','D',value=2)])
    ids=['A','B','C','D','E']
    effects,_,_=estimate(gs,ids,prior_games=0)
    assert effects[0,0,0]>effects[1,0,0]


def test_turnover_net_direction_is_reversed():
    _,net,_=estimate([game('A','B',value=1)],['A','B'],prior_games=0)
    assert net[0,0]>0
    assert net[0,4]<0


def test_probability_metrics_exclude_ties_explicitly():
    rows=[{'margin':1},{'margin':-1},{'margin':0}]
    result=metrics(rows,np.array([1,-1,0]),np.array([.8,.2,.99]))
    assert result['games']==3 and result['decisiveGames']==2
    assert result['brier']==pytest.approx(.04)


def test_scaler_and_coefficients_fitted_on_training_only():
    train=[{'x':[i], 'margin':i} for i in range(-5,6)]
    models=fit(train,10)
    center=models[0].named_steps['standardscaler'].mean_.copy()
    evaluate([{'x':[999], 'margin':1}],models)
    assert np.array_equal(center,models[0].named_steps['standardscaler'].mean_)
