from __future__ import annotations

import json
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

CNES_XML_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_xml.zip"


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(record: dict[str, str], *names: str) -> str | None:
    normalized = {_norm(key).replace(" ", "_"): value for key, value in record.items()}
    for name in names:
        value = normalized.get(_norm(name).replace(" ", "_"))
        if value not in (None, ""):
            return value
    return None


def download_cnes_xml(destination: str | Path, timeout: float = 600.0) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", CNES_XML_URL, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            downloaded = 0
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                handle.write(chunk)
                downloaded += len(chunk)
                if downloaded and downloaded % (25 * 1024 * 1024) < 1024 * 1024:
                    print(f"CNES S3 download: {downloaded / 1_048_576:.1f} MB", flush=True)
    if not zipfile.is_zipfile(target):
        raise RuntimeError("The official CNES S3 resource is not a valid ZIP archive.")
    return target


def extract_para_xml(archive_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    archive_path = Path(archive_path)
    output_path = Path(output_path)
    with zipfile.ZipFile(archive_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if not members:
            raise RuntimeError("The CNES ZIP contains no XML file.")
        member = members[0]
        rows: list[dict[str, str]] = []
        with archive.open(member) as stream:
            for _, element in ET.iterparse(stream, events=("end",)):
                children = list(element)
                if not children:
                    continue
                record: dict[str, str] = {}
                for child in children:
                    if list(child):
                        continue
                    text = (child.text or "").strip()
                    if text:
                        record[_local_name(child.tag)] = text
                if not record:
                    element.clear()
                    continue
                municipality = _first(
                    record,
                    "CO_MUNICIPIO_GESTOR",
                    "CO_MUNICIPIO",
                    "CODUFMUN",
                    "IBGE",
                    "codigo_municipio",
                    "codigo_ibge",
                )
                state = _first(record, "CO_ESTADO_GESTOR", "CO_UF", "UF", "codigo_uf")
                municipality_digits = "".join(character for character in str(municipality or "") if character.isdigit())
                state_text = _norm(state or "")
                if municipality_digits.zfill(6).startswith("15") or state_text in {"15", "pa", "para"}:
                    rows.append(record)
                element.clear()
    if not rows:
        raise RuntimeError("No Pará establishments were identified in the official CNES XML.")
    frame = pd.DataFrame(rows).drop_duplicates()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    print(f"CNES Pará snapshot: {len(frame)} establishments.", flush=True)
    return frame


def _column(frame: pd.DataFrame, *names: str) -> str | None:
    normalized = {_norm(column).replace(" ", "_"): column for column in frame.columns}
    for name in names:
        found = normalized.get(_norm(name).replace(" ", "_"))
        if found is not None:
            return found
    return None


def build_indicators(establishments: pd.DataFrame) -> pd.DataFrame:
    local = establishments.copy()
    municipality = _column(local, "CO_MUNICIPIO_GESTOR", "CO_MUNICIPIO", "CODUFMUN", "IBGE", "codigo_municipio")
    municipality_name = _column(local, "NO_MUNICIPIO", "MUNICIPIO", "nome_municipio")
    cnes = _column(local, "CO_CNES", "CNES", "codigo_cnes")
    type_name = _column(local, "DS_TIPO_UNIDADE", "descricao_tipo_unidade", "tipo_unidade")
    active = _column(local, "ST_ATIVO", "STATUS", "situacao_estabelecimento")
    if municipality is None:
        raise RuntimeError(f"CNES XML has no municipality code field: {list(local.columns)}")
    if active is not None:
        values = local[active].astype(str).str.upper().str.strip()
        local = local.loc[values.isin(["1", "1.0", "S", "SIM", "ATIVO"])]
    local["municipality_code"] = local[municipality].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    local["_type"] = local[type_name].map(_norm) if type_name else ""
    local["_is_ubs"] = local["_type"].str.contains("posto de saude|centro de saude|unidade basica|saude da familia", regex=True)
    local["_is_hospital"] = local["_type"].str.contains("hospital", regex=False)
    local["_is_caps"] = local["_type"].str.contains("atencao psicossocial|caps", regex=True)
    local["_is_emergency"] = local["_type"].str.contains("pronto atendimento|pronto socorro|upa", regex=True)
    keys = ["municipality_code"]
    if municipality_name:
        local["municipality"] = local[municipality_name].astype(str)
        keys.append("municipality")
    result = local.groupby(keys, dropna=False).agg(
        cnes_active_establishments=(cnes or municipality, "nunique"),
        cnes_ubs=("_is_ubs", "sum"),
        cnes_hospitals=("_is_hospital", "sum"),
        cnes_caps=("_is_caps", "sum"),
        cnes_emergency_units=("_is_emergency", "sum"),
    ).reset_index()
    result["cnes_obstetric_centers"] = 0
    for column in [name for name in result.columns if name.startswith("cnes_")]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["cnes_health_service_deficit"] = (
        result["cnes_ubs"].eq(0).astype(int)
        + result["cnes_hospitals"].eq(0).astype(int)
        + result["cnes_caps"].eq(0).astype(int)
        + result["cnes_emergency_units"].eq(0).astype(int)
    )
    return result.sort_values("municipality_code")


def collect_cnes_pa(output_directory: str | Path = "data/processed") -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "cnes_establishments_pa.csv"
    types_path = output / "cnes_unit_types.csv"
    indicators_path = output / "cnes_municipal_indicators_pa.csv"
    metadata_path = output / "cnes_municipal_indicators_pa.metadata.json"
    snapshot_reused = raw_path.exists() and raw_path.stat().st_size > 0
    if snapshot_reused:
        establishments = pd.read_csv(raw_path, low_memory=False)
    else:
        archive = download_cnes_xml(output / "cnes_bulk" / "cnes_estabelecimentos_xml.zip")
        establishments = extract_para_xml(archive, raw_path)
    indicators = build_indicators(establishments)
    indicators.to_csv(indicators_path, index=False, encoding="utf-8")
    if not types_path.exists():
        pd.DataFrame(columns=["codigo_tipo_unidade", "descricao_tipo_unidade"]).to_csv(types_path, index=False)
    metadata_path.write_text(json.dumps({
        "source": "OpenDataSUS CNES official daily XML snapshot",
        "source_url": CNES_XML_URL,
        "establishments": int(len(establishments)),
        "municipal_rows": int(len(indicators)),
        "snapshot_reused": snapshot_reused,
        "limitations": ["Professional indicators require a separate CNES human-resources extraction.", "Obstetric-center count remains unavailable in this extraction."],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "cnes_establishments": raw_path,
        "cnes_unit_types": types_path,
        "cnes_indicators": indicators_path,
        "cnes_metadata": metadata_path,
    }
