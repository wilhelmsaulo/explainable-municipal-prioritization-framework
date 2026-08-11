from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

DIMENSIONS = ["institutional_deficit", "service_network_deficit", "transport_barrier"]
METHODS = ("additive", "topsis", "promethee_ii")


def topsis(matrix: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Return TOPSIS relative closeness for benefit criteria using vector normalization."""
    denominator = np.linalg.norm(matrix, axis=0)
    normalized = np.divide(matrix, denominator, out=np.zeros_like(matrix), where=denominator != 0)
    weighted = normalized * weights
    positive, negative = weighted.max(axis=0), weighted.min(axis=0)
    d_positive = np.linalg.norm(weighted - positive, axis=1)
    d_negative = np.linalg.norm(weighted - negative, axis=1)
    total = d_positive + d_negative
    return np.divide(d_negative, total, out=np.full(len(matrix), 0.5), where=total != 0)


def promethee_ii(matrix: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, ...]:
    """Return usual-preference positive, negative and net flows and a [0, 1] score."""
    # preference[i,j] is the weighted evidence that alternative i strictly dominates j.
    preference = (matrix[:, None, :] > matrix[None, :, :]).astype(float) @ weights
    n = len(matrix)
    positive = preference.sum(axis=1) / (n - 1)
    negative = preference.sum(axis=0) / (n - 1)
    net = positive - negative
    span = np.ptp(net)
    score = (net - net.min()) / span if span else np.full(n, 0.5)
    return positive, negative, net, score


def fractional_top_membership(scores: np.ndarray, mass: int) -> np.ndarray:
    """Allocate exact top-set mass, fractionally sharing membership across cutoff ties."""
    if not 0 < mass <= len(scores):
        raise ValueError("Top-set mass must be between one and the number of alternatives")
    cutoff = np.sort(scores)[::-1][mass - 1]
    membership = (scores > cutoff).astype(float)
    tied = scores == cutoff
    membership[tied] = (mass - membership.sum()) / tied.sum()
    return membership


def sample_convex_weights(draws: int, seed: int, vertices: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(seed)
    barycentric = rng.dirichlet(np.ones(len(vertices)), size=draws)
    return barycentric @ vertices


def tie_neutral_rank_counts(values: np.ndarray) -> tuple[np.ndarray, int]:
    """Accumulate rank counts, sharing tied rank positions equally among alternatives."""
    order = np.argsort(-values, axis=0, kind="stable")
    ranks = np.empty_like(order)
    ranks[order, np.arange(order.shape[1])] = np.arange(1, len(values) + 1)[:, None]
    counts = np.zeros((len(values), len(values)), dtype=float)
    for alternative in range(len(values)):
        counts[alternative] = np.bincount(
            ranks[alternative] - 1, minlength=len(values)
        )

    sorted_values = np.take_along_axis(values, order, axis=0)
    tied_draws = np.flatnonzero(
        np.any(sorted_values[1:] == sorted_values[:-1], axis=0)
    )
    allocations = 0
    for draw in tied_draws:
        boundaries = np.flatnonzero(
            np.r_[True, sorted_values[1:, draw] != sorted_values[:-1, draw], True]
        )
        for start, stop in zip(boundaries[:-1], boundaries[1:], strict=True):
            size = stop - start
            if size == 1:
                continue
            members = order[start:stop, draw]
            positions = np.arange(start, stop)
            counts[members, ranks[members, draw] - 1] -= 1.0
            counts[np.ix_(members, positions)] += 1.0 / size
            allocations += 1
    return counts, allocations


def _rank(scores: np.ndarray) -> np.ndarray:
    return pd.Series(scores).rank(ascending=False, method="min").to_numpy(dtype=int)


def _average_rank(scores: np.ndarray) -> np.ndarray:
    return pd.Series(scores).rank(ascending=False, method="average").to_numpy()


def _paths(config: dict[str, Any]) -> dict[str, Path]:
    return {name: Path(path) for name, path in config["multimethod_validation"]["outputs"].items()}


def build_multimethod_validation(
    config_path: str | Path = "config/capacity_priority.yml",
) -> dict[str, Path]:
    """Run deterministic multimethod comparison and additive SMAA-inspired validation."""
    config_path = Path(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    settings = config["multimethod_validation"]
    smaa = settings["smaa"]
    paths = _paths(config)

    profiles = pd.read_csv(config["outputs"]["profiles"], dtype={"municipality_code": str})
    transport = pd.read_csv(config["inputs"]["transport_scenarios"], dtype={"municipality_code": str})
    published = pd.read_csv(config["outputs"]["scenarios"], dtype={"municipality_code": str})
    transport_columns = [column for column in transport if column.endswith("__score")]
    merged = profiles[["municipality_code", "municipality", *DIMENSIONS[:2]]].merge(
        transport[["municipality_code", *transport_columns]], on="municipality_code", validate="one_to_one"
    )
    published = merged[["municipality_code"]].merge(
        published, on="municipality_code", validate="one_to_one"
    )
    weights_by_name = config["macro_weight_scenarios"]
    records: list[dict[str, Any]] = []
    agreement: list[dict[str, Any]] = []
    reconstruction_error = 0.0
    additive_rank_mismatches = 0

    for transport_column in transport_columns:
        transport_name = transport_column.removesuffix("__score")
        matrix = np.column_stack(
            [merged[DIMENSIONS[0]], merged[DIMENSIONS[1]], 1 - merged[transport_column]]
        )
        for weight_name, weight_mapping in weights_by_name.items():
            weights = np.array([weight_mapping[name] for name in DIMENSIONS])
            additive_reconstructed = matrix @ weights
            top = topsis(matrix, weights)
            p_plus, p_minus, p_net, prom = promethee_ii(matrix, weights)
            scenario = f"{transport_name}___{weight_name}"
            additive = published[f"{scenario}__score"].to_numpy()
            outputs = {"additive": additive, "topsis": top, "promethee_ii": prom}
            reconstruction_error = max(
                reconstruction_error,
                float(np.max(np.abs(additive_reconstructed - additive))),
            )
            additive_rank_mismatches += int(
                np.count_nonzero(_rank(additive) != published[f"{scenario}__rank"].to_numpy())
            )
            for method, scores in outputs.items():
                ranks = _rank(scores)
                for index, score in enumerate(scores):
                    row = {
                        "municipality_code": merged.iloc[index]["municipality_code"],
                        "municipality": merged.iloc[index]["municipality"],
                        "method": method,
                        "transport_scenario": transport_name,
                        "macro_weight_scheme": weight_name,
                        "score": score,
                        "rank": ranks[index],
                    }
                    if method == "promethee_ii":
                        row.update(
                            positive_flow=p_plus[index], negative_flow=p_minus[index], net_flow=p_net[index]
                        )
                    records.append(row)
            for first, second in combinations(METHODS, 2):
                a, b = outputs[first], outputs[second]
                rank_a, rank_b = _average_rank(a), _average_rank(b)
                shifts = np.abs(rank_a - rank_b)
                agreement.append(
                    {
                        "transport_scenario": transport_name,
                        "macro_weight_scheme": weight_name,
                        "method_a": first,
                        "method_b": second,
                        "spearman_rank_correlation": float(np.corrcoef(rank_a, rank_b)[0, 1]),
                        "top_10_overlap": float(np.minimum(fractional_top_membership(a, 10), fractional_top_membership(b, 10)).sum()),
                        "top_quartile_overlap": float(np.minimum(fractional_top_membership(a, 36), fractional_top_membership(b, 36)).sum()),
                        "mean_absolute_rank_shift": shifts.mean(),
                        "maximum_absolute_rank_shift": shifts.max(),
                    }
                )

    scores_frame = pd.DataFrame(records)
    agreement_frame = pd.DataFrame(agreement)
    method_profiles = (
        scores_frame.groupby(["municipality_code", "municipality", "method"], as_index=False)
        .agg(mean_score=("score", "mean"), mean_rank=("rank", "mean"), best_rank=("rank", "min"), worst_rank=("rank", "max"), top_10_frequency=("rank", lambda x: (x <= 10).mean()), top_quartile_frequency=("rank", lambda x: (x <= 36).mean()))
    )

    vertices = np.array([[vector[name] for name in DIMENSIONS] for vector in smaa["convex_hull_vertices"].values()])
    sampled = sample_convex_weights(int(smaa["macro_weight_draws"]), int(smaa["random_seed"]), vertices)
    rank_counts = np.zeros((len(merged), len(merged)), dtype=float)
    tie_neutral_allocations = 0
    evaluations = 0
    for transport_column in transport_columns:
        matrix = np.column_stack([merged[DIMENSIONS[0]], merged[DIMENSIONS[1]], 1 - merged[transport_column]])
        for weight_chunk in np.array_split(sampled, 20):
            values = matrix @ weight_chunk.T
            chunk_counts, chunk_allocations = tie_neutral_rank_counts(values)
            rank_counts += chunk_counts
            tie_neutral_allocations += chunk_allocations
            evaluations += values.shape[1]
    acceptability = rank_counts / evaluations
    rank_positions = np.arange(1, len(merged) + 1)
    mean_rank = acceptability @ rank_positions
    mean_squared_rank = acceptability @ (rank_positions * rank_positions)
    summary = merged[["municipality_code", "municipality"]].copy()
    summary["mean_rank"] = mean_rank
    summary["rank_standard_deviation"] = np.sqrt(
        np.maximum(0.0, mean_squared_rank - mean_rank * mean_rank)
    )
    summary["rank_1_acceptability"] = acceptability[:, 0]
    summary["top_10_acceptability"] = acceptability[:, :10].sum(axis=1)
    summary["top_quartile_acceptability"] = acceptability[:, :36].sum(axis=1)
    distribution = pd.concat(
        [
            merged[["municipality_code", "municipality"]].reset_index(drop=True),
            pd.DataFrame(
                acceptability,
                columns=[f"rank_{rank}" for rank in range(1, len(merged) + 1)],
            ),
        ],
        axis=1,
    )

    checks = {
        "municipalities": len(merged) == 144,
        "transport_scenarios": len(transport_columns) == 12,
        "macro_weight_schemes": len(weights_by_name) == 4,
        "methods": len(METHODS) == 3,
        "method_scenario_configurations": scores_frame.groupby(["method", "transport_scenario", "macro_weight_scheme"]).ngroups == 144,
        "deterministic_records": len(scores_frame) == 20736,
        "evaluations_per_municipality": evaluations == 120000,
        "sampled_weights_sum_one": bool(np.allclose(sampled.sum(axis=1), 1)),
        "sampled_weights_in_bounds": bool(((sampled >= 0.25) & (sampled <= 0.50)).all()),
        "finite_valid_scores_and_ranks": bool(np.isfinite(scores_frame[["score", "rank"]]).all().all() and scores_frame["rank"].between(1, 144).all()),
        "rank_acceptability_complete": bool(np.allclose(acceptability.sum(axis=1), 1)),
        "rank_position_mass_complete": bool(np.allclose(acceptability.sum(axis=0), 1)),
        "tie_neutral_rank_allocations_applied": tie_neutral_allocations > 0,
        "additive_reconstruction_within_1e_12": reconstruction_error <= 1e-12,
        "additive_ranks_reproduced": additive_rank_mismatches == 0,
        "excluded_variables_inactive": not any(term in " ".join(DIMENSIONS) for term in ("police", "population", "violence")),
    }
    if not all(checks.values()):
        raise ValueError(f"Multimethod audit failed: {checks}")
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    scores_frame.to_csv(paths["scores"], index=False)
    agreement_frame.to_csv(paths["agreement"], index=False)
    method_profiles.to_csv(paths["profiles"], index=False)
    summary.to_csv(paths["smaa_summary"], index=False)
    distribution.to_csv(paths["smaa_rank_acceptability"], index=False)
    audit_payload = {
        "method_version": config["method_version"],
        "checks": checks,
        "additive_reconstruction_max_absolute_error": reconstruction_error,
        "additive_rank_mismatches": additive_rank_mismatches,
        "counts": {
            "municipalities": len(merged),
            "transport_scenarios": len(transport_columns),
            "macro_weight_schemes": len(weights_by_name),
            "methods": len(METHODS),
            "method_scenario_configurations": 144,
            "deterministic_records": len(scores_frame),
            "monte_carlo_evaluations_per_municipality": evaluations,
        },
        "smaa": {
            "random_seed": smaa["random_seed"],
            "macro_weight_draws": smaa["macro_weight_draws"],
            "scenario_frequency": "equal",
            "weight_minimum": float(sampled.min()),
            "weight_maximum": float(sampled.max()),
            "maximum_weight_sum_error": float(
                np.abs(sampled.sum(axis=1) - 1).max()
            ),
            "tie_neutral_rank_allocations": tie_neutral_allocations,
        },
    }
    paths["audit"].write_text(
        json.dumps(audit_payload, indent=2), encoding="utf-8"
    )
    return paths
