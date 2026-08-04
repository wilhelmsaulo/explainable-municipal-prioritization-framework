from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from empriority.cnes import (
    build_cnes_municipal_indicators,
    extract_para_establishments,
    fetch_cnes_unit_types,
)


def collect_cnes_pa_from_archive(
    archive_path: str | Path,
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    """Build Pará CNES indicators from a previously downloaded official archive."""
    archive = Path(archive_path)
    if not archive.exists() or archive.stat().st_size == 0:
        raise FileNotFoundError(f"CNES archive not found or empty: {archive}")

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "cnes_establishments_pa.csv"
    types_path = output / "cnes_unit_types.csv"
    indicators_path = output / "cnes_municipal_indicators_pa.csv"
    metadata_path = output / "cnes_municipal_indicators_pa.metadata.json"

    if raw_path.exists() and raw_path.stat().st_size > 0:
        print("Using existing Pará CNES snapshot.", flush=True)
        establishments = pd.read_csv(raw_path, low_memory=False)
        snapshot_reused = True
    else:
        establishments = extract_para_establishments(archive, raw_path)
        snapshot_reused = False

    if types_path.exists() and types_path.stat().st_size > 0:
        unit_types = pd.read_csv(types_path, low_memory=False)
    else:
        unit_types = fetch_cnes_unit_types()
        unit_types.to_csv(types_path, index=False, encoding="utf-8")

    indicators = build_cnes_municipal_indicators(establishments, unit_types)
    indicators.to_csv(indicators_path, index=False, encoding="utf-8")

    metadata_path.write_text(
        json.dumps(
            {
                "source": "DATASUS monthly CNES complete database",
                "archive_name": archive.name,
                "archive_size_bytes": archive.stat().st_size,
                "establishments": int(len(establishments)),
                "municipal_rows": int(len(indicators)),
                "snapshot_reused": snapshot_reused,
                "limitations": [
                    "Establishment indicators are derived from the monthly CNES database.",
                    "Professional indicators require the CNES professional table.",
                    "Obstetric-center count remains unavailable pending the installations table.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "cnes_establishments": raw_path,
        "cnes_unit_types": types_path,
        "cnes_indicators": indicators_path,
        "cnes_metadata": metadata_path,
    }
