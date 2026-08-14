import json

import numpy as np
import pandas as pd

from empriority.spatial_autocorrelation import (
    calculate_spatial_autocorrelation,
    global_moran,
    queen_contiguity,
)


def _grid_features() -> list[dict[str, object]]:
    features = []
    for row in range(2):
        for column in range(2):
            x0, y0 = float(column), float(row)
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "CD_MUN": str(row * 2 + column + 1),
                        "NM_MUN": f"M{row * 2 + column + 1}",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [x0, y0],
                                [x0 + 1, y0],
                                [x0 + 1, y0 + 1],
                                [x0, y0 + 1],
                                [x0, y0],
                            ]
                        ],
                    },
                }
            )
    return features


def test_queen_contiguity_detects_shared_vertices() -> None:
    neighbors = queen_contiguity(_grid_features())
    assert all(len(adjacent) == 3 for adjacent in neighbors)
    assert all(index not in adjacent for index, adjacent in enumerate(neighbors))


def test_global_moran_is_finite_for_nonconstant_values() -> None:
    neighbors = queen_contiguity(_grid_features())
    observed = global_moran(np.array([0.0, 0.2, 0.8, 1.0]), neighbors)
    assert np.isfinite(observed)


def test_spatial_autocorrelation_is_reproducible(tmp_path) -> None:
    geometry = {"type": "FeatureCollection", "features": _grid_features()}
    geometry_path = tmp_path / "municipalities.geojson"
    geometry_path.write_text(json.dumps(geometry), encoding="utf-8")
    profiles = pd.DataFrame(
        {
            "municipality_code": ["1", "2", "3", "4"],
            "top_quartile_frequency": [0.0, 0.2, 0.8, 1.0],
        }
    )

    first = calculate_spatial_autocorrelation(
        profiles,
        geometry_path,
        municipality_key="municipality_code",
        permutations=99,
        seed=42,
    )
    second = calculate_spatial_autocorrelation(
        profiles,
        geometry_path,
        municipality_key="municipality_code",
        permutations=99,
        seed=42,
    )

    assert first == second
    assert first["municipalities"] == 4
    assert first["spatial_weights"]["undirected_edges"] == 6
    assert first["spatial_weights"]["islands"] == []
    assert 0.0 <= first["permutation_test"]["pseudo_p_value"] <= 1.0
