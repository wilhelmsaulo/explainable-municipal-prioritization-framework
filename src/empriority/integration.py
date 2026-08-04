from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

_CODE_CANDIDATES = (
    "municipality_code",
    "municipio_codigo",
    "codigo_municipio",
    "codigo_ibge",
    "d1c",
)
_NAME_CANDIDATES = (
    "municipality",
    "municipio",
    "municipio_nome",
    "nome_municipio",
    "d1n",
)
_VALUE_CANDIDATES = ("value", "valor", "v", "records")
_VARIABLE_CANDIDATES = ("variable", "variavel", "d2n")


def _slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    normalized = {_slug(column): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _clean_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def aggregate_police(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate normalized police records into municipal analytical criteria."""
    required = {"municipality", "year", "occurrence_type", "records"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Police frame missing: {', '.join(sorted(missing))}")

    local = frame.copy()
    local["criterion"] = "police_" + local["occurrence_type"].map(_slug)
    keys = ["municipality"]
    if "municipality_code" in local.columns:
        local["municipality_code"] = _clean_code(local["municipality_code"])
        keys.insert(0, "municipality_code")

    totals = local.pivot_table(
        index=keys,
        columns="criterion",
        values="records",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    totals.columns.name = None

    years = local.groupby(keys)["year"].nunique().rename("police_years_observed").reset_index()
    persistence = (
        local.assign(has_record=local["records"].gt(0).astype(int))
        .groupby(keys)["has_record"]
        .sum()
        .rename("police_positive_rows")
        .reset_index()
    )
    return totals.merge(years, on=keys, how="left").merge(persistence, on=keys, how="left")


def reshape_indicator(frame: pd.DataFrame, indicator_name: str) -> pd.DataFrame:
    """Convert common SIDRA long outputs or municipal wide outputs to one row per municipality."""
    code_col = _first_existing(frame.columns, _CODE_CANDIDATES)
    name_col = _first_existing(frame.columns, _NAME_CANDIDATES)
    if code_col is None and name_col is None:
        raise ValueError(f"Indicator '{indicator_name}' has no municipal identifier column.")

    local = frame.copy()
    id_columns: list[str] = []
    rename: dict[str, str] = {}
    if code_col is not None:
        local[code_col] = _clean_code(local[code_col])
        id_columns.append(code_col)
        rename[code_col] = "municipality_code"
    if name_col is not None:
        id_columns.append(name_col)
        rename[name_col] = "municipality"

    value_col = _first_existing(local.columns, _VALUE_CANDIDATES)
    variable_col = _first_existing(local.columns, _VARIABLE_CANDIDATES)
    if value_col is not None and variable_col is not None:
        local["_criterion"] = indicator_name + "__" + local[variable_col].map(_slug)
        wide = local.pivot_table(
            index=id_columns,
            columns="_criterion",
            values=value_col,
            aggfunc="first",
        ).reset_index()
        wide.columns.name = None
        return wide.rename(columns=rename)

    excluded = set(id_columns)
    numeric_columns = []
    for column in local.columns:
        if column in excluded:
            continue
        converted = pd.to_numeric(local[column], errors="coerce")
        if converted.notna().any():
            local[column] = converted
            numeric_columns.append(column)

    if not numeric_columns:
        raise ValueError(f"Indicator '{indicator_name}' has no usable numeric values.")
    selected = local[id_columns + numeric_columns].drop_duplicates(subset=id_columns)
    selected = selected.rename(columns=rename)
    selected = selected.rename(
        columns={column: f"{indicator_name}__{_slug(column)}" for column in numeric_columns}
    )
    return selected


def build_integrated_matrix(
    municipalities_path: str | Path,
    indicator_paths: dict[str, str | Path],
    *,
    police_path: str | Path | None = None,
    output_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
) -> Path:
    """Merge municipal reference, declared indicators and optional police criteria."""
    base = pd.read_csv(municipalities_path, dtype=str)
    code_col = _first_existing(base.columns, _CODE_CANDIDATES)
    name_col = _first_existing(base.columns, _NAME_CANDIDATES)
    if code_col is None or name_col is None:
        raise ValueError("Municipality reference requires code and name columns.")
    base = base.rename(columns={code_col: "municipality_code", name_col: "municipality"})
    base["municipality_code"] = _clean_code(base["municipality_code"])
    matrix = base.drop_duplicates("municipality_code")

    for name, path in indicator_paths.items():
        indicator = pd.read_csv(path, dtype=str)
        reshaped = reshape_indicator(indicator, name)
        if "municipality_code" in reshaped.columns:
            matrix = matrix.merge(reshaped, on="municipality_code", how="left", suffixes=("", "_new"))
            if "municipality_new" in matrix.columns:
                matrix = matrix.drop(columns="municipality_new")
        else:
            matrix = matrix.merge(reshaped, on="municipality", how="left")

    if police_path is not None:
        police = pd.read_csv(police_path)
        aggregated = aggregate_police(police)
        join_key = "municipality_code" if "municipality_code" in aggregated.columns else "municipality"
        matrix = matrix.merge(aggregated, on=join_key, how="left", suffixes=("", "_police"))
        if "municipality_police" in matrix.columns:
            matrix = matrix.drop(columns="municipality_police")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(path, index=False, encoding="utf-8")
    return path
