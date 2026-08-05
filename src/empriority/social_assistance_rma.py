from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pandas as pd
from lxml import etree, html

RMA_URL = "https://aplicacoes.mds.gov.br/sagi/atendimento/adm/lista_preenchimento_mu.php?p_uf=PA"


def _read_valid_tables(url: str, timeout: float = 120.0) -> list[pd.DataFrame]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/126.0 Safari/537.36"
        )
    }
    response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    response.raise_for_status()

    document = html.fromstring(response.content)
    frames: list[pd.DataFrame] = []
    rejected = 0

    for element in document.xpath("//table"):
        fragment = etree.tostring(element, encoding="unicode", method="html")
        try:
            parsed = pd.read_html(io.StringIO(fragment), flavor="lxml")
        except (ValueError, IndexError):
            rejected += 1
            continue
        for frame in parsed:
            if not frame.empty and len(frame.columns) > 0:
                frames.append(frame)

    print(
        f"RMA HTML tables parsed: valid={len(frames)}, rejected={rejected}",
        flush=True,
    )
    if not frames:
        raise RuntimeError("No valid tabular data found in the official RMA page")
    return frames


def _find_table(tables: list[pd.DataFrame], keyword: str) -> pd.DataFrame:
    keyword_upper = keyword.upper()
    for table in tables:
        columns_text = " ".join(map(str, table.columns)).upper()
        values_text = table.astype(str).head(20).to_string().upper()
        text = f"{columns_text} {values_text}"
        if keyword_upper in text and "IBGE" in text:
            return table
    available = [" | ".join(map(str, table.columns)) for table in tables]
    raise RuntimeError(
        f"Unable to locate {keyword} table in RMA page. "
        f"Available table headers: {available}"
    )


def _normalize_table(table: pd.DataFrame, indicator: str) -> pd.DataFrame:
    local = table.copy()
    local.columns = [
        " ".join(map(str, column)) if isinstance(column, tuple) else str(column)
        for column in local.columns
    ]
    ibge_col = next((column for column in local.columns if "IBGE" in column.upper()), None)
    cadsuas_col = next(
        (
            column
            for column in local.columns
            if "CADSUAS" in column.upper() and "QUANTIDADE" in column.upper()
        ),
        None,
    )
    if ibge_col is None or cadsuas_col is None:
        raise RuntimeError(f"Unexpected RMA columns for {indicator}: {list(local.columns)}")

    result = local[[ibge_col, cadsuas_col]].copy()
    result["municipality_code"] = (
        result[ibge_col]
        .astype(str)
        .str.extract(r"(\d{6,7})", expand=False)
        .str[:6]
    )
    result[indicator] = pd.to_numeric(result[cadsuas_col], errors="coerce")
    result = result.dropna(subset=["municipality_code", indicator])
    result = result[result["municipality_code"].str.startswith("15")]
    result[indicator] = result[indicator].round().astype(int)
    return result[["municipality_code", indicator]].drop_duplicates("municipality_code")


def collect_social_assistance_rma_pa(
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    tables = _read_valid_tables(RMA_URL)
    cras = _normalize_table(_find_table(tables, "CRAS CADSUAS"), "social_cras")
    creas = _normalize_table(_find_table(tables, "CREAS CADSUAS"), "social_creas")
    centro_pop = _normalize_table(
        _find_table(tables, "CENTROPOP CADSUAS"),
        "social_centro_pop",
    )

    result = cras.merge(creas, on="municipality_code", how="outer")
    result = result.merge(centro_pop, on="municipality_code", how="outer")
    for column in ["social_cras", "social_creas", "social_centro_pop"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)

    # These services are not exposed by this official RMA table.
    # Keep them as missing values rather than treating unavailable data as observed zeros.
    for column in [
        "social_centro_dia",
        "social_centros_convivencia",
        "social_unidades_acolhimento",
        "social_cras_professionals",
        "social_creas_professionals",
    ]:
        result[column] = pd.NA

    result["social_basic_protection_deficit"] = result["social_cras"].eq(0).astype(int)
    result["social_specialized_service_deficit"] = result["social_creas"].eq(0).astype(int)
    result = result.sort_values("municipality_code")

    indicators_path = output / "social_assistance_indicators_pa.csv"
    metadata_path = output / "social_assistance_indicators_pa.metadata.json"
    result.to_csv(indicators_path, index=False, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "source": "MDS/SNAS Registro Mensal de Atendimentos (RMA)",
                "source_url": RMA_URL,
                "state": "Pará",
                "municipal_rows": int(len(result)),
                "observed_indicators": ["social_cras", "social_creas", "social_centro_pop"],
                "unavailable_in_source": [
                    "social_centro_dia",
                    "social_centros_convivencia",
                    "social_unidades_acolhimento",
                    "social_cras_professionals",
                    "social_creas_professionals",
                ],
                "note": "Unavailable indicators are stored as missing, not zero.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"social_indicators": indicators_path, "social_metadata": metadata_path}
