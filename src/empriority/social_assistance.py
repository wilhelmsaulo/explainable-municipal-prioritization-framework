from __future__ import annotations

import io
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

ENDPOINTS = [
    "https://dados.gov.br/dados/api/3/action/package_show",
    "https://dados.gov.br/api/3/action/package_show",
]
PACKAGES = [
    "cadsuas---sistema-de-cadastro-do-sistema-unico-de-assistencia-social-suas",
    "unidades-de-atendimento-da-assistencia-social",
]
PATTERNS = {
    "cras": ["quantidade de cras", "brasil: cras"],
    "creas": ["quantidade de creas", "brasil: creas"],
    "centro_pop": ["quantidade de centro pop", "brasil: centro pop"],
    "centro_dia": ["quantidade de centro dia", "brasil: centro-dia"],
    "centro_convivencia": ["quantidade de centro de convivencia", "brasil: centro de convivencia"],
    "unidade_acolhimento": ["quantidade de unidade de acolhimento", "brasil: unidades de acolhimento"],
    "profissionais_cras": ["profissionais em cras"],
    "profissionais_creas": ["profissionais em creas"],
}


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower()).strip()


def column(frame: pd.DataFrame, *names: str) -> str | None:
    cols = {norm(c).replace(" ", "_"): c for c in frame.columns}
    for name in names:
        found = cols.get(norm(name).replace(" ", "_"))
        if found:
            return found
    return None


def discover(timeout: float = 90.0) -> dict[str, dict[str, str]]:
    resources: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for package in PACKAGES:
            for endpoint in ENDPOINTS:
                try:
                    response = client.get(endpoint, params={"id": package})
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("success"):
                        resources.extend(payload["result"].get("resources", []))
                        break
                except Exception:
                    continue
    selected: dict[str, dict[str, str]] = {}
    for indicator, patterns in PATTERNS.items():
        matches = []
        for resource in resources:
            haystack = norm(f"{resource.get('name', '')} {resource.get('description', '')}")
            score = max((len(p) for p in patterns if p in haystack), default=0)
            if score and resource.get("url"):
                matches.append((score, resource))
        if matches:
            resource = sorted(matches, reverse=True, key=lambda x: x[0])[0][1]
            selected[indicator] = {"name": str(resource.get("name", indicator)), "url": str(resource["url"])}
    return selected


def read_csv(content: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        for sep in (";", ",", "\t"):
            try:
                frame = pd.read_csv(io.BytesIO(content), encoding=encoding, sep=sep, low_memory=False)
                if len(frame.columns) >= 2:
                    return frame
            except Exception:
                pass
    raise RuntimeError("Unable to parse CADSUAS CSV")


def municipal_series(frame: pd.DataFrame, indicator: str) -> pd.DataFrame:
    code = column(frame, "codigo_ibge", "cod_ibge", "ibge", "co_municipio")
    value = column(frame, indicator, f"cadsuas_qtd_{indicator}_i", "valor", "quantidade", "qtd")
    date_col = column(frame, "anomes", "ano_mes", "competencia")
    if code is None:
        raise RuntimeError(f"No municipality code in {indicator}: {list(frame.columns)}")
    if value is None:
        candidates = [c for c in frame.columns if c != code and pd.api.types.is_numeric_dtype(frame[c])]
        if date_col in candidates:
            candidates.remove(date_col)
        if not candidates:
            raise RuntimeError(f"No value column in {indicator}: {list(frame.columns)}")
        value = candidates[-1]
    local = frame[[code, value] + ([date_col] if date_col else [])].copy()
    local["municipality_code"] = local[code].astype(str).str.replace(r"\.0$", "", regex=True).str.extract(r"(\d+)", expand=False)
    local = local[local["municipality_code"].str.startswith("15", na=False)]
    local["municipality_code"] = local["municipality_code"].str[:6].str.zfill(6)
    local[indicator] = pd.to_numeric(local[value], errors="coerce")
    if date_col:
        local["_date"] = pd.to_numeric(local[date_col], errors="coerce")
        local = local.sort_values("_date").drop_duplicates("municipality_code", keep="last")
    else:
        local = local.groupby("municipality_code", as_index=False)[indicator].sum(min_count=1)
    return local[["municipality_code", indicator]]


def collect_social_assistance_pa(output_directory: str | Path = "data/processed", timeout: float = 180.0) -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    resources = discover(timeout)
    missing = sorted({"cras", "creas"} - resources.keys())
    if missing:
        raise RuntimeError(f"Required CADSUAS resources not found: {missing}")

    merged: pd.DataFrame | None = None
    provenance: dict[str, Any] = {}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for indicator, resource in resources.items():
            print(f"Downloading {indicator}: {resource['url']}", flush=True)
            response = client.get(resource["url"])
            response.raise_for_status()
            source = read_csv(response.content)
            series = municipal_series(source, indicator)
            merged = series if merged is None else merged.merge(series, on="municipality_code", how="outer")
            provenance[indicator] = {
                "resource_name": resource["name"],
                "resource_url": resource["url"],
                "source_rows": int(len(source)),
                "para_rows": int(len(series)),
            }

    assert merged is not None
    rename = {
        "cras": "social_cras",
        "creas": "social_creas",
        "centro_pop": "social_centro_pop",
        "centro_dia": "social_centro_dia",
        "centro_convivencia": "social_centros_convivencia",
        "unidade_acolhimento": "social_unidades_acolhimento",
        "profissionais_cras": "social_cras_professionals",
        "profissionais_creas": "social_creas_professionals",
    }
    result = merged.rename(columns=rename)
    for final_name in rename.values():
        if final_name not in result:
            result[final_name] = 0
        result[final_name] = pd.to_numeric(result[final_name], errors="coerce").fillna(0).round().astype(int)
    result["social_basic_protection_deficit"] = result["social_cras"].eq(0).astype(int)
    result["social_specialized_service_deficit"] = (
        result["social_creas"].eq(0).astype(int)
        + result["social_centro_dia"].eq(0).astype(int)
        + result["social_unidades_acolhimento"].eq(0).astype(int)
    )
    result = result.sort_values("municipality_code")

    indicators_path = output / "social_assistance_indicators_pa.csv"
    metadata_path = output / "social_assistance_indicators_pa.metadata.json"
    result.to_csv(indicators_path, index=False, encoding="utf-8")
    metadata_path.write_text(json.dumps({
        "source": "MDS CADSUAS / Brazilian Open Data Portal",
        "state": "Pará",
        "municipal_rows": int(len(result)),
        "resources": provenance,
        "selection": "Latest available competence by municipality when anomes exists",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"social_indicators": indicators_path, "social_metadata": metadata_path}
