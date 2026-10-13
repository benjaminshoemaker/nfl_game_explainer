import pytest
pytest.importorskip('sklearn')
from research.team_power_situation import qb_features


def game(week):
    return {'gameId':str(week),'season':2020,'week':week,'teams':[{'id':'A','homeAway':'home'},{'id':'B','homeAway':'away'}]}


def test_qb_features_ignore_target_game_and_later_starter():
    games=[game(1),game(2),game(3)]
    past=[('1','A','q1',30,200,1),('1','B','q2',30,150,2)]
    later=past+[('2','A','replacement',40,500,0),('3','A','q1',10,50,3)]
    assert qb_features(games,past)['2']==qb_features(games,later)['2']
    assert qb_features(games,later)['3'][0]==1


def test_no_history_has_explicit_missing_not_future_starter():
    assert qb_features([game(1)],[('1','A','q',30,300,0)])['1']==[0]*6
    # Both teams are missing, so the missingness difference is zero.
    result=qb_features([game(1),game(2)],[('1','A','q',30,300,0)])['2']
    assert result[-1]==-1
    assert result[2]==10
