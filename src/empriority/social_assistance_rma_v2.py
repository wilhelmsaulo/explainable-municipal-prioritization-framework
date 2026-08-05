from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pandas as pd
from lxml import etree, html

RMA_URL = "https://aplicacoes.mds.gov.br/sagi/atendimento/adm/lista_preenchimento_mu.php?p_uf=PA"


def _tables() -> list[pd.DataFrame]:
    response = httpx.get(
        RMA_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=120,
        follow_redirects=True,
    )
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
        frames.extend(frame for frame in parsed if not frame.empty and frame.shape[1] > 0)
    print(f"RMA HTML tables parsed: valid={len(frames)}, rejected={rejected}", flush=True)
    return frames


def _mask(series: pd.Series) -> pd.Series:
    codes = (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.extract(r"(\d{6,7})", expand=False)
    )
    return codes.str.startswith("15", na=False)


def _municipal_tables(frames: list[pd.DataFrame]) -> list[pd.DataFrame]:
    result: list[pd.DataFrame] = []
    for index, frame in enumerate(frames):
        if frame.shape[1] < 3:
            continue
        count = int(_mask(frame.iloc[:, 0]).sum())
        if count:
            print(f"RMA municipal table {index}: rows={count}, columns={frame.shape[1]}", flush=True)
            result.append(frame)
    if len(result) < 3:
        raise RuntimeError(f"Expected three municipal tables; found {len(result)}")
    return result[:3]


def _series(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    local = frame.loc[_mask(frame.iloc[:, 0])].copy()
    result = pd.DataFrame(
        {
            "municipality_code": (
                local.iloc[:, 0]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.extract(r"(\d{6,7})", expand=False)
                .str[:6]
            ),
            name: pd.to_numeric(local.iloc[:, 2], errors="coerce"),
        }
    ).dropna()
    result[name] = result[name].round().astype(int)
    result = result.groupby("municipality_code", as_index=False)[name].max()
    print(f"RMA {name}: municipalities={len(result)}, total={int(result[name].sum())}", flush=True)
    return result


def collect_social_assistance_rma_pa(output_directory: str | Path = "data/processed") -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    cras_t, creas_t, pop_t = _municipal_tables(_tables())
    result = _series(cras_t, "social_cras")
    result = result.merge(_series(creas_t, "social_creas"), on="municipality_code", how="outer")
    result = result.merge(_series(pop_t, "social_centro_pop"), on="municipality_code", how="outer")
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
    csv_path = output / "social_assistance_indicators_pa.csv"
    metadata_path = output / "social_assistance_indicators_pa.metadata.json"
    result.to_csv(csv_path, index=False, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "source": "MDS/SNAS RMA",
                "source_url": RMA_URL,
                "state": "Pará",
                "municipal_rows": int(len(result)),
                "table_assignment": "First three municipal tables in page order: CRAS, CREAS, Centro POP",
                "unavailable_values_stored_as_missing": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"social_indicators": csv_path, "social_metadata": metadata_path}
