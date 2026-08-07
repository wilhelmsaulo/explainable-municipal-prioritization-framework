"""Data contract and presentation helpers for the scientific dashboard.

This module never recalculates framework scores. It only validates and reshapes
the outputs produced by the audited pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

EXPECTED_MUNICIPALITIES = 144
EXPECTED_SCENARIOS = 48
REFERENCE_SCENARIO = "equal_modes__equal_roles___equal_dimensions"

TRANSPORT_LABELS = {
    "equal_modes__equal_roles": "Modos iguais · papéis iguais",
    "equal_modes__availability_emphasis": "Modos iguais · ênfase em disponibilidade",
    "equal_modes__proximity_emphasis": "Modos iguais · ênfase em proximidade",
    "road_emphasis__equal_roles": "Ênfase rodoviária · papéis iguais",
    "road_emphasis__availability_emphasis": "Ênfase rodoviária · disponibilidade",
    "road_emphasis__proximity_emphasis": "Ênfase rodoviária · proximidade",
    "water_emphasis__equal_roles": "Ênfase hidroviária · papéis iguais",
    "water_emphasis__availability_emphasis": "Ênfase hidroviária · disponibilidade",
    "water_emphasis__proximity_emphasis": "Ênfase hidroviária · proximidade",
    "air_emphasis__equal_roles": "Ênfase aérea · papéis iguais",
    "air_emphasis__availability_emphasis": "Ênfase aérea · disponibilidade",
    "air_emphasis__proximity_emphasis": "Ênfase aérea · proximidade",
}

WEIGHT_LABELS = {
    "equal_dimensions": "Dimensões com pesos iguais",
    "institutional_emphasis": "Ênfase institucional",
    "service_network_emphasis": "Ênfase na rede de serviços",
    "transport_emphasis": "Ênfase no transporte",
}

PROFILE_LABELS = {
    "robust_higher_capacity_strengthening_priority": "Prioridade superior robusta",
    "scenario_sensitive_higher_priority": "Prioridade superior sensível ao cenário",
    "intermediate_or_scenario_sensitive": "Intermediária ou sensível ao cenário",
    "robust_lower_relative_priority": "Prioridade relativa inferior robusta",
}


@dataclass(frozen=True)
class DashboardData:
    profiles: pd.DataFrame
    scenarios: pd.DataFrame
    explanations: pd.DataFrame
    municipalities: pd.DataFrame
    agreement: pd.DataFrame
    correlations: pd.DataFrame
    scenario_names: tuple[str, ...]


def scenario_names(frame: pd.DataFrame) -> tuple[str, ...]:
    scores = {column.removesuffix("__score") for column in frame if column.endswith("__score")}
    ranks = {column.removesuffix("__rank") for column in frame if column.endswith("__rank")}
    names = tuple(sorted(scores & ranks))
    if len(names) != EXPECTED_SCENARIOS:
        raise ValueError(f"Expected {EXPECTED_SCENARIOS} complete scenarios, found {len(names)}")
    return names


def split_scenario(name: str) -> tuple[str, str]:
    parts = name.split("___")
    if len(parts) != 2:
        raise ValueError(f"Invalid scenario name: {name}")
    return parts[0], parts[1]


def scenario_label(name: str) -> str:
    transport, weight = split_scenario(name)
    return f"{TRANSPORT_LABELS.get(transport, transport)} | {WEIGHT_LABELS.get(weight, weight)}"


def selected_scenario(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    score = f"{name}__score"
    rank = f"{name}__rank"
    if score not in frame or rank not in frame:
        raise KeyError(f"Scenario not found: {name}")
    result = frame[["municipality_code", "municipality", score, rank]].copy()
    return result.rename(columns={score: "selected_score", rank: "selected_rank"})


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required dashboard input is missing: {path}")
    return pd.read_csv(path, dtype={"municipality_code": str})


def load_dashboard_data(root: Path) -> DashboardData:
    results = root / "data" / "results"
    processed = root / "data" / "processed"

    profiles = _read(results / "integrated_capacity_priority_profiles.csv")
    scenarios = _read(results / "integrated_capacity_priority_scenarios.csv")
    explanations = _read(results / "capacity_municipality_explanations.csv")
    agreement = _read(results / "capacity_scenario_agreement.csv")
    correlations = _read(results / "capacity_dimension_correlations.csv")
    matrix = _read(processed / "integrated_municipal_matrix.csv")

    key = "municipality_code"
    required_coordinates = [
        key,
        "municipality",
        "protection_network_seat_latitude",
        "protection_network_seat_longitude",
    ]
    municipalities = matrix[required_coordinates].copy()
    municipalities = municipalities.rename(
        columns={
            "protection_network_seat_latitude": "latitude",
            "protection_network_seat_longitude": "longitude",
        }
    )

    names = scenario_names(scenarios)
    for label, frame in {
        "profiles": profiles,
        "scenarios": scenarios,
        "explanations": explanations,
        "municipalities": municipalities,
    }.items():
        if len(frame) != EXPECTED_MUNICIPALITIES or frame[key].nunique() != EXPECTED_MUNICIPALITIES:
            raise ValueError(f"{label} does not contain exactly {EXPECTED_MUNICIPALITIES} municipalities")

    if scenarios[[f"{name}__score" for name in names]].isna().any().any():
        raise ValueError("Scenario scores contain missing values")
    if scenarios[[f"{name}__rank" for name in names]].isna().any().any():
        raise ValueError("Scenario ranks contain missing values")

    return DashboardData(
        profiles=profiles,
        scenarios=scenarios,
        explanations=explanations,
        municipalities=municipalities,
        agreement=agreement,
        correlations=correlations,
        scenario_names=names,
    )
