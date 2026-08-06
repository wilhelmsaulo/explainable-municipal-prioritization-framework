from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

import httpx
import pandas as pd
from lxml import html

DPE_URL = "https://defensoria.pa.def.br/localizar-defensorias"


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _text(element: object) -> str:
    return " ".join(part.strip() for part in element.itertext() if part.strip())


def _download_directory(timeout: float, attempts: int = 4) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; municipal-research-framework/1.0)"}
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(timeout, connect=60.0),
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(DPE_URL)
                response.raise_for_status()
                return response.content
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 5)
    assert last_error is not None
    raise last_error


def collect_defensoria_access_pa(
    municipality_reference: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
    timeout: float = 180.0,
) -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    reference = pd.read_csv(municipality_reference, dtype={"municipality_code": str})[
        ["municipality_code", "municipality"]
    ].drop_duplicates()
    reference["_key"] = reference["municipality"].map(_norm)
    valid_keys = set(reference["_key"])

    document = html.fromstring(_download_directory(timeout))
    records: list[dict[str, object]] = []
    headings = document.xpath("//h4")
    for heading in headings:
        label = _text(heading)
        key = _norm(label)
        if key not in valid_keys:
            candidates = [candidate for candidate in valid_keys if key.startswith(candidate + " ")]
            key = max(candidates, key=len) if candidates else ""
        if not key:
            continue
        details: list[str] = []
        sibling = heading.getnext()
        while sibling is not None and sibling.tag.lower() != "h4":
            value = _text(sibling)
            if value:
                details.append(value)
            sibling = sibling.getnext()
        details_text = " ".join(details)
        records.append({
            "municipality_key": key,
            "listed_municipality": label,
            "details": details_text,
            "justice_dpe_covered": 1,
            "justice_dpe_local_unit": int(key in _norm(details_text)),
        })

    raw = pd.DataFrame(records)
    diagnostic_path = output / "justice_defensoria_diagnostic.json"
    diagnostic_path.write_text(json.dumps({
        "source_url": DPE_URL,
        "h4_headings": len(headings),
        "matched_entries": len(raw),
        "sample_labels": raw.get("listed_municipality", pd.Series(dtype=str)).head(10).tolist(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if raw.empty:
        raise RuntimeError("No municipal Defensoria entries found on official DPE page")

    grouped = raw.groupby("municipality_key", as_index=False).agg(
        justice_dpe_covered=("justice_dpe_covered", "max"),
        justice_dpe_local_unit=("justice_dpe_local_unit", "max"),
        justice_dpe_listed_entries=("listed_municipality", "count"),
    )
    result = reference.merge(grouped, left_on="_key", right_on="municipality_key", how="left")
    for column in ["justice_dpe_covered", "justice_dpe_local_unit", "justice_dpe_listed_entries"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["justice_dpe_referred_service"] = ((result["justice_dpe_covered"] == 1) & (result["justice_dpe_local_unit"] == 0)).astype(int)
    result["justice_dpe_access_deficit"] = (result["justice_dpe_covered"] == 0).astype(int)
    result = result.drop(columns=["_key", "municipality_key"])
    assert len(result) == 144 and result["municipality_code"].nunique() == 144
    if result["justice_dpe_covered"].sum() <= 0:
        raise AssertionError("Defensoria coverage is zero; refusing invalid snapshot")

    indicators_path = output / "justice_defensoria_indicators_pa.csv"
    raw_path = output / "justice_defensoria_directory_raw_pa.csv"
    metadata_path = output / "justice_defensoria_indicators_pa.metadata.json"
    result.to_csv(indicators_path, index=False, encoding="utf-8")
    raw.to_csv(raw_path, index=False, encoding="utf-8")
    metadata_path.write_text(json.dumps({
        "source": "Defensoria Pública do Estado do Pará — Localize uma Defensoria",
        "source_url": DPE_URL,
        "municipal_rows": int(len(result)),
        "covered_municipalities": int(result["justice_dpe_covered"].sum()),
        "municipalities_with_local_unit": int(result["justice_dpe_local_unit"].sum()),
        "municipalities_served_by_referral": int(result["justice_dpe_referred_service"].sum()),
        "method_note": "Official municipality entries paired with address and telephone elements; network requests use bounded retries.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "justice_indicators": indicators_path,
        "justice_raw": raw_path,
        "justice_metadata": metadata_path,
        "justice_diagnostic": diagnostic_path,
    }
