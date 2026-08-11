from __future__ import annotations

import io
import json
import re
from pathlib import Path

import httpx
import pandas as pd
from lxml import etree, html

RMA_URL = "https://aplicacoes.mds.gov.br/sagi/atendimento/adm/lista_preenchimento_mu.php?p_uf=PA"


def _read_valid_tables(url: str, timeout: float = 120.0) -> list[pd.DataFrame]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
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
            parsed = pd.read_html(io.StringIO(fragment), flavor="lxml", header=None)
        except (ValueError, IndexError):
            rejected += 1
            continue
        for frame in parsed:
            if not frame.empty and len(frame.columns) >= 3:
                frames.append(frame)

    print(f"RMA HTML tables parsed: valid={len(frames)}, rejected={rejected}", flush=True)
    if not frames:
        raise RuntimeError("No valid tabular data found in the official RMA page")
    return frames


def _table_text(table: pd.DataFrame) -> str:
    return " ".join(table.fillna("").astype(str).values.flatten()).upper()


def _find_table(tables: list[pd.DataFrame], keyword: str) -> pd.DataFrame:
    normalized_keyword = re.sub(r"\s+", "", keyword.upper())
    for table in tables:
        normalized_text = re.sub(r"\s+", "", _table_text(table))
        if normalized_keyword in normalized_text and "IBGE" in normalized_text:
            return table
    previews = [_table_text(table)[:180] for table in tables]
    raise RuntimeError(
        f"Unable to locate {keyword} table in RMA page. Available table previews: {previews}"
    )


def _normalize_table(table: pd.DataFrame, indicator: str) -> pd.DataFrame:
    rows: list[tuple[str, int]] = []
    for _, row in table.iterrows():
        values = [str(value).strip() for value in row.tolist()]
        if len(values) < 3:
            continue
        code_match = re.search(r"\b(15\d{4})\b", values[0])
        if not code_match:
            continue
        quantity_match = re.search(r"-?\d+", values[2].replace(".", ""))
        if not quantity_match:
            continue
        rows.append((code_match.group(1), int(quantity_match.group(0))))

    if not rows:
        raise RuntimeError(f"No municipal rows parsed for {indicator}")

    result = pd.DataFrame(rows, columns=["municipality_code", indicator])
    result = result.drop_duplicates("municipality_code", keep="last")
    print(
        f"RMA parsed {indicator}: municipalities={len(result)}, total={int(result[indicator].sum())}",
        flush=True,
    )
    return result


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
