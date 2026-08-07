from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def _load_framework_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Framework configuration must be a YAML mapping")
    required = {
        "schema_version",
        "method_version",
        "study_scope",
        "inputs",
        "outputs",
        "dimensions",
        "macro_weight_scenarios",
        "robustness",
    }
    missing = sorted(required - set(document))
    if missing:
        raise ValueError(f"Framework configuration is missing: {', '.join(missing)}")
    return document


def _indicator_definitions(items: list[dict[str, str]]) -> list[tuple[str, str]]:
    definitions: list[tuple[str, str]] = []
    for item in items:
        column = item.get("column")
        direction = item.get("direction")
        if not column or direction not in {"benefit", "cost"}:
            raise ValueError(f"Invalid indicator definition: {item}")
        definitions.append((column, direction))
    return definitions


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
    municipal_csv: str | Path | None = None,
    transport_scenarios_csv: str | Path | None = None,
    output_csv: str | Path | None = None,
    scenarios_csv: str | Path | None = None,
    method_json: str | Path | None = None,
    audit_json: str | Path | None = None,
    config_path: str | Path = "config/capacity_priority.yml",
) -> dict[str, Path]:
    config = _load_framework_config(config_path)
    inputs = config["inputs"]
    outputs = config["outputs"]
    municipal_csv = municipal_csv or inputs["municipal_matrix"]
    transport_scenarios_csv = (
        transport_scenarios_csv or inputs["transport_scenarios"]
    )
    output_csv = output_csv or outputs["profiles"]
    scenarios_csv = scenarios_csv or outputs["scenarios"]
    method_json = method_json or outputs["method"]
    audit_json = audit_json or outputs["audit"]
    institutional_indicators = _indicator_definitions(
        config["dimensions"]["institutional_deficit"]["indicators"]
    )
    service_indicators = {
        name: _indicator_definitions(component["indicators"])
        for name, component in config["dimensions"]["service_network"][
            "components"
        ].items()
    }
    macro_weights = config["macro_weight_scenarios"]
    expected_municipalities = int(config["study_scope"]["expected_municipalities"])
    expected_transport_scenarios = int(
        config["study_scope"]["expected_transport_scenarios"]
    )
    top_k = int(config["robustness"]["top_k"])

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
        return "".join(
            character for character in decomposed if character.isalnum()
        ).casefold()

    names_agree = merged.apply(
        lambda row: canonical_name(row["municipality"])
        == canonical_name(row["municipality_transport"]),
        axis=1,
    )
    if not names_agree.all():
        raise ValueError("Municipality names disagree after code-based integration")
    dimensions = merged[["municipality_code", "municipality"]].copy()
    dimensions["institutional_deficit"] = _component(
        merged, institutional_indicators
    )
    service_components: dict[str, pd.Series] = {}
    for name, definitions in service_indicators.items():
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
        for weight_name, weights in macro_weights.items():
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
    quartile_fraction = float(config["robustness"]["quartile_fraction"])
    robust_frequency = float(config["robustness"]["robust_frequency"])
    sensitive_frequency = float(config["robustness"]["sensitive_frequency"])
    top_quartile_cutoff = int(np.ceil(n * quartile_fraction))
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
        scenario_output[rank_columns].le(top_k).mean(axis=1)
    )
    scenario_output["top_quartile_frequency"] = (
        scenario_output[rank_columns].le(top_quartile_cutoff).mean(axis=1)
    )
    scenario_output["bottom_quartile_frequency"] = (
        scenario_output[rank_columns].ge(bottom_quartile_start).mean(axis=1)
    )

    def stability_label(row: pd.Series) -> str:
        if row["top_quartile_frequency"] >= robust_frequency:
            return "robust_higher_capacity_strengthening_priority"
        if row["top_quartile_frequency"] >= sensitive_frequency:
            return "scenario_sensitive_higher_priority"
        if row["bottom_quartile_frequency"] >= robust_frequency:
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
        "municipal_rows_expected": len(municipal) == expected_municipalities,
        "transport_rows_expected": len(transport) == expected_municipalities,
        "integrated_rows_expected": len(merged) == expected_municipalities,
        "unique_municipality_codes_expected": (
            merged["municipality_code"].nunique() == expected_municipalities
        ),
        "transport_scenarios_expected": (
            len(transport_score_columns) == expected_transport_scenarios
        ),
        "integrated_scenarios_expected": (
            len(score_columns) == expected_transport_scenarios * len(macro_weights)
        ),
        "macro_weights_sum_one": all(
            np.isclose(sum(weights.values()), 1) for weights in macro_weights.values()
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
        "schema_version": config["schema_version"],
        "method_version": config["method_version"],
        "configuration": str(config_path),
        "research_target": config["research_target"],
        "excluded_outcomes": config["exclusions"]["outcomes"],
        "normalization": {
            "method": "within-sample percentile rank scaled to [0,1]",
            "ties": "average rank",
            "interpretation": "higher values always mean greater strengthening priority",
        },
        "hierarchy": {
            "institutional_deficit": institutional_indicators,
            "service_components": service_indicators,
            "service_network_aggregation": (
                "equal mean across health, social protection, justice, and "
                "specialized protection network components"
            ),
            "macro_dimensions": [
                "institutional_deficit",
                "service_network_deficit",
                "transport_barrier",
            ],
        },
        "macro_weight_scenarios": macro_weights,
        "transport_scenarios": transport_score_columns,
        "integrated_scenario_count": len(scenario_metadata),
        "classification": {
            "top_quartile_cutoff": top_quartile_cutoff,
            "quartile_fraction": quartile_fraction,
            "robust_frequency": robust_frequency,
            "scenario_sensitive_frequency": sensitive_frequency,
        },
        "warnings": config.get("warnings", []),
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
        "top_by_mean_rank": profiles[
            [
                "municipality_code",
                "municipality",
                "mean_priority_rank",
                "best_priority_rank",
                "worst_priority_rank",
                "top_10_frequency",
                "priority_stability_profile",
            ]
        ].head(top_k).to_dict("records"),
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
