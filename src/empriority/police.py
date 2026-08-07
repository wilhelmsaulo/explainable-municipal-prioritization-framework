from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

REQUIRED_POLICE_FIELDS = {
    "municipality",
    "year",
    "occurrence_type",
    "records",
}

ALIASES = {
    "municipio": "municipality",
    "municipios": "municipality",
    "ano": "year",
    "ano_do_fato": "year",
    "mes": "month",
    "mes_do_fato": "month",
    "tipo_de_ocorrencia": "occurrence_type",
    "tipo_ocorrencia": "occurrence_type",
    "ocorrencia": "occurrence_type",
    "consolidados": "crime",
    "especificacao_crime": "crime_specification",
    "sexo_vitima": "victim_sex",
    "quantidade": "records",
    "qtd": "records",
    "registros": "records",
    "codigo_ibge": "municipality_code",
    "cod_ibge": "municipality_code",
}

MUNICIPALITY_ALIASES = {
    "ALTAMIRA/CASTELO DOS SONHOS": "ALTAMIRA",
}

OUTPUT_COLUMNS = [
    "municipality",
    "year",
    "all_female_records",
    "violencia_domestica_lesao",
    "lesao_corporal",
    "violencia_sexual",
    "estupro",
    "estupro_vulneravel",
    "homicidio_mulher",
    "feminicidio",
    "tentativa_feminicidio",
]


def _normalize_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()


def _normalize_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
        .str.upper()
        .str.strip()
    )


def _normalize_municipality(series: pd.Series) -> pd.Series:
    return _normalize_text(series).replace(MUNICIPALITY_ALIASES)


def _read_table(source: Path) -> pd.DataFrame:
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(source)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(source)
    raise ValueError("Police data must be CSV, XLSX or XLS.")


def _rename_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for column in frame.columns:
        normalized = _normalize_name(str(column))
        renamed[column] = ALIASES.get(normalized, normalized)
    return frame.rename(columns=renamed)


def _aggregate_raw_microdata(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"municipality", "year", "crime", "crime_specification", "victim_sex"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Raw police data missing fields: {', '.join(sorted(missing))}")

    local = frame.copy()
    local["municipality"] = _normalize_municipality(local["municipality"])
    local["crime"] = _normalize_text(local["crime"])
    local["crime_specification"] = _normalize_text(local["crime_specification"])
    local["victim_sex"] = _normalize_text(local["victim_sex"])
    local["year"] = pd.to_numeric(local["year"], errors="raise").astype("int64")
    local = local.loc[local["victim_sex"].eq("F")].copy()

    crime = local["crime"]
    specification = local["crime_specification"]
    local["all_female_records"] = 1
    local["lesao_corporal"] = crime.eq("LESAO CORPORAL").astype(int)
    local["violencia_domestica_lesao"] = (
        crime.eq("LESAO CORPORAL") & specification.str.contains("VIOLENCIA DOMESTICA", regex=False)
    ).astype(int)
    local["estupro"] = crime.eq("ESTUPRO").astype(int)
    local["estupro_vulneravel"] = crime.eq("ESTUPRO DE VULNERAVEL").astype(int)
    local["violencia_sexual"] = crime.isin(["ESTUPRO", "ESTUPRO DE VULNERAVEL"]).astype(int)
    local["homicidio_mulher"] = crime.eq("HOMICIDIO").astype(int)
    local["feminicidio"] = (
        crime.eq("HOMICIDIO")
        & specification.str.contains("FEMINICIDIO", regex=False)
        & ~specification.str.contains("TENTATIVA", regex=False)
    ).astype(int)
    local["tentativa_feminicidio"] = specification.str.contains(
        "TENTATIVA DE FEMINICIDIO", regex=False
    ).astype(int)

    return (
        local.groupby(["municipality", "year"], as_index=False)[OUTPUT_COLUMNS[2:]]
        .sum()
        .sort_values(["year", "municipality"])
        .reset_index(drop=True)
    )


def load_police_file(path: str | Path) -> pd.DataFrame:
    """Load an aggregated police file or aggregate one raw annual microdata file."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Police data file not found: {source}")

    frame = _rename_columns(_read_table(source))
    if {"crime", "crime_specification", "victim_sex"}.issubset(frame.columns):
        return _aggregate_raw_microdata(frame)

    missing = REQUIRED_POLICE_FIELDS.difference(frame.columns)
    if missing:
        raise ValueError(f"Police data missing required fields: {', '.join(sorted(missing))}")

    frame["year"] = pd.to_numeric(frame["year"], errors="raise").astype("int64")
    frame["records"] = pd.to_numeric(frame["records"], errors="raise")
    frame["municipality"] = _normalize_municipality(frame["municipality"])
    frame["occurrence_type"] = frame["occurrence_type"].astype(str).str.strip()
    if "municipality_code" in frame:
        frame["municipality_code"] = (
            frame["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
        )
    return frame


def load_police_files(paths: Iterable[str | Path]) -> pd.DataFrame:
    """Aggregate multiple annual police files into one municipal-year table."""
    frames = [load_police_file(path) for path in paths]
    if not frames:
        raise ValueError("At least one police file is required.")

    combined = pd.concat(frames, ignore_index=True)
    if set(OUTPUT_COLUMNS).issubset(combined.columns):
        return (
            combined.groupby(["municipality", "year"], as_index=False)[OUTPUT_COLUMNS[2:]]
            .sum()
            .sort_values(["year", "municipality"])
            .reset_index(drop=True)
        )
    return combined
