from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

BASE_URL = "https://apidadosabertos.saude.gov.br"


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "resultados", "estabelecimentos"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload and all(not isinstance(value, (dict, list)) for value in payload.values()):
            return [payload]
    return []


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _column(frame: pd.DataFrame, *names: str) -> str | None:
    normalized = {_norm(column).replace(" ", "_"): column for column in frame.columns}
    for name in names:
        found = normalized.get(_norm(name).replace(" ", "_"))
        if found is not None:
            return found
    return None


def fetch_cnes_establishments(
    state_code: int = 15,
    *,
    status: int = 1,
    page_size: int = 500,
    timeout: float = 45.0,
    max_pages: int = 200,
) -> pd.DataFrame:
    """Collect active CNES establishments from the official DEMAS open-data API."""
    if page_size < 1:
        raise ValueError("page_size must be positive.")

    rows: list[dict[str, Any]] = []
    offset = 0
    previous_signature: tuple[str, ...] | None = None

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for page_number in range(1, max_pages + 1):
            response = client.get(
                f"{BASE_URL}/cnes/estabelecimentos",
                params={
                    "codigo_uf": state_code,
                    "status": status,
                    "limit": page_size,
                    "offset": offset,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            page = _records(response.json())
            print(
                f"CNES page={page_number} offset={offset} "
                f"records={len(page)} total={len(rows) + len(page)}",
                flush=True,
            )
            if not page:
                break

            signature = tuple(
                str(item.get("codigo_cnes") or item.get("cnes") or item) for item in page[:5]
            )
            if signature == previous_signature:
                raise RuntimeError(
                    f"CNES API repeated the same page at offset {offset}; pagination stopped."
                )
            previous_signature = signature

            rows.extend(page)
            if len(page) < page_size:
                break

            # The API offset is a record offset, not a page number.
            offset += len(page)
        else:
            raise RuntimeError(
                f"CNES collection exceeded the safety limit of {max_pages} pages."
            )

    frame = pd.json_normalize(rows)
    if frame.empty:
        raise ValueError("CNES returned no establishments for the requested filters.")
    return frame.drop_duplicates().reset_index(drop=True)


def fetch_cnes_unit_types(timeout: float = 45.0) -> pd.DataFrame:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(
            f"{BASE_URL}/cnes/tipounidades",
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return pd.json_normalize(_records(response.json()))


def build_cnes_municipal_indicators(
    establishments: pd.DataFrame,
    unit_types: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Aggregate CNES establishments into one row per municipality."""
    if establishments.empty:
        raise ValueError("CNES returned no establishments.")

    local = establishments.copy()
    municipal_code = _column(local, "codigo_municipio", "codigo_ibge", "municipio_codigo")
    municipal_name = _column(local, "nome_municipio", "municipio", "municipio_nome")
    type_code = _column(local, "codigo_tipo_unidade", "tipo_unidade_codigo")
    type_name = _column(local, "descricao_tipo_unidade", "tipo_unidade", "tipo_unidade_descricao")
    cnes_code = _column(local, "codigo_cnes", "cnes")
    obstetric = _column(
        local,
        "estabelecimento_possui_centro_obstetrico",
        "possui_centro_obstetrico",
    )

    if municipal_code is None:
        raise ValueError(f"CNES response has no municipality code column: {list(local.columns)}")

    if type_name is None and type_code is not None and unit_types is not None and not unit_types.empty:
        types = unit_types.copy()
        types_code = _column(types, "codigo_tipo_unidade", "codigo")
        types_name = _column(types, "descricao_tipo_unidade", "descricao", "nome")
        if types_code and types_name:
            types = types[[types_code, types_name]].rename(
                columns={types_code: type_code, types_name: "_type_name"}
            )
            local = local.merge(types, on=type_code, how="left")
            type_name = "_type_name"

    local["municipality_code"] = (
        local[municipal_code].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    )
    local["_type"] = local[type_name].map(_norm) if type_name else ""
    local["_is_ubs"] = local["_type"].str.contains(
        "posto de saude|centro de saude|unidade basica|saude da familia", regex=True
    )
    local["_is_hospital"] = local["_type"].str.contains("hospital", regex=False)
    local["_is_caps"] = local["_type"].str.contains("atencao psicossocial|caps", regex=True)
    local["_is_emergency"] = local["_type"].str.contains(
        "pronto atendimento|pronto socorro|upa", regex=True
    )
    if obstetric:
        local["_has_obstetric_center"] = pd.to_numeric(local[obstetric], errors="coerce").eq(1)
    else:
        local["_has_obstetric_center"] = False

    keys = ["municipality_code"]
    if municipal_name:
        local["municipality"] = local[municipal_name].astype(str)
        keys.append("municipality")

    grouped = local.groupby(keys, dropna=False)
    result = grouped.agg(
        cnes_active_establishments=(cnes_code or municipal_code, "nunique"),
        cnes_ubs=("_is_ubs", "sum"),
        cnes_hospitals=("_is_hospital", "sum"),
        cnes_caps=("_is_caps", "sum"),
        cnes_emergency_units=("_is_emergency", "sum"),
        cnes_obstetric_centers=("_has_obstetric_center", "sum"),
    ).reset_index()

    numeric = [column for column in result.columns if column.startswith("cnes_")]
    result[numeric] = result[numeric].astype(int)
    result["cnes_health_service_deficit"] = (
        result["cnes_ubs"].eq(0).astype(int)
        + result["cnes_hospitals"].eq(0).astype(int)
        + result["cnes_caps"].eq(0).astype(int)
        + result["cnes_emergency_units"].eq(0).astype(int)
        + result["cnes_obstetric_centers"].eq(0).astype(int)
    )
    return result.sort_values("municipality_code")


def collect_cnes_pa(output_directory: str | Path = "data/processed") -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    raw_path = output / "cnes_establishments_pa.csv"
    types_path = output / "cnes_unit_types.csv"
    indicators_path = output / "cnes_municipal_indicators_pa.csv"
    metadata_path = output / "cnes_municipal_indicators_pa.metadata.json"

    if raw_path.exists() and types_path.exists():
        print("Using existing CNES snapshot.", flush=True)
        establishments = pd.read_csv(raw_path)
        unit_types = pd.read_csv(types_path)
    else:
        establishments = fetch_cnes_establishments(15)
        unit_types = fetch_cnes_unit_types()
        establishments.to_csv(raw_path, index=False, encoding="utf-8")
        unit_types.to_csv(types_path, index=False, encoding="utf-8")

    indicators = build_cnes_municipal_indicators(establishments, unit_types)
    indicators.to_csv(indicators_path, index=False, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "source": "DEMAS Open Data API / CNES",
                "official_endpoint": f"{BASE_URL}/cnes/estabelecimentos",
                "state_code": 15,
                "status": 1,
                "establishments": int(len(establishments)),
                "municipal_rows": int(len(indicators)),
                "snapshot_reused": raw_path.exists() and types_path.exists(),
                "limitations": [
                    "This endpoint covers establishments and unit types.",
                    "Professional occupation indicators require a separate CNES human-resources source.",
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
