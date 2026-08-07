from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from .catalog import SOURCES

_ALLOWED_EXTENSIONS = (
    ".zip", ".csv", ".json", ".geojson", ".kml", ".kmz", ".gpkg", ".shp"
)
_BLOCKED_HOSTS = {
    "facebook.com",
    "www.facebook.com",
    "api.whatsapp.com",
    "twitter.com",
    "x.com",
}
_KEYWORDS = {
    "dnit_roads": ("rodov", "shapefile", "shp", "snv", "geo"),
    "antaq_ports": ("porto", "instala", "travess", "geograf", "shp", "kml"),
    "antaq_waterways": ("hidrovia", "navega", "via interior", "geograf", "shp"),
    "anac_public_aerodromes": ("aerodromo", "aeródromo", "csv", "json"),
    "decea_airports": ("airport", "aerodromo", "aeródromo", "wfs", "getfeature"),
}


def _query_output_extension(url: str) -> str | None:
    query = {
        key.lower(): values
        for key, values in parse_qs(urlparse(url).query).items()
    }
    formats = query.get("outputformat", [])
    if not formats:
        return None
    value = formats[0].lower()
    if "shape-zip" in value or "shapefile" in value:
        return ".zip"
    if "json" in value:
        return ".geojson"
    if "csv" in value:
        return ".csv"
    if "kml" in value:
        return ".kml"
    return None


def _is_download_candidate(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.fragment or host in _BLOCKED_HOSTS:
        return False
    return (
        parsed.path.lower().endswith(_ALLOWED_EXTENSIONS)
        or _query_output_extension(url) is not None
    )


def _validate_download_response(response: httpx.Response) -> None:
    content_type = (response.headers.get("content-type") or "").lower()
    path = urlparse(str(response.url)).path.lower()
    if "text/html" in content_type:
        raise RuntimeError("rejected HTML response; expected a transport data file")
    if not (
        path.endswith(_ALLOWED_EXTENSIONS)
        or _query_output_extension(str(response.url)) is not None
    ):
        raise RuntimeError("rejected response without an approved data-file extension")


def _safe_name(url: str, fallback: str) -> str:
    name = Path(urlparse(url).path).name or fallback
    extension = _query_output_extension(url)
    if extension and not name.lower().endswith(_ALLOWED_EXTENSIONS):
        name = f"{fallback}{extension}"
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
    if _query_output_extension(url):
        score += 8
    if "request=getfeature" in text:
        score += 4
    if any(host in text for host in ("gov.br", "dnit.gov.br", "antaq.gov.br", "anac.gov.br")):
        score += 2
    return score


def _get_page_with_retry(
    client: httpx.Client,
    url: str,
    attempts: int = 3,
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
    max_candidates_per_source: int = 3,
    max_bytes_per_file: int = 80_000_000,
    download_attempts: int = 3,
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
            "download_attempts": download_attempts,
            "note": "Raw layers are cached artifacts; manifests are committed for provenance.",
        },
    }

    headers = {"User-Agent": "empriority-research/0.1 (public-data reproducibility)"}
    transport = httpx.HTTPTransport(retries=2)
    timeout = httpx.Timeout(90.0, connect=60.0, read=90.0, write=30.0, pool=30.0)
    with httpx.Client(
        timeout=timeout,
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
                "preserved": [],
                "errors": [],
            }
            manifest["sources"][source_id] = record
            direct_urls = list(source.get("direct_urls", []))
            try:
                page = _get_page_with_retry(client, source["official_page"])
                links = _extract_links(page.text, str(page.url))
            except Exception as exc:
                record["errors"].append({"stage": "page", "type": type(exc).__name__, "message": str(exc)})
                links = []
            links = sorted(set(links) | set(direct_urls))

            ranked = sorted(
                ((url, _score(source_id, url)) for url in links),
                key=lambda item: (-item[1], item[0]),
            )
            candidates = [
                url for url, score in ranked
                if score >= 5 and _is_download_candidate(url)
            ][:max_candidates_per_source]
            record["discovered"] = candidates
            target_dir = raw_root / source_id
            target_dir.mkdir(parents=True, exist_ok=True)
            for existing in sorted(target_dir.iterdir()):
                if existing.is_file() and existing.suffix.lower() in _ALLOWED_EXTENSIONS:
                    record["preserved"].append(
                        {
                            "path": str(existing),
                            "bytes": existing.stat().st_size,
                            "sha256": _sha256(existing),
                            "zip_inventory": _zip_inventory(existing),
                        }
                    )

            for index, url in enumerate(candidates, start=1):
                last_error: Exception | None = None
                for attempt in range(1, download_attempts + 1):
                    path: Path | None = None
                    try:
                        with client.stream("GET", url) as response:
                            response.raise_for_status()
                            _validate_download_response(response)
                            length = int(response.headers.get("content-length") or 0)
                            if length and length > max_bytes_per_file:
                                raise RuntimeError(f"download size {length} exceeds limit")
                            filename = _safe_name(str(response.url), f"candidate_{index}")
                            path = target_dir / filename
                            total = 0
                            with path.open("wb") as handle:
                                for chunk in response.iter_bytes(1024 * 1024):
                                    total += len(chunk)
                                    if total > max_bytes_per_file:
                                        raise RuntimeError(
                                            f"download exceeded {max_bytes_per_file} bytes"
                                        )
                                    handle.write(chunk)
                        entry = {
                            "url": url,
                            "resolved_url": str(response.url),
                            "path": str(path),
                            "bytes": path.stat().st_size,
                            "sha256": _sha256(path),
                            "content_type": response.headers.get("content-type"),
                            "zip_inventory": _zip_inventory(path),
                            "attempt": attempt,
                        }
                        record["downloads"].append(entry)
                        print(source_id, path.name, entry["bytes"])
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        if path is not None and path.exists():
                            path.unlink()
                        if attempt < download_attempts:
                            time.sleep(min(2 ** attempt, 8))
                if last_error is not None:
                    record["errors"].append(
                        {
                            "stage": "download",
                            "url": url,
                            "type": type(last_error).__name__,
                            "message": str(last_error),
                            "attempts": download_attempts,
                        }
                    )

    manifest_path = output / "transport_layer_download_manifest.json"
    status_path = output / "transport_layer_download_status.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    source_status = {}
    for source_id, record in manifest["sources"].items():
        available = len(record["downloads"]) + len(record["preserved"])
        source_status[source_id] = {
            "discovered": len(record["discovered"]),
            "downloaded": len(record["downloads"]),
            "preserved": len(record["preserved"]),
            "available": available,
            "errors": len(record["errors"]),
            "status": "success" if available else "failed",
        }
    status = {
        "generated_at_utc": generated_at,
        "status": "complete" if all(v["available"] > 0 for v in source_status.values()) else "partial",
        "sources": source_status,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": manifest_path, "status": status_path}
