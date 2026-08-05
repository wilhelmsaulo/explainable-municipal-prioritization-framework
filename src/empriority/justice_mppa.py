from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import httpx
import pandas as pd
from lxml import html

BASE = "https://www2.mppa.mp.br"
SITEMAPS = [
    f"{BASE}/sitemap.xml",
    f"{BASE}/sitemap_index.xml",
    "https://www.mppa.mp.br/sitemap.xml",
]
VIOLENCE_TERMS = (
    "violencia domestica",
    "violencia familiar contra a mulher",
    "crimes contra a mulher",
    "maria da penha",
)


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower()).strip()


def _extract_urls(client: httpx.Client) -> list[str]:
    urls: set[str] = set()
    for sitemap in SITEMAPS:
        try:
            response = client.get(sitemap)
            if response.status_code != 200:
                continue
            document = html.fromstring(response.content)
            for value in document.xpath("//*[local-name()='loc']/text()"):
                value = str(value).strip()
                if value:
                    urls.add(value)
        except Exception:
            continue
    if not urls:
        response = client.get(BASE)
        response.raise_for_status()
        document = html.fromstring(response.content)
        for href in document.xpath("//a/@href"):
            urls.add(urljoin(BASE, href))
    return sorted(urls)


def collect_mppa_access_pa(
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
    max_pages: int = 2500,
) -> dict[str, Path]:
    matrix = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    municipalities = matrix[["municipality_code", "municipality"]].copy()
    municipalities["_name"] = municipalities["municipality"].map(_norm)

    headers = {"User-Agent": "Mozilla/5.0 institutional-research-crawler/1.0"}
    pages: list[dict[str, object]] = []
    with httpx.Client(timeout=45.0, follow_redirects=True, headers=headers) as client:
        candidates = [
            url for url in _extract_urls(client)
            if "mppa.mp.br" in url
            and "/noticias/" not in url.lower()
            and not url.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"))
        ][:max_pages]
        print(f"MPPA institutional candidate pages: {len(candidates)}", flush=True)
        for index, url in enumerate(candidates, start=1):
            try:
                response = client.get(url)
                if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
                    continue
                document = html.fromstring(response.content)
                text = _norm(" ".join(document.xpath("//body//text()")))
                if "promotoria de justica" not in text:
                    continue
                for row in municipalities.itertuples(index=False):
                    if row._name not in text:
                        continue
                    has_contact = any(term in text for term in ("endereco", "telefone", "e-mail", "email", "atendimento"))
                    pages.append({
                        "municipality_code": row.municipality_code,
                        "municipality": row.municipality,
                        "url": url,
                        "has_contact": int(has_contact),
                        "specialized_women": int(any(term in text for term in VIOLENCE_TERMS)),
                    })
                if index % 250 == 0:
                    print(f"MPPA pages inspected: {index}", flush=True)
            except Exception:
                continue

    raw = pd.DataFrame(pages)
    if raw.empty:
        raise RuntimeError("No MPPA institutional promotoria pages matched Pará municipalities")
    raw = raw.drop_duplicates(["municipality_code", "url"])
    summary = raw.groupby(["municipality_code", "municipality"], as_index=False).agg(
        justice_mppa_pages=("url", "nunique"),
        justice_mppa_local_unit=("has_contact", "max"),
        justice_mppa_specialized_women=("specialized_women", "max"),
    )
    result = municipalities.drop(columns="_name").merge(summary, on=["municipality_code", "municipality"], how="left")
    for column in ["justice_mppa_pages", "justice_mppa_local_unit", "justice_mppa_specialized_women"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["justice_mppa_covered"] = result["justice_mppa_pages"].gt(0).astype(int)
    result["justice_mppa_access_deficit"] = result["justice_mppa_covered"].eq(0).astype(int)

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    indicators = output / "justice_mppa_indicators_pa.csv"
    raw_path = output / "justice_mppa_institutional_pages_pa.csv"
    metadata = output / "justice_mppa_indicators_pa.metadata.json"
    result.to_csv(indicators, index=False, encoding="utf-8")
    raw.to_csv(raw_path, index=False, encoding="utf-8")
    metadata.write_text(json.dumps({
        "source": "MPPA official institutional website",
        "base_url": BASE,
        "news_excluded": True,
        "municipal_rows": int(len(result)),
        "matched_pages": int(len(raw)),
        "method": "Official sitemap/pages containing Promotoria de Justiça and municipality name; news URLs excluded",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"justice_indicators": indicators, "raw_pages": raw_path, "metadata": metadata}
