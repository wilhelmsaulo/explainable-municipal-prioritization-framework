from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def _load_config(path: str | Path) -> dict[str, Any]:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Framework configuration must be a YAML mapping")
    if "diagnostics" not in document:
        raise ValueError("Framework configuration is missing diagnostics")
    return document


def _rank_correlation(left: pd.Series, right: pd.Series) -> float:
    return float(left.rank(method="average").corr(right.rank(method="average")))


def build_capacity_diagnostics(
    config_path: str | Path = "config/capacity_priority.yml",
) -> dict[str, Path]:
    """Diagnose the published capacity-priority scenarios without changing them."""
    config = _load_config(config_path)
    outputs = config["outputs"]
    diagnostic_config = config["diagnostics"]
    diagnostic_outputs = diagnostic_config["outputs"]
    municipality_key = config["study_scope"]["municipality_key"]
    expected_municipalities = int(config["study_scope"]["expected_municipalities"])
    expected_transport_scenarios = int(
        config["study_scope"]["expected_transport_scenarios"]
    )
    macro_weights = config["macro_weight_scenarios"]
    expected_integrated_scenarios = expected_transport_scenarios * len(macro_weights)
    top_k = int(config["robustness"]["top_k"])

    profiles = pd.read_csv(outputs["profiles"], dtype={municipality_key: str})
    scenarios = pd.read_csv(outputs["scenarios"], dtype={municipality_key: str})
    transport = pd.read_csv(
        config["inputs"]["transport_scenarios"], dtype={municipality_key: str}
    )
    for name, frame in {
        "profiles": profiles,
        "scenarios": scenarios,
        "transport": transport,
    }.items():
        if frame[municipality_key].duplicated().any():
            raise ValueError(f"Duplicate municipality codes in {name}")

    transport_columns = [column for column in transport if column.endswith("__score")]
    reference_transport = diagnostic_config["reference_transport_scenario"]
    reference_weight = diagnostic_config["reference_macro_weight_scenario"]
    reference_scenario = f"{reference_transport}___{reference_weight}"
    reference_rank_column = f"{reference_scenario}__rank"
    reference_transport_column = f"{reference_transport}__score"
    if reference_rank_column not in scenarios:
        raise ValueError(f"Reference scenario not found: {reference_scenario}")
    if reference_transport_column not in transport:
        raise ValueError(f"Reference transport scenario not found: {reference_transport}")

    joined = profiles.merge(
        transport[[municipality_key, *transport_columns]],
        on=municipality_key,
        how="inner",
        validate="one_to_one",
    ).merge(
        scenarios,
        on=municipality_key,
        how="inner",
        suffixes=("", "_scenario"),
        validate="one_to_one",
    )

    dimensions = pd.DataFrame(
        {
            "institutional_deficit": joined["institutional_deficit"],
            "service_network_deficit": joined["service_network_deficit"],
            "transport_barrier_reference": 1 - joined[reference_transport_column],
        }
    )
    correlation_rows: list[dict[str, Any]] = []
    for left_index, left in enumerate(dimensions.columns):
        for right in dimensions.columns[left_index + 1 :]:
            correlation_rows.append(
                {
                    "dimension_1": left,
                    "dimension_2": right,
                    "spearman_correlation": _rank_correlation(
                        dimensions[left], dimensions[right]
                    ),
                    "reference_transport_scenario": reference_transport,
                    "municipalities": len(dimensions),
                }
            )
    correlations = pd.DataFrame(correlation_rows)

    reference_ranks = joined[reference_rank_column]
    reference_top_k = set(joined.loc[reference_ranks.le(top_k), municipality_key])
    quartile_cutoff = int(np.ceil(len(joined) * float(config["robustness"]["quartile_fraction"])))
    reference_quartile = set(
        joined.loc[reference_ranks.le(quartile_cutoff), municipality_key]
    )
    agreement_rows: list[dict[str, Any]] = []
    reconstruction_errors: list[float] = []
    contribution_frames: list[pd.DataFrame] = []

    for transport_column in transport_columns:
        transport_name = transport_column.removesuffix("__score")
        barrier = 1 - joined[transport_column]
        for weight_name, weights in macro_weights.items():
            scenario_name = f"{transport_name}___{weight_name}"
            score_column = f"{scenario_name}__score"
            rank_column = f"{scenario_name}__rank"
            if score_column not in joined or rank_column not in joined:
                raise ValueError(f"Published scenario is missing: {scenario_name}")

            institutional = joined["institutional_deficit"] * float(
                weights["institutional_deficit"]
            )
            service = joined["service_network_deficit"] * float(
                weights["service_network_deficit"]
            )
            transport_contribution = barrier * float(weights["transport_barrier"])
            reconstructed = institutional + service + transport_contribution
            reconstruction_errors.extend(
                np.abs(reconstructed - joined[score_column]).tolist()
            )
            contribution_frames.append(
                pd.DataFrame(
                    {
                        municipality_key: joined[municipality_key],
                        "scenario": scenario_name,
                        "institutional_contribution": institutional,
                        "service_network_contribution": service,
                        "transport_barrier_contribution": transport_contribution,
                    }
                )
            )

            ranks = joined[rank_column]
            absolute_shift = np.abs(ranks - reference_ranks)
            scenario_top_k = set(joined.loc[ranks.le(top_k), municipality_key])
            scenario_quartile = set(
                joined.loc[ranks.le(quartile_cutoff), municipality_key]
            )
            agreement_rows.append(
                {
                    "scenario": scenario_name,
                    "transport_scenario": transport_name,
                    "macro_weight_scenario": weight_name,
                    "reference_scenario": reference_scenario,
                    "rank_correlation": float(ranks.corr(reference_ranks)),
                    "top_k": top_k,
                    "top_k_overlap_count": len(scenario_top_k & reference_top_k),
                    "top_k_overlap_fraction": len(scenario_top_k & reference_top_k)
                    / top_k,
                    "top_quartile_cutoff": quartile_cutoff,
                    "top_quartile_overlap_count": len(
                        scenario_quartile & reference_quartile
                    ),
                    "top_quartile_overlap_fraction": len(
                        scenario_quartile & reference_quartile
                    )
                    / quartile_cutoff,
                    "mean_absolute_rank_shift": float(absolute_shift.mean()),
                    "median_absolute_rank_shift": float(absolute_shift.median()),
                    "maximum_absolute_rank_shift": int(absolute_shift.max()),
                }
            )

    agreement = pd.DataFrame(agreement_rows)
    contribution_long = pd.concat(contribution_frames, ignore_index=True)
    contribution_columns = [
        "institutional_contribution",
        "service_network_contribution",
        "transport_barrier_contribution",
    ]
    contribution_long["dominant_dimension"] = (
        contribution_long[contribution_columns]
        .idxmax(axis=1)
        .str.removesuffix("_contribution")
    )
    contribution_means = contribution_long.groupby(municipality_key)[
        contribution_columns
    ].mean()
    contribution_means.columns = [f"mean_{column}" for column in contribution_columns]
    dominant_frequencies = (
        pd.crosstab(
            contribution_long[municipality_key],
            contribution_long["dominant_dimension"],
            normalize="index",
        )
        .reindex(
            columns=["institutional", "service_network", "transport_barrier"],
            fill_value=0.0,
        )
        .rename(columns=lambda column: f"dominant_{column}_frequency")
    )
    explanation = (
        profiles[
            [
                municipality_key,
                "municipality",
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
        ]
        .set_index(municipality_key)
        .join(contribution_means)
        .join(dominant_frequencies)
        .reset_index()
        .sort_values(municipality_key)
    )
    frequency_columns = [column for column in explanation if column.startswith("dominant_")]
    frequency_labels = [
        column.removeprefix("dominant_").removesuffix("_frequency")
        for column in frequency_columns
    ]
    frequency_values = explanation[frequency_columns].to_numpy()
    maxima = frequency_values.max(axis=1, keepdims=True)
    explanation["dominant_dimension_across_scenarios"] = [
        labels[0] if len(labels) == 1 else "tie:" + "+".join(labels)
        for labels in [
            [
                frequency_labels[index]
                for index, value in enumerate(row)
                if np.isclose(value, maximum[0])
            ]
            for row, maximum in zip(frequency_values, maxima, strict=True)
        ]
    ]

    numeric_outputs = [correlations, agreement, explanation]
    checks = {
        "municipalities_expected": len(joined) == expected_municipalities,
        "transport_scenarios_expected": len(transport_columns)
        == expected_transport_scenarios,
        "integrated_scenarios_expected": len(agreement)
        == expected_integrated_scenarios,
        "explanations_cover_all_municipalities": len(explanation)
        == expected_municipalities,
        "unique_explanation_municipalities": explanation[municipality_key].nunique()
        == expected_municipalities,
        "published_scores_reconstructed": max(reconstruction_errors, default=np.inf)
        <= 1e-12,
        "all_diagnostics_complete": all(
            frame.select_dtypes(include="number").notna().all().all()
            for frame in numeric_outputs
        ),
        "all_diagnostics_finite": all(
            np.isfinite(frame.select_dtypes(include="number").to_numpy()).all()
            for frame in numeric_outputs
        ),
        "reference_scenario_included": reference_scenario in set(agreement["scenario"]),
    }
    if not all(checks.values()):
        raise ValueError(f"Capacity diagnostics audit failed: {checks}")

    paths = {name: Path(path) for name, path in diagnostic_outputs.items()}
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    correlations.to_csv(paths["correlations"], index=False, encoding="utf-8")
    agreement.to_csv(paths["scenario_agreement"], index=False, encoding="utf-8")
    explanation.to_csv(paths["municipality_explanations"], index=False, encoding="utf-8")
    audit = {
        "schema_version": config["schema_version"],
        "method_version": config["method_version"],
        "configuration": str(config_path),
        "diagnostic_scope": {
            "municipalities": len(joined),
            "transport_scenarios": len(transport_columns),
            "macro_weight_scenarios": len(macro_weights),
            "integrated_scenarios": len(agreement),
            "reference_scenario": reference_scenario,
        },
        "checks": checks,
        "maximum_score_reconstruction_error": max(reconstruction_errors),
        "scenario_agreement_summary": {
            "minimum_rank_correlation": float(agreement["rank_correlation"].min()),
            "median_rank_correlation": float(agreement["rank_correlation"].median()),
            "maximum_rank_correlation": float(agreement["rank_correlation"].max()),
            "minimum_top_k_overlap_fraction": float(
                agreement["top_k_overlap_fraction"].min()
            ),
            "maximum_top_k_overlap_fraction": float(
                agreement["top_k_overlap_fraction"].max()
            ),
        },
        "interpretation": (
            "Diagnostics describe agreement and contribution patterns in the already "
            "published scenarios; they do not alter criteria, weights, scores, or ranks."
        ),
    }
    paths["audit"].write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return paths
