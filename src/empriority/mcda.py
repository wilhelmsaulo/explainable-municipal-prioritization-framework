from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MCDAResult:
    ranking: pd.DataFrame
    weights: pd.DataFrame
    contributions: pd.DataFrame


def _numeric_matrix(frame: pd.DataFrame, criteria: list[str]) -> pd.DataFrame:
    missing = [column for column in criteria if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing criteria columns: {', '.join(missing)}")

    matrix = frame.loc[:, criteria].apply(pd.to_numeric, errors="coerce")
    if matrix.isna().any().any():
        bad = matrix.columns[matrix.isna().any()].tolist()
        raise ValueError(f"Criteria contain missing or non-numeric values: {', '.join(bad)}")
    return matrix.astype(float)


def minmax_normalize(matrix: pd.DataFrame, directions: dict[str, str]) -> pd.DataFrame:
    normalized = pd.DataFrame(index=matrix.index)
    for column in matrix.columns:
        values = matrix[column]
        minimum = float(values.min())
        maximum = float(values.max())
        span = maximum - minimum
        if span == 0:
            normalized[column] = 0.0
            continue
        direction = directions.get(column, "benefit")
        if direction == "benefit":
            normalized[column] = (values - minimum) / span
        elif direction == "cost":
            normalized[column] = (maximum - values) / span
        else:
            raise ValueError(f"Invalid direction for '{column}': {direction}")
    return normalized


def entropy_weights(normalized: pd.DataFrame) -> pd.Series:
    epsilon = np.finfo(float).eps
    column_sums = normalized.sum(axis=0).replace(0, np.nan)
    probabilities = normalized.div(column_sums, axis=1).fillna(0.0)
    n = len(normalized)
    if n <= 1:
        return pd.Series(1 / len(normalized.columns), index=normalized.columns)
    entropy = -(probabilities * np.log(probabilities + epsilon)).sum(axis=0) / np.log(n)
    diversification = 1 - entropy
    if float(diversification.sum()) == 0:
        return pd.Series(1 / len(diversification), index=diversification.index)
    return diversification / diversification.sum()


def critic_weights(normalized: pd.DataFrame) -> pd.Series:
    standard_deviation = normalized.std(axis=0, ddof=0)
    correlation = normalized.corr().fillna(0.0)
    contrast = standard_deviation * (1 - correlation).sum(axis=1)
    if float(contrast.sum()) == 0:
        return pd.Series(1 / len(contrast), index=contrast.index)
    return contrast / contrast.sum()


def hybrid_weights(normalized: pd.DataFrame, alpha: float = 0.5) -> pd.DataFrame:
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")
    entropy = entropy_weights(normalized)
    critic = critic_weights(normalized)
    hybrid = alpha * entropy + (1 - alpha) * critic
    hybrid = hybrid / hybrid.sum()
    return pd.DataFrame(
        {
            "criterion": hybrid.index,
            "entropy_weight": entropy.values,
            "critic_weight": critic.values,
            "hybrid_weight": hybrid.values,
        }
    )


def topsis_scores(normalized: pd.DataFrame, weights: pd.Series) -> pd.Series:
    weighted = normalized.mul(weights, axis=1)
    ideal = weighted.max(axis=0)
    anti_ideal = weighted.min(axis=0)
    distance_ideal = np.sqrt(((weighted - ideal) ** 2).sum(axis=1))
    distance_anti = np.sqrt(((weighted - anti_ideal) ** 2).sum(axis=1))
    denominator = distance_ideal + distance_anti
    return distance_anti.div(denominator.replace(0, np.nan)).fillna(0.0)


def run_hybrid_topsis(
    frame: pd.DataFrame,
    *,
    id_columns: list[str],
    criteria: list[str],
    directions: dict[str, str],
    alpha: float = 0.5,
) -> MCDAResult:
    matrix = _numeric_matrix(frame, criteria)
    normalized = minmax_normalize(matrix, directions)
    weights_frame = hybrid_weights(normalized, alpha=alpha)
    weights = weights_frame.set_index("criterion")["hybrid_weight"]
    scores = topsis_scores(normalized, weights)

    ranking = frame.loc[:, id_columns].copy()
    ranking["priority_score"] = scores
    ranking["priority_rank"] = (
        ranking["priority_score"].rank(ascending=False, method="min").astype(int)
    )
    ranking = ranking.sort_values(["priority_rank", *id_columns], kind="stable").reset_index(
        drop=True
    )

    contributions = normalized.mul(weights, axis=1)
    contributions.columns = [f"contribution_{column}" for column in contributions.columns]
    contributions = pd.concat(
        [frame.loc[:, id_columns].reset_index(drop=True), contributions.reset_index(drop=True)],
        axis=1,
    )
    contributions["dominant_criterion"] = normalized.mul(weights, axis=1).idxmax(axis=1).values

    return MCDAResult(
        ranking=ranking,
        weights=weights_frame.sort_values("hybrid_weight", ascending=False).reset_index(drop=True),
        contributions=contributions,
    )
