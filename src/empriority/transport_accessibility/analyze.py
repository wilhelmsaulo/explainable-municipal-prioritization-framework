from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from empriority.transport_accessibility.integrate import VARIABLES

HIGH_CORRELATION_THRESHOLD = 0.90
NEAR_CONSTANT_PREVALENCE = 0.05


def analyze_transport_indicators(
    matrix_csv: str | Path,
    descriptive_csv: str | Path = "data/processed/transport/transport_indicator_descriptive.csv",
    correlation_csv: str | Path = "data/processed/transport/transport_indicator_spearman.csv",
    report_json: str | Path = "data/processed/transport/transport_indicator_redundancy.json",
) -> dict[str, Path]:
    matrix_path = Path(matrix_csv)
    frame = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    variables = list(VARIABLES)
    values = frame[variables].apply(pd.to_numeric, errors="raise")

    rows: list[dict[str, Any]] = []
    near_constant: list[str] = []
    for variable in variables:
        series = values[variable]
        metadata = VARIABLES[variable]
        zero_share = float(series.eq(0).mean())
        unique_values = int(series.nunique(dropna=True))
        record = {
            "variable": variable,
            "mode": metadata["mode"],
            "direction": metadata["direction"],
            "unit": metadata["unit"],
            "n": int(series.notna().sum()),
            "missing": int(series.isna().sum()),
            "unique_values": unique_values,
            "zero_count": int(series.eq(0).sum()),
            "zero_share": zero_share,
            "mean": float(series.mean()),
            "std": float(series.std()),
            "min": float(series.min()),
            "p25": float(series.quantile(0.25)),
            "median": float(series.median()),
            "p75": float(series.quantile(0.75)),
            "max": float(series.max()),
            "skewness": float(series.skew()) if unique_values > 1 else 0.0,
        }
        rows.append(record)
        if unique_values == 1:
            near_constant.append(variable)
        elif metadata["unit"] == "binary":
            prevalence = float(series.mean())
            if prevalence <= NEAR_CONSTANT_PREVALENCE or prevalence >= 1 - NEAR_CONSTANT_PREVALENCE:
                near_constant.append(variable)

    descriptive = pd.DataFrame(rows)
    correlation = values.corr(method="spearman")

    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(variables):
        for right in variables[left_index + 1 :]:
            coefficient = correlation.loc[left, right]
            if pd.notna(coefficient) and abs(float(coefficient)) >= HIGH_CORRELATION_THRESHOLD:
                pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "spearman_rho": round(float(coefficient), 6),
                        "absolute_rho": round(abs(float(coefficient)), 6),
                        "same_mode": VARIABLES[left]["mode"] == VARIABLES[right]["mode"],
                        "left_direction": VARIABLES[left]["direction"],
                        "right_direction": VARIABLES[right]["direction"],
                    }
                )
    pairs.sort(key=lambda item: (-item["absolute_rho"], item["left"], item["right"]))

    exact_relationships = [
        {
            "variables": ["road_total_km", "road_federal_km", "road_state_km", "road_other_km"],
            "relationship": "road_total_km is the arithmetic sum of the three network classes",
            "recommendation": "Do not use total and all components simultaneously in one additive score.",
        },
        {
            "variables": ["port_count", "port_presence"],
            "relationship": "presence is deterministically derived from count > 0",
            "recommendation": "Choose count or presence according to the model interpretation.",
        },
        {
            "variables": ["decea_airport_count", "decea_airport_presence"],
            "relationship": "presence is deterministically derived from count > 0",
            "recommendation": "Choose count or presence according to the model interpretation.",
        },
        {
            "variables": ["passenger_crossing_km", "passenger_crossing_presence"],
            "relationship": "presence is deterministically derived from length > 0",
            "recommendation": "Choose length or presence according to the model interpretation.",
        },
        {
            "variables": ["navigated_waterway_km", "navigated_waterway_presence"],
            "relationship": "presence is deterministically derived from length > 0",
            "recommendation": "Choose length or presence according to the model interpretation.",
        },
    ]

    directional = [
        variable for variable, metadata in VARIABLES.items() if metadata["direction"] != "context"
    ]
    context = [
        variable for variable, metadata in VARIABLES.items() if metadata["direction"] == "context"
    ]
    eligible_after_variance_screen = [
        variable for variable in directional if variable not in near_constant
    ]

    checks = {
        "rows_144": len(frame) == 144,
        "variables_24": len(variables) == 24,
        "no_missing": bool(values.notna().all().all()),
        "finite_values": bool(np.isfinite(values.to_numpy()).all()),
        "symmetric_correlation": bool(
            np.allclose(correlation.to_numpy(), correlation.to_numpy().T, equal_nan=True)
        ),
        "correlation_diagonal_one": bool(
            np.allclose(np.diag(correlation.to_numpy()), 1.0, equal_nan=False)
        ),
    }
    if not all(checks.values()):
        raise ValueError(f"Transport screening audit failed: {checks}")

    descriptive_path = Path(descriptive_csv)
    correlation_path = Path(correlation_csv)
    report_path = Path(report_json)
    descriptive_path.parent.mkdir(parents=True, exist_ok=True)
    descriptive.to_csv(descriptive_path, index=False, encoding="utf-8")
    correlation.to_csv(correlation_path, index=True, encoding="utf-8")

    report = {
        "method": {
            "association": "Spearman rank correlation",
            "high_absolute_correlation_threshold": HIGH_CORRELATION_THRESHOLD,
            "near_constant_binary_prevalence_threshold": NEAR_CONSTANT_PREVALENCE,
            "note": "Thresholds are screening rules, not automatic exclusion criteria.",
        },
        "rows": len(frame),
        "variables": len(variables),
        "directional_variables": directional,
        "context_variables": context,
        "near_constant_variables": near_constant,
        "eligible_after_variance_screen": eligible_after_variance_screen,
        "high_correlation_pairs": pairs,
        "exact_or_constructed_relationships": exact_relationships,
        "recommendations": [
            "Keep context variables outside any direct additive accessibility score.",
            "Review each high-correlation pair using conceptual relevance before selection.",
            "Do not combine a derived presence indicator with the count or length that defines it.",
            "Prefer continuous distance or density information when a binary presence variable is near constant.",
            "Apply transformations and normalization only after the retained indicator set is documented.",
        ],
        "checks": checks,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "descriptive": descriptive_path,
        "correlation": correlation_path,
        "report": report_path,
    }
