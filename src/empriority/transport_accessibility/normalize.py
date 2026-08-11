from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROLE_WEIGHTS = {
    "equal_roles": {"availability": 0.5, "proximity": 0.5},
    "availability_emphasis": {"availability": 2 / 3, "proximity": 1 / 3},
    "proximity_emphasis": {"availability": 1 / 3, "proximity": 2 / 3},
}
MODE_WEIGHTS = {
    "equal_modes": {"road": 1 / 3, "water": 1 / 3, "air": 1 / 3},
    "road_emphasis": {"road": 0.5, "water": 0.25, "air": 0.25},
    "water_emphasis": {"road": 0.25, "water": 0.5, "air": 0.25},
    "air_emphasis": {"road": 0.25, "water": 0.25, "air": 0.5},
}
BASELINE = "equal_modes__equal_roles"


def _percentile_access(series: pd.Series, polarity: str, binary: bool) -> pd.Series:
    numeric = pd.to_numeric(series, errors="raise")
    if binary:
        normalized = numeric.astype(float)
    else:
        ranks = numeric.rank(method="average")
        normalized = (ranks - 1) / (len(numeric) - 1)
    if polarity == "cost":
        normalized = 1 - normalized
    return normalized


def build_multimodal_transport_construct(
    selected_csv: str | Path,
    selection_json: str | Path,
    normalized_csv: str | Path = "data/processed/transport/transport_indicators_pa_normalized.csv",
    scenarios_csv: str | Path = "data/processed/transport/transport_multimodal_scenarios.csv",
    method_json: str | Path = "data/processed/transport/transport_normalization_hierarchy.json",
    audit_json: str | Path = "data/processed/transport/transport_normalization_audit.json",
    sensitivity_json: str | Path = "data/processed/transport/transport_multimodal_sensitivity.json",
) -> dict[str, Path]:
    frame = pd.read_csv(selected_csv, dtype={"municipality_code": str})
    selection = json.loads(Path(selection_json).read_text(encoding="utf-8"))
    definitions: dict[str, dict[str, Any]] = selection["selected"]
    normalized = frame[["municipality_code", "municipality"]].copy()

    for variable, metadata in definitions.items():
        normalized[f"{variable}__access"] = _percentile_access(
            frame[variable],
            metadata["polarity"],
            metadata["unit"] == "binary",
        )

    components = selection["component_structure"]

    def component_scores(role_weights: dict[str, float]) -> dict[str, pd.Series]:
        scores: dict[str, pd.Series] = {}
        for component, variables in components.items():
            score = pd.Series(0.0, index=frame.index)
            for variable in variables:
                role = definitions[variable]["role"]
                score += normalized[f"{variable}__access"] * role_weights[role]
            scores[component] = score
        return scores

    scenario_frame = frame[["municipality_code", "municipality"]].copy()
    scenario_details: dict[str, Any] = {}
    baseline_components: dict[str, pd.Series] | None = None

    for mode_name, role_name in product(MODE_WEIGHTS, ROLE_WEIGHTS):
        scenario = f"{mode_name}__{role_name}"
        component = component_scores(ROLE_WEIGHTS[role_name])
        modes = {
            "road": component["road"],
            "water": (
                component["port"]
                + component["passenger_crossing"]
                + component["navigated_waterway"]
            )
            / 3,
            "air": component["air"],
        }
        score = sum(modes[mode] * weight for mode, weight in MODE_WEIGHTS[mode_name].items())
        scenario_frame[f"{scenario}__score"] = score
        scenario_frame[f"{scenario}__rank"] = score.rank(ascending=False, method="min").astype(int)
        scenario_details[scenario] = {
            "mode_weights": MODE_WEIGHTS[mode_name],
            "role_weights": ROLE_WEIGHTS[role_name],
        }
        if scenario == BASELINE:
            baseline_components = component
            for component_name, values in component.items():
                normalized[f"component_{component_name}"] = values
            for mode, values in modes.items():
                normalized[f"mode_{mode}"] = values
            normalized["multimodal_access_baseline"] = score
            normalized["multimodal_access_rank"] = scenario_frame[f"{scenario}__rank"]

    if baseline_components is None:
        raise ValueError("Baseline scenario was not generated")

    baseline_rank = scenario_frame[f"{BASELINE}__rank"]
    baseline_top = set(scenario_frame.nsmallest(10, f"{BASELINE}__rank")["municipality_code"])
    sensitivity: dict[str, Any] = {}
    rank_columns = []
    score_columns = []
    for scenario in scenario_details:
        rank_column = f"{scenario}__rank"
        score_column = f"{scenario}__score"
        rank_columns.append(rank_column)
        score_columns.append(score_column)
        ranks = scenario_frame[rank_column]
        top = set(scenario_frame.nsmallest(10, rank_column)["municipality_code"])
        shifts = (ranks - baseline_rank).abs()
        sensitivity[scenario] = {
            "spearman_rank_vs_baseline": float(ranks.corr(baseline_rank, method="pearson")),
            "top_10_overlap_with_baseline": len(top & baseline_top),
            "median_absolute_rank_shift": float(shifts.median()),
            "maximum_absolute_rank_shift": int(shifts.max()),
        }

    scenario_frame["mean_rank"] = scenario_frame[rank_columns].mean(axis=1)
    scenario_frame["minimum_rank"] = scenario_frame[rank_columns].min(axis=1)
    scenario_frame["maximum_rank"] = scenario_frame[rank_columns].max(axis=1)
    scenario_frame["rank_range"] = scenario_frame["maximum_rank"] - scenario_frame["minimum_rank"]
    scenario_frame["mean_score"] = scenario_frame[score_columns].mean(axis=1)
    scenario_frame["score_range"] = scenario_frame[score_columns].max(axis=1) - scenario_frame[
        score_columns
    ].min(axis=1)

    normalized_values = normalized.select_dtypes(include="number")
    scenario_values = scenario_frame.select_dtypes(include="number")
    checks = {
        "rows_144": len(frame) == 144,
        "selected_indicators_10": len(definitions) == 10,
        "scenarios_12": len(scenario_details) == 12,
        "no_missing_normalized": bool(normalized_values.notna().all().all()),
        "no_missing_scenarios": bool(scenario_values.notna().all().all()),
        "normalized_within_zero_one": bool(
            normalized_values.drop(columns=["multimodal_access_rank"], errors="ignore")
            .ge(0)
            .all()
            .all()
            and normalized_values.drop(columns=["multimodal_access_rank"], errors="ignore")
            .le(1)
            .all()
            .all()
        ),
        "scenario_scores_within_zero_one": bool(
            scenario_frame[score_columns].ge(0).all().all()
            and scenario_frame[score_columns].le(1).all().all()
        ),
        "finite_outputs": bool(
            np.isfinite(normalized_values.to_numpy()).all()
            and np.isfinite(scenario_values.to_numpy()).all()
        ),
        "mode_weights_sum_one": all(
            np.isclose(sum(weights.values()), 1) for weights in MODE_WEIGHTS.values()
        ),
        "role_weights_sum_one": all(
            np.isclose(sum(weights.values()), 1) for weights in ROLE_WEIGHTS.values()
        ),
    }
    if not all(checks.values()):
        raise ValueError(f"Normalization and hierarchy audit failed: {checks}")

    paths = {
        "normalized": Path(normalized_csv),
        "scenarios": Path(scenarios_csv),
        "method": Path(method_json),
        "audit": Path(audit_json),
        "sensitivity": Path(sensitivity_json),
    }
    paths["normalized"].parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(paths["normalized"], index=False, encoding="utf-8")
    scenario_frame.to_csv(paths["scenarios"], index=False, encoding="utf-8")

    method = {
        "schema_version": "1.0",
        "normalization": {
            "method": "within-sample percentile rank",
            "range": [0, 1],
            "ties": "average rank",
            "binary_indicators": "retained as 0/1",
            "cost_indicators": "inverted after normalization",
            "interpretation": "All normalized values increase with transport access.",
        },
        "hierarchy": {
            "indicator_to_component": "weighted mean of availability and proximity",
            "water_components": ["port", "passenger_crossing", "navigated_waterway"],
            "component_to_water_mode": "equal mean of the three water components",
            "modes": ["road", "water", "air"],
            "mode_to_multimodal": "weighted mean across the three modes",
        },
        "baseline": BASELINE,
        "scenarios": scenario_details,
        "warning": "The baseline score is a transparent reference scenario, not a validated ground truth.",
    }
    paths["method"].write_text(json.dumps(method, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["audit"].write_text(
        json.dumps({"checks": checks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    sensitivity_document = {
        "baseline": BASELINE,
        "scenario_count": len(scenario_details),
        "scenario_comparison": sensitivity,
        "municipal_rank_stability": scenario_frame[
            [
                "municipality_code",
                "municipality",
                "mean_rank",
                "minimum_rank",
                "maximum_rank",
                "rank_range",
                "mean_score",
                "score_range",
            ]
        ]
        .sort_values(["mean_rank", "municipality_code"])
        .to_dict("records"),
    }
    paths["sensitivity"].write_text(
        json.dumps(sensitivity_document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return paths
