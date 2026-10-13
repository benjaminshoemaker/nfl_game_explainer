"""One-time export of the preselected Ridge-10 adjusted-point comparator.

No model search or current-season outcomes are allowed here. Weekly runs only
read the committed export and never call this training command.
"""
import json
from pathlib import Path
import numpy as np
from research.team_power_final_audit import export_linear
from research.team_power_flexible import estimator
from research.team_power_ratings import MODEL_PATH, ROOT, digest


def freeze(base, destination):
    model = json.loads(MODEL_PATH.read_text())
    path = base / 'model-v6-situation/features.npz'
    if digest(path) != model['inputMatrixSha256']:
        raise ValueError('Training matrix does not match frozen model')
    meta = json.loads(path.with_suffix('.json').read_text())
    name = 'original_p8_h8_point_margin'
    spec = {'family': 'point_baseline', 'kind': 'ridge', 'strength': 10,
            'columns': [meta['columns'].index(name)]}
    with np.load(path) as data:
        mask = (data['season'] >= 2012) & (data['season'] <= 2025)
        if data['season'].max() > 2025:
            raise ValueError('Refuse a matrix containing evaluation-season outcomes')
        x = data['x'][mask][:, spec['columns']]
        fitted = estimator(spec, 'margin').fit(x, data['y'][mask])
        artifact = export_linear(fitted, [name], spec)
        np.testing.assert_allclose(fitted.predict(x),
            x @ np.array(artifact['coefficients']) + artifact['intercept'], atol=1e-10, rtol=0)
    artifact.update(trainingSeasons=[2012, 2025], intendedFirstSeason=2026,
                    inputMatrixSha256=digest(path),
                    selection='Previously established fixed_v2 comparator: priorGames=8, halfLife=8, Ridge alpha=10; no new selection',
                    exporterSha256=digest(Path(__file__)))
    with destination.open('x') as handle:
        json.dump(artifact, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return artifact


if __name__ == '__main__':
    print(freeze(ROOT / 'game_summaries/nflverse',
                 ROOT / 'research/models/frozen-point-baseline.json'))
