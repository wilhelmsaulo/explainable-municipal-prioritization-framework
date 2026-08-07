from pathlib import Path

import pandas as pd
import pytest

from dashboard.data import (
    EXPECTED_MUNICIPALITIES,
    EXPECTED_SCENARIOS,
    REFERENCE_SCENARIO,
    load_dashboard_data,
    scenario_label,
    selected_scenario,
    split_scenario,
)

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_contract_matches_audited_outputs():
    data = load_dashboard_data(ROOT)
    assert len(data.profiles) == EXPECTED_MUNICIPALITIES
    assert len(data.scenario_names) == EXPECTED_SCENARIOS
    assert REFERENCE_SCENARIO in data.scenario_names
    assert data.municipalities[["latitude", "longitude"]].notna().all().all()


def test_selected_scenario_preserves_published_scores_and_ranks():
    data = load_dashboard_data(ROOT)
    selected = selected_scenario(data.scenarios, REFERENCE_SCENARIO)
    assert selected["selected_score"].between(0, 1).all()
    assert set(selected["selected_rank"].astype(int)) == set(range(1, 145))


def test_scenario_parser_and_label():
    transport, weight = split_scenario(REFERENCE_SCENARIO)
    assert transport == "equal_modes__equal_roles"
    assert weight == "equal_dimensions"
    assert "Modos iguais" in scenario_label(REFERENCE_SCENARIO)


def test_invalid_scenario_is_rejected():
    frame = pd.DataFrame({"municipality_code": ["1"], "municipality": ["A"]})
    with pytest.raises(KeyError):
        selected_scenario(frame, "not_a_scenario")
