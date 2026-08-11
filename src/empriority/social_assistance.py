from __future__ import annotations

import html
import io
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

BASE_ENDPOINTS = [
    "https://dados.gov.br/dados/api/3/action",
    "https://dados.gov.br/api/3/action",
]
PACKAGES = [
    "cadsuas---sistema-de-cadastro-do-sistema-unico-de-assistencia-social-suas",
    "unidades-de-atendimento-da-assistencia-social",
]
PUBLIC_DATASET_PAGES = [
    "https://dados.gov.br/dados/conjuntos-dados/cadsuas---sistema-de-cadastro-do-sistema-unico-de-assistencia-social-suas",
    "https://dados.gov.br/dados/conjuntos-dados/unidades-de-atendimento-da-assistencia-social",
]
SEARCH_TERMS = ["CADSUAS", "Unidades de Atendimento da Assistência Social"]
PATTERNS = {
    "cras": ["quantidade de cras", "brasil: cras", "centro de referencia de assistencia social"],
    "creas": ["quantidade de creas", "brasil: creas", "centro de referencia especializado"],
    "centro_pop": ["quantidade de centro pop", "brasil: centro pop"],
    "centro_dia": ["quantidade de centro dia", "centro dia e similares", "brasil: centro-dia"],
    "centro_convivencia": ["quantidade de centro de convivencia", "centros de convivencias"],
    "unidade_acolhimento": ["quantidade de unidade de acolhimento", "unidades de acolhimento"],
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


def _package_resources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload.get("success"):
        return []
    result = payload.get("result", {})
    if isinstance(result, dict) and isinstance(result.get("resources"), list):
        return list(result["resources"])
    resources: list[dict[str, Any]] = []
    for package in result.get("results", []) if isinstance(result, dict) else []:
        resources.extend(package.get("resources", []))
    return resources


def _walk_resources(value: Any) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    if isinstance(value, dict):
        url = value.get("url") or value.get("downloadURL") or value.get("accessURL")
        if isinstance(url, str) and url.startswith("http"):
            resources.append(
                {
                    "url": url,
                    "name": value.get("name")
                    or value.get("title")
                    or value.get("description")
                    or "",
                    "description": value.get("description") or value.get("name") or "",
                    "format": value.get("format") or value.get("mediaType") or "",
                }
            )
        for item in value.values():
            resources.extend(_walk_resources(item))
    elif isinstance(value, list):
        for item in value:
            resources.extend(_walk_resources(item))
    return resources


def _decode_embedded_text(text: str) -> str:
    decoded = html.unescape(text).replace("\\/", "/")
    return re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda match: chr(int(match.group(1), 16)),
        decoded,
    )


