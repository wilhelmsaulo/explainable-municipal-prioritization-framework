from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

DEPRECATED_JUSTICE_COLUMNS = {
    "justice_components_available",
    "justice_access_score_available",
    "justice_access_coverage_ratio",
    "justice_access_deficit_ratio",
    "justice_full_access_available",
    "justice_specialized_women_services",
    "justice_specialized_women_access",
}

DEPRECATED_OUTPUTS = (
    "justice_defensoria_indicators_pa.csv",
    "justice_defensoria_directory_raw_pa.csv",
    "justice_defensoria_indicators_pa.metadata.json",
    "justice_defensoria_diagnostic.json",
    "justice_mppa_indicators_pa.csv",
    "justice_mppa_institutional_pages_pa.csv",
    "justice_mppa_indicators_pa.metadata.json",
    "justice_mppa_diagnostic.json",
    "justice_composite_indicators_pa.csv",
    "justice_composite.metadata.json",
    "justice_dimension_status.json",
    "justice_access_summary.json",
)

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
    "transport_",
)

COORDINATE_COLUMNS = {
    "protection_network_seat_latitude",
    "protection_network_seat_longitude",
}

SUPPORT_SUFFIXES = (
    "_service_id",
    "_display_name",
    "_query",
    "_note",
    "_status",
    "_confidence",
)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _dimension(column: str) -> str:
    if column == "population_2023":
        return "demography"
    for name, prefixes in DIMENSION_PREFIXES.items():
        if column.startswith(prefixes):
            return name
    return "other"


