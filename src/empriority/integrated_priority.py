from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SERVICE_INDICATORS: dict[str, list[tuple[str, str]]] = {
    "health": [
        ("cnes_health_service_deficit", "benefit"),
        ("cnes_multidisciplinary_staff_deficit", "benefit"),
    ],
    "social_protection": [
        ("social_specialized_service_deficit", "benefit"),
    ],
    "justice": [
        ("justice_tjpa_access_deficit", "benefit"),
    ],
    "specialized_protection_network": [
        ("protection_network_validated_category_diversity", "cost"),
        ("protection_network_specialized_non_health_services", "cost"),
    ],
}

INSTITUTIONAL_INDICATORS: list[tuple[str, str]] = [
    ("institutional_deficit_available_4", "benefit"),
]

MACRO_WEIGHTS: dict[str, dict[str, float]] = {
    "equal_dimensions": {
        "institutional_deficit": 1 / 3,
        "service_network_deficit": 1 / 3,
        "transport_barrier": 1 / 3,
    },
    "institutional_emphasis": {
        "institutional_deficit": 0.50,
        "service_network_deficit": 0.25,
        "transport_barrier": 0.25,
    },
    "service_network_emphasis": {
        "institutional_deficit": 0.25,
        "service_network_deficit": 0.50,
        "transport_barrier": 0.25,
    },
    "transport_emphasis": {
        "institutional_deficit": 0.25,
        "service_network_deficit": 0.25,
        "transport_barrier": 0.50,
    },
}


