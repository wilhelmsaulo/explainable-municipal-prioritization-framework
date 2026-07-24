from __future__ import annotations

from pathlib import Path

import pandas as pd

from empriority.config import Settings
from empriority.connectors.ibge_localities import IBGELocalitiesConnector
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
