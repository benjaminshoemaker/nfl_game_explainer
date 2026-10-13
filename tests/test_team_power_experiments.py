"""Regression guards for v2 temporal features and phased experiments."""
import copy

import numpy as np
import pytest
pytest.importorskip('sklearn')

from api.lib.team_season import FACTORS
from research.team_power_model import make_features as first_features
from research.team_power_experiments import BASE, decay, make_features, ratings, predict_rolling, specifications


def game(a,b,week=1,season=2012,value=1):
    return {'gameId':f'{season}-{week}-{a}-{b}','season':season,'week':week,'teams':[
        {'id':a,'homeAway':'home','score':21,'factors':{f['id']:{'usable':True,'numerator':value,'denominator':1} for f in FACTORS}},
        {'id':b,'homeAway':'away','score':14,'factors':{f['id']:{'usable':True,'numerator':0,'denominator':1} for f in FACTORS}}]}


def test_base_net_features_match_first_experiment():
    gs=[game(str(i),str(i+1),w,y,i+w) for y in (2011,2012) for w in (1,2,3) for i in range(0,32,2)]
    v1,_=first_features(gs,prior_games=4)
    v2=make_features(gs,BASE)
    assert [r['gameId'] for r in v1]==[r['gameId'] for r in v2]
    np.testing.assert_allclose([r['x'] for r in v1],[r['x'][:8] for r in v2],atol=1e-12)
    np.testing.assert_allclose([r['pointX'][0] for r in v1],[r['x'][24] for r in v2],atol=1e-12)


def test_net_equals_production_plus_prevention():
    rows=make_features([game('A','B',w,value=w) for w in (1,2,3)],BASE)
    for r in rows:
        np.testing.assert_allclose(r['x'][:8],np.array(r['x'][8:16])+r['x'][16:24])


def test_same_week_changes_cannot_change_any_predictor():
    gs=[game('A','B',w,value=w) for w in (1,2,3)]
    changed=copy.deepcopy(gs);changed[-1]['teams'][0]['score']=99
    for f in changed[-1]['teams'][0]['factors'].values():f['numerator']=999
    for half in (None,4,8):
        config={**BASE,'halfLife':half}
        a,b=make_features(gs,config),make_features(changed,config)
        np.testing.assert_array_equal([r['x'] for r in a],[r['x'] for r in b])


def test_recent_reversal_gets_more_weight():
    gs=[game('A','B',1,value=10),game('A','B',9,value=-10)]
    _,_,plain=ratings(gs,['A','B'],10,None,None,BASE)
    _,_,recent=ratings(gs,['A','B'],10,None,None,{**BASE,'halfLife':4})
    assert abs(plain[0,0])<1e-12
    assert recent[0,0]<0
    assert decay(4,4)==.5
    with pytest.raises(ValueError):decay(-1,4)
    with pytest.raises(ValueError):ratings(gs,['A','B'],9,None,None,BASE)


def test_missing_value_does_not_enter_fit_as_zero():
    g=game('A','B');g['teams'][0]['factors']['turnovers']['usable']=False
    g2=copy.deepcopy(g);g2['teams'][0]['factors']['turnovers']['numerator']=999
    a=ratings([g],['A','B'],2,None,None,BASE)[2]
    b=ratings([g2],['A','B'],2,None,None,BASE)[2]
    np.testing.assert_array_equal(a,b)


def test_factor_specific_stabilization_only_changes_selected_factors():
    g=game('A','B',value=4)
    a=ratings([g],['A','B'],2,None,None,BASE)[2]
    b=ratings([g],['A','B'],2,None,None,{**BASE,'profile':'factor_specific'})[2]
    assert b[0,0]==pytest.approx(a[0,0])
    assert abs(b[0,4])<abs(a[0,4])
    assert b[0,24]==pytest.approx(a[0,24])


def test_evaluation_outcomes_cannot_change_fitted_predictions():
    rows=[{'season':y,'week':i,'margin':i-2,'x':[float(i)]} for y in (2012,2013,2014) for i in range(5)]
    altered=copy.deepcopy(rows)
    for r in altered:
        if r['season']==2014:r['margin']=999
    for c in (None,.1):
        a=predict_rolling(rows,[0],[2014],probability_c=c)[1]
        b=predict_rolling(altered,[0],[2014],probability_c=c)[1]
        np.testing.assert_array_equal(a,b)


def test_search_contains_all_requested_families_without_duplicate_columns():
    specs=specifications()
    assert {s['family'] for s in specs}=={'point_baseline','all_eight','fewer_factors','point_plus_factors','separate_sides'}
    assert all(len(s['columns'])==len(set(s['columns'])) for s in specs)
    assert len({tuple(s['columns']) for s in specs})==len(specs)


def test_opponent_diagnostic_holds_priors_and_rewards_tougher_defenses():
    gs=[game('A','C',value=1),game('B','D',value=1)]
    for _ in range(10):
        gs.extend([game('E','C',value=-2),game('E','D',value=2)])
    ids=['A','B','C','D','E']
    adjusted=ratings(gs,ids,2,None,None,BASE)[2]
    control=ratings(gs,ids,2,None,None,BASE,adjust_opponents=False)[2]
    assert control[0,8]==pytest.approx(control[1,8])
    assert adjusted[0,8]>adjusted[1,8]
    prior=np.arange(80).reshape(5,8,2)/100
    points=np.arange(5,dtype=float)
    actual=ratings([],ids,2,prior,points,BASE)
    diagnostic=ratings([],ids,2,prior,points,BASE,adjust_opponents=False)
    for a,b in zip(actual,diagnostic):np.testing.assert_allclose(a,b)
