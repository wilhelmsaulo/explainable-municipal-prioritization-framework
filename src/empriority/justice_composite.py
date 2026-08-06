from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


COMPONENT_COLUMNS = {
    "dpe": "justice_dpe_covered",
    "tjpa": "justice_tjpa_local_access",
    "mppa": "justice_mppa_covered",
}

SPECIALIZED_COLUMNS = {
    "tjpa": "justice_tjpa_women_specialized_units",
    "mppa": "justice_mppa_specialized_women",
}


def build_justice_composite(
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    matrix_path = Path(matrix_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    matrix = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    if len(matrix) != 144 or matrix["municipality_code"].nunique() != 144:
        raise AssertionError("Integrated matrix must contain exactly 144 unique municipalities")

    available_components: list[str] = []
    component_columns: list[str] = []
    for component, column in COMPONENT_COLUMNS.items():
        if column in matrix.columns and pd.to_numeric(matrix[column], errors="coerce").notna().any():
            matrix[column] = pd.to_numeric(matrix[column], errors="coerce")
            available_components.append(component)
            component_columns.append(column)

    if not component_columns:
        raise RuntimeError("No justice-access component is available in the integrated matrix")

    matrix["justice_components_available"] = matrix[component_columns].notna().sum(axis=1)
    matrix["justice_access_score_available"] = matrix[component_columns].sum(axis=1, min_count=1)
    matrix["justice_access_coverage_ratio"] = (
        matrix["justice_access_score_available"] / matrix["justice_components_available"]
    )
    matrix["justice_access_deficit_ratio"] = 1 - matrix["justice_access_coverage_ratio"]
    matrix["justice_full_access_available"] = (
        matrix["justice_access_score_available"] == matrix["justice_components_available"]
    ).astype(int)

    specialized_columns = [
        column
        for column in SPECIALIZED_COLUMNS.values()
        if column in matrix.columns and pd.to_numeric(matrix[column], errors="coerce").notna().any()
    ]
    if specialized_columns:
        for column in specialized_columns:
            matrix[column] = pd.to_numeric(matrix[column], errors="coerce")
        matrix["justice_specialized_women_services"] = matrix[specialized_columns].sum(axis=1, min_count=1)
        matrix["justice_specialized_women_access"] = (
            matrix["justice_specialized_women_services"] > 0
        ).astype(int)
    else:
        matrix["justice_specialized_women_services"] = pd.NA
        matrix["justice_specialized_women_access"] = pd.NA

    matrix.to_csv(matrix_path, index=False, encoding="utf-8")

    report_path = output / "justice_access_summary.json"
    report = {
        "municipalities": int(len(matrix)),
        "available_components": available_components,
        "component_columns": component_columns,
        "mean_coverage_ratio": float(matrix["justice_access_coverage_ratio"].mean()),
        "municipalities_with_full_available_access": int(matrix["justice_full_access_available"].sum()),
        "specialized_columns": specialized_columns,
        "municipalities_with_specialized_women_access": (
            int(matrix["justice_specialized_women_access"].fillna(0).sum())
            if specialized_columns
            else None
        ),
        "method": "Scores use only components available for each municipality; missing components are not converted to zero.",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"matrix": matrix_path, "summary": report_path}
