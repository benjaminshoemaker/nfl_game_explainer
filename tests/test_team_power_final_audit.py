import numpy as np
import pytest
pytest.importorskip('sklearn')
from research.team_power_flexible import estimator
from research.team_power_final_audit import export_linear


@pytest.mark.parametrize('kind,strength',[('ridge',100),('elastic',.1)])
def test_exported_formula_matches_model_including_intercept(kind,strength):
    rng=np.random.default_rng(22);x=rng.normal(size=(100,4))*[1,10,.01,5]+[0,30,.3,-1]
    y=2+x@np.array([.7,-.2,40,.1])+rng.normal(size=100)
    spec={'kind':kind,'strength':strength,'columns':[0,1,2,3]};m=estimator(spec,'margin').fit(x,y)
    artifact=export_linear(m,['a','b','c','d'],spec)
    novel=x[:10]+1
    np.testing.assert_allclose(novel@artifact['coefficients']+artifact['intercept'],m.predict(novel),atol=1e-10)