def _public_page_resources(client: httpx.Client, page_url: str) -> list[dict[str, Any]]:
    response = client.get(page_url, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    text = _decode_embedded_text(response.text)
    resources: list[dict[str, Any]] = []

    for script in re.findall(r"<script[^>]*>(.*?)</script>", text, flags=re.I | re.S):
        candidate = script.strip()
        if not candidate or candidate[0] not in "[{":
            continue
        try:
            resources.extend(_walk_resources(json.loads(candidate)))
        except Exception:
            continue

    url_pattern = re.compile(r"https?://[^\s\"'<>]+", flags=re.I)
    for match in url_pattern.finditer(text):
        url = match.group(0).rstrip("),.;]")
        if not any(token in url.lower() for token in ("csv", "download", "recurso", "resource")):
            continue
        context = text[max(0, match.start() - 700) : min(len(text), match.end() + 250)]
        resources.append(
            {
                "url": url,
                "name": context,
                "description": context,
                "format": "CSV" if "csv" in url.lower() or "csv" in norm(context) else "",
            }
        )
    return resources


def discover(timeout: float = 90.0) -> dict[str, dict[str, str]]:
    resources: list[dict[str, Any]] = []
    attempts: list[str] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for base in BASE_ENDPOINTS:
            for package in PACKAGES:
                try:
                    response = client.get(f"{base}/package_show", params={"id": package})
                    attempts.append(f"package_show {base} {package}: {response.status_code}")
                    response.raise_for_status()
                    resources.extend(_package_resources(response.json()))
                except Exception as exc:  # noqa: BLE001
                    attempts.append(f"package_show {base} {package}: {type(exc).__name__}")
            for term in SEARCH_TERMS:
                try:
                    response = client.get(f"{base}/package_search", params={"q": term, "rows": 10})
                    attempts.append(f"package_search {base} {term}: {response.status_code}")
                    response.raise_for_status()
                    resources.extend(_package_resources(response.json()))
                except Exception as exc:  # noqa: BLE001
                    attempts.append(f"package_search {base} {term}: {type(exc).__name__}")

        if not resources:
            for page_url in PUBLIC_DATASET_PAGES:
                try:
                    page_resources = _public_page_resources(client, page_url)
                    attempts.append(f"public_page {page_url}: {len(page_resources)} resources")
                    resources.extend(page_resources)
                except Exception as exc:  # noqa: BLE001
                    attempts.append(f"public_page {page_url}: {type(exc).__name__}")

    unique: dict[str, dict[str, Any]] = {}
    for resource in resources:
        url = str(resource.get("url", "")).strip()
        if url:
            existing = unique.get(url)
            if existing is None or len(str(resource.get("name", ""))) > len(
                str(existing.get("name", ""))
            ):
                unique[url] = resource
    resources = list(unique.values())
    print(f"CADSUAS catalog resources discovered: {len(resources)}", flush=True)
    for attempt in attempts:
        print(attempt, flush=True)

    selected: dict[str, dict[str, str]] = {}
    for indicator, patterns in PATTERNS.items():
        matches: list[tuple[int, dict[str, Any]]] = []
        for resource in resources:
            haystack = norm(
                f"{resource.get('name', '')} {resource.get('description', '')} "
                f"{resource.get('format', '')}"
            )
            score = max((len(pattern) for pattern in patterns if pattern in haystack), default=0)
            if score and resource.get("url"):
                format_bonus = 5 if "csv" in norm(resource.get("format", "")) else 0
                matches.append((score + format_bonus, resource))
        if matches:
            resource = sorted(matches, reverse=True, key=lambda item: item[0])[0][1]
            selected[indicator] = {
                "name": str(resource.get("name", indicator))[:500],
                "url": str(resource["url"]),
            }
            print(f"CADSUAS selected {indicator}: {selected[indicator]['url']}", flush=True)
    return selected


def read_csv(content: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        for sep in (";", ",", "\t"):
            try:
                frame = pd.read_csv(
                    io.BytesIO(content), encoding=encoding, sep=sep, low_memory=False
                )
                if len(frame.columns) >= 2:
                    return frame
            except Exception:
                pass
    raise RuntimeError("Unable to parse CADSUAS CSV")


def municipal_series(frame: pd.DataFrame, indicator: str) -> pd.DataFrame:
    code = column(frame, "codigo_ibge", "cod_ibge", "ibge", "co_municipio")
    value_names = {
        "cras": "cadsuas_qtd_cras_i",
        "creas": "cadsuas_qtd_creas_i",
        "centro_pop": "cadsuas_qtd_centro_pop_i",
        "centro_dia": "cadsuas_qtd_centro_dia_similares_i",
        "centro_convivencia": "cadsuas_qtd_centro_convivencia_i",
        "unidade_acolhimento": "cadsuas_qtd_unidade_acolhimento_i",
        "profissionais_cras": "cadsuas_qtd_profissionais_cras_i",
        "profissionais_creas": "cadsuas_qtd_profissionais_creas_i",
    }
    value = column(
        frame, value_names.get(indicator, indicator), indicator, "valor", "quantidade", "qtd"
    )
    date_col = column(frame, "anomes", "ano_mes", "competencia")
    if code is None:
        raise RuntimeError(f"No municipality code in {indicator}: {list(frame.columns)}")
    if value is None:
        candidates = [
            c for c in frame.columns if c != code and pd.api.types.is_numeric_dtype(frame[c])
        ]
        if date_col in candidates:
            candidates.remove(date_col)
        if not candidates:
            raise RuntimeError(f"No value column in {indicator}: {list(frame.columns)}")
        value = candidates[-1]
    local = frame[[code, value] + ([date_col] if date_col else [])].copy()
    local["municipality_code"] = (
        local[code]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.extract(r"(\d+)", expand=False)
    )
    local = local[local["municipality_code"].str.startswith("15", na=False)]
    local["municipality_code"] = local["municipality_code"].str[:6].str.zfill(6)
    local[indicator] = pd.to_numeric(local[value], errors="coerce")
    if date_col:
        local["_date"] = pd.to_numeric(local[date_col], errors="coerce")
        local = local.sort_values("_date").drop_duplicates("municipality_code", keep="last")
    else:
        local = local.groupby("municipality_code", as_index=False)[indicator].sum(min_count=1)
    return local[["municipality_code", indicator]]


def collect_social_assistance_pa(
    output_directory: str | Path = "data/processed",
    timeout: float = 180.0,
) -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    resources = discover(timeout)
    missing = sorted({"cras", "creas"} - resources.keys())
    if missing:
        diagnostic = output / "social_assistance_discovery_error.json"
        diagnostic.write_text(
            json.dumps({"missing": missing, "discovered": resources}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise RuntimeError(f"Required CADSUAS resources not found: {missing}")

    merged: pd.DataFrame | None = None
    provenance: dict[str, Any] = {}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for indicator, resource in resources.items():
            print(f"Downloading {indicator}: {resource['url']}", flush=True)
            response = client.get(resource["url"], headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            source = read_csv(response.content)
            series = municipal_series(source, indicator)
            merged = (
                series
                if merged is None
                else merged.merge(series, on="municipality_code", how="outer")
            )
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
        result[final_name] = (
            pd.to_numeric(result[final_name], errors="coerce").fillna(0).round().astype(int)
        )
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
    metadata_path.write_text(
        json.dumps(
            {
                "source": "MDS CADSUAS / Brazilian Open Data Portal",
                "state": "Pará",
                "municipal_rows": int(len(result)),
                "resources": provenance,
                "selection": "Latest available competence by municipality when anomes exists",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"social_indicators": indicators_path, "social_metadata": metadata_path}
