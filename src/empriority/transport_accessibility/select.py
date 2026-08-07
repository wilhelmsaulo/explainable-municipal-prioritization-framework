from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from empriority.transport_accessibility.integrate import VARIABLES


SELECTION: dict[str, dict[str, str]] = {
    "road_density_km_per_1000_km2": {
        "component": "road",
        "role": "availability",
        "polarity": "benefit",
        "rationale": "Area-adjusted road-network availability avoids raw municipal-size effects.",
    },
    "distance_to_mapped_road_km": {
        "component": "road",
        "role": "proximity",
        "polarity": "cost",
        "rationale": "Continuous measure of spatial separation from the mapped road network.",
    },
    "port_presence": {
        "component": "port",
        "role": "availability",
        "polarity": "benefit",
        "rationale": "Transparent local-availability measure; chosen instead of the highly skewed count.",
    },
    "distance_to_port_km": {
        "component": "port",
        "role": "proximity",
        "polarity": "cost",
        "rationale": "Continuous measure of access barrier to the nearest port facility.",
    },
    "passenger_crossing_presence": {
        "component": "passenger_crossing",
        "role": "availability",
        "polarity": "benefit",
        "rationale": "Local crossing availability; chosen instead of raw line length.",
    },
    "distance_to_passenger_crossing_km": {
        "component": "passenger_crossing",
        "role": "proximity",
        "polarity": "cost",
        "rationale": "Continuous measure of access barrier to a passenger-crossing line.",
    },
    "navigated_waterway_presence": {
        "component": "navigated_waterway",
        "role": "availability",
        "polarity": "benefit",
        "rationale": "Local navigated-waterway availability; chosen instead of raw segment length.",
    },
    "distance_to_navigated_waterway_km": {
        "component": "navigated_waterway",
        "role": "proximity",
        "polarity": "cost",
        "rationale": "Continuous measure of access barrier to a published navigated waterway.",
    },
    "decea_airport_presence": {
        "component": "air",
        "role": "availability",
        "polarity": "benefit",
        "rationale": "Transparent local airport availability; chosen instead of the correlated count.",
    },
    "distance_to_decea_airport_km": {
        "component": "air",
        "role": "proximity",
        "polarity": "cost",
        "rationale": "Continuous measure of spatial access barrier to the nearest DECEA/ICA airport.",
    },
}

EXCLUSION_REASONS: dict[str, str] = {
    "road_federal_km": "Raw contextual length and part of the constructed road total.",
    "road_state_km": "Raw contextual length and part of the constructed road total.",
    "road_other_km": "Raw contextual length, part of road total, and highly correlated with it.",
    "road_paved_km": "Raw contextual length affected by municipal extent; retain for sensitivity analysis.",
    "road_unpaved_km": "Raw contextual length affected by municipal extent; retain for sensitivity analysis.",
    "road_total_km": "Constructed sum of network classes and affected by municipal extent.",
    "road_mapped_presence": "Less informative than the retained continuous road density and distance measures.",
    "road_federal_presence": "Correlated with federal-road length and narrower than overall road accessibility.",
    "road_state_presence": "Narrower network-class indicator; retain for sensitivity analysis.",
    "municipality_area_km2": "Territorial denominator/context, not an accessibility indicator.",
    "port_count": "Deterministically linked to port presence and strongly right-skewed.",
    "decea_airport_count": "Deterministically linked to airport presence and correlated with it.",
    "passenger_crossing_km": "Deterministically linked to crossing presence and nearly perfectly correlated with it.",
    "navigated_waterway_km": "Deterministically linked to waterway presence and strongly correlated with it.",
}


