from __future__ import annotations

import json
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Iterator

import httpx
import pandas as pd
import yaml

SOURCES_PATH = Path("config/sources.yml")


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


def _month_shift(reference: date, months: int) -> str:
    index = reference.year * 12 + reference.month - 1 - months
    year, month_zero = divmod(index, 12)
    return f"{year:04d}{month_zero + 1:02d}"


def _source_config(path: str | Path = SOURCES_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    try:
        return payload["sources"]["cnes"]
    except KeyError as exc:
        raise RuntimeError("CNES source is missing from config/sources.yml.") from exc


def download_latest_cnes_archive(
    destination_directory: str | Path,
    *,
    sources_path: str | Path = SOURCES_PATH,
    timeout: float = 300.0,
) -> tuple[Path, str, str]:
    """Download the newest available monthly CNES full database from DATASUS."""
    config = _source_config(sources_path)
    template = str(config["url_template"])
    lag = int(config.get("competence_lag_months", 2))
    fallback = int(config.get("fallback_months", 8))
    destination = Path(destination_directory)
    destination.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for extra in range(fallback):
            competence = _month_shift(date.today(), lag + extra)
            url = template.format(competence=competence)
            target = destination / f"BASE_DE_DADOS_CNES_{competence}.ZIP"
            print(f"Trying CNES competence {competence}: {url}", flush=True)
            try:
                with client.stream("GET", url) as response:
                    if response.status_code == 404:
                        errors.append(f"{competence}: 404")
                        continue
                    response.raise_for_status()
                    with target.open("wb") as handle:
                        downloaded = 0
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            handle.write(chunk)
                            downloaded += len(chunk)
                            if downloaded and downloaded % (25 * 1024 * 1024) < 1024 * 1024:
                                print(
                                    f"CNES {competence}: {downloaded / 1_048_576:.1f} MB",
                                    flush=True,
                                )
                if target.stat().st_size == 0 or not zipfile.is_zipfile(target):
                    errors.append(f"{competence}: invalid or empty ZIP")
                    target.unlink(missing_ok=True)
                    continue
                print(f"Selected CNES competence {competence}.", flush=True)
                return target, competence, url
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{competence}: {exc}")
                target.unlink(missing_ok=True)

    raise RuntimeError("No recent CNES archive could be downloaded. " + " | ".join(errors))


def _establishment_member(archive: zipfile.ZipFile) -> str:
    csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    preferred = [
        name
        for name in csv_members
        if "estabelecimento" in _norm(Path(name).name)
        and "complementar" not in _norm(Path(name).name)
    ]
    if preferred:
        return sorted(preferred, key=len)[0]
    if csv_members:
        return csv_members[0]
    raise RuntimeError("CNES archive contains no CSV file.")


def _csv_options(archive_path: Path, member: str) -> tuple[str, str]:
    errors: list[str] = []
    for encoding in ("latin1", "utf-8", "utf-8-sig"):
        for separator in (";", ","):
            try:
                with zipfile.ZipFile(archive_path) as archive, archive.open(member) as handle:
                    sample = pd.read_csv(handle, encoding=encoding, sep=separator, nrows=5)
                if len(sample.columns) > 3:
                    return encoding, separator
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{encoding}/{separator}: {exc}")
    raise RuntimeError("Unable to detect CNES CSV format. " + " | ".join(errors[-4:]))


def _chunks_from_archive(
    archive_path: Path,
    member: str,
    encoding: str,
    separator: str,
) -> Iterator[pd.DataFrame]:
    with zipfile.ZipFile(archive_path) as archive, archive.open(member) as handle:
        yield from pd.read_csv(
            handle,
            encoding=encoding,
            sep=separator,
            chunksize=100_000,
            low_memory=False,
        )


def extract_para_establishments(
    archive_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """Extract the establishment table and retain only Pará records."""
    source = Path(archive_path)
    target = Path(output_path)
    with zipfile.ZipFile(source) as archive:
        member = _establishment_member(archive)
    encoding, separator = _csv_options(source, member)
    print(
        f"CNES table={member} encoding={encoding} separator={separator!r}",
        flush=True,
    )

    selected: list[pd.DataFrame] = []
    scanned = 0
    for chunk in _chunks_from_archive(source, member, encoding, separator):
        scanned += len(chunk)
        municipality = _column(
            chunk,
            "CO_MUNICIPIO_GESTOR",
            "CO_MUNICIPIO",
            "CODUFMUN",
            "IBGE",
            "codigo_municipio",
            "codigo_ibge",
        )
        state = _column(chunk, "CO_ESTADO_GESTOR", "CO_UF", "UF", "codigo_uf")
        if municipality is not None:
            codes = chunk[municipality].astype(str).str.replace(r"\.0$", "", regex=True)
            mask = codes.str.zfill(6).str.startswith("15")
        elif state is not None:
            states = chunk[state].astype(str).str.replace(r"\.0$", "", regex=True).str.upper()
            mask = states.isin(["15", "PA", "PARA", "PARÁ"])
        else:
            raise RuntimeError(
                "CNES establishment table has no municipality or state column: "
                f"{list(chunk.columns)}"
            )
        if mask.any():
            selected.append(chunk.loc[mask].copy())
        print(
            f"CNES filter scanned={scanned} pa={sum(len(item) for item in selected)}",
            flush=True,
        )

    if not selected:
        raise RuntimeError("No Pará establishments were identified in the CNES archive.")
    frame = pd.concat(selected, ignore_index=True).drop_duplicates()
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, encoding="utf-8")
    return frame


def fetch_cnes_unit_types(timeout: float = 60.0) -> pd.DataFrame:
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
    if establishments.empty:
        raise ValueError("CNES returned no establishments.")

    local = establishments.copy()
    municipal_code = _column(
        local,
        "CO_MUNICIPIO_GESTOR",
        "CO_MUNICIPIO",
        "CODUFMUN",
        "IBGE",
        "codigo_municipio",
        "codigo_ibge",
    )
    municipal_name = _column(local, "NO_MUNICIPIO", "MUNICIPIO", "nome_municipio")
    type_code = _column(local, "TP_UNIDADE", "CO_TIPO_UNIDADE", "codigo_tipo_unidade")
    type_name = _column(local, "DS_TIPO_UNIDADE", "descricao_tipo_unidade", "tipo_unidade")
    cnes_code = _column(local, "CO_CNES", "CNES", "codigo_cnes")
    active = _column(local, "ST_ATIVO", "STATUS", "situacao_estabelecimento")

    if municipal_code is None:
        raise ValueError(f"CNES has no municipality code column: {list(local.columns)}")
    if active is not None:
        active_values = local[active].astype(str).str.upper().str.strip()
        local = local.loc[active_values.isin(["1", "1.0", "S", "SIM", "ATIVO"])]

    if type_name is None and type_code is not None and unit_types is not None and not unit_types.empty:
        types = unit_types.copy()
        types_code = _column(types, "codigo_tipo_unidade", "codigo")
        types_name = _column(types, "descricao_tipo_unidade", "descricao", "nome")
        if types_code and types_name:
            local[type_code] = local[type_code].astype(str).str.replace(r"\.0$", "", regex=True)
            types[types_code] = types[types_code].astype(str).str.replace(r"\.0$", "", regex=True)
            local = local.merge(
                types[[types_code, types_name]].rename(
                    columns={types_code: type_code, types_name: "_type_name"}
                ),
                on=type_code,
                how="left",
            )
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
    ).reset_index()
    result["cnes_obstetric_centers"] = 0
    numeric = [column for column in result.columns if column.startswith("cnes_")]
    result[numeric] = result[numeric].astype(int)
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

    competence: str | None = None
    source_url: str | None = None
    snapshot_reused = raw_path.exists() and raw_path.stat().st_size > 0
    if snapshot_reused:
        print("Using existing Pará CNES snapshot.", flush=True)
        establishments = pd.read_csv(raw_path, low_memory=False)
    else:
        archive, competence, source_url = download_latest_cnes_archive(output / "cnes_bulk")
        establishments = extract_para_establishments(archive, raw_path)

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
                "source_manifest": str(SOURCES_PATH),
                "competence": competence,
                "source_url": source_url,
                "state_code": 15,
                "establishments": int(len(establishments)),
                "municipal_rows": int(len(indicators)),
                "snapshot_reused": snapshot_reused,
                "limitations": [
                    "Establishment indicators are derived from the monthly CNES database.",
                    "Professional indicators require the CNES professional table.",
                    "Obstetric-center count remains unavailable in this extraction and is set to zero pending the installations table.",
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
