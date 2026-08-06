from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


DIMENSION_PREFIXES = {
    "municipal_policy": ("women_", "institutional_", "campaigns_", "programs_", "human_rights_", "specialized_women_"),
    "violence": ("police_", "rate_"),
    "health": ("cnes_",),
    "social_assistance": ("social_",),
    "justice": ("justice_",),
}

NONNEGATIVE_PREFIXES = ("police_", "rate_", "cnes_", "social_", "justice_")


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
        errors.append(f"Expected 144 unique municipality codes, found {df['municipality_code'].nunique(dropna=True)}")

    duplicate_codes = []
    if "municipality_code" in df.columns:
        duplicate_codes = df.loc[df["municipality_code"].duplicated(keep=False), "municipality_code"].dropna().unique().tolist()

    entirely_missing = [column for column in df.columns if df[column].isna().all()]
    constant_columns = [
        column for column in df.columns
        if column not in {"municipality_code", "municipality"} and df[column].nunique(dropna=True) <= 1
    ]

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
        usable = [column for column in columns if not df[column].isna().all()]
        completeness = float(df[usable].notna().mean().mean()) if usable else 0.0
        dimension_summary[dimension] = {
            "columns": columns,
            "usable_columns": usable,
            "usable_column_count": len(usable),
            "mean_cell_completeness": completeness,
        }
        if not usable:
            warnings.append(f"No usable columns for dimension {dimension}")

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
        "unique_municipalities": int(df["municipality_code"].nunique(dropna=True)) if "municipality_code" in df.columns else None,
        "duplicate_codes": duplicate_codes,
        "entirely_missing_columns": entirely_missing,
        "constant_or_empty_columns": constant_columns,
        "negative_value_counts": negative_counts,
        "dimensions": dimension_summary,
        "errors": errors,
        "warnings": warnings,
        "method_note": "The audit checks structural integrity and observed availability. Missing thematic sources are not converted to zero.",
    }

    report_path = output / "integrated_matrix_audit.json"
    profile_path = output / "integrated_matrix_column_profile.csv"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    column_profile.to_csv(profile_path, index=False, encoding="utf-8")

    if errors:
        raise AssertionError("Integrated matrix audit failed: " + "; ".join(errors))

    print(
        f"Matrix audit {status}: rows={len(df)}, columns={len(df.columns)}, "
        f"entirely_missing={len(entirely_missing)}, warnings={len(warnings)}",
        flush=True,
    )
    return {"report": report_path, "column_profile": profile_path}
