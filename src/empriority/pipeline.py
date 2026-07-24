from __future__ import annotations

from pathlib import Path

import pandas as pd

from empriority.config import Settings
from empriority.connectors.ibge_localities import IBGELocalitiesConnector
from empriority.connectors.sidra import SidraConnector, SidraQuery
from empriority.validation import MunicipalityValidationResult, validate_municipalities


def build_municipality_reference(
    settings: Settings,
) -> tuple[pd.DataFrame, MunicipalityValidationResult, Path]:
    source = settings.sources.ibge_localities
    connector = IBGELocalitiesConnector(
        base_url=str(source.base_url),
        timeout=settings.runtime.request_timeout_seconds,
    )
    frame = connector.fetch_municipalities(settings.project.state_code)
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
    source = settings.sources.sidra
    connector = SidraConnector(
        base_url=str(source.base_url),
        timeout=settings.runtime.request_timeout_seconds,
    )
    frame, metadata = connector.fetch(query)

    safe_name = Path(output_name).stem
    output_dir = settings.runtime.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / f"{safe_name}.csv"
    metadata_path = output_dir / f"{safe_name}.metadata.json"

    frame.to_csv(data_path, index=False, encoding="utf-8")
    metadata.write_json(metadata_path)
    return frame, data_path, metadata_path
