import numpy as np
import pytest
pytest.importorskip('sklearn')
from research.team_power_nested import select_candidate,paired_intervals


def test_selection_does_not_use_outer_year_outcomes_or_predictions():
    s=np.array([2015,2016,2017,2018,2019]);y=np.array([1.,2.,3.,4.,5.]);p=np.array([[1,2,3,99,99],[9,9,9,4,5]],dtype=float)
    assert select_candidate(p,y,s,2018,'margin',[0,1])==0
    p[:,3:]=10000;y[3:]=-10000
    assert select_candidate(p,y,s,2018,'margin',[0,1])==0


def test_three_season_window_discards_older_validation():
    s=np.array([2014,2015,2016,2017]);y=np.zeros(4);p=np.array([[1000,0,0,0],[0,1,1,1]])
    assert select_candidate(p,y,s,2018,'margin',[0,1])==0


def test_baseline_compared_on_identical_season_blocks():
    y=np.array([0.,1.,2.,3.]);s=np.array([2020,2020,2021,2021]);p=y+.5
    result=paired_intervals(y,p,p,s,'margin')
    assert result['difference']==0 and result['lower']==0 and result['upper']==0
