from __future__ import annotations

from pathlib import Path

import pandas as pd

from empriority.catalog import load_indicator_catalog
from empriority.config import Settings
from empriority.connectors.sidra import SidraQuery
from empriority.source_registry import build_data_source_manager
from empriority.validation import MunicipalityValidationResult, validate_municipalities


def build_municipality_reference(
    settings: Settings,
) -> tuple[pd.DataFrame, MunicipalityValidationResult, Path]:
    manager = build_data_source_manager(settings)
    frame = manager.run(
        "ibge.localities.municipalities",
        settings.project.state_code,
    )
    validation = validate_municipalities(
        frame,
        expected_count=settings.project.expected_municipalities,
    )
    if not validation.is_valid:
        raise ValueError(f"Municipality validation failed: {validation}")

    output_dir = settings.runtime.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "municipalities.csv"
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return frame, validation, output_path


def collect_sidra_table(
    settings: Settings,
    query: SidraQuery,
    output_name: str,
) -> tuple[pd.DataFrame, Path, Path]:
    """Collect one SIDRA table and persist data plus an audit metadata sidecar."""
    manager = build_data_source_manager(settings)
    frame, metadata = manager.run("ibge.sidra.values", query)

    safe_name = Path(output_name).stem
    output_dir = settings.runtime.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / f"{safe_name}.csv"
    metadata_path = output_dir / f"{safe_name}.metadata.json"

    frame.to_csv(data_path, index=False, encoding="utf-8")
    metadata.write_json(metadata_path)
    return frame, data_path, metadata_path


def collect_catalog_indicator(
    settings: Settings,
    indicator_name: str,
    catalog_path: str | Path = "config/indicators.yml",
) -> tuple[pd.DataFrame, Path, Path]:
    """Collect a named indicator declared in the project catalog."""
    catalog = load_indicator_catalog(catalog_path)
    indicator = catalog.get(indicator_name)
    return collect_sidra_table(settings, indicator.to_query(), indicator.output)
