from __future__ import annotations

import hashlib
import json
import math
import time
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = (
    "explainable-municipal-prioritization-framework/1.0 "
    "(https://github.com/wilhelmsaulo/explainable-municipal-prioritization-framework)"
)
EARTH_RADIUS_KM = 6371.0088

DISTANCE_GROUPS = {
    "any_public": [],
    "specialized_non_health": [
        "protection_network_specialized_police",
        "protection_network_specialized_judiciary",
        "protection_network_specialized_prosecution",
        "protection_network_specialized_defense",
        "protection_network_shelter",
        "protection_network_reference_center",
        "protection_network_maria_da_penha_patrol",
        "protection_network_women_policy_body",
    ],
    "specialized_police": ["protection_network_specialized_police"],
    "justice": [
        "protection_network_specialized_judiciary",
        "protection_network_specialized_prosecution",
        "protection_network_specialized_defense",
    ],
    "shelter": ["protection_network_shelter"],
    "reference_center": ["protection_network_reference_center"],
    "health": ["protection_network_health_service"],
}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _query_key(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _geocode(
    client: httpx.Client, query: str, cache: dict[str, Any], delay: float = 1.1
) -> dict[str, Any] | None:
    key = _query_key(query)
    if key in cache:
        return cache[key]

    result: dict[str, Any] | None = None
    for attempt in range(3):
        try:
            response = client.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": 1,
                    "countrycodes": "br",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload:
                item = payload[0]
                result = {
                    "query": query,
                    "latitude": float(item["lat"]),
                    "longitude": float(item["lon"]),
                    "display_name": item.get("display_name"),
                    "importance": item.get("importance"),
                    "type": item.get("type"),
                    "class": item.get("class"),
                    "address": item.get("address", {}),
                    "osm_type": item.get("osm_type"),
                    "osm_id": item.get("osm_id"),
                }
                break
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                result = {"query": query, "error": f"{type(exc).__name__}: {exc}"}
            else:
                time.sleep(2 * (attempt + 1))
        finally:
            time.sleep(delay)

    cache[key] = result
    return result


def _confidence(result: dict[str, Any] | None, municipality: str) -> tuple[str, str]:
    if not result or result.get("error") or result.get("latitude") is None:
        return "unmatched", "No geocoding result"
    display = _norm(result.get("display_name"))
    address = result.get("address") or {}
    state = _norm(address.get("state"))
    city_values = " ".join(
        _norm(address.get(field)) for field in ("city", "town", "municipality", "county", "village")
    )
    municipality_key = _norm(municipality)
    para_match = state in {"para", "estado do para"} or " para " in f" {display} "
    municipality_match = municipality_key in city_values or municipality_key in display
    if para_match and municipality_match:
        return "high", "Municipality and Pará matched"
    if para_match:
        return "medium", "Pará matched; municipality not explicit"
    return "low", "Result did not clearly match Pará"


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _group_mask(services: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series(True, index=services.index)
    existing = [column for column in columns if column in services.columns]
    if not existing:
        return pd.Series(False, index=services.index)
    numeric = services[existing].apply(pd.to_numeric, errors="coerce").fillna(0)
    return numeric.gt(0).any(axis=1)


def build_protection_network_geospatial(
    records_path: str | Path = "data/processed/protection_network_records_normalized_pa.csv",
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
    cache_path: str | Path = "data/cache/nominatim_protection_network.json",
) -> dict[str, Path]:
    records_path = Path(records_path)
    matrix_path = Path(matrix_path)
    output = Path(output_directory)
    cache_path = Path(cache_path)
    output.mkdir(parents=True, exist_ok=True)

    records = pd.read_csv(records_path, dtype={"municipality_code": str})
    matrix = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    if len(matrix) != 144 or matrix["municipality_code"].nunique() != 144:
        raise AssertionError("Integrated matrix must contain exactly 144 unique municipalities")

    address_column = "Endereço do Serviço"
    name_column = "Nome do Serviço"
    records["_address"] = (
        records.get(address_column, pd.Series(index=records.index, dtype=object))
        .fillna("")
        .astype(str)
        .str.strip()
    )
    records["_public"] = (
        pd.to_numeric(records.get("protection_network_public_address"), errors="coerce")
        .fillna(0)
        .eq(1)
        & records["_address"].ne("")
        & records["_address"].str.upper().ne("SIGILOSO")
    )
    services = records.loc[records["_public"]].copy().reset_index(drop=True)
    services.insert(0, "service_id", [f"L180-PA-{index + 1:03d}" for index in range(len(services))])

    cache = _load_cache(cache_path)
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}
    geocoded_rows: list[dict[str, Any]] = []
    seats: list[dict[str, Any]] = []

    with httpx.Client(timeout=45.0, follow_redirects=True, headers=headers) as client:
        for index, row in services.iterrows():
            municipality = str(row["municipality"])
            service_name = str(row.get(name_column, ""))
            address = str(row["_address"])
            queries = [
                f"{service_name}, {address}, {municipality}, Pará, Brasil",
                f"{address}, {municipality}, Pará, Brasil",
                f"{service_name}, {municipality}, Pará, Brasil",
            ]
            selected = None
            selected_query = None
            for query in queries:
                candidate = _geocode(client, query, cache)
                if candidate and candidate.get("latitude") is not None:
                    selected = candidate
                    selected_query = query
                    break
            confidence, note = _confidence(selected, municipality)
            record = row.drop(labels=["_address", "_public"]).to_dict()
            record.update(
                {
                    "geocoding_query": selected_query,
                    "latitude": selected.get("latitude") if selected else None,
                    "longitude": selected.get("longitude") if selected else None,
                    "geocoding_display_name": selected.get("display_name") if selected else None,
                    "geocoding_importance": selected.get("importance") if selected else None,
                    "geocoding_confidence": confidence,
                    "geocoding_note": note,
                    "geocoding_source": "OpenStreetMap Nominatim",
                }
            )
            geocoded_rows.append(record)
            if (index + 1) % 20 == 0:
                _save_cache(cache_path, cache)
                print(f"Public services geocoded: {index + 1}/{len(services)}", flush=True)

        for index, row in matrix[["municipality_code", "municipality"]].iterrows():
            query = f"{row['municipality']}, Pará, Brasil"
            result = _geocode(client, query, cache)
            confidence, note = _confidence(result, str(row["municipality"]))
            seats.append(
                {
                    "municipality_code": row["municipality_code"],
                    "municipality": row["municipality"],
                    "seat_query": query,
                    "seat_latitude": result.get("latitude") if result else None,
                    "seat_longitude": result.get("longitude") if result else None,
                    "seat_geocoding_confidence": confidence,
                    "seat_geocoding_note": note,
                    "seat_display_name": result.get("display_name") if result else None,
                }
            )
            if (index + 1) % 30 == 0:
                _save_cache(cache_path, cache)
                print(f"Municipal seats geocoded: {index + 1}/144", flush=True)

    _save_cache(cache_path, cache)
    geocoded = pd.DataFrame(geocoded_rows)
    seats_df = pd.DataFrame(seats)

    accepted = geocoded[
        geocoded["geocoding_confidence"].isin(["high", "medium"])
        & geocoded["latitude"].notna()
        & geocoded["longitude"].notna()
    ].copy()
    review = geocoded[~geocoded.index.isin(accepted.index)].copy()

    features = []
    for _, row in accepted.iterrows():
        properties = {
            "service_id": row["service_id"],
            "municipality_code": row["municipality_code"],
            "municipality": row["municipality"],
            "service_name": row.get(name_column),
            "category": row.get("Categoria Padronizada"),
            "address": row.get(address_column),
            "confidence": row["geocoding_confidence"],
            "source": "Painel Ligue 180 / OpenStreetMap Nominatim",
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["longitude"]), float(row["latitude"])],
                },
                "properties": properties,
            }
        )
    geojson = {"type": "FeatureCollection", "features": features}

    accessibility_rows: list[dict[str, Any]] = []
    for _, seat in seats_df.iterrows():
        item: dict[str, Any] = {
            "municipality_code": seat["municipality_code"],
            "municipality": seat["municipality"],
            "protection_network_seat_latitude": seat["seat_latitude"],
            "protection_network_seat_longitude": seat["seat_longitude"],
            "protection_network_seat_geocoding_confidence": seat["seat_geocoding_confidence"],
        }
        valid_seat = pd.notna(seat["seat_latitude"]) and pd.notna(seat["seat_longitude"])
        for group, columns in DISTANCE_GROUPS.items():
            subset = accepted.loc[_group_mask(accepted, columns)]
            distance_column = f"protection_network_nearest_{group}_km"
            service_column = f"protection_network_nearest_{group}_service_id"
            if not valid_seat or subset.empty:
                item[distance_column] = pd.NA
                item[service_column] = pd.NA
                continue
            distances = subset.apply(
                lambda service: _haversine(
                    float(seat["seat_latitude"]),
                    float(seat["seat_longitude"]),
                    float(service["latitude"]),
                    float(service["longitude"]),
                ),
                axis=1,
            )
            nearest_index = distances.idxmin()
            item[distance_column] = float(distances.loc[nearest_index])
            item[service_column] = subset.loc[nearest_index, "service_id"]
        accessibility_rows.append(item)

    accessibility = pd.DataFrame(accessibility_rows)
    distance_columns = [column for column in accessibility.columns if column.endswith("_km")]
    old_columns = [
        column
        for column in matrix.columns
        if column.startswith("protection_network_nearest_")
        or column.startswith("protection_network_seat_")
    ]
    if old_columns:
        matrix = matrix.drop(columns=old_columns)
    matrix = matrix.merge(
        accessibility.drop(columns=["municipality"], errors="ignore"),
        on="municipality_code",
        how="left",
    )
    assert len(matrix) == 144
    assert matrix["municipality_code"].nunique() == 144

    geocoded_path = output / "protection_network_services_geocoded_pa.csv"
    review_path = output / "protection_network_geocoding_review_pa.csv"
    seats_path = output / "municipal_seats_geocoded_pa.csv"
    accessibility_path = output / "protection_network_accessibility_pa.csv"
    geojson_path = output / "protection_network_services_pa.geojson"
    metadata_path = output / "protection_network_geospatial.metadata.json"

    geocoded.to_csv(geocoded_path, index=False, encoding="utf-8")
    review.to_csv(review_path, index=False, encoding="utf-8")
    seats_df.to_csv(seats_path, index=False, encoding="utf-8")
    accessibility.to_csv(accessibility_path, index=False, encoding="utf-8")
    geojson_path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    matrix.to_csv(matrix_path, index=False, encoding="utf-8")

    metadata = {
        "service_source": "Painel da Rede de Atendimento à Mulher - Ligue 180 / Ministério das Mulheres",
        "geocoder": "OpenStreetMap Nominatim",
        "distance_method": "Great-circle (Haversine) distance from municipal seat; not road/travel distance",
        "public_services_submitted": int(len(services)),
        "services_accepted_high_or_medium": int(len(accepted)),
        "services_requiring_review": int(len(review)),
        "confidential_addresses_geocoded": 0,
        "municipalities": int(len(accessibility)),
        "distance_columns": distance_columns,
        "methodological_caution": "Coordinates with low confidence are excluded from distance calculations. Confidential shelter addresses are never submitted to the geocoder or written to GeoJSON.",
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return {
        "geocoded_services": geocoded_path,
        "review": review_path,
        "municipal_seats": seats_path,
        "accessibility": accessibility_path,
        "geojson": geojson_path,
        "metadata": metadata_path,
        "matrix": matrix_path,
        "cache": cache_path,
    }
