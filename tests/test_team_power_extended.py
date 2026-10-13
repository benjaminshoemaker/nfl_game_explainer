import csv
import numpy as np
import pytest
pytest.importorskip('sklearn')
from research.team_power_extended_data import schedule_context, revised_records
from research.team_power_flexible import rolling


def test_schedule_whitelist_excludes_retrospective_and_market_fields(tmp_path):
    p=tmp_path/'schedule.csv'
    p.write_text('game_id,game_type,home_rest,away_rest,location,spread_line,home_qb_id,temp\ng,REG,10,7,Neutral,99,future,90\n')
    r=schedule_context(p)['g']
    assert r=={'restDifference':3.,'neutral':1.,'restMissing':0.}


def test_opportunity_normalization_preserves_unusable_sources():
    fs={k:{'numerator':10,'denominator':1,'reasons':[],'usable':True} for k in ('turnovers','penalties','non_offensive_points','field_position')}
    fs['turnovers']['reasons']=['ambiguous'];fs['turnovers']['usable']=False
    g={'gameId':'g','teams':[{'id':'A','counters':{'Drives Count':10,'Plays':50},'factors':fs}]}
    r=revised_records([g],{},'opportunity')[0]['teams'][0]['factors']
    assert not r['turnovers']['usable']
    assert r['penalties']['value']==.2
    assert fs['penalties']['denominator']==1


def test_flexible_models_ignore_evaluation_targets():
    x=np.arange(80,dtype=float).reshape(40,2);s=np.array([2012]*20+[2013]*20);y=np.tile(np.arange(20)-10,2).astype(float)
    altered=y.copy();altered[20:]=999
    for kind,strength in [('ridge',10),('elastic',.1),('tree',3)]:
        spec={'kind':kind,'strength':strength,'columns':[0,1]}
        for objective in ('margin','probability'):
            a=rolling(x,y,s,spec,objective,[2013])[1]
            b=rolling(x,altered,s,spec,objective,[2013])[1]
            np.testing.assert_array_equal(a,b)
