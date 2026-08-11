from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from empriority.matrix_audit import audit_integrated_matrix

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
)


def finalize_dataset(
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    matrix_path = Path(matrix_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    matrix = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    original_columns = list(matrix.columns)

    removed_columns = [
        column
        for column in matrix.columns
        if column.startswith(("justice_dpe_", "justice_mppa_"))
        or column in DEPRECATED_JUSTICE_COLUMNS
    ]
    if removed_columns:
        matrix = matrix.drop(columns=removed_columns)

    if len(matrix) != 144:
        raise AssertionError(f"Expected 144 municipalities, found {len(matrix)}")
    if matrix["municipality_code"].nunique() != 144:
        raise AssertionError("Municipality codes are not unique after cleanup")

    required_blocks = {
        "municipal_policy": any(c.startswith("women_") for c in matrix.columns),
        "violence": any(c.startswith("police_") for c in matrix.columns),
        "health": any(c.startswith("cnes_") for c in matrix.columns),
        "social_assistance": any(c.startswith("social_") for c in matrix.columns),
        "state_judiciary": any(c.startswith("justice_tjpa_") for c in matrix.columns),
        "protection_network": any(c.startswith("protection_network_") for c in matrix.columns),
    }
    missing_blocks = [name for name, available in required_blocks.items() if not available]
    if missing_blocks:
        raise AssertionError("Required integrated blocks missing: " + ", ".join(missing_blocks))

    matrix.to_csv(matrix_path, index=False, encoding="utf-8")

    removed_files: list[str] = []
    for name in DEPRECATED_OUTPUTS:
        path = output / name
        if path.exists():
            path.unlink()
            removed_files.append(str(path))

    audit_outputs = audit_integrated_matrix(matrix_path, output)

    status_path = output / "dataset_finalization_status.json"
    status_path.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "status": "ready_for_criterion_screening",
                "rows": int(len(matrix)),
                "columns_before_cleanup": len(original_columns),
                "columns_after_cleanup": int(len(matrix.columns)),
                "removed_columns": removed_columns,
                "removed_deprecated_outputs": removed_files,
                "retained_scope": {
                    "state_judiciary": "TJPA only",
                    "dpe": "excluded from this study version",
                    "mppa": "excluded from this study version",
                    "protection_network": "retained, including Ligue 180 and geospatial accessibility",
                    "transport": "source layer prepared; municipal indicators pending next stage",
                },
                "required_blocks": required_blocks,
                "next_step": "Conceptual and statistical screening of candidate criteria",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Dataset finalized: rows={len(matrix)}, columns={len(matrix.columns)}, "
        f"removed_columns={len(removed_columns)}",
        flush=True,
    )
    return {"status": status_path, **audit_outputs}
