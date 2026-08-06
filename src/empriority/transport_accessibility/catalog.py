from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "dnit_roads",
        "agency": "DNIT",
        "theme": "roads",
        "official_page": "https://www.gov.br/dnit/pt-br/dadosabertos",
        "expected_formats": ["shp", "geojson", "csv"],
        "map_reference_year": 2023,
        "purpose": "Federal road network and road-surface/status classes.",
    },
    {
        "source_id": "antaq_ports",
        "agency": "ANTAQ",
        "theme": "ports",
        "official_page": "https://www.gov.br/antaq/pt-br/central-de-conteudos/informacoes-geograficas",
        "expected_formats": ["shp", "kml"],
        "map_reference_year": 2022,
        "purpose": "Port facilities and authorized passenger/ferry crossing lines.",
    },
    {
        "source_id": "antaq_waterways",
        "agency": "ANTAQ",
        "theme": "waterways",
        "official_page": "https://www.gov.br/antaq/pt-br/central-de-conteudos/informacoes-geograficas",
        "expected_formats": ["shp"],
        "map_reference_year": 2022,
        "purpose": "Economically navigated inland waterways and navigation corridors.",
    },
    {
        "source_id": "anac_public_aerodromes",
        "agency": "ANAC",
        "theme": "airports",
        "official_page": "https://www.gov.br/anac/pt-br/acesso-a-informacao/dados-abertos/areas-de-atuacao/aerodromos/aerodromos-publicos",
        "expected_formats": ["csv", "json"],
        "map_reference_year": 2023,
        "purpose": "Public aerodromes and their geographic coordinates.",
    },
    {
        "source_id": "ibge_municipal_boundaries",
        "agency": "IBGE",
        "theme": "municipal_boundaries",
        "official_page": "https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/15774-malhas.html",
        "expected_formats": ["shp"],
        "map_reference_year": 2023,
        "purpose": "Municipal boundaries and territorial reference geometry.",
    },
]


def _probe(client: httpx.Client, url: str) -> dict[str, Any]:
    try:
        response = client.get(url, follow_redirects=True)
        return {
            "status": "available" if response.is_success else "http_error",
            "http_status": response.status_code,
            "resolved_url": str(response.url),
            "content_type": response.headers.get("content-type"),
        }
    except Exception as exc:  # network diagnostics must be persisted
        return {
            "status": "unreachable",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def build_transport_source_catalog(
    output_dir: str | Path = "data/processed/transport",
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    checked_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=45.0, headers={"User-Agent": "empriority-research/0.1"}) as client:
        for source in SOURCES:
            result = dict(source)
            result.update(_probe(client, source["official_page"]))
            result["checked_at_utc"] = checked_at
            rows.append(result)
            print(source["source_id"], result["status"], result.get("http_status", ""))

    catalog_path = output / "official_transport_sources.json"
    status_path = output / "transport_source_status.json"

    catalog_path.write_text(
        json.dumps({"sources": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    status_path.write_text(
        json.dumps(
            {
                "generated_at_utc": checked_at,
                "source_count": len(rows),
                "available": sum(row["status"] == "available" for row in rows),
                "unavailable": sum(row["status"] != "available" for row in rows),
                "sources": {
                    row["source_id"]: {
                        "status": row["status"],
                        "http_status": row.get("http_status"),
                        "error": row.get("error"),
                    }
                    for row in rows
                },
                "provenance": {
                    "reference_map": "Mapa Multimodal Pará - Ministério dos Transportes",
                    "reference_map_updated": "2023-09-22",
                    "note": "Catalog follows agencies cited in the official multimodal map: DNIT, ANTAQ, ANAC and IBGE.",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"catalog": catalog_path, "status": status_path}
