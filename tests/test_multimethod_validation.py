import numpy as np
import pandas as pd

from empriority.multimethod_validation import (
    fractional_top_membership,
    promethee_ii,
    sample_convex_weights,
    topsis,
)


def test_dominance_preservation_all_methods() -> None:
    matrix = np.array([[1.0, 1.0, 1.0], [0.5, 0.5, 0.5], [0.0, 0.0, 0.0]])
    weights = np.repeat(1 / 3, 3)
    assert np.all(np.diff(matrix @ weights) < 0)
    assert np.all(np.diff(topsis(matrix, weights)) < 0)
    assert np.all(np.diff(promethee_ii(matrix, weights)[3]) < 0)


def test_topsis_scores_are_finite_probability_scale() -> None:
    scores = topsis(np.eye(3), np.repeat(1 / 3, 3))
    assert np.isfinite(scores).all()
    assert ((scores >= 0) & (scores <= 1)).all()


def test_promethee_scores_flows_and_scale_invariance() -> None:
    matrix = np.array([[1.0, 4.0], [2.0, 2.0], [3.0, 1.0]])
    outputs = promethee_ii(matrix, np.array([0.5, 0.5]))
    assert all(np.isfinite(value).all() for value in outputs)
    assert ((outputs[0] >= 0) & (outputs[0] <= 1)).all()
    assert ((outputs[1] >= 0) & (outputs[1] <= 1)).all()
    assert ((outputs[3] >= 0) & (outputs[3] <= 1)).all()
    scaled = promethee_ii(matrix * np.array([7.0, 0.2]), np.array([0.5, 0.5]))
    for original, transformed in zip(outputs, scaled, strict=True):
        assert np.allclose(original, transformed)


def test_convex_weight_sampling() -> None:
    vertices = np.array([[0.5, 0.25, 0.25], [0.25, 0.5, 0.25], [0.25, 0.25, 0.5]])
    weights = sample_convex_weights(1000, 42, vertices)
    assert np.allclose(weights.sum(axis=1), 1)
    assert ((weights >= 0.25) & (weights <= 0.5)).all()


def test_fractional_top_membership_is_tie_neutral_and_exact() -> None:
    membership = fractional_top_membership(np.array([5.0, 4.0, 4.0, 4.0, 1.0]), 2)
    assert np.allclose(membership, [1.0, 1 / 3, 1 / 3, 1 / 3, 0.0])
    assert np.isclose(membership.sum(), 2)


def test_published_outputs_have_complete_territorial_and_scenario_coverage() -> None:
    scores = pd.read_csv("data/results/multimethod_capacity_scores.csv")
    assert scores["municipality_code"].nunique() == 144
    assert scores["transport_scenario"].nunique() == 12
    assert scores["macro_weight_scheme"].nunique() == 4
    assert set(scores["method"]) == {"additive", "topsis", "promethee_ii"}
    assert len(scores) == 20_736


def test_published_additive_scores_and_ranks_reproduce_primary_results() -> None:
    scores = pd.read_csv("data/results/multimethod_capacity_scores.csv")
    additive = scores[scores["method"] == "additive"].copy()
    primary = pd.read_csv("data/results/integrated_capacity_priority_scenarios.csv")
    for (transport, weights), group in additive.groupby(
        ["transport_scenario", "macro_weight_scheme"]
    ):
        scenario = f"{transport}___{weights}"
        expected = primary.set_index("municipality_code")
        observed = group.set_index("municipality_code")
        assert np.allclose(observed["score"], expected.loc[observed.index, f"{scenario}__score"])
        assert np.array_equal(observed["rank"], expected.loc[observed.index, f"{scenario}__rank"])
