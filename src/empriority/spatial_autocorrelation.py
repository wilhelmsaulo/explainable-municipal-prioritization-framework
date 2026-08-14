from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _vertices(coordinates: Any, precision: int) -> Iterator[tuple[float, float]]:
    if (
        isinstance(coordinates, Sequence)
        and len(coordinates) >= 2
        and isinstance(coordinates[0], (int, float))
        and isinstance(coordinates[1], (int, float))
    ):
        yield (round(float(coordinates[0]), precision), round(float(coordinates[1]), precision))
        return
    for item in coordinates:
        yield from _vertices(item, precision)


def queen_contiguity(
    features: list[dict[str, Any]],
    precision: int = 6,
) -> list[set[int]]:
    """Build first-order queen neighbors from shared polygon vertices."""
    vertex_owners: dict[tuple[float, float], list[int]] = {}
    for index, feature in enumerate(features):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"Unsupported municipal geometry: {geometry.get('type')}")
        unique_vertices = set(_vertices(geometry.get("coordinates", []), precision))
        if not unique_vertices:
            raise ValueError(f"Municipal geometry {index} has no vertices")
        for vertex in unique_vertices:
            vertex_owners.setdefault(vertex, []).append(index)

    neighbors = [set() for _ in features]
    for owners in vertex_owners.values():
        if len(owners) < 2:
            continue
        for index in owners:
            neighbors[index].update(other for other in owners if other != index)
    return neighbors


def global_moran(values: np.ndarray, neighbors: list[set[int]]) -> float:
    """Calculate global Moran's I with row-standardized binary weights."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) != len(neighbors):
        raise ValueError("Values and spatial-neighbor rows must have the same length")
    if not np.isfinite(values).all():
        raise ValueError("Moran values must be complete and finite")
    islands = [index for index, adjacent in enumerate(neighbors) if not adjacent]
    if islands:
        raise ValueError(f"Queen contiguity produced islands at indices: {islands}")

    centered = values - values.mean()
    denominator = float(centered @ centered)
    if denominator <= 0:
        raise ValueError("Moran's I is undefined for a constant variable")

    numerator = 0.0
    weight_sum = 0.0
    for index, adjacent in enumerate(neighbors):
        weight = 1.0 / len(adjacent)
        for neighbor in adjacent:
            numerator += weight * centered[index] * centered[neighbor]
            weight_sum += weight
    return float(len(values) / weight_sum * numerator / denominator)


def calculate_spatial_autocorrelation(
    profiles: pd.DataFrame,
    geometry_path: str | Path,
    municipality_key: str,
    variable: str = "top_quartile_frequency",
    id_property: str = "CD_MUN",
    name_property: str = "NM_MUN",
    permutations: int = 999,
    seed: int = 42,
    precision: int = 6,
) -> dict[str, Any]:
    """Calculate audited global Moran's I for one municipal profile variable."""
    if permutations < 1:
        raise ValueError("Permutation count must be positive")
    if precision < 0:
        raise ValueError("Coordinate precision cannot be negative")
    if municipality_key not in profiles or variable not in profiles:
        raise ValueError(f"Profiles must contain {municipality_key} and {variable}")
    if profiles[municipality_key].duplicated().any():
        raise ValueError("Duplicate municipality codes in spatial profiles")

    document = json.loads(Path(geometry_path).read_text(encoding="utf-8"))
    features = document.get("features", [])
    if not features:
        raise ValueError("Municipal GeoJSON contains no features")

    profile_values = (
        profiles.assign(**{municipality_key: profiles[municipality_key].astype(str)})
        .set_index(municipality_key)[variable]
        .to_dict()
    )
    geometry_codes = [str(feature.get("properties", {}).get(id_property, "")) for feature in features]
    if any(not code for code in geometry_codes) or len(set(geometry_codes)) != len(geometry_codes):
        raise ValueError("Duplicate or empty municipality identifiers in municipal GeoJSON")
    missing_profiles = sorted(set(geometry_codes) - set(profile_values))
    extra_profiles = sorted(set(profile_values) - set(geometry_codes))
    if missing_profiles or extra_profiles:
        raise ValueError(
            f"Spatial identity mismatch; missing profiles={missing_profiles}, "
            f"extra profiles={extra_profiles}"
        )

    values = np.asarray([profile_values[code] for code in geometry_codes], dtype=float)
    neighbors = queen_contiguity(features, precision=precision)
    observed = global_moran(values, neighbors)
    expected = -1.0 / (len(values) - 1)

    rng = np.random.default_rng(seed)
    simulated = np.asarray(
        [global_moran(rng.permutation(values), neighbors) for _ in range(permutations)],
        dtype=float,
    )
    greater_or_equal = int(np.count_nonzero(simulated >= observed))
    pseudo_p = (greater_or_equal + 1) / (permutations + 1)
    degrees = np.asarray([len(adjacent) for adjacent in neighbors], dtype=int)
    islands = [
        str(features[index].get("properties", {}).get(name_property, geometry_codes[index]))
        for index, degree in enumerate(degrees)
        if degree == 0
    ]

    return {
        "variable": variable,
        "municipalities": int(len(values)),
        "spatial_weights": {
            "contiguity": "first_order_queen",
            "row_standardized": True,
            "coordinate_precision": precision,
            "undirected_edges": int(degrees.sum() // 2),
            "minimum_neighbors": int(degrees.min()),
            "maximum_neighbors": int(degrees.max()),
            "mean_neighbors": float(degrees.mean()),
            "islands": islands,
        },
        "moran_i": observed,
        "expected_i_under_randomness": expected,
        "permutation_test": {
            "alternative": "greater",
            "permutations": permutations,
            "random_seed": seed,
            "greater_or_equal_permutations": greater_or_equal,
            "pseudo_p_value": float(pseudo_p),
            "permuted_mean": float(simulated.mean()),
            "permuted_standard_deviation": float(simulated.std(ddof=1)),
        },
        "interpretation": (
            "Global spatial autocorrelation is not statistically significant at alpha=0.05."
            if pseudo_p >= 0.05
            else "Global spatial autocorrelation is statistically significant at alpha=0.05."
        ),
    }
