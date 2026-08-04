from __future__ import annotations

import json
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

CKAN_PACKAGE_URL = (
    "https://ckan-dadosabertos.saude.gov.br/api/3/action/package_show"
)
DATASET_ID = "cnes-cadastro-nacional-de-estabelecimentos-de-saude"


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


def discover_cnes_csv_resource(timeout: float = 60.0) -> dict[str, Any]:
    """Discover the newest official CNES establishments CSV in OpenDataSUS."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(CKAN_PACKAGE_URL, params={"id": DATASET_ID})
        response.raise_for_status()
        payload = response.json()

    if not payload.get("success"):
        raise RuntimeError("OpenDataSUS CKAN did not return a successful package response.")

    resources = payload.get("result", {}).get("resources", [])
    candidates = []
    for resource in resources:
        fmt = str(resource.get("format", "")).upper()
        name = _norm(resource.get("name", ""))
        url = str(resource.get("url", ""))
        if fmt == "CSV" and "estabelecimento" in name and url:
            candidates.append(resource)

    if not candidates:
        raise RuntimeError("No official CNES establishments CSV resource was found in OpenDataSUS.")

    candidates.sort(
        key=lambda item: str(
            item.get("last_modified")
            or item.get("metadata_modified")
            or item.get("created")
            or ""
        ),
        reverse=True,
    )
    selected = candidates[0]
    print(
        "CNES resource selected: "
        f"{selected.get('name')} | {selected.get('last_modified') or selected.get('created')}",
        flush=True,
    )
    return selected


def download_cnes_resource(
    destination: str | Path,
    *,
    timeout: float = 300.0,
) -> tuple[Path, dict[str, Any]]:
    """Download the current official CNES bulk CSV exactly once."""
    resource = discover_cnes_csv_resource()
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream(
        "GET",
        resource["url"],
        timeout=timeout,
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", "0") or 0)
        downloaded = 0
        with destination_path.open("wb") as file_handle:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                file_handle.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(
                        f"CNES download: {downloaded / 1_048_576:.1f} MB / "
                        f"{total / 1_048_576:.1f} MB",
                        flush=True,
                    )

    if destination_path.stat().st_size == 0:
        raise RuntimeError("Downloaded CNES resource is empty.")
    return destination_path, resource


def _read_csv_robust(path: Path, **kwargs: Any) -> pd.DataFrame | Any:
    errors: list[str] = []
    for encoding in ("utf-8", "utf-8-sig", "latin1"):
        for separator in (";", ","):
            try:
                return pd.read_csv(
                    path,
                    encoding=encoding,
                    sep=separator,
                    low_memory=False,
                    **kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{encoding}/{separator}: {exc}")
    raise RuntimeError("Unable to read CNES CSV. " + " | ".join(errors[-4:]))


def extract_para_establishments(
    downloaded_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """Filter the national bulk resource to Pará and create the reusable state snapshot."""
    source = Path(downloaded_path)
    target = Path(output_path)

    if zipfile.is_zipfile(source):
        extract_directory = source.parent / "cnes_bulk_extracted"
        extract_directory.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as archive:
            csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not csv_members:
                raise RuntimeError("CNES ZIP contains no CSV file.")
            archive.extract(csv_members[0], extract_directory)
            source = extract_directory / csv_members[0]

    sample = _read_csv_robust(source, nrows=10)
    uf_column = _column(sample, "UF", "sigla_uf", "estado", "codigo_uf")
    municipality_code = _column(
        sample,
        "IBGE",
        "codigo_municipio",
        "codigo_ibge",
        "municipio_codigo",
    )
    if uf_column is None and municipality_code is None:
        raise RuntimeError(f"CNES bulk file has no UF or municipality code column: {list(sample.columns)}")

    chunks: list[pd.DataFrame] = []
    for encoding in ("utf-8", "utf-8-sig", "latin1"):
        for separator in (";", ","):
            try:
                iterator = pd.read_csv(
                    source,
                    encoding=encoding,
                    sep=separator,
                    chunksize=100_000,
                    low_memory=False,
                )
                chunks.clear()
                total_seen = 0
                for chunk in iterator:
                    total_seen += len(chunk)
                    if uf_column in chunk.columns:
                        uf_values = chunk[uf_column].astype(str).str.strip().str.upper()
                        mask = uf_values.isin(["PA", "15", "15.0", "PARA", "PARÁ"])
                    else:
                        codes = (
                            chunk[municipality_code]
                            .astype(str)
                            .str.replace(r"\.0$", "", regex=True)
                            .str.zfill(6)
                        )
                        mask = codes.str.startswith("15")
                    if mask.any():
                        chunks.append(chunk.loc[mask].copy())
                    print(
                        f"CNES bulk filter: scanned={total_seen} pa={sum(len(item) for item in chunks)}",
                        flush=True,
                    )
                if chunks:
                    frame = pd.concat(chunks, ignore_index=True).drop_duplicates()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    frame.to_csv(target, index=False, encoding="utf-8")
                    return frame
            except Exception:  # noqa: BLE001
                continue

    raise RuntimeError("CNES bulk file was read, but no Pará establishments were identified.")


def fetch_cnes_unit_types(timeout: float = 60.0) -> pd.DataFrame:
    """Get the official CNES unit-type dictionary from the DEMAS API."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(
            "https://apidadosabertos.saude.gov.br/cnes/tipounidades",
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()

    if isinstance(payload, list):
        records = payload
    else:
        records = next(
            (
                payload[key]
                for key in ("data", "items", "results", "resultados")
                if isinstance(payload.get(key), list)
            ),
            [],
        )
    return pd.json_normalize(records)


def build_cnes_municipal_indicators(
    establishments: pd.DataFrame,
    unit_types: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Aggregate CNES establishments into one row per municipality."""
    if establishments.empty:
        raise ValueError("CNES returned no establishments.")

    local = establishments.copy()
    municipal_code = _column(local, "IBGE", "codigo_municipio", "codigo_ibge", "municipio_codigo")
    municipal_name = _column(local, "MUNICIPIO", "nome_municipio", "municipio_nome")
    type_code = _column(local, "codigo_tipo_unidade", "tipo_unidade_codigo", "TIPO UNIDADE")
    type_name = _column(
        local,
        "descricao_tipo_unidade",
        "tipo_unidade",
        "tipo_unidade_descricao",
        "DESCRICAO TIPO UNIDADE",
    )
    cnes_code = _column(local, "CNES", "codigo_cnes")
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
    bulk_path = output / "cnes_establishments_national_download"

    resource: dict[str, Any] | None = None
    snapshot_reused = raw_path.exists() and raw_path.stat().st_size > 0
    if snapshot_reused:
        print("Using existing Pará CNES snapshot.", flush=True)
        establishments = pd.read_csv(raw_path, low_memory=False)
    else:
        downloaded, resource = download_cnes_resource(bulk_path)
        establishments = extract_para_establishments(downloaded, raw_path)

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
                "source": "OpenDataSUS / CNES bulk CSV",
                "dataset": DATASET_ID,
                "resource_url": resource.get("url") if resource else None,
                "resource_last_modified": (
                    resource.get("last_modified") if resource else None
                ),
                "state_code": 15,
                "establishments": int(len(establishments)),
                "municipal_rows": int(len(indicators)),
                "snapshot_reused": snapshot_reused,
                "limitations": [
                    "Bulk establishments data support facility indicators.",
                    "Professional occupation indicators require the CNES professionals extraction.",
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