def _percentile(values: pd.Series, direction: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.isna().any():
        raise ValueError(f"Missing/non-numeric values in {values.name}")
    if numeric.nunique() <= 1:
        raise ValueError(f"Constant indicator cannot contribute: {values.name}")
    ranked = numeric.rank(method="average", pct=True)
    minimum = float(ranked.min())
    maximum = float(ranked.max())
    normalized = (ranked - minimum) / (maximum - minimum)
    if direction == "cost":
        normalized = 1 - normalized
    elif direction != "benefit":
        raise ValueError(f"Unknown direction: {direction}")
    return normalized


def _component(
    frame: pd.DataFrame, definitions: list[tuple[str, str]]
) -> pd.Series:
    values = [_percentile(frame[column], direction) for column, direction in definitions]
    return pd.concat(values, axis=1).mean(axis=1)


def build_integrated_priority_profiles(
    municipal_csv: str | Path,
    transport_scenarios_csv: str | Path,
    output_csv: str | Path = "data/results/integrated_capacity_priority_profiles.csv",
    scenarios_csv: str | Path = "data/results/integrated_capacity_priority_scenarios.csv",
    method_json: str | Path = "data/results/integrated_capacity_priority_method.json",
    audit_json: str | Path = "data/results/integrated_capacity_priority_audit.json",
) -> dict[str, Path]:
    municipal = pd.read_csv(municipal_csv, dtype={"municipality_code": str})
    transport = pd.read_csv(
        transport_scenarios_csv, dtype={"municipality_code": str}
    )
    if municipal["municipality_code"].duplicated().any():
        raise ValueError("Duplicate municipality codes in municipal matrix")
    if transport["municipality_code"].duplicated().any():
        raise ValueError("Duplicate municipality codes in transport matrix")

    transport_score_columns = [
        column for column in transport if column.endswith("__score")
    ]
    merged = municipal.merge(
        transport[["municipality_code", "municipality", *transport_score_columns]],
        on="municipality_code",
        how="inner",
        suffixes=("", "_transport"),
        validate="one_to_one",
    )
    def canonical_name(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", str(value))
        return "".join(character for character in decomposed if character.isalnum()).casefold()

    names_agree = merged.apply(
        lambda row: canonical_name(row["municipality"])
        == canonical_name(row["municipality_transport"]),
        axis=1,
    )
    if not names_agree.all():
        raise ValueError("Municipality names disagree after code-based integration")

    dimensions = merged[["municipality_code", "municipality"]].copy()
    dimensions["institutional_deficit"] = _component(
        merged, INSTITUTIONAL_INDICATORS
    )
    service_components: dict[str, pd.Series] = {}
    for name, definitions in SERVICE_INDICATORS.items():
        service_components[name] = _component(merged, definitions)
        dimensions[f"service_component_{name}_deficit"] = service_components[name]
    dimensions["service_network_deficit"] = pd.concat(
        service_components.values(), axis=1
    ).mean(axis=1)

    scenario_output = dimensions[["municipality_code", "municipality"]].copy()
    rank_columns: list[str] = []
    score_columns: list[str] = []
    scenario_metadata: dict[str, Any] = {}
    for transport_column in transport_score_columns:
        transport_name = transport_column.removesuffix("__score")
        transport_barrier = 1 - merged[transport_column]
        for weight_name, weights in MACRO_WEIGHTS.items():
            scenario = f"{transport_name}___{weight_name}"
            score_column = f"{scenario}__score"
            rank_column = f"{scenario}__rank"
            scenario_output[score_column] = (
                dimensions["institutional_deficit"]
                * weights["institutional_deficit"]
                + dimensions["service_network_deficit"]
                * weights["service_network_deficit"]
                + transport_barrier * weights["transport_barrier"]
            )
            scenario_output[rank_column] = scenario_output[score_column].rank(
                ascending=False, method="min"
            ).astype(int)
            score_columns.append(score_column)
            rank_columns.append(rank_column)
            scenario_metadata[scenario] = {
                "transport_scenario": transport_name,
                "macro_weights": weights,
            }

    n = len(scenario_output)
    top_quartile_cutoff = int(np.ceil(n * 0.25))
    bottom_quartile_start = n - top_quartile_cutoff + 1
    scenario_output["mean_priority_score"] = scenario_output[score_columns].mean(axis=1)
    scenario_output["mean_priority_rank"] = scenario_output[rank_columns].mean(axis=1)
    scenario_output["best_priority_rank"] = scenario_output[rank_columns].min(axis=1)
    scenario_output["worst_priority_rank"] = scenario_output[rank_columns].max(axis=1)
    scenario_output["priority_rank_range"] = (
        scenario_output["worst_priority_rank"]
        - scenario_output["best_priority_rank"]
    )
    scenario_output["top_10_frequency"] = (
        scenario_output[rank_columns].le(10).mean(axis=1)
    )
    scenario_output["top_quartile_frequency"] = (
        scenario_output[rank_columns].le(top_quartile_cutoff).mean(axis=1)
    )
    scenario_output["bottom_quartile_frequency"] = (
        scenario_output[rank_columns].ge(bottom_quartile_start).mean(axis=1)
    )

    def stability_label(row: pd.Series) -> str:
        if row["top_quartile_frequency"] >= 0.75:
            return "robust_higher_capacity_strengthening_priority"
        if row["top_quartile_frequency"] >= 0.25:
            return "scenario_sensitive_higher_priority"
        if row["bottom_quartile_frequency"] >= 0.75:
            return "robust_lower_relative_priority"
        return "intermediate_or_scenario_sensitive"

    scenario_output["priority_stability_profile"] = scenario_output.apply(
        stability_label, axis=1
    )
    profiles = dimensions.merge(
        scenario_output[
            [
                "municipality_code",
                "mean_priority_score",
                "mean_priority_rank",
                "best_priority_rank",
                "worst_priority_rank",
                "priority_rank_range",
                "top_10_frequency",
                "top_quartile_frequency",
                "bottom_quartile_frequency",
                "priority_stability_profile",
            ]
        ],
        on="municipality_code",
        validate="one_to_one",
    ).sort_values(["mean_priority_rank", "municipality_code"])

    numeric_profiles = profiles.select_dtypes(include="number")
    numeric_scenarios = scenario_output.select_dtypes(include="number")
    checks = {
        "municipal_rows_144": len(municipal) == 144,
        "transport_rows_144": len(transport) == 144,
        "integrated_rows_144": len(merged) == 144,
        "unique_municipality_codes_144": merged["municipality_code"].nunique() == 144,
        "transport_scenarios_12": len(transport_score_columns) == 12,
        "macro_weight_scenarios_4": len(MACRO_WEIGHTS) == 4,
        "integrated_scenarios_48": len(score_columns) == 48,
        "macro_weights_sum_one": all(
            np.isclose(sum(weights.values()), 1) for weights in MACRO_WEIGHTS.values()
        ),
        "no_missing_outputs": bool(
            numeric_profiles.notna().all().all()
            and numeric_scenarios.notna().all().all()
        ),
        "finite_outputs": bool(
            np.isfinite(numeric_profiles.to_numpy()).all()
            and np.isfinite(numeric_scenarios.to_numpy()).all()
        ),
        "scores_within_zero_one": bool(
            scenario_output[score_columns].ge(0).all().all()
            and scenario_output[score_columns].le(1).all().all()
        ),
        "all_profiles_assigned": profiles["priority_stability_profile"].notna().all(),
    }
    if not all(checks.values()):
        raise ValueError(f"Integrated priority audit failed: {checks}")

    paths = {
        "profiles": Path(output_csv),
        "scenarios": Path(scenarios_csv),
        "method": Path(method_json),
        "audit": Path(audit_json),
    }
    paths["profiles"].parent.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(paths["profiles"], index=False, encoding="utf-8")
    scenario_output.to_csv(paths["scenarios"], index=False, encoding="utf-8")
    method = {
        "schema_version": "1.0",
        "research_target": "relative priority for strengthening municipal service capacity under multimodal access constraints",
        "excluded_outcomes": [
            "police occurrence counts",
            "police occurrence rates",
            "inferred or estimated hidden violence incidence",
        ],
        "normalization": {
            "method": "within-sample percentile rank scaled to [0,1]",
            "ties": "average rank",
            "interpretation": "higher values always mean greater strengthening priority",
        },
        "hierarchy": {
            "institutional_deficit": INSTITUTIONAL_INDICATORS,
            "service_components": SERVICE_INDICATORS,
            "service_network_aggregation": "equal mean across health, social protection, justice, and specialized protection network components",
            "macro_dimensions": [
                "institutional_deficit",
                "service_network_deficit",
                "transport_barrier",
            ],
        },
        "macro_weight_scenarios": MACRO_WEIGHTS,
        "transport_scenarios": transport_score_columns,
        "integrated_scenario_count": len(scenario_metadata),
        "classification": {
            "top_quartile_cutoff": top_quartile_cutoff,
            "robust_threshold": "municipality remains in the relevant quartile in at least 75% of scenarios",
            "scenario_sensitive_higher_threshold": "municipality is in the top quartile in 25% to less than 75% of scenarios",
        },
        "warnings": [
            "The scores are relative decision-support constructs, not ground truth.",
            "The model prioritizes capacity strengthening and does not estimate violence incidence or underreporting.",
            "Facility presence and mapped proximity do not measure service quality, capacity, frequency, affordability, travel time, or seasonality.",
            "Profile labels are exploratory robustness summaries and not automatic funding decisions.",
        ],
    }
    paths["method"].write_text(
        json.dumps(
            method,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item()
            if isinstance(value, np.generic)
            else str(value),
        ),
        encoding="utf-8",
    )
    audit = {
        "checks": checks,
        "profile_counts": profiles["priority_stability_profile"].value_counts().to_dict(),
        "top_10_by_mean_rank": profiles[
            [
                "municipality_code",
                "municipality",
                "mean_priority_rank",
                "best_priority_rank",
                "worst_priority_rank",
                "top_10_frequency",
                "priority_stability_profile",
            ]
        ].head(10).to_dict("records"),
    }
    paths["audit"].write_text(
        json.dumps(
            audit,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item()
            if isinstance(value, np.generic)
            else str(value),
        ),
        encoding="utf-8",
    )
    return paths