def select_transport_indicators(
    matrix_csv: str | Path,
    redundancy_json: str | Path,
    output_csv: str | Path = "data/processed/transport/transport_indicators_pa_selected.csv",
    selection_json: str | Path = "data/processed/transport/transport_indicator_selection.json",
    audit_json: str | Path = "data/processed/transport/transport_indicator_selection_audit.json",
) -> dict[str, Path]:
    matrix_path = Path(matrix_csv)
    redundancy_path = Path(redundancy_json)
    frame = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    redundancy = json.loads(redundancy_path.read_text(encoding="utf-8"))

    selected_variables = list(SELECTION)
    excluded_variables = list(EXCLUSION_REASONS)
    all_variables = set(VARIABLES)
    selected_set = set(selected_variables)
    excluded_set = set(excluded_variables)

    retained_high_pairs = [
        pair
        for pair in redundancy["high_correlation_pairs"]
        if pair["left"] in selected_set and pair["right"] in selected_set
    ]
    selected = frame[["municipality_code", "municipality", *selected_variables]].copy()

    checks = {
        "rows_144": len(selected) == 144,
        "unique_codes_144": selected["municipality_code"].nunique() == 144,
        "selected_variables_10": len(selected_variables) == 10,
        "complete_partition_of_24": (
            selected_set | excluded_set == all_variables
            and not selected_set.intersection(excluded_set)
        ),
        "no_missing": bool(selected[selected_variables].notna().all().all()),
        "nonnegative": bool(selected[selected_variables].ge(0).all().all()),
        "five_components": len({item["component"] for item in SELECTION.values()}) == 5,
        "availability_and_proximity_per_component": all(
            {
                item["role"]
                for item in SELECTION.values()
                if item["component"] == component
            }
            == {"availability", "proximity"}
            for component in {item["component"] for item in SELECTION.values()}
        ),
        "no_high_correlation_pair_retained": not retained_high_pairs,
    }
    if not all(checks.values()):
        raise ValueError(f"Transport selection audit failed: {checks}")

    output_path = Path(output_csv)
    selection_path = Path(selection_json)
    audit_path = Path(audit_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output_path, index=False, encoding="utf-8")

    component_structure: dict[str, list[str]] = {}
    for variable, metadata in SELECTION.items():
        component_structure.setdefault(metadata["component"], []).append(variable)

    selection_document: dict[str, Any] = {
        "schema_version": "1.0",
        "selection_principles": [
            "Retain one local-availability and one continuous-proximity indicator per component.",
            "Exclude raw contextual lengths and municipal area from direct accessibility scoring.",
            "Avoid deterministic count/presence and length/presence duplication.",
            "Preserve excluded variables in the integrated matrix for sensitivity analysis.",
            "Use hierarchical aggregation so components and modes, not variable counts, determine influence.",
        ],
        "selected_count": len(selected_variables),
        "selected": {
            variable: {
                **SELECTION[variable],
                "source_direction": VARIABLES[variable]["direction"],
                "unit": VARIABLES[variable]["unit"],
                "year": VARIABLES[variable]["year"],
            }
            for variable in selected_variables
        },
        "component_structure": component_structure,
        "excluded": EXCLUSION_REASONS,
        "aggregation_constraint": {
            "required": True,
            "reason": "Water transport has three components while road and air have one each; flat aggregation would implicitly overweight water indicators.",
            "proposed_levels": [
                "indicator",
                "component",
                "mode",
                "multimodal transport construct",
            ],
            "weights_defined": False,
        },
        "normalization_applied": False,
        "weights_applied": False,
        "composite_score_created": False,
    }
    selection_path.write_text(
        json.dumps(selection_document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    audit = {
        "rows": len(selected),
        "columns": len(selected.columns),
        "selected_variables": selected_variables,
        "excluded_variables": excluded_variables,
        "retained_high_correlation_pairs": retained_high_pairs,
        "checks": checks,
        "limitations": [
            "Selection is theory- and screening-informed, not an optimization result.",
            "Facility presence does not represent service frequency, capacity, quality, or affordability.",
            "Selected indicators retain different official reference years.",
            "No normalization, weighting, aggregation, or final score is calculated at this stage.",
        ],
    }
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "selected_matrix": output_path,
        "selection": selection_path,
        "audit": audit_path,
    }
