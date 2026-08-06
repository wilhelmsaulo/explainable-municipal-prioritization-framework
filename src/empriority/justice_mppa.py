from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import httpx
import pandas as pd
from lxml import etree, html

BASE = "https://www2.mppa.mp.br"
SITEMAPS = [f"{BASE}/sitemap.xml", f"{BASE}/sitemap_index.xml", "https://www.mppa.mp.br/sitemap.xml"]
VIOLENCE_TERMS = (
    "violencia domestica",
    "violencia familiar contra a mulher",
    "crimes contra a mulher",
    "maria da penha",
)


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower()).strip()


def _xml_locations(content: bytes) -> list[str]:
    try:
        root = etree.fromstring(content)
    except etree.XMLSyntaxError:
        return []
    return [str(v).strip() for v in root.xpath("//*[local-name()='loc']/text()") if str(v).strip()]


def _extract_urls(client: httpx.Client) -> tuple[list[str], list[dict[str, object]]]:
    urls: set[str] = set()
    attempts: list[dict[str, object]] = []
    nested: list[str] = []
    for sitemap in SITEMAPS:
        try:
            response = client.get(sitemap)
            locations = _xml_locations(response.content) if response.status_code == 200 else []
            attempts.append({"url": sitemap, "status": response.status_code, "locations": len(locations)})
            for location in locations:
                (nested if location.lower().endswith(".xml") else urls).append(location) if False else None
                if location.lower().endswith(".xml"):
                    nested.append(location)
                else:
                    urls.add(location)
        except Exception as exc:
            attempts.append({"url": sitemap, "error": type(exc).__name__})
    for sitemap in nested[:100]:
        try:
            response = client.get(sitemap)
            locations = _xml_locations(response.content) if response.status_code == 200 else []
            attempts.append({"url": sitemap, "status": response.status_code, "locations": len(locations)})
            urls.update(v for v in locations if not v.lower().endswith(".xml"))
        except Exception as exc:
            attempts.append({"url": sitemap, "error": type(exc).__name__})
    if not urls:
        try:
            response = client.get(BASE)
            response.raise_for_status()
            document = html.fromstring(response.content)
            for href in document.xpath("//a/@href"):
                urls.add(urljoin(BASE, str(href)))
            attempts.append({"url": BASE, "status": response.status_code, "homepage_links": len(urls)})
        except Exception as exc:
            attempts.append({"url": BASE, "error": type(exc).__name__})
    return sorted(urls), attempts


def collect_mppa_access_pa(
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
    max_pages: int = 2500,
) -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    matrix = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    municipalities = matrix[["municipality_code", "municipality"]].copy()
    municipalities["municipality_key"] = municipalities["municipality"].map(_norm)

    pages: list[dict[str, object]] = []
    diagnostic: dict[str, object] = {"source": "MPPA official institutional website"}
    headers = {"User-Agent": "Mozilla/5.0 institutional-research-crawler/1.0"}

    with httpx.Client(timeout=45.0, follow_redirects=True, headers=headers) as client:
        discovered, attempts = _extract_urls(client)
        candidates = [
            url for url in discovered
            if "mppa.mp.br" in url
            and "/noticias/" not in url.lower()
            and not url.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"))
        ][:max_pages]
        diagnostic.update({"discovery_attempts": attempts, "discovered_urls": len(discovered), "candidate_pages": len(candidates)})
        inspected = html_pages = promotoria_pages = 0
        for url in candidates:
            try:
                response = client.get(url)
                inspected += 1
                if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
                    continue
                html_pages += 1
                document = html.fromstring(response.content)
                text = _norm(" ".join(document.xpath("//body//text()")))
                if "promotoria de justica" not in text:
                    continue
                promotoria_pages += 1
                for row in municipalities.itertuples(index=False):
                    if row.municipality_key not in text:
                        continue
                    pages.append({
                        "municipality_code": row.municipality_code,
                        "municipality": row.municipality,
                        "url": url,
                        "has_contact": int(any(term in text for term in ("endereco", "telefone", "e-mail", "email", "atendimento"))),
                        "specialized_women": int(any(term in text for term in VIOLENCE_TERMS)),
                    })
            except Exception:
                continue

    diagnostic.update({"inspected_pages": inspected, "html_pages": html_pages, "promotoria_pages": promotoria_pages, "municipality_matches": len(pages)})
    diagnostic_path = output / "justice_mppa_diagnostic.json"
    diagnostic_path.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")

    raw = pd.DataFrame(pages)
    if raw.empty:
        raise RuntimeError("No MPPA institutional promotoria pages matched Pará municipalities")
    raw = raw.drop_duplicates(["municipality_code", "url"])
    summary = raw.groupby(["municipality_code", "municipality"], as_index=False).agg(
        justice_mppa_pages=("url", "nunique"),
        justice_mppa_local_unit=("has_contact", "max"),
        justice_mppa_specialized_women=("specialized_women", "max"),
    )
    result = municipalities.drop(columns="municipality_key").merge(summary, on=["municipality_code", "municipality"], how="left")
    for column in ["justice_mppa_pages", "justice_mppa_local_unit", "justice_mppa_specialized_women"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["justice_mppa_covered"] = result["justice_mppa_pages"].gt(0).astype(int)
    result["justice_mppa_access_deficit"] = result["justice_mppa_covered"].eq(0).astype(int)
    assert len(result) == 144 and result["municipality_code"].nunique() == 144

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
    return {"justice_indicators": indicators, "raw_pages": raw_path, "metadata": metadata, "diagnostic": diagnostic_path}
