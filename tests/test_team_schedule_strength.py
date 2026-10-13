import copy
import numpy as np
import pytest
from research.team_schedule_strength import schedule_strength


def game(a,b,week,margin):
    return {'gameId':f'{a}-{b}-{week}','week':week,'teams':[
        {'id':a,'homeAway':'home','score':20+margin},{'id':b,'homeAway':'away','score':20}]}


def test_focal_results_do_not_influence_its_opponent_strength():
    games=[game('A','B',1,10),game('A','C',2,-5),game('B','C',1,7)]
    venues={g['gameId']:1 for g in games}
    before=schedule_strength(games,['A','B','C'],3,None,2.5,venues)
    changed=copy.deepcopy(games);changed[0]['teams'][0]['score']=150
    after=schedule_strength(changed,['A','B','C'],3,None,2.5,venues)
    assert before['A']==after['A']
    for row in before.values():
        assert sum(o['contribution'] for o in row['opponents'])==pytest.approx(row['value'])
    ordered=sorted(before.values(),key=lambda r:-r['value'])
    assert [r['rank'] for r in ordered]==sorted(r['rank'] for r in ordered)


def test_future_week_is_rejected_and_empty_schedule_is_missing():
    g=game('A','B',2,7)
    with pytest.raises(ValueError):schedule_strength([g],['A','B'],2,None,2.5,{g['gameId']:1})
    result=schedule_strength([],['A','B'],1,None,2.5,{})
    assert all(r['value'] is None and r['rank'] is None and r['opponents']==[] for r in result.values())


def test_prior_and_current_responses_are_additive():
    from api.lib.team_season import FACTORS
    from research.team_power_experiments import ratings
    g=game('A','B',1,10)
    for i,t in enumerate(g['teams']):
        t['factors']={f['id']:{'usable':True,'numerator':3-i,'denominator':2} for f in FACTORS}
    ids=['A','B'];cfg={'priorGames':8,'halfLife':8,'profile':'uniform'}
    prior=np.arange(32,dtype=float).reshape(2,8,2)/20;points=np.array([2.,-2.])
    full=ratings([g],ids,2,prior,points,cfg)[2]
    data=ratings([g],ids,2,None,None,cfg)[2]
    doubled=ratings([g],ids,2,2*prior,2*points,cfg)[2]
    np.testing.assert_allclose(doubled-data,2*(full-data),atol=1e-12)
