import numpy as np
import pytest
pytest.importorskip('sklearn')
from research.team_power_baseline_audit import fit_strength,predict


def game(a,b,week=1,margin=7):
    return {'gameId':a+b+str(week),'week':week,'teams':[{'id':a,'homeAway':'home','score':20+margin},{'id':b,'homeAway':'away','score':20}]}


def test_balanced_home_effect_is_not_team_strength():
    games=[game('A','B'),game('B','C'),game('C','A')]
    ratings,hfa=fit_strength(games,['A','B','C'],2,None,2.5,8,None,{g['gameId']:1 for g in games})
    np.testing.assert_allclose(ratings,0,atol=1e-12)
    assert hfa>2.5


def test_neutral_games_do_not_update_home_advantage():
    g=game('A','B',margin=0)
    ratings,hfa=fit_strength([g],['A','B'],2,None,2.5,8,None,{g['gameId']:0})
    np.testing.assert_allclose(ratings,0)
    assert hfa==2.5
    with pytest.raises(ValueError):fit_strength([g],['A','B'],1,None,2.5,8,None,{g['gameId']:0})


def test_neutral_equal_teams_have_no_home_intercept():
    seasons=np.repeat(np.arange(2012,2026),4)
    x=np.tile([[1.,2.5,0],[-1.,2.5,0],[0,0,0],[2,0,1]],(14,1));y=x[:,0]+x[:,1]
    idx,p=predict(x,y,seasons,10,True)
    assert np.all(p[np.all(x[idx]==0,axis=1)]==0)
