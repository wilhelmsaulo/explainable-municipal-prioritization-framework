from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import httpx
import pandas as pd
from lxml import html

TJPA_URL = "https://centralservicos.tjpa.jus.br/bv/todos.php"


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.upper()).strip()


def _municipal_base() -> pd.DataFrame:
    source = pd.read_csv(
        "data/processed/integrated_municipal_matrix.csv",
        dtype={"municipality_code": str},
        usecols=["municipality_code", "municipality"],
    )
    return source.drop_duplicates("municipality_code").copy()


def collect_tjpa_access_pa(output_directory: str | Path = "data/processed") -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    response = httpx.get(
        TJPA_URL,
        headers={"User-Agent": "Mozilla/5.0 Chrome/126 Safari/537.36"},
        timeout=120,
        follow_redirects=True,
    )
    response.raise_for_status()
    document = html.fromstring(response.content)
    text = document.text_content()

    pattern = re.compile(
        r"(?P<unit>[^\n]+?)\s+Cidade\s*:\s*(?P<city>[^|\n]+?)\s*\|\s*Tipo\s*:\s*(?P<type>[^|\n]+)",
        flags=re.IGNORECASE,
    )
    rows = []
    for match in pattern.finditer(text):
        unit = re.sub(r"\s+", " ", match.group("unit")).strip()
        city = re.sub(r"\s+", " ", match.group("city")).strip()
        unit_type = re.sub(r"\s+", " ", match.group("type")).strip()
        if len(unit) > 250 or not city:
            continue
        rows.append({"unit_name": unit, "city": city, "unit_type": unit_type})

    raw = pd.DataFrame(rows).drop_duplicates()
    if raw.empty:
        raise RuntimeError("No TJPA units parsed from official Balcao Virtual directory")

    base = _municipal_base()
    name_to_code = {
        _norm(name): code for code, name in zip(base["municipality_code"], base["municipality"])
    }
    raw["municipality_code"] = raw["city"].map(lambda value: name_to_code.get(_norm(value)))
    raw = raw.dropna(subset=["municipality_code"]).copy()
    if raw.empty:
        raise RuntimeError("TJPA units were parsed but none matched Para municipalities")

    raw["_unit"] = raw["unit_name"].map(_norm)
    raw["_type"] = raw["unit_type"].map(_norm)
    raw["is_criminal"] = (
        raw["_unit"].str.contains("CRIM") | raw["_type"].str.contains("CRIM")
    ).astype(int)
    raw["is_juizado"] = (
        raw["_unit"].str.contains("JUIZADO") | raw["_type"].str.contains("JUIZADO")
    ).astype(int)
    raw["is_ceJusc"] = (
        raw["_unit"].str.contains("CEJUSC") | raw["_type"].str.contains("CEJUSC")
    ).astype(int)
    raw["is_women_specialized"] = (
        raw["_unit"]
        .str.contains(r"MULHER|VIOLENCIA DOMESTICA|MARIA DA PENHA", regex=True)
        .astype(int)
    )

    grouped = raw.groupby("municipality_code", as_index=False).agg(
        justice_tjpa_units=("unit_name", "nunique"),
        justice_tjpa_criminal_units=("is_criminal", "sum"),
        justice_tjpa_juizados=("is_juizado", "sum"),
        justice_tjpa_cejusc=("is_ceJusc", "sum"),
        justice_tjpa_women_specialized_units=("is_women_specialized", "sum"),
    )
    result = base.merge(grouped, on="municipality_code", how="left")
    count_columns = [column for column in result.columns if column.startswith("justice_tjpa_")]
    for column in count_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["justice_tjpa_local_access"] = result["justice_tjpa_units"].gt(0).astype(int)
    result["justice_tjpa_access_deficit"] = result["justice_tjpa_local_access"].eq(0).astype(int)

    indicators = output / "justice_tjpa_indicators_pa.csv"
    raw_path = output / "justice_tjpa_directory_raw_pa.csv"
    metadata = output / "justice_tjpa_indicators_pa.metadata.json"
    result.to_csv(indicators, index=False, encoding="utf-8")
    raw.drop(columns=["_unit", "_type"], errors="ignore").to_csv(
        raw_path, index=False, encoding="utf-8"
    )
    metadata.write_text(
        json.dumps(
            {
                "source": "Tribunal de Justica do Estado do Para - Balcao Virtual",
                "source_url": TJPA_URL,
                "municipal_rows": int(len(result)),
                "matched_units": int(len(raw)),
                "method": "Municipality-level aggregation of official virtual service directory",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"TJPA: units={len(raw)}, municipalities={int(result['justice_tjpa_local_access'].sum())}, "
        f"criminal={int(result['justice_tjpa_criminal_units'].sum())}, "
        f"women_specialized={int(result['justice_tjpa_women_specialized_units'].sum())}",
        flush=True,
    )
    return {"indicators": indicators, "raw": raw_path, "metadata": metadata}
