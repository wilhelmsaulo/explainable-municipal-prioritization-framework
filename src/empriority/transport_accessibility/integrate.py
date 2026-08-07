from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


IDENTIFIERS = ["municipality_code", "municipality"]

VARIABLES: dict[str, dict[str, Any]] = {
    "road_federal_km": {"mode": "road", "year": 2023, "unit": "km", "direction": "context", "description": "Mapped federal-road length inside the municipality."},
    "road_state_km": {"mode": "road", "year": 2023, "unit": "km", "direction": "context", "description": "Mapped state-road length inside the municipality."},
    "road_other_km": {"mode": "road", "year": 2023, "unit": "km", "direction": "context", "description": "Other mapped road-segment length inside the municipality."},
    "road_paved_km": {"mode": "road", "year": 2023, "unit": "km", "direction": "context", "description": "Mapped paved-road length inside the municipality."},
    "road_unpaved_km": {"mode": "road", "year": 2023, "unit": "km", "direction": "context", "description": "Mapped unpaved-road length inside the municipality."},
    "road_total_km": {"mode": "road", "year": 2023, "unit": "km", "direction": "context", "description": "Total mapped road length inside the municipality."},
    "road_mapped_presence": {"mode": "road", "year": 2023, "unit": "binary", "direction": "access_positive", "description": "Presence of any mapped road segment."},
    "road_federal_presence": {"mode": "road", "year": 2023, "unit": "binary", "direction": "access_positive", "description": "Presence of a mapped federal-road segment."},
    "road_state_presence": {"mode": "road", "year": 2023, "unit": "binary", "direction": "access_positive", "description": "Presence of a mapped state-road segment."},
    "municipality_area_km2": {"mode": "territorial_context", "year": 2023, "unit": "km2", "direction": "context", "description": "Municipal polygon area used for density calculation."},
    "road_density_km_per_1000_km2": {"mode": "road", "year": 2023, "unit": "km_per_1000_km2", "direction": "access_positive", "description": "Mapped road density per 1,000 square kilometres."},
    "distance_to_mapped_road_km": {"mode": "road", "year": 2023, "unit": "km", "direction": "barrier_positive", "description": "Distance from the municipal representative point to the mapped road network."},
    "port_count": {"mode": "water", "year": 2025, "unit": "count", "direction": "access_positive", "description": "ANTAQ port facilities intersecting the municipality."},
    "port_presence": {"mode": "water", "year": 2025, "unit": "binary", "direction": "access_positive", "description": "Presence of at least one ANTAQ port facility."},
    "distance_to_port_km": {"mode": "water", "year": 2025, "unit": "km", "direction": "barrier_positive", "description": "Distance from the municipal representative point to the nearest ANTAQ port facility."},
    "decea_airport_count": {"mode": "air", "year": 2026, "unit": "count", "direction": "access_positive", "description": "DECEA/ICA airport features intersecting the municipality."},
    "decea_airport_presence": {"mode": "air", "year": 2026, "unit": "binary", "direction": "access_positive", "description": "Presence of at least one DECEA/ICA airport feature."},
    "distance_to_decea_airport_km": {"mode": "air", "year": 2026, "unit": "km", "direction": "barrier_positive", "description": "Distance from the municipal representative point to the nearest DECEA/ICA airport feature."},
    "passenger_crossing_km": {"mode": "water", "year": 2025, "unit": "km", "direction": "context", "description": "ANTAQ passenger-crossing line length inside the municipality."},
    "passenger_crossing_presence": {"mode": "water", "year": 2025, "unit": "binary", "direction": "access_positive", "description": "Presence of an ANTAQ passenger-crossing line."},
    "distance_to_passenger_crossing_km": {"mode": "water", "year": 2025, "unit": "km", "direction": "barrier_positive", "description": "Distance from the municipal representative point to the nearest passenger-crossing line."},
    "navigated_waterway_km": {"mode": "water", "year": 2022, "unit": "km", "direction": "context", "description": "ANTAQ navigated-waterway length inside the municipality."},
    "navigated_waterway_presence": {"mode": "water", "year": 2022, "unit": "binary", "direction": "access_positive", "description": "Presence of a published navigated-waterway segment."},
    "distance_to_navigated_waterway_km": {"mode": "water", "year": 2022, "unit": "km", "direction": "barrier_positive", "description": "Distance from the municipal representative point to the nearest published navigated waterway."},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_integrated_transport_matrix(
    road_csv: str | Path,
    nonroad_csv: str | Path,
    output_csv: str | Path = "data/processed/transport/transport_indicators_pa_integrated.csv",
    audit_json: str | Path = "data/processed/transport/transport_indicators_pa_integrated_audit.json",
    dictionary_json: str | Path = "data/processed/transport/transport_indicator_dictionary.json",
) -> dict[str, Path]:
    road_path = Path(road_csv)
    nonroad_path = Path(nonroad_csv)
    road = pd.read_csv(road_path, dtype={"municipality_code": str})
    nonroad = pd.read_csv(nonroad_path, dtype={"municipality_code": str})

    road_codes = set(road["municipality_code"])
    nonroad_codes = set(nonroad["municipality_code"])
    name_check = road[IDENTIFIERS].merge(
        nonroad[IDENTIFIERS],
        on="municipality_code",
        how="inner",
        suffixes=("_road", "_nonroad"),
    )
    names_match = bool(
        name_check["municipality_road"].eq(name_check["municipality_nonroad"]).all()
    )

    integrated = road.merge(
        nonroad.drop(columns=["municipality"]),
        on="municipality_code",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    merge_complete = bool(integrated["_merge"].eq("both").all())
    integrated = integrated.drop(columns=["_merge"]).sort_values(
        "municipality_code"
    ).reset_index(drop=True)

    expected_columns = IDENTIFIERS + list(VARIABLES)
    numeric = list(VARIABLES)
    unexpected_columns = sorted(set(integrated.columns) - set(expected_columns))
    missing_columns = sorted(set(expected_columns) - set(integrated.columns))

    checks = {
        "road_rows_144": len(road) == 144,
        "nonroad_rows_144": len(nonroad) == 144,
        "integrated_rows_144": len(integrated) == 144,
        "unique_codes_144": integrated["municipality_code"].nunique() == 144,
        "all_codes_para": bool(integrated["municipality_code"].str.startswith("15").all()),
        "same_code_sets": road_codes == nonroad_codes,
        "municipality_names_match": names_match,
        "merge_complete": merge_complete,
        "expected_columns_complete": not missing_columns,
        "no_unexpected_columns": not unexpected_columns,
        "no_missing_numeric": bool(integrated[numeric].notna().all().all()),
        "nonnegative_numeric": bool(integrated[numeric].ge(0).all().all()),
    }
    if not all(checks.values()):
        raise ValueError(f"Integrated transport audit failed: {checks}")

    output_path = Path(output_csv)
    audit_path = Path(audit_json)
    dictionary_path = Path(dictionary_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    integrated[expected_columns].to_csv(output_path, index=False, encoding="utf-8")

    dictionary = {
        "schema_version": "1.0",
        "identifiers": {
            "municipality_code": "Seven-digit IBGE municipality code.",
            "municipality": "IBGE municipality name.",
        },
        "direction_semantics": {
            "access_positive": "Higher values indicate more transport availability or proximity.",
            "barrier_positive": "Higher values indicate a larger spatial access barrier.",
            "context": "Descriptive variable; direction must not be assumed before modelling.",
        },
        "variables": VARIABLES,
    }
    dictionary_path.write_text(
        json.dumps(dictionary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    audit = {
        "rows": len(integrated),
        "columns": len(expected_columns),
        "transport_variables": len(VARIABLES),
        "sources": {
            "road_indicators": {
                "path": str(road_path),
                "sha256": _sha256(road_path),
            },
            "nonroad_indicators": {
                "path": str(nonroad_path),
                "sha256": _sha256(nonroad_path),
            },
        },
        "mode_counts": (
            pd.Series([item["mode"] for item in VARIABLES.values()])
            .value_counts()
            .sort_index()
            .to_dict()
        ),
        "direction_counts": (
            pd.Series([item["direction"] for item in VARIABLES.values()])
            .value_counts()
            .sort_index()
            .to_dict()
        ),
        "missing_columns": missing_columns,
        "unexpected_columns": unexpected_columns,
        "checks": checks,
        "limitations": [
            "The matrix integrates indicators with different official reference years.",
            "Raw lengths and municipal area are contextual and are not automatically interpreted as access.",
            "No normalization, weighting, aggregation, or multimodal score is calculated here.",
        ],
    }
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "matrix": output_path,
        "audit": audit_path,
        "dictionary": dictionary_path,
    }
