from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


DIMENSION_PREFIXES = {
    "municipal_policy": (
        "women_",
        "institutional_",
        "campaigns_",
        "programs_",
        "human_rights_",
        "specialized_women_",
    ),
    "violence": ("police_", "rate_"),
    "health": ("cnes_",),
    "social_assistance": ("social_",),
    "state_judiciary": ("justice_tjpa_",),
    "protection_network": ("protection_network_",),
    "transport_accessibility": ("transport_",),
}

NONNEGATIVE_PREFIXES = (
    "police_",
    "rate_",
    "cnes_",
    "social_",
    "justice_tjpa_",
    "protection_network_",
    "transport_",
)

IDENTIFIER_SUFFIXES = (
    "_service_id",
    "_display_name",
    "_query",
    "_note",
    "_status",
    "_confidence",
)


def _is_numeric_candidate(series: pd.Series) -> bool:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.notna().sum() > 0


def audit_integrated_matrix(
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    matrix_path = Path(matrix_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    errors: list[str] = []
    warnings: list[str] = []

    if len(df) != 144:
        errors.append(f"Expected 144 rows, found {len(df)}")
    if "municipality_code" not in df.columns:
        errors.append("Missing municipality_code")
    elif df["municipality_code"].nunique(dropna=True) != 144:
        errors.append(
            "Expected 144 unique municipality codes, found "
            f"{df['municipality_code'].nunique(dropna=True)}"
        )

    duplicate_codes: list[str] = []
    if "municipality_code" in df.columns:
        duplicate_codes = (
            df.loc[df["municipality_code"].duplicated(keep=False), "municipality_code"]
            .dropna()
            .unique()
            .tolist()
        )

    entirely_missing = [column for column in df.columns if df[column].isna().all()]
    constant_columns = [
        column
        for column in df.columns
        if column not in {"municipality_code", "municipality"}
        and df[column].nunique(dropna=True) <= 1
    ]

    deprecated_justice = [
        column
        for column in df.columns
        if column.startswith(("justice_dpe_", "justice_mppa_"))
        or column
        in {
            "justice_components_available",
            "justice_access_score_available",
            "justice_access_coverage_ratio",
            "justice_access_deficit_ratio",
            "justice_full_access_available",
            "justice_specialized_women_services",
            "justice_specialized_women_access",
        }
    ]
    if deprecated_justice:
        errors.append(
            "Deprecated DPE/MPPA or cross-institution justice columns remain: "
            + ", ".join(deprecated_justice)
        )

    negative_counts: dict[str, int] = {}
    for column in df.columns:
        if column.startswith(NONNEGATIVE_PREFIXES):
            numeric = pd.to_numeric(df[column], errors="coerce")
            count = int((numeric < 0).sum())
            if count:
                negative_counts[column] = count
                errors.append(f"Negative values in {column}: {count}")

    if "population_2023" in df.columns:
        population = pd.to_numeric(df["population_2023"], errors="coerce")
        invalid_population = int((population <= 0).sum() + population.isna().sum())
        if invalid_population:
            errors.append(f"Invalid or missing population_2023 values: {invalid_population}")

    dimension_summary: dict[str, dict[str, object]] = {}
    for dimension, prefixes in DIMENSION_PREFIXES.items():
        columns = [column for column in df.columns if column.startswith(prefixes)]
        observed = [column for column in columns if not df[column].isna().all()]
        varying = [column for column in observed if df[column].nunique(dropna=True) > 1]
        numeric_varying = [column for column in varying if _is_numeric_candidate(df[column])]
        completeness = float(df[observed].notna().mean().mean()) if observed else 0.0
        dimension_summary[dimension] = {
            "columns": columns,
            "observed_columns": observed,
            "varying_columns": varying,
            "numeric_candidate_columns": numeric_varying,
            "numeric_candidate_count": len(numeric_varying),
            "mean_cell_completeness": completeness,
        }
        if not observed:
            warnings.append(f"No observed columns for dimension {dimension}")

    readiness_rows: list[dict[str, object]] = []
    for column in df.columns:
        series = df[column]
        missing_fraction = float(series.isna().mean())
        unique = int(series.nunique(dropna=True))
        numeric = _is_numeric_candidate(series)

        if column in {"municipality_code", "municipality"}:
            role = "identifier"
            eligible = False
            reason = "municipal identifier"
        elif column.endswith(IDENTIFIER_SUFFIXES) or column in {
            "protection_network_seat_latitude",
            "protection_network_seat_longitude",
        }:
            role = "audit_or_location"
            eligible = False
            reason = "provenance, identifier or geographic support field"
        elif series.isna().all():
            role = "unavailable"
            eligible = False
            reason = "entirely missing"
        elif unique <= 1:
            role = "constant"
            eligible = False
            reason = "no municipal discrimination"
        elif not numeric:
            role = "categorical_support"
            eligible = False
            reason = "not numeric; requires explicit encoding decision"
        elif missing_fraction > 0.20:
            role = "incomplete_numeric"
            eligible = False
            reason = "more than 20% missing"
        else:
            role = "candidate_numeric"
            eligible = True
            reason = "observed, varying numeric municipal indicator"

        dimension = "other"
        for name, prefixes in DIMENSION_PREFIXES.items():
            if column.startswith(prefixes):
                dimension = name
                break
        if column == "population_2023":
            dimension = "demography"

        readiness_rows.append(
            {
                "column": column,
                "dimension": dimension,
                "role": role,
                "eligible_for_screening": eligible,
                "reason": reason,
                "missing_fraction": missing_fraction,
                "unique_non_missing": unique,
                "numeric_detected": numeric,
            }
        )

    readiness = pd.DataFrame(readiness_rows)
    candidate_columns = readiness.loc[
        readiness["eligible_for_screening"], "column"
    ].tolist()

    column_profile = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(df[column].dtype) for column in df.columns],
            "non_missing": [int(df[column].notna().sum()) for column in df.columns],
            "missing": [int(df[column].isna().sum()) for column in df.columns],
            "missing_fraction": [float(df[column].isna().mean()) for column in df.columns],
            "unique_non_missing": [int(df[column].nunique(dropna=True)) for column in df.columns],
            "entirely_missing": [bool(df[column].isna().all()) for column in df.columns],
            "constant_or_empty": [bool(df[column].nunique(dropna=True) <= 1) for column in df.columns],
        }
    )

    status = "failed" if errors else ("warning" if warnings or entirely_missing else "passed")
    report = {
        "status": status,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "unique_municipalities": int(df["municipality_code"].nunique(dropna=True))
        if "municipality_code" in df.columns
        else None,
        "duplicate_codes": duplicate_codes,
        "entirely_missing_columns": entirely_missing,
        "constant_or_empty_columns": constant_columns,
        "deprecated_justice_columns": deprecated_justice,
        "negative_value_counts": negative_counts,
        "dimensions": dimension_summary,
        "candidate_columns_for_screening": candidate_columns,
        "candidate_column_count": len(candidate_columns),
        "errors": errors,
        "warnings": warnings,
        "method_note": (
            "The audit checks structural integrity, availability and preliminary modeling "
            "readiness. Missing thematic sources are not converted to zero. Candidate "
            "columns still require redundancy, correlation and conceptual screening."
        ),
    }

    report_path = output / "integrated_matrix_audit.json"
    profile_path = output / "integrated_matrix_column_profile.csv"
    readiness_path = output / "modeling_readiness_columns.csv"
    readiness_json_path = output / "modeling_readiness_status.json"

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    column_profile.to_csv(profile_path, index=False, encoding="utf-8")
    readiness.to_csv(readiness_path, index=False, encoding="utf-8")
    readiness_json_path.write_text(
        json.dumps(
            {
                "status": "ready_for_criterion_screening" if not errors else "not_ready",
                "matrix_rows": int(len(df)),
                "matrix_columns": int(len(df.columns)),
                "candidate_numeric_columns": len(candidate_columns),
                "next_step": (
                    "Screen candidates for conceptual relevance, redundancy, correlation, "
                    "direction and temporal compatibility before configuring MCDA."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if errors:
        raise AssertionError("Integrated matrix audit failed: " + "; ".join(errors))

    print(
        f"Matrix audit {status}: rows={len(df)}, columns={len(df.columns)}, "
        f"candidates={len(candidate_columns)}, entirely_missing={len(entirely_missing)}",
        flush=True,
    )
    return {
        "report": report_path,
        "column_profile": profile_path,
        "readiness_columns": readiness_path,
        "readiness_status": readiness_json_path,
    }
