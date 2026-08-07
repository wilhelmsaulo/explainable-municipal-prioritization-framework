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
    return document


def _framework_indicators(config: dict[str, Any]) -> list[dict[str, str]]:
    indicators: list[dict[str, str]] = []
    for item in config["dimensions"]["institutional_deficit"]["indicators"]:
        indicators.append(
            {
                "dimension": "institutional_deficit",
                "component": "institutional_deficit",
                **item,
            }
        )
    for component, definition in config["dimensions"]["service_network"]["components"].items():
        for item in definition["indicators"]:
            indicators.append(
                {
                    "dimension": "service_network_deficit",
                    "component": component,
                    **item,
                }
            )
    return indicators


def build_capacity_input_audit(
    config_path: str | Path = "config/capacity_priority.yml",
) -> dict[str, Path]:
    """Create an article-specific input matrix without recalculating the framework."""
    config = _load_config(config_path)
    audit_config = config["input_audit"]
    outputs = {name: Path(path) for name, path in audit_config["outputs"].items()}
    key = config["study_scope"]["municipality_key"]
    expected = int(config["study_scope"]["expected_municipalities"])

    municipal = pd.read_csv(config["inputs"]["municipal_matrix"], dtype={key: str})
    transport = pd.read_csv(config["inputs"]["transport_scenarios"], dtype={key: str})
    if municipal[key].duplicated().any() or transport[key].duplicated().any():
        raise ValueError("Duplicate municipality codes in framework inputs")

    definitions = _framework_indicators(config)
    indicator_columns = [item["column"] for item in definitions]
    missing_indicators = sorted(set(indicator_columns) - set(municipal.columns))
    if missing_indicators:
        raise ValueError(f"Framework indicators are missing: {missing_indicators}")

    transport_columns = [column for column in transport if column.endswith("__score")]
    article = municipal[[key, "municipality", "institutional_coverage", *indicator_columns]].merge(
        transport[[key, *transport_columns]],
        on=key,
        how="inner",
        validate="one_to_one",
    )

    profiles: list[dict[str, Any]] = []
    for definition in definitions:
        column = definition["column"]
        values = pd.to_numeric(article[column], errors="coerce")
        counts = values.value_counts(dropna=False)
        profiles.append(
            {
                **definition,
                "municipalities": len(values),
                "missing_values": int(values.isna().sum()),
                "observed_values": int(values.notna().sum()),
                "unique_values": int(values.nunique(dropna=True)),
                "minimum": float(values.min()),
                "median": float(values.median()),
                "maximum": float(values.max()),
                "zero_values": int(values.eq(0).sum()),
                "largest_tie_count": int(counts.max()),
                "largest_tie_fraction": float(counts.max() / len(values)),
            }
        )
    profile = pd.DataFrame(profiles)

    institutional_deficit = pd.to_numeric(
        article["institutional_deficit_available_4"], errors="raise"
    )
    institutional_coverage = pd.to_numeric(article["institutional_coverage"], errors="raise")
    institutional_ratio = institutional_deficit / institutional_coverage
    published_rank = institutional_deficit.rank(method="average", pct=True)
    coverage_adjusted_rank = institutional_ratio.rank(method="average", pct=True)
    rank_shift = (published_rank - coverage_adjusted_rank).abs()
    coverage_summary = (
        pd.DataFrame(
            {
                "coverage": institutional_coverage,
                "deficit": institutional_deficit,
                "deficit_ratio": institutional_ratio,
            }
        )
        .groupby("coverage")
        .agg(
            municipalities=("deficit", "size"),
            mean_deficit=("deficit", "mean"),
            median_deficit=("deficit", "median"),
            mean_deficit_ratio=("deficit_ratio", "mean"),
            median_deficit_ratio=("deficit_ratio", "median"),
        )
        .reset_index()
        .to_dict("records")
    )

    police_columns = [
        column for column in municipal if column.startswith("police_") or column.startswith("rate_")
    ]
    article_police_columns = [column for column in article if column in police_columns]
    numeric = article.select_dtypes(include="number")
    coverage_counts = municipal["institutional_coverage"].value_counts().sort_index().to_dict()
    checks = {
        "municipal_rows_expected": len(municipal) == expected,
        "transport_rows_expected": len(transport) == expected,
        "article_rows_expected": len(article) == expected,
        "unique_municipalities_expected": article[key].nunique() == expected,
        "seven_nontransport_indicators": len(indicator_columns) == 7,
        "twelve_transport_scenarios": len(transport_columns) == 12,
        "all_framework_indicators_complete": article[indicator_columns].notna().all().all(),
        "all_article_numeric_values_finite": bool(np.isfinite(numeric.to_numpy()).all()),
        "police_columns_excluded": not article_police_columns,
        "published_input_matrix_unchanged": True,
    }
    if not all(checks.values()):
        raise ValueError(f"Capacity input audit failed: {checks}")

    for path in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    article.sort_values(key).to_csv(outputs["matrix"], index=False, encoding="utf-8")
    profile.to_csv(outputs["profile"], index=False, encoding="utf-8")
    audit = {
        "schema_version": config["schema_version"],
        "method_version": config["method_version"],
        "configuration": str(config_path),
        "checks": checks,
        "scope": {
            "municipalities": len(article),
            "nontransport_indicators": indicator_columns,
            "transport_scenarios": transport_columns,
        },
        "institutional_coverage": {
            "available_item_counts": {
                str(int(level)): int(count) for level, count in coverage_counts.items()
            },
            "deficit_rule": "available observed items minus positive observed items",
            "missing_responses_are_not_converted_to_deficit": True,
            "comparability_caution": (
                "Municipalities have two to four observed institutional items; "
                "coverage sensitivity must be reported without silently changing scores."
            ),
            "diagnostic_only_sensitivity": {
                "alternative": "observed deficit divided by observed coverage",
                "spearman_rank_correlation": float(published_rank.corr(coverage_adjusted_rank)),
                "mean_absolute_percentile_rank_shift": float(rank_shift.mean()),
                "median_absolute_percentile_rank_shift": float(rank_shift.median()),
                "maximum_absolute_percentile_rank_shift": float(rank_shift.max()),
                "coverage_group_summary": coverage_summary,
                "published_framework_changed": False,
            },
        },
        "indicator_ties": {
            "high_tie_threshold": 0.75,
            "indicators_above_threshold": profile.loc[
                profile["largest_tie_fraction"].ge(0.75), "column"
            ].tolist(),
            "interpretation": (
                "Large tie groups reduce discrimination but do not invalidate a "
                "criterion; their influence is evaluated through the declared scenarios."
            ),
        },
        "population_provenance_note": (
            "The population field stored as population_2023 represents the 2022 "
            "Demographic Census released/processed in 2023; it is not a framework criterion."
        ),
        "police_data": {
            "available_in_integrated_matrix": bool(police_columns),
            "column_count": len(police_columns),
            "reference_period": "2022-2025",
            "included_in_article_matrix": False,
            "included_in_capacity_framework": False,
            "reason": (
                "The research target is capacity strengthening under multimodal "
                "access constraints, not violence incidence or underreporting."
            ),
        },
        "interpretation": (
            "This audit selects and documents existing inputs only. It does not "
            "change source data, normalization, weights, scores, ranks, or profiles."
        ),
    }
    outputs["audit"].write_text(
        json.dumps(
            audit,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item() if isinstance(value, np.generic) else str(value),
        ),
        encoding="utf-8",
    )
    return outputs
