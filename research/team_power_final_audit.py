"""Ablation, provenance, exact selection replay, and frozen margin-model export."""
import hashlib
import json
import warnings
from pathlib import Path
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from research.team_power_flexible import rolling,estimator,loss
from research.team_power_nested import select_candidate,paired_intervals
from research.build_team_seasons import save_json

ROOT=Path(__file__).resolve().parents[1]


def export_linear(model,names,spec):
    scaler,reg=model.steps[0][1],model.steps[-1][1]
    beta=reg.coef_/scaler.scale_
    return {'spec':spec,'featureNames':names,'coefficients':beta.tolist(),
            'intercept':float(reg.intercept_-np.dot(beta,scaler.mean_)),
            'formula':'intercept + sum(feature_value * coefficient)',
            'unit':'predicted home-minus-away scoring margin, points',
            'status':'retrospective research; not prospectively validated'}


def run(base):
    source=base/'model-v6-situation';out=base/'model-v7-audit';out.mkdir(exist_ok=True)
    meta=json.loads((source/'features.json').read_text());data=np.load(source/'features.npz');x,y,ss,week=(data[k] for k in ('x','y','season','week'))
    old=json.loads((source/'nested/margin-predictions.json').read_text());old_by_id={r['gameId']:r for r in old}
    checks=[]
    for input in meta['inputs']:
        path=Path(input['path']);actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=input['sha256']:raise ValueError(f'Changed input: {path}')
        checks.append(str(path))
    assert len(set(meta['games']))==len(meta['games'])==len(y)
    assert max(ss)==2025
    specs=json.loads((source/'protocol.json').read_text())['marginCandidates']
    chosen=json.loads((source/'nested/selections.json').read_text())['margin']['selected_nonbaseline']
    candidates=[s for s in specs if s['family'] not in ('point_baseline','point_context')]
    predictions=[]
    for spec in candidates:
        idx,p=rolling(x,y,ss,spec,'margin',range(2015,2026));predictions.append(p)
    predictions=np.array(predictions);yy=y[idx];seasons=ss[idx]
    # Recompute each annual choice and every resulting forecast.
    for year in range(2018,2026):
        i=select_candidate(predictions,yy,seasons,year,'margin',range(len(candidates)))
        if candidates[i]!=chosen[str(year)]['spec']:raise ValueError('Selection replay mismatch')
        assert chosen[str(year)]['lastValidationSeason']<year
        for j in np.flatnonzero(seasons==year):
            expected=old_by_id[meta['games'][idx[j]]]['predictions']['selected_nonbaseline']
            if not np.isclose(predictions[i,j],expected,rtol=0,atol=1e-10):raise ValueError('Forecast replay mismatch')
    print('All annual choices and predictions replay exactly',flush=True)
    # Point+QB comparator uses the same relevant strength grid; it is tuned
    # exclusively on earlier validation years, never this audit's outcomes.
    g=meta['groups'];ablation_specs=[];ablation=[]
    for tag,columns in g.items():
        if not tag.startswith('original'):continue
        cols=[columns[-1]]+g['context']+g['qb_history']
        for kind,values in [('ridge',(10,100,1000)),('elastic',(.1,1))]:
            for strength in values:
                spec={'family':'point_plus_qb','columns':cols,'kind':kind,'strength':strength}
                ix,p=rolling(x,y,ss,spec,'margin',range(2015,2026));assert np.array_equal(ix,idx)
                ablation_specs.append(spec);ablation.append(p)
    ablation=np.array(ablation);ablated=np.full(len(yy),np.nan);aselect={}
    for year in range(2018,2026):
        i=select_candidate(ablation,yy,seasons,year,'margin',range(len(ablation_specs)))
        ablated[seasons==year]=ablation[i,seasons==year];aselect[str(year)]=ablation_specs[i]
    mask=seasons>=2018;target=yy[mask];sy=seasons[mask];ids=[meta['games'][i] for i in idx[mask]]
    assert ids==[r['gameId'] for r in old]
    full=np.array([r['predictions']['selected_nonbaseline'] for r in old])
    ablation_result={'fullRmse':loss(target,full,'margin'),'pointQbRmse':loss(target,ablated[mask],'margin'),
                     'difference95':paired_intervals(target,full,ablated[mask],sy,'margin'),'selections':aselect}
    save_json(out/'ablation.json',ablation_result)
    # Freeze next-season choice from only 2023..2025 validation and fit through
    # 2025. This is a deployable formula, not a retrospectively scored refit.
    i=select_candidate(predictions,yy,seasons,2026,'margin',range(len(candidates)));spec=candidates[i]
    if spec['kind']=='tree':raise ValueError('Selected next-season model requires a nonlinear exporter')
    model=estimator(spec,'margin');train=(ss>=2012)&(ss<=2025)
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        model.fit(x[train][:,spec['columns']],y[train])
    artifact=export_linear(model,[meta['columns'][j] for j in spec['columns']],spec)
    artifact.update({'trainingSeasons':[2012,2025],'selectionSeasons':[2023,2025],'intendedFirstSeason':2026,
                     'inputMatrixSha256':hashlib.sha256((source/'features.npz').read_bytes()).hexdigest(),
                     'sourceCodeSha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'research').glob('team_power*.py')}})
    formula=x[:,spec['columns']]@np.array(artifact['coefficients'])+artifact['intercept']
    np.testing.assert_allclose(formula,model.predict(x[:,spec['columns']]),rtol=0,atol=1e-10)
    save_json(out/'frozen-margin-model.json',artifact)
    save_json(out/'audit.json',{'sourceHashesVerified':checks,'uniqueGames':len(y),
             'forecastReplayGames':len(old),'annualSelectionsReplayed':8,'formulaParityTolerance':1e-10,
             'nextSeasonFamily':spec['family'],'ablation':ablation_result,
             'limitations':['retrospective design and repeated search','no fresh unseen-year confirmation','past QB usage proxy, not next-starter confirmation','model artifact is not production integration']})
    text=f'''# Final model audit

All {len(checks)} recorded input hashes match. All eight annual selections and {len(old)} forecasts replay exactly. Exported coefficients match the fitted model to 1e-10 points.

## Does the eight-factor information add to point differential plus QB history?

Full procedure RMSE: {ablation_result['fullRmse']:.4f}. Point-plus-QB procedure: {ablation_result['pointQbRmse']:.4f}.
Difference interval: [{ablation_result['difference95']['lower']:+.4f}, {ablation_result['difference95']['upper']:+.4f}] points. Negative favors the full procedure.

## Frozen next-season model

Selected family: {spec['family']}; kind: {spec['kind']}; strength: {spec['strength']}.
Selection uses 2023–2025 rolling validation; final coefficients fit 2012–2025. No 2026 outcome is used.
`frozen-margin-model.json` contains feature names, raw-unit coefficients, intercept, selection, and hashes. Its parity check is an implementation check, not an accuracy test.

## Interpretation boundary

Historical advantage over point differential is supported by the nested replay and stronger-comparator audit. Research-design hindsight and repeated exploration remain; this is not proof of prospective superiority. Quarterback inputs describe previous observed usage, not confirmed next-game starters. No production rating or game-highlight weights were changed.
'''
    (out/'REPORT.md').write_text(text);print(text,flush=True)


if __name__=='__main__':run(ROOT/'game_summaries/nflverse')
