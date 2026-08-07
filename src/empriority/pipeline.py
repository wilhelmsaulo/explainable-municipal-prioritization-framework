from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from empriority.catalog import load_indicator_catalog
from empriority.config import Settings
from empriority.connectors.sidra import SidraQuery
from empriority.police import load_police_file, load_police_files
from empriority.source_registry import build_data_source_manager
from empriority.storage import ArtifactStore
from empriority.validation import MunicipalityValidationResult, validate_municipalities


def _store(settings: Settings) -> ArtifactStore:
    return ArtifactStore(settings.runtime.cache_directory, settings.runtime.output_directory)


def build_municipality_reference(
    settings: Settings,
) -> tuple[pd.DataFrame, MunicipalityValidationResult, Path]:
    manager = build_data_source_manager(settings)
    frame = manager.run("ibge.localities.municipalities", settings.project.state_code)
    validation = validate_municipalities(
        frame,
        expected_count=settings.project.expected_municipalities,
    )
    if not validation.is_valid:
        raise ValueError(f"Municipality validation failed: {validation}")

    metadata = {
        "source": "IBGE Localities",
        "state_code": settings.project.state_code,
        "record_count": len(frame),
    }
    output_path, _, _ = _store(settings).write_output("municipalities", frame, metadata)
    return frame, validation, output_path


def collect_munic(
    settings: Settings,
    year: int = 2023,
) -> dict[str, Path]:
    """Download MUNIC, preserve the workbook and export a worksheet inventory."""
    manager = build_data_source_manager(settings)
    workbook = manager.run("ibge.munic.workbook", year)
    inventory = manager.run("ibge.munic.inventory", year)

    raw_directory = settings.runtime.output_directory.parent / "raw" / "munic"
    raw_directory.mkdir(parents=True, exist_ok=True)
    workbook_path = raw_directory / f"Base_MUNIC_{year}.xlsx"
    workbook_path.write_bytes(workbook)

    metadata = {
        "source": "IBGE MUNIC",
        "year": year,
        "official_url": (
            f"https://ftp.ibge.gov.br/Perfil_Municipios/{year}/Base_de_Dados/Base_MUNIC_{year}.xlsx"
        ),
        "worksheet_count": len(inventory),
    }
    inventory_path, metadata_path, _ = _store(settings).write_output(
        f"munic_{year}_inventory",
        inventory,
        metadata,
    )
    return {
        "munic_workbook": workbook_path,
        "munic_inventory": inventory_path,
        "munic_metadata": metadata_path,
    }


def collect_sidra_table(
    settings: Settings,
    query: SidraQuery,
    output_name: str,
    *,
    refresh: bool = False,
) -> tuple[pd.DataFrame, Path, Path]:
    """Collect one SIDRA table with cache, provenance metadata and a snapshot."""
    store = _store(settings)
    parameters = query.as_parameters()
    fingerprint = store.fingerprint(parameters)

    cached = None
    if settings.runtime.cache_enabled and not refresh:
        cached = store.read_cache("sidra", fingerprint)

    if cached is None:
        manager = build_data_source_manager(settings)
        frame, metadata_object = manager.run("ibge.sidra.values", query)
        metadata = asdict(metadata_object)
        metadata["cache_hit"] = False
        metadata["fingerprint"] = fingerprint
        if settings.runtime.cache_enabled:
            store.write_cache("sidra", fingerprint, frame, metadata)
    else:
        frame, metadata = cached

    data_path, metadata_path, snapshot_path = store.write_output(output_name, frame, metadata)
    metadata["snapshot_directory"] = str(snapshot_path)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return frame, data_path, metadata_path


def collect_catalog_indicator(
    settings: Settings,
    indicator_name: str,
    catalog_path: str | Path = "config/indicators.yml",
    *,
    refresh: bool = False,
) -> tuple[pd.DataFrame, Path, Path]:
    """Collect a named indicator declared in the project catalog."""
    catalog = load_indicator_catalog(catalog_path)
    indicator = catalog.get(indicator_name)
    return collect_sidra_table(
        settings,
        indicator.to_query(),
        indicator.output,
        refresh=refresh,
    )


def import_police_data(
    settings: Settings,
    source_paths: str | Path | Iterable[str | Path],
) -> tuple[pd.DataFrame, Path, Path]:
    """Import one or multiple annual police files and preserve an auditable snapshot."""
    if isinstance(source_paths, (str, Path)):
        paths = [source_paths]
        frame = load_police_file(source_paths)
    else:
        paths = list(source_paths)
        frame = load_police_files(paths)

    metadata = {
        "source": "public police dataset",
        "source_paths": [str(Path(path)) for path in paths],
        "record_count": len(frame),
        "years": sorted(frame["year"].unique().tolist()),
    }
    data_path, metadata_path, _ = _store(settings).write_output(
        "police_occurrences",
        frame,
        metadata,
    )
    return frame, data_path, metadata_path


def collect_project(
    settings: Settings,
    catalog_path: str | Path = "config/indicators.yml",
    police_path: str | Path | Iterable[str | Path] | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Path]:
    """Run the current end-to-end collection pipeline."""
    outputs: dict[str, Path] = {}
    _, _, municipality_path = build_municipality_reference(settings)
    outputs["municipalities"] = municipality_path

    catalog = load_indicator_catalog(catalog_path)
    for name in catalog.names():
        _, data_path, _ = collect_catalog_indicator(
            settings,
            name,
            catalog_path,
            refresh=refresh,
        )
        outputs[name] = data_path

    if police_path is not None:
        _, data_path, _ = import_police_data(settings, police_path)
        outputs["police_occurrences"] = data_path
    return outputs
