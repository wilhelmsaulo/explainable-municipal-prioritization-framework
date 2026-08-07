from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_shapefile(archive_path: Path, output_dir: Path) -> Path:
    if not zipfile.is_zipfile(archive_path):
        raise ValueError(f"Invalid ZIP archive: {archive_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(output_dir)
    shapefiles = sorted(output_dir.rglob("*.shp"))
    if len(shapefiles) != 1:
        raise ValueError(
            f"Expected one shapefile in {archive_path}, found {len(shapefiles)}"
        )
    return shapefiles[0]


def _column(frame: Any, *candidates: str) -> str:
    normalized = {
        unicodedata.normalize("NFKD", str(name))
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .replace(" ", "")
        .replace("_", ""): str(name)
        for name in frame.columns
    }
    for candidate in candidates:
        key = (
            unicodedata.normalize("NFKD", candidate)
            .encode("ascii", "ignore")
            .decode()
            .lower()
            .replace(" ", "")
            .replace("_", "")
        )
        if key in normalized:
            return normalized[key]
    raise ValueError(f"None of the expected columns exists: {candidates}")


def _parse_coordinate(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().upper().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        pass
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text)]
    if not numbers:
        return None
    coordinate = numbers[0]
    if len(numbers) > 1:
        coordinate += numbers[1] / 60
    if len(numbers) > 2:
        coordinate += numbers[2] / 3600
    if "S" in text or "W" in text or "O" in text:
        coordinate *= -1
    return coordinate


