import json
import numpy as np
import pytest
from research.team_power_ratings import MODEL_PATH, contributions, predict_matchup
from research.team_power_situation import qb_features


@pytest.fixture
def model():
    return json.loads(MODEL_PATH.read_text())


def test_neutral_rating_is_symmetric_and_matches_frozen_model(model):
    rng=np.random.default_rng(42)
    values={t:rng.normal(size=len(model['featureNames'])).tolist() for t in ['A','B','C']}
    result={t['id']:t for t in contributions(values,model)}
    h=result['A']['features'];a=result['B']['features']
    forward=predict_matchup(h,a,model,neutral=True)
    backward=predict_matchup(a,h,model,neutral=True)
    assert result['A']['rating']-result['B']['rating']==pytest.approx((forward-backward)/2)
    assert sum(t['rating'] for t in result.values())==pytest.approx(0,abs=1e-10)
    for t in result.values():
        assert sum(t['contributions'].values())==pytest.approx(t['rating'])


def test_context_changes_matchup_not_team_ranking(model):
    values={'A':[0.]*len(model['featureNames']),'B':[0.]*len(model['featureNames'])}
    original=contributions(values,model)
    for name in ['neutral','restDifference','restMissing']:
        values['A'][model['featureNames'].index(name)]=10
    after=contributions(values,model)
    assert [t['rating'] for t in original]==[t['rating'] for t in after]
    h=original[0]['features'];a=original[1]['features']
    expected=3*model['coefficients'][model['featureNames'].index('restDifference')]
    assert predict_matchup(h,a,model,rest_difference=3)-predict_matchup(h,a,model)==pytest.approx(expected)


def test_bad_features_fail_closed(model):
    with pytest.raises(ValueError):contributions({'A':[float('nan')]*34},model)
    model['featureNames'][0]='unrecognized'
    with pytest.raises(ValueError):contributions({'A':[0]*34},model)


def test_qb_team_vectors_match_historical_difference_and_exclude_same_week():
    def game(w):return {'gameId':str(w),'season':2026,'week':w,'teams':[{'id':'A','homeAway':'home'},{'id':'B','homeAway':'away'}]}
    games=[game(1),game(2)]
    rows=[('1','A','qb1',20,100,0),('1','B','qb2',20,60,1)]
    by_team=qb_features(games,rows,by_team=True)['2']
    np.testing.assert_allclose(np.array(by_team['A'])-by_team['B'],qb_features(games,rows)['2'])
    assert qb_features(games,rows+[('2','A','new',50,500,0)],by_team=True)['2']==by_team


def test_component_ranks_ties_and_percentiles():
    from research.team_power_ratings import rank_components
    teams=[{'contributions':{'x':v}} for v in [2.,1.,1.,-2.]]
    rank_components(teams)
    ranks=[t['componentRanks']['x'] for t in teams]
    assert [r['rank'] for r in ranks]==[1,2,2,4]
    assert [r['percentile'] for r in ranks]==pytest.approx([100,50,50,0])
    assert ranks[1]['tied'] and not ranks[0]['tied']
    all_tied=[{'contributions':{'x':0.}} for _ in range(32)]
    rank_components(all_tied)
    assert all(t['componentRanks']['x']['percentile']==50 for t in all_tied)


def test_weight_groups_overlap_before_normalizing(model):
    from research.team_power_ratings import component_weights
    x=np.zeros((3,len(model['featureNames'])))
    model['coefficients']=[1.]*len(model['featureNames'])
    # The first factor's two terms cancel exactly; summing absolute individual
    # coefficients or their SDs would incorrectly assign it a positive weight.
    x[:,0]=[-1,0,1];x[:,8]=[1,0,-1]
    x[:,24]=[-1,0,1];x[:,28]=[-2,0,2]
    weights=component_weights(x,model)
    assert weights['success_rate']['weightPercent']==0
    assert weights['point_margin']['weightPercent']==pytest.approx(100/3)
    assert weights['quarterback']['weightPercent']==pytest.approx(200/3)
    assert sum(w['weightPercent'] for w in weights.values())==pytest.approx(100)


def test_weights_are_invariant_to_feature_unit_changes(model):
    from research.team_power_ratings import component_weights
    rng=np.random.default_rng(7)
    x=rng.normal(size=(100,len(model['featureNames'])))
    before=component_weights(x,model)
    x[:,0]*=100
    model['coefficients'][0]/=100
    after=component_weights(x,model)
    for key in before:
        assert before[key]['weightPercent']==pytest.approx(after[key]['weightPercent'])


def test_calculation_trace_reconciles_every_term_to_team_rating(model):
    from research.team_power_ratings import attach_calculation_trace
    rng=np.random.default_rng(17)
    ids=['A','B','C']
    values={t:rng.normal(size=len(model['featureNames'])).tolist() for t in ids}
    teams=contributions(values,model)
    original=[t['rating'] for t in teams]
    before=np.zeros((3,25))
    attach_calculation_trace(teams,before,ids,[],model)
    assert [t['rating'] for t in teams]==original
    for team in teams:
        total=0
        for key,component in team['calculationTrace'].items():
            assert sum(v['points'] for v in component['terms'])==pytest.approx(team['contributions'][key])
            for term in component['terms']:
                assert term['points']==pytest.approx((term['value']-term['leagueMean'])*term['coefficient'])
            if key!='quarterback':
                assert component['beforeOpponent']+component['opponentDelta']==pytest.approx(component['afterOpponent'])
            total+=component['contribution']
        assert total==pytest.approx(team['rating'])
        assert team['calculationTrace']['point_margin']['rawMargin'] is None


def test_opponent_impact_reconciles_and_excludes_qb(model):
    from research.team_power_ratings import attach_calculation_trace
    ids=['A','B','C']
    values={t:[0.]*len(model['featureNames']) for t in ids}
    # Opponent adjustment changes A's scoring estimate by +2, B's by -2.
    # Unequal QB history is intentionally retained in both diagnostic ratings.
    values['A'][24]=2;values['B'][24]=-2
    values['A'][28]=1;values['C'][30]=7
    teams=contributions(values,model)
    attach_calculation_trace(teams,np.zeros((3,25)),ids,[],model)
    by_id={t['id']:t for t in teams}
    assert by_id['A']['opponentAdjustment']['points']==pytest.approx(2*model['coefficients'][24])
    assert sum(t['opponentAdjustment']['points'] for t in teams)==pytest.approx(0,abs=1e-12)
    for team in teams:
        a=team['opponentAdjustment']
        assert a['ratingWithoutCurrentOpponentTerms']+a['points']==pytest.approx(team['rating'])
        assert sum(a['components'].values())==pytest.approx(a['points'])
        assert a['components']['quarterback']==pytest.approx(0)
    ordered=sorted(teams,key=lambda t:-t['opponentAdjustment']['points'])
    assert [t['opponentAdjustment']['rank'] for t in ordered]==[1,2,3]


def test_opponent_impact_all_tied(model):
    from research.team_power_ratings import attach_calculation_trace
    ids=['A','B','C']
    teams=contributions({t:[0.]*len(model['featureNames']) for t in ids},model)
    attach_calculation_trace(teams,np.zeros((3,25)),ids,[],model)
    assert all(t['opponentAdjustment']['rank']==1 and t['opponentAdjustment']['tied']
               and t['opponentAdjustment']['percentile']==50 for t in teams)
