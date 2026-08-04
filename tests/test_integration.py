from pathlib import Path

import pandas as pd

from empriority.integration import aggregate_police, build_integrated_matrix, reshape_indicator


def test_reshape_long_indicator() -> None:
    frame = pd.DataFrame(
        {
            "D1C": ["1500107", "1500107"],
            "D1N": ["Abaetetuba", "Abaetetuba"],
            "D2N": ["Population", "Density"],
            "V": ["100", "2.5"],
        }
    )
    result = reshape_indicator(frame, "demography")
    assert result.loc[0, "municipality_code"] == "1500107"
    assert "demography__population" in result.columns
    assert "demography__density" in result.columns


def test_aggregate_police() -> None:
    frame = pd.DataFrame(
        {
            "municipality_code": ["1500107", "1500107"],
            "municipality": ["Abaetetuba", "Abaetetuba"],
            "year": [2022, 2023],
            "occurrence_type": ["Ameaça", "Lesão corporal"],
            "records": [3, 2],
        }
    )
    result = aggregate_police(frame)
    assert result.loc[0, "police_ameaca"] == 3
    assert result.loc[0, "police_lesao_corporal"] == 2
    assert result.loc[0, "police_years_observed"] == 2


def test_build_integrated_matrix(tmp_path: Path) -> None:
    municipalities = tmp_path / "municipalities.csv"
    indicator = tmp_path / "indicator.csv"
    output = tmp_path / "matrix.csv"
    pd.DataFrame(
        {"municipality_code": ["1500107"], "municipality": ["Abaetetuba"]}
    ).to_csv(municipalities, index=False)
    pd.DataFrame(
        {
            "D1C": ["1500107"],
            "D1N": ["Abaetetuba"],
            "D2N": ["Population"],
            "V": ["100"],
        }
    ).to_csv(indicator, index=False)

    path = build_integrated_matrix(
        municipalities,
        {"demography": indicator},
        output_path=output,
    )
    result = pd.read_csv(path)
    assert len(result) == 1
    assert result.loc[0, "demography__population"] == 100
