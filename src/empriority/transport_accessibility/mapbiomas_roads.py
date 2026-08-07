from __future__ import annotations

import hashlib
import json
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
            f"Expected exactly one shapefile in {archive_path}, found {len(shapefiles)}"
        )
    return shapefiles[0]


def _column(frame: Any, *candidates: str) -> str:
    lookup = {str(name).lower(): str(name) for name in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    raise ValueError(f"None of the expected columns exists: {candidates}")


def build_mapbiomas_road_indicators(
    state_roads_zip: str | Path,
    federal_roads_zip: str | Path,
    other_roads_zip: str | Path,
    municipalities_zip: str | Path,
    output_csv: str | Path = "data/processed/transport/road_indicators_pa_2023.csv",
    audit_json: str | Path = "data/processed/transport/road_indicators_pa_2023_audit.json",
    work_dir: str | Path = "data/cache/transport_roads",
) -> dict[str, Path]:
    import geopandas as gpd
    import pandas as pd

    state_archive = Path(state_roads_zip)
    federal_archive = Path(federal_roads_zip)
    other_archive = Path(other_roads_zip)
    municipal_archive = Path(municipalities_zip)
    cache = Path(work_dir)

    state_path = _extract_shapefile(state_archive, cache / "state")
    federal_path = _extract_shapefile(federal_archive, cache / "federal")
    other_path = _extract_shapefile(other_archive, cache / "other")
    municipal_path = _extract_shapefile(municipal_archive, cache / "municipalities")

    state = gpd.read_file(state_path)
    federal = gpd.read_file(federal_path)
    other = gpd.read_file(other_path)
    municipalities = gpd.read_file(municipal_path)

    code_col = _column(municipalities, "CD_MUN", "CD_GEOCMU", "municipality_code")
    name_col = _column(municipalities, "NM_MUN", "NM_MUNICIP", "municipality_name")
    municipalities = municipalities[[code_col, name_col, "geometry"]].rename(
        columns={code_col: "municipality_code", name_col: "municipality"}
    )
    municipalities["municipality_code"] = (
        municipalities["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    municipalities = municipalities[
        municipalities["municipality_code"].str.startswith("15")
    ].copy()

    if len(municipalities) != 144:
        raise ValueError(f"Expected 144 Para municipalities, found {len(municipalities)}")
    if municipalities["municipality_code"].nunique() != 144:
        raise ValueError("Municipality codes are not unique")

    target_crs = municipalities.crs
    if target_crs is None:
        raise ValueError("Municipality boundary CRS is missing")

    road_frames = []
    for network_class, frame in (
        ("state", state),
        ("federal", federal),
        ("other", other),
    ):
        if frame.crs is None:
            raise ValueError(f"{network_class} road CRS is missing")
        local = frame.to_crs(target_crs).copy()
        local["network_class"] = network_class
        road_frames.append(local)

    roads = gpd.GeoDataFrame(
        pd.concat(road_frames, ignore_index=True),
        geometry="geometry",
        crs=target_crs,
    )
    minx, miny, maxx, maxy = municipalities.total_bounds
    roads = roads.cx[minx:maxx, miny:maxy].copy()
    roads = roads[roads.geometry.notna() & ~roads.geometry.is_empty].copy()
    roads = roads[roads.geometry.is_valid].copy()

    revest_col = _column(roads, "revestimen", "revestimento")
    roads["surface_class"] = "other"
    surface = roads[revest_col].fillna("").astype(str).str.lower()
    roads.loc[surface.str.contains("pavimentado", regex=False), "surface_class"] = "paved"
    roads.loc[
        surface.str.contains("prim\\u00e1rio|primario|sem revestimento", regex=True),
        "surface_class",
    ] = "unpaved"

    intersections = gpd.overlay(
        roads[["network_class", "surface_class", "geometry"]],
        municipalities[["municipality_code", "municipality", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    projected_crs = "EPSG:5880"
    municipal_projected = municipalities.to_crs(projected_crs)
    intersections = intersections.to_crs(projected_crs)
    intersections["length_km"] = intersections.geometry.length / 1000.0

    grouped = (
        intersections.groupby(
            ["municipality_code", "network_class", "surface_class"],
            as_index=False,
        )["length_km"]
        .sum()
    )
    result = municipalities[["municipality_code", "municipality"]].copy()

    def add_length(name: str, mask: Any) -> None:
        values = (
            grouped.loc[mask]
            .groupby("municipality_code")["length_km"]
            .sum()
            .rename(name)
        )
        nonlocal result
        result = result.merge(values, on="municipality_code", how="left")

    add_length("road_federal_km", grouped["network_class"].eq("federal"))
    add_length("road_state_km", grouped["network_class"].eq("state"))
    add_length("road_other_km", grouped["network_class"].eq("other"))
    add_length("road_paved_km", grouped["surface_class"].eq("paved"))
    add_length("road_unpaved_km", grouped["surface_class"].eq("unpaved"))

    length_columns = [
        "road_federal_km",
        "road_state_km",
        "road_other_km",
        "road_paved_km",
        "road_unpaved_km",
    ]
    result[length_columns] = result[length_columns].fillna(0.0)
    result["road_total_km"] = (
        result["road_federal_km"]
        + result["road_state_km"]
        + result["road_other_km"]
    )
    result["road_structured_presence"] = result["road_total_km"].gt(0).astype(int)
    result["road_federal_presence"] = result["road_federal_km"].gt(0).astype(int)
    result["road_state_presence"] = result["road_state_km"].gt(0).astype(int)

    areas = municipal_projected.set_index("municipality_code").geometry.area / 1_000_000
    result["municipality_area_km2"] = result["municipality_code"].map(areas)
    result["road_density_km_per_1000_km2"] = (
        result["road_total_km"] / result["municipality_area_km2"] * 1000.0
    )

    road_union = intersections.geometry.union_all()
    reference_points = municipal_projected.geometry.representative_point()
    distances = reference_points.distance(road_union) / 1000.0
    distance_by_code = dict(zip(municipal_projected["municipality_code"], distances))
    result["distance_to_structured_road_km"] = result["municipality_code"].map(
        distance_by_code
    )

    result = result.sort_values("municipality_code").reset_index(drop=True)
    numeric_columns = result.select_dtypes(include="number").columns
    result[numeric_columns] = result[numeric_columns].round(6)

    output_path = Path(output_csv)
    audit_path = Path(audit_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8")

    zero_road = result.loc[
        result["road_structured_presence"].eq(0),
        ["municipality_code", "municipality"],
    ].to_dict("records")
    audit = {
        "reference_year": 2023,
        "source": "MapBiomas infrastructure compilation",
        "rows": len(result),
        "unique_municipality_codes": int(result["municipality_code"].nunique()),
        "state_road_sha256": _sha256(state_archive),
        "federal_road_sha256": _sha256(federal_archive),
        "other_road_sha256": _sha256(other_archive),
        "municipality_boundary_sha256": _sha256(municipal_archive),
        "road_features_national": {
            "state": int(len(state)),
            "federal": int(len(federal)),
            "other": int(len(other)),
        },
        "road_features_para_bbox": int(len(roads)),
        "intersection_features": int(len(intersections)),
        "total_road_km": float(result["road_total_km"].sum()),
        "municipalities_with_structured_roads": int(
            result["road_structured_presence"].sum()
        ),
        "municipalities_without_structured_roads": zero_road,
        "checks": {
            "rows_144": len(result) == 144,
            "unique_codes_144": result["municipality_code"].nunique() == 144,
            "all_codes_para": bool(
                result["municipality_code"].str.startswith("15").all()
            ),
            "no_missing_numeric": bool(result[numeric_columns].notna().all().all()),
            "nonnegative_lengths": bool(result[length_columns].ge(0).all().all()),
        },
        "limitations": [
            "MapBiomas federal, state, and other road segments.",
            "No claim of complete municipal, local, or rural branch-road coverage.",
            "Lengths result from clipping national road geometry to 2023 IBGE boundaries.",
        ],
    }
    if not all(audit["checks"].values()):
        raise ValueError(f"Road-indicator audit failed: {audit['checks']}")
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"indicators": output_path, "audit": audit_path}
