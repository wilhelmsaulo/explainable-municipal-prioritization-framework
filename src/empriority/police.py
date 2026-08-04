from __future__ import annotations

import re
import unicodedata
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
    "município": "municipality",
    "ano": "year",
    "mes": "month",
    "mês": "month",
    "tipo_de_ocorrencia": "occurrence_type",
    "tipo_ocorrencia": "occurrence_type",
    "ocorrencia": "occurrence_type",
    "quantidade": "records",
    "qtd": "records",
    "registros": "records",
    "codigo_ibge": "municipality_code",
    "cod_ibge": "municipality_code",
}


def _normalize_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()


def load_police_file(path: str | Path) -> pd.DataFrame:
    """Load and normalize a public police CSV or Excel file without changing source values."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Police data file not found: {source}")

    suffix = source.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(source)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(source)
    else:
        raise ValueError("Police data must be CSV, XLSX or XLS.")

    normalized_columns = {}
    for column in frame.columns:
        normalized = _normalize_name(str(column))
        normalized_columns[column] = ALIASES.get(normalized, normalized)
    frame = frame.rename(columns=normalized_columns)

    missing = REQUIRED_POLICE_FIELDS.difference(frame.columns)
    if missing:
        raise ValueError(f"Police data missing required fields: {', '.join(sorted(missing))}")

    frame["year"] = pd.to_numeric(frame["year"], errors="raise").astype("int64")
    frame["records"] = pd.to_numeric(frame["records"], errors="raise")
    frame["municipality"] = frame["municipality"].astype(str).str.strip()
    frame["occurrence_type"] = frame["occurrence_type"].astype(str).str.strip()
    if "municipality_code" in frame:
        frame["municipality_code"] = (
            frame["municipality_code"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )
    return frame
