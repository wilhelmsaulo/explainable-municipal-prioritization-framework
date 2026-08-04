from __future__ import annotations

import pandas as pd

from empriority.mcda import run_hybrid_topsis


def test_hybrid_topsis_produces_ranking_weights_and_explanations() -> None:
    frame = pd.DataFrame(
        {
            "municipality_code": ["1", "2", "3"],
            "municipality_name": ["A", "B", "C"],
            "violence": [10, 30, 20],
            "service_capacity": [8, 2, 5],
        }
    )

    result = run_hybrid_topsis(
        frame,
        id_columns=["municipality_code", "municipality_name"],
        criteria=["violence", "service_capacity"],
        directions={"violence": "benefit", "service_capacity": "cost"},
    )

    assert result.ranking.iloc[0]["municipality_name"] == "B"
    assert result.ranking["priority_rank"].tolist() == [1, 2, 3]
    assert abs(result.weights["hybrid_weight"].sum() - 1.0) < 1e-9
    assert "dominant_criterion" in result.contributions.columns


def test_constant_criterion_is_handled() -> None:
    frame = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "criterion_a": [1, 2, 3],
            "criterion_b": [5, 5, 5],
        }
    )
    result = run_hybrid_topsis(
        frame,
        id_columns=["id"],
        criteria=["criterion_a", "criterion_b"],
        directions={"criterion_a": "benefit", "criterion_b": "benefit"},
    )
    assert len(result.ranking) == 3
