"""Export the 2025 field-goal EP baseline used by epa_benchmark.py.

Requires research/requirements.txt and the pinned 2025 nflverse parquet file.
The exported tree format is read by api/lib/epa.py without sklearn at runtime.
"""

import json
from pathlib import Path

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from research.epa_benchmark import PBP_2025, ensure_parquet, feature_vector, reference_rows


def main():
    ensure_parquet(2025, PBP_2025)
    rows = reference_rows(
        duckdb.connect(), PBP_2025,
        "season=2025 and season_type='REG' and ep is not null",
    )
    field_goals = [row for row in rows if row['play_type'] == 'field_goal'
                   and feature_vector(row) is not None]
    model = HistGradientBoostingRegressor(
        max_iter=160, max_leaf_nodes=12, min_samples_leaf=15,
        learning_rate=0.05, l2_regularization=5, random_state=5,
    ).fit(
        np.asarray([feature_vector(row) for row in field_goals], dtype=float),
        np.asarray([row['ep'] for row in field_goals], dtype=float),
    )
    payload = {
        'source': '2025 nflverse regular-season field goals',
        'sample_size': len(field_goals),
        'baseline': float(model._baseline_prediction[0, 0]),
        'trees': [[{
            'value': float(node['value']),
            'feature': int(node['feature_idx']),
            'threshold': float(node['num_threshold']),
            'missing_left': bool(node['missing_go_to_left']),
            'left': int(node['left']),
            'right': int(node['right']),
            'leaf': bool(node['is_leaf']),
        } for node in predictor[0].nodes] for predictor in model._predictors],
    }
    output = Path(__file__).resolve().parents[1] / 'api/lib/data/fg_ep_2025.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(',', ':')) + '\n')
    print(f'{output}: {len(field_goals)} field goals, {len(payload["trees"])} trees')


if __name__ == '__main__':
    main()
