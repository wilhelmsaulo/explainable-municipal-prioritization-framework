from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .catalog import SOURCES

_ALLOWED_EXTENSIONS = (
    ".zip", ".csv", ".json", ".geojson", ".kml", ".kmz", ".gpkg", ".shp"
)
_KEYWORDS = {
    "dnit_roads": ("rodov", "shapefile", "shp", "snv", "geo"),
    "antaq_ports": ("porto", "instala", "travess", "geograf", "shp", "kml"),
    "antaq_waterways": ("hidrovia", "navega", "via interior", "geograf", "shp"),
    "anac_public_aerodromes": ("aerodromo", "aeródromo", "csv", "json"),
}


def _safe_name(url: str, fallback: str) -> str:
    name = Path(urlparse(url).path).name or fallback
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:180]


def _extract_links(html: str, base_url: str) -> list[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    return sorted({urljoin(base_url, href) for href in hrefs})


def _score(source_id: str, url: str) -> int:
    text = url.lower()
    score = sum(3 for term in _KEYWORDS.get(source_id, ()) if term in text)
    if text.endswith(_ALLOWED_EXTENSIONS):
        score += 5
    if any(host in text for host in ("gov.br", "dnit.gov.br", "antaq.gov.br", "anac.gov.br")):
        score += 2
    return score


def _get_page_with_retry(
    client: httpx.Client,
    url: str,
    attempts: int = 5,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(2 ** (attempt - 1), 16))
    assert last_error is not None
    raise last_error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_inventory(path: Path) -> list[str]:
    if not zipfile.is_zipfile(path):
        return []
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()[:5000]


def discover_and_download_transport_layers(
    raw_dir: str | Path = "data/raw/transport",
    output_dir: str | Path = "data/processed/transport",
    max_candidates_per_source: int = 8,
    max_bytes_per_file: int = 300_000_000,
) -> dict[str, Path]:
    raw_root = Path(raw_dir)
    output = Path(output_dir)
    raw_root.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    manifest: dict[str, Any] = {
        "generated_at_utc": generated_at,
        "sources": {},
        "policy": {
            "max_candidates_per_source": max_candidates_per_source,
            "max_bytes_per_file": max_bytes_per_file,
            "note": "Raw layers are workflow artifacts; manifests are committed for provenance.",
        },
    }

    headers = {"User-Agent": "empriority-research/0.1 (public-data reproducibility)"}
    transport = httpx.HTTPTransport(retries=5)
    with httpx.Client(
        timeout=90.0,
        follow_redirects=True,
        headers=headers,
        transport=transport,
    ) as client:
        for source in SOURCES:
            source_id = source["source_id"]
            if source_id == "ibge_municipal_boundaries":
                continue
            record: dict[str, Any] = {
                "agency": source["agency"],
                "official_page": source["official_page"],
                "discovered": [],
                "downloads": [],
                "errors": [],
            }
            manifest["sources"][source_id] = record
            try:
                page = _get_page_with_retry(client, source["official_page"])
                links = _extract_links(page.text, str(page.url))
            except Exception as exc:
                record["errors"].append({"stage": "page", "type": type(exc).__name__, "message": str(exc)})
                continue

            ranked = sorted(
                ((url, _score(source_id, url)) for url in links),
                key=lambda item: (-item[1], item[0]),
            )
            candidates = [url for url, score in ranked if score >= 5][:max_candidates_per_source]
            record["discovered"] = candidates
            target_dir = raw_root / source_id
            target_dir.mkdir(parents=True, exist_ok=True)

            for index, url in enumerate(candidates, start=1):
                try:
                    with client.stream("GET", url) as response:
                        response.raise_for_status()
                        length = int(response.headers.get("content-length") or 0)
                        if length and length > max_bytes_per_file:
                            record["errors"].append({"stage": "download", "url": url, "message": f"skipped size {length}"})
                            continue
                        filename = _safe_name(str(response.url), f"candidate_{index}")
                        path = target_dir / filename
                        total = 0
                        with path.open("wb") as handle:
                            for chunk in response.iter_bytes(1024 * 1024):
                                total += len(chunk)
                                if total > max_bytes_per_file:
                                    raise RuntimeError(f"download exceeded {max_bytes_per_file} bytes")
                                handle.write(chunk)
                    entry = {
                        "url": url,
                        "resolved_url": str(response.url),
                        "path": str(path),
                        "bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                        "content_type": response.headers.get("content-type"),
                        "zip_inventory": _zip_inventory(path),
                    }
                    record["downloads"].append(entry)
                    print(source_id, path.name, entry["bytes"])
                except Exception as exc:
                    record["errors"].append({"stage": "download", "url": url, "type": type(exc).__name__, "message": str(exc)})

    manifest_path = output / "transport_layer_download_manifest.json"
    status_path = output / "transport_layer_download_status.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    source_status = {}
    for source_id, record in manifest["sources"].items():
        source_status[source_id] = {
            "discovered": len(record["discovered"]),
            "downloaded": len(record["downloads"]),
            "errors": len(record["errors"]),
            "status": "success" if record["downloads"] else "failed",
        }
    status = {
        "generated_at_utc": generated_at,
        "status": "complete" if all(v["downloaded"] > 0 for v in source_status.values()) else "partial",
        "sources": source_status,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": manifest_path, "status": status_path}
