from __future__ import annotations

import json
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from empriority.cnes import (
    build_cnes_municipal_indicators,
    extract_para_establishments,
    fetch_cnes_unit_types,
)


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(text.lower().replace("_", " ").split())


def _column(frame: pd.DataFrame, *names: str) -> str | None:
    normalized = {_norm(column): column for column in frame.columns}
    for name in names:
        found = normalized.get(_norm(name))
        if found is not None:
            return found
    return None


def _read_archive_csv(archive: zipfile.ZipFile, member: str) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in ("latin1", "utf-8", "utf-8-sig"):
        for separator in (";", ","):
            try:
                with archive.open(member) as handle:
                    frame = pd.read_csv(
                        handle,
                        encoding=encoding,
                        sep=separator,
                        low_memory=False,
                    )
                if len(frame.columns) > 1:
                    return frame
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{encoding}/{separator}: {exc}")
    raise RuntimeError(
        f"Unable to read CNES archive member {member}. " + " | ".join(errors[-4:])
    )


def extract_unit_types_from_archive(archive_path: str | Path) -> pd.DataFrame:
    """Extract the official unit-type dictionary bundled in the CNES archive."""
    archive_path = Path(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        candidates = [
            name
            for name in csv_members
            if any(
                token in _norm(Path(name).stem)
                for token in (
                    "tipo unidade",
                    "tipounidade",
                    "tipo de unidade",
                    "tb tipo unidade",
                )
            )
        ]

        for member in sorted(candidates, key=len):
            try:
                frame = _read_archive_csv(archive, member)
            except RuntimeError:
                continue
            code = _column(
                frame,
                "codigo_tipo_unidade",
                "co_tipo_unidade",
                "tp_unidade",
                "codigo",
                "co_tipo",
            )
            description = _column(
                frame,
                "descricao_tipo_unidade",
                "ds_tipo_unidade",
                "descricao",
                "nome",
                "ds_tipo",
            )
            if code is None or description is None:
                continue
            result = frame[[code, description]].copy()
            result.columns = ["codigo_tipo_unidade", "descricao_tipo_unidade"]
            result["codigo_tipo_unidade"] = (
                result["codigo_tipo_unidade"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
            )
            result["descricao_tipo_unidade"] = (
                result["descricao_tipo_unidade"].astype(str).str.strip()
            )
            result = result.dropna().drop_duplicates("codigo_tipo_unidade")
            if not result.empty:
                print(
                    f"CNES unit types extracted from {member}: {len(result)} records.",
                    flush=True,
                )
                return result

    return pd.DataFrame(
        columns=["codigo_tipo_unidade", "descricao_tipo_unidade"]
    )


def _load_existing_types(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()
    return frame if len(frame.columns) >= 2 and not frame.empty else pd.DataFrame()


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

    unit_types = _load_existing_types(types_path)
    if unit_types.empty:
        unit_types = extract_unit_types_from_archive(archive)
    if unit_types.empty:
        try:
            unit_types = fetch_cnes_unit_types()
        except Exception as exc:  # noqa: BLE001
            print(f"CNES unit-type API unavailable: {exc}", flush=True)
            unit_types = pd.DataFrame(
                columns=["codigo_tipo_unidade", "descricao_tipo_unidade"]
            )
    unit_types.to_csv(types_path, index=False, encoding="utf-8")

    indicators = build_cnes_municipal_indicators(establishments, unit_types)
    classified_total = int(
        indicators[
            ["cnes_ubs", "cnes_hospitals", "cnes_caps", "cnes_emergency_units"]
        ].to_numpy().sum()
    )
    if len(establishments) > 0 and classified_total == 0:
        raise RuntimeError(
            "CNES establishments were collected, but no UBS, hospital, CAPS or emergency "
            "unit was classified. The unit-type dictionary is missing or incompatible."
        )

    indicators.to_csv(indicators_path, index=False, encoding="utf-8")

    metadata_path.write_text(
        json.dumps(
            {
                "source": "DATASUS monthly CNES complete database",
                "archive_name": archive.name,
                "archive_size_bytes": archive.stat().st_size,
                "establishments": int(len(establishments)),
                "municipal_rows": int(len(indicators)),
                "unit_type_records": int(len(unit_types)),
                "classified_service_units": classified_total,
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
