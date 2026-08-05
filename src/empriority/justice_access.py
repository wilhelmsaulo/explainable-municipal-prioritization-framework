from __future__ import annotations

import json
import re
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


def collect_defensoria_access_pa(
    municipality_reference: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
    timeout: float = 120.0,
) -> dict[str, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    reference = pd.read_csv(municipality_reference, dtype={"municipality_code": str})[
        ["municipality_code", "municipality"]
    ].drop_duplicates()
    reference["_key"] = reference["municipality"].map(_norm)
    valid_keys = set(reference["_key"])

    response = httpx.get(
        DPE_URL,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; municipal-research-framework/1.0)"},
    )
    response.raise_for_status()
    document = html.fromstring(response.content)

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
        details_norm = _norm(details_text)

        records.append(
            {
                "municipality_key": key,
                "listed_municipality": label,
                "details": details_text,
                "justice_dpe_covered": 1,
                "justice_dpe_local_unit": int(key in details_norm),
            }
        )

    raw = pd.DataFrame(records)
    diagnostic_path = output / "justice_defensoria_diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "source_url": DPE_URL,
                "h4_headings": len(headings),
                "matched_entries": len(raw),
                "sample_labels": raw.get("listed_municipality", pd.Series(dtype=str)).head(10).tolist(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
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
    result["justice_dpe_referred_service"] = (
        (result["justice_dpe_covered"] == 1) & (result["justice_dpe_local_unit"] == 0)
    ).astype(int)
    result["justice_dpe_access_deficit"] = (result["justice_dpe_covered"] == 0).astype(int)
    result = result.drop(columns=["_key", "municipality_key"])

    assert len(result) == 144
    assert result["municipality_code"].nunique() == 144
    if result["justice_dpe_covered"].sum() <= 0:
        raise AssertionError("Defensoria coverage is zero; refusing invalid snapshot")

    indicators_path = output / "justice_defensoria_indicators_pa.csv"
    raw_path = output / "justice_defensoria_directory_raw_pa.csv"
    metadata_path = output / "justice_defensoria_indicators_pa.metadata.json"
    result.to_csv(indicators_path, index=False, encoding="utf-8")
    raw.to_csv(raw_path, index=False, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "source": "Defensoria Pública do Estado do Pará — Localize uma Defensoria",
                "source_url": DPE_URL,
                "municipal_rows": int(len(result)),
                "covered_municipalities": int(result["justice_dpe_covered"].sum()),
                "municipalities_with_local_unit": int(result["justice_dpe_local_unit"].sum()),
                "municipalities_served_by_referral": int(result["justice_dpe_referred_service"].sum()),
                "method_note": "Each official h4 municipality entry is paired with subsequent address/telephone elements until the next h4. Local presence requires the address text to reference the same municipality.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"DPE indicators: covered={int(result['justice_dpe_covered'].sum())}, "
        f"local={int(result['justice_dpe_local_unit'].sum())}, "
        f"referred={int(result['justice_dpe_referred_service'].sum())}",
        flush=True,
    )
    return {
        "justice_indicators": indicators_path,
        "justice_raw": raw_path,
        "justice_metadata": metadata_path,
        "justice_diagnostic": diagnostic_path,
    }