def finalize_dataset_v2(
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    matrix_path = Path(matrix_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    original_columns = list(df.columns)

    removed_columns = [
        c
        for c in df.columns
        if c.startswith(("justice_dpe_", "justice_mppa_")) or c in DEPRECATED_JUSTICE_COLUMNS
    ]
    if removed_columns:
        df = df.drop(columns=removed_columns)

    errors: list[str] = []
    warnings: list[str] = []

    if len(df) != 144:
        errors.append(f"Expected 144 rows, found {len(df)}")
    if "municipality_code" not in df.columns:
        errors.append("Missing municipality_code")
        unique_municipalities = None
        duplicate_codes: list[str] = []
    else:
        unique_municipalities = int(df["municipality_code"].nunique(dropna=True))
        if unique_municipalities != 144:
            errors.append(f"Expected 144 unique municipality codes, found {unique_municipalities}")
        duplicate_codes = (
            df.loc[df["municipality_code"].duplicated(keep=False), "municipality_code"]
            .dropna()
            .unique()
            .tolist()
        )

    if "population_2023" in df.columns:
        pop = _numeric(df["population_2023"])
        invalid_pop = int(pop.isna().sum() + (pop <= 0).sum())
        if invalid_pop:
            errors.append(f"Invalid population_2023 values: {invalid_pop}")
    else:
        errors.append("Missing population_2023")

    required_blocks = {
        "municipal_policy": any(c.startswith(("women_", "institutional_")) for c in df.columns),
        "violence": any(c.startswith("police_") for c in df.columns),
        "health": any(c.startswith("cnes_") for c in df.columns),
        "social_assistance": any(c.startswith("social_") for c in df.columns),
        "state_judiciary": any(c.startswith("justice_tjpa_") for c in df.columns),
        "protection_network": any(c.startswith("protection_network_") for c in df.columns),
    }
    missing_blocks = [name for name, present in required_blocks.items() if not present]
    if missing_blocks:
        errors.append("Missing required blocks: " + ", ".join(missing_blocks))

    deprecated_remaining = [
        c
        for c in df.columns
        if c.startswith(("justice_dpe_", "justice_mppa_")) or c in DEPRECATED_JUSTICE_COLUMNS
    ]
    if deprecated_remaining:
        errors.append("Deprecated justice columns remain: " + ", ".join(deprecated_remaining))

    entirely_missing = [c for c in df.columns if df[c].isna().all()]
    constant_columns = [
        c
        for c in df.columns
        if c not in {"municipality_code", "municipality"} and df[c].nunique(dropna=True) <= 1
    ]

    negative_counts: dict[str, int] = {}
    for column in df.columns:
        validate_nonnegative = column.startswith(NONNEGATIVE_PREFIXES)
        if column.startswith("protection_network_"):
            validate_nonnegative = column not in COORDINATE_COLUMNS and not column.endswith(
                SUPPORT_SUFFIXES
            )
        if not validate_nonnegative:
            continue
        numeric = _numeric(df[column])
        count = int((numeric < 0).sum())
        if count:
            negative_counts[column] = count
            errors.append(f"Negative values in {column}: {count}")

    readiness_rows: list[dict[str, object]] = []
    for column in df.columns:
        series = df[column]
        numeric = _numeric(series)
        missing_fraction = float(series.isna().mean())
        unique = int(series.nunique(dropna=True))
        numeric_count = int(numeric.notna().sum())

        if column in {"municipality_code", "municipality"}:
            role, eligible, reason = "identifier", False, "municipal identifier"
        elif column in COORDINATE_COLUMNS or column.endswith(SUPPORT_SUFFIXES):
            role, eligible, reason = (
                "audit_or_support",
                False,
                "location, provenance or identifier field",
            )
        elif series.isna().all():
            role, eligible, reason = "unavailable", False, "entirely missing"
        elif unique <= 1:
            role, eligible, reason = "constant", False, "no municipal discrimination"
        elif numeric_count == 0:
            role, eligible, reason = "categorical_support", False, "requires explicit encoding"
        elif missing_fraction > 0.20:
            role, eligible, reason = "incomplete_numeric", False, "more than 20% missing"
        else:
            role, eligible, reason = (
                "candidate_numeric",
                True,
                "observed and varying numeric indicator",
            )

        readiness_rows.append(
            {
                "column": column,
                "dimension": _dimension(column),
                "role": role,
                "eligible_for_screening": eligible,
                "reason": reason,
                "missing_fraction": missing_fraction,
                "unique_non_missing": unique,
                "numeric_non_missing": numeric_count,
            }
        )

    readiness = pd.DataFrame(readiness_rows)
    candidates = readiness.loc[readiness["eligible_for_screening"], "column"].tolist()

    dimensions: dict[str, dict[str, object]] = {}
    for name, prefixes in DIMENSION_PREFIXES.items():
        columns = [c for c in df.columns if c.startswith(prefixes)]
        observed = [c for c in columns if not df[c].isna().all()]
        candidate = [c for c in candidates if c in columns]
        dimensions[name] = {
            "column_count": len(columns),
            "observed_column_count": len(observed),
            "candidate_column_count": len(candidate),
            "candidate_columns": candidate,
            "mean_cell_completeness": float(df[observed].notna().mean().mean())
            if observed
            else 0.0,
        }
        if name != "transport_accessibility" and not observed:
            warnings.append(f"No observed columns for required analytical dimension {name}")

    if not any(c.startswith("transport_") for c in df.columns):
        warnings.append(
            "Transport source layer exists, but municipal transport indicators are not yet integrated"
        )

    status = "failed" if errors else ("warning" if warnings or entirely_missing else "passed")

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "unique_municipalities": unique_municipalities,
        "duplicate_codes": duplicate_codes,
        "removed_columns": removed_columns,
        "deprecated_justice_columns_remaining": deprecated_remaining,
        "entirely_missing_columns": entirely_missing,
        "constant_or_empty_columns": constant_columns,
        "negative_value_counts": negative_counts,
        "required_blocks": required_blocks,
        "dimensions": dimensions,
        "candidate_column_count": len(candidates),
        "candidate_columns_for_screening": candidates,
        "errors": errors,
        "warnings": warnings,
        "method_note": "Coordinates are allowed to be negative and are excluded from criterion screening. Missing sources are not converted to zero.",
    }

    column_profile = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(df[c].dtype) for c in df.columns],
            "non_missing": [int(df[c].notna().sum()) for c in df.columns],
            "missing": [int(df[c].isna().sum()) for c in df.columns],
            "missing_fraction": [float(df[c].isna().mean()) for c in df.columns],
            "unique_non_missing": [int(df[c].nunique(dropna=True)) for c in df.columns],
            "entirely_missing": [bool(df[c].isna().all()) for c in df.columns],
            "constant_or_empty": [bool(df[c].nunique(dropna=True) <= 1) for c in df.columns],
        }
    )

    matrix_path.write_text(df.to_csv(index=False), encoding="utf-8")

    removed_files: list[str] = []
    for name in DEPRECATED_OUTPUTS:
        path = output / name
        if path.exists():
            path.unlink()
            removed_files.append(name)

    report_path = output / "integrated_matrix_audit.json"
    profile_path = output / "integrated_matrix_column_profile.csv"
    readiness_path = output / "modeling_readiness_columns.csv"
    readiness_status_path = output / "modeling_readiness_status.json"
    final_status_path = output / "dataset_finalization_status.json"

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    column_profile.to_csv(profile_path, index=False, encoding="utf-8")
    readiness.to_csv(readiness_path, index=False, encoding="utf-8")
    readiness_status_path.write_text(
        json.dumps(
            {
                "status": "ready_for_criterion_screening" if not errors else "not_ready",
                "matrix_rows": int(len(df)),
                "matrix_columns": int(len(df.columns)),
                "candidate_numeric_columns": len(candidates),
                "transport_indicators_pending": not any(
                    c.startswith("transport_") for c in df.columns
                ),
                "next_step": "Conceptual and statistical screening of candidate criteria",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    final_status_path.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "status": "ready_for_criterion_screening" if not errors else "not_ready",
                "audit_status": status,
                "rows": int(len(df)),
                "columns_before_cleanup": len(original_columns),
                "columns_after_cleanup": int(len(df.columns)),
                "removed_columns": removed_columns,
                "removed_deprecated_outputs": removed_files,
                "retained_scope": {
                    "state_judiciary": "TJPA only",
                    "dpe": "excluded",
                    "mppa": "excluded",
                    "protection_network": "retained with geospatial accessibility",
                    "transport": "official source layer prepared; municipal indicators pending",
                },
                "next_step": "Conceptual and statistical screening of candidate criteria",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if errors:
        raise AssertionError("Final dataset audit failed: " + "; ".join(errors))

    print(
        f"Final dataset audit {status}: rows={len(df)}, columns={len(df.columns)}, candidates={len(candidates)}",
        flush=True,
    )
    return {
        "matrix": matrix_path,
        "audit": report_path,
        "profile": profile_path,
        "readiness_columns": readiness_path,
        "readiness_status": readiness_status_path,
        "finalization_status": final_status_path,
    }