def _load_anac_points(csv_path: Path) -> Any:
    import geopandas as gpd
    import pandas as pd

    frame = None
    for encoding in ("utf-8-sig", "latin1"):
        try:
            frame = pd.read_csv(csv_path, sep=None, engine="python", encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if frame is None:
        raise ValueError("Unable to decode the ANAC public-aerodrome CSV")

    latitude = _column(frame, "Latitude", "LATGEOPOINT", "LATITUDE_DECIMAL")
    longitude = _column(frame, "Longitude", "LONGEOPOINT", "LONGITUDE_DECIMAL")
    frame["_latitude"] = frame[latitude].map(_parse_coordinate)
    frame["_longitude"] = frame[longitude].map(_parse_coordinate)
    frame = frame.dropna(subset=["_latitude", "_longitude"]).copy()
    geometry = gpd.points_from_xy(frame["_longitude"], frame["_latitude"])
    return gpd.GeoDataFrame(frame, geometry=geometry, crs="EPSG:4326")


def _municipalities(archive_path: Path, cache: Path) -> Any:
    import geopandas as gpd

    shape_path = _extract_shapefile(archive_path, cache)
    frame = gpd.read_file(shape_path)
    code = _column(frame, "CD_MUN", "CD_GEOCMU", "municipality_code")
    name = _column(frame, "NM_MUN", "NM_MUNICIP", "municipality")
    frame = frame[[code, name, "geometry"]].rename(
        columns={code: "municipality_code", name: "municipality"}
    )
    frame["municipality_code"] = (
        frame["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    frame = frame[frame["municipality_code"].str.startswith("15")].copy()
    if len(frame) != 144 or frame["municipality_code"].nunique() != 144:
        raise ValueError("The IBGE boundary input does not contain 144 unique Para municipalities")
    return frame


def _point_metrics(
    result: Any,
    points: Any,
    municipalities: Any,
    prefix: str,
    projected_crs: str,
) -> Any:
    import geopandas as gpd

    local = points.to_crs(municipalities.crs)
    local = local[local.geometry.notna() & ~local.geometry.is_empty].copy()
    if not local.geom_type.isin(["Point", "MultiPoint"]).all():
        local["geometry"] = local.geometry.centroid
    assigned = gpd.sjoin(
        local[["geometry"]],
        municipalities[["municipality_code", "geometry"]],
        how="inner",
        predicate="intersects",
    )
    counts = assigned.groupby("municipality_code").size().rename(f"{prefix}_count")
    result = result.merge(counts, on="municipality_code", how="left")
    result[f"{prefix}_count"] = result[f"{prefix}_count"].fillna(0).astype(int)
    result[f"{prefix}_presence"] = result[f"{prefix}_count"].gt(0).astype(int)

    projected_points = local.to_crs(projected_crs)
    union = projected_points.geometry.union_all()
    reference = municipalities.to_crs(projected_crs).geometry.representative_point()
    distances = reference.distance(union) / 1000
    distance_by_code = dict(zip(municipalities["municipality_code"], distances))
    result[f"distance_to_{prefix}_km"] = result["municipality_code"].map(distance_by_code)
    return result


def _line_metrics(
    result: Any,
    lines: Any,
    municipalities: Any,
    prefix: str,
    projected_crs: str,
) -> tuple[Any, int]:
    import geopandas as gpd

    local = lines.to_crs(municipalities.crs)
    minx, miny, maxx, maxy = municipalities.total_bounds
    local = local.cx[minx:maxx, miny:maxy].copy()
    local = local[local.geometry.notna() & ~local.geometry.is_empty].copy()
    local = local[local.geometry.is_valid].copy()
    intersections = gpd.overlay(
        local[["geometry"]],
        municipalities[["municipality_code", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    ).to_crs(projected_crs)
    intersections["length_km"] = intersections.geometry.length / 1000
    lengths = intersections.groupby("municipality_code")["length_km"].sum()
    result[f"{prefix}_km"] = result["municipality_code"].map(lengths).fillna(0.0)
    result[f"{prefix}_presence"] = result[f"{prefix}_km"].gt(0).astype(int)

    projected = local.to_crs(projected_crs)
    union = projected.geometry.union_all()
    reference = municipalities.to_crs(projected_crs).geometry.representative_point()
    distances = reference.distance(union) / 1000
    distance_by_code = dict(zip(municipalities["municipality_code"], distances))
    result[f"distance_to_{prefix}_km"] = result["municipality_code"].map(distance_by_code)
    return result, int(len(intersections))


def build_nonroad_transport_indicators(
    ports_zip: str | Path,
    crossings_zip: str | Path,
    waterways_zip: str | Path,
    decea_airports_zip: str | Path,
    anac_public_csv: str | Path,
    municipalities_zip: str | Path,
    output_csv: str | Path = "data/processed/transport/nonroad_indicators_pa.csv",
    audit_json: str | Path = "data/processed/transport/nonroad_indicators_pa_audit.json",
    work_dir: str | Path = "data/cache/nonroad_transport",
) -> dict[str, Path]:
    import geopandas as gpd

    inputs = {
        "ports": Path(ports_zip),
        "crossings": Path(crossings_zip),
        "waterways": Path(waterways_zip),
        "decea_airports": Path(decea_airports_zip),
        "anac_public": Path(anac_public_csv),
        "municipalities": Path(municipalities_zip),
    }
    cache = Path(work_dir)
    municipalities = _municipalities(inputs["municipalities"], cache / "municipalities")
    projected_crs = "EPSG:5880"

    ports = gpd.read_file(_extract_shapefile(inputs["ports"], cache / "ports"))
    crossings = gpd.read_file(
        _extract_shapefile(inputs["crossings"], cache / "crossings")
    )
    waterways = gpd.read_file(
        _extract_shapefile(inputs["waterways"], cache / "waterways")
    )
    decea = gpd.read_file(
        _extract_shapefile(inputs["decea_airports"], cache / "decea")
    )
    anac = _load_anac_points(inputs["anac_public"])

    result = municipalities[["municipality_code", "municipality"]].copy()
    result = _point_metrics(result, ports, municipalities, "port", projected_crs)
    result = _point_metrics(
        result,
        anac,
        municipalities,
        "public_aerodrome",
        projected_crs,
    )
    result = _point_metrics(
        result,
        decea,
        municipalities,
        "decea_airport",
        projected_crs,
    )
    result, crossing_features = _line_metrics(
        result,
        crossings,
        municipalities,
        "passenger_crossing",
        projected_crs,
    )
    result, waterway_features = _line_metrics(
        result,
        waterways,
        municipalities,
        "navigated_waterway",
        projected_crs,
    )

    numeric = result.select_dtypes(include="number").columns
    result[numeric] = result[numeric].round(6)
    result = result.sort_values("municipality_code").reset_index(drop=True)

    output_path = Path(output_csv)
    audit_path = Path(audit_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8")

    checks = {
        "rows_144": len(result) == 144,
        "unique_codes_144": result["municipality_code"].nunique() == 144,
        "all_codes_para": bool(result["municipality_code"].str.startswith("15").all()),
        "no_missing_numeric": bool(result[numeric].notna().all().all()),
        "nonnegative_metrics": bool(result[numeric].ge(0).all().all()),
        "ports_present": int(result["port_count"].sum()) > 0,
        "public_aerodromes_present": int(result["public_aerodrome_count"].sum()) > 0,
        "waterways_present": float(result["navigated_waterway_km"].sum()) > 0,
    }
    audit = {
        "sources": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in inputs.items()
        },
        "reference_years": {
            "ports_and_crossings": 2025,
            "navigated_waterways": 2022,
            "anac_public_aerodromes": 2026,
            "decea_airports": 2026,
            "municipal_boundaries": 2023,
        },
        "rows": len(result),
        "unique_municipality_codes": int(result["municipality_code"].nunique()),
        "totals": {
            "ports": int(result["port_count"].sum()),
            "public_aerodromes": int(result["public_aerodrome_count"].sum()),
            "decea_airports": int(result["decea_airport_count"].sum()),
            "passenger_crossing_km": float(result["passenger_crossing_km"].sum()),
            "navigated_waterway_km": float(result["navigated_waterway_km"].sum()),
            "crossing_intersections": crossing_features,
            "waterway_intersections": waterway_features,
        },
        "checks": checks,
        "limitations": [
            "Distances use a representative point inside each municipal polygon.",
            "ANTAQ navigated-waterway geometry represents the published 2022 layer.",
            "ANAC public aerodromes and DECEA operational airports remain separate.",
            "No multimodal composite is calculated before indicator-level audit.",
        ],
    }
    if not all(checks.values()):
        raise ValueError(f"Non-road transport audit failed: {checks}")
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"indicators": output_path, "audit": audit_path}
