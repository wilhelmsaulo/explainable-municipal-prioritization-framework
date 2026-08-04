from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from empriority.criteria import load_model_config
from empriority.mcda import run_hybrid_topsis


def run_prioritization(
    data_path: str | Path,
    criteria_path: str | Path = "config/criteria.yml",
    output_directory: str | Path = "data/results",
    sensitivity_iterations: int = 200,
    seed: int = 42,
) -> dict[str, Path]:
    frame = pd.read_csv(data_path)
    config = load_model_config(criteria_path)
    result = run_hybrid_topsis(
        frame,
        id_columns=config.id_columns,
        criteria=config.criterion_columns,
        directions=config.directions,
        alpha=config.alpha,
    )

    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    ranking_path = output_dir / "municipal_priority_ranking.csv"
    weights_path = output_dir / "criterion_weights.csv"
    contributions_path = output_dir / "municipal_contributions.csv"
    sensitivity_path = output_dir / "rank_sensitivity.csv"

    result.ranking.to_csv(ranking_path, index=False)
    result.weights.to_csv(weights_path, index=False)
    result.contributions.to_csv(contributions_path, index=False)

    sensitivity = _sensitivity_analysis(
        frame,
        config.id_columns,
        config.criterion_columns,
        config.directions,
        config.alpha,
        sensitivity_iterations,
        seed,
    )
    sensitivity.to_csv(sensitivity_path, index=False)
    return {
        "ranking": ranking_path,
        "weights": weights_path,
        "contributions": contributions_path,
        "sensitivity": sensitivity_path,
    }


def _sensitivity_analysis(
    frame: pd.DataFrame,
    id_columns: list[str],
    criteria: list[str],
    directions: dict[str, str],
    alpha: float,
    iterations: int,
    seed: int,
) -> pd.DataFrame:
    baseline = run_hybrid_topsis(
        frame,
        id_columns=id_columns,
        criteria=criteria,
        directions=directions,
        alpha=alpha,
    ).ranking
    baseline_index = baseline.set_index(id_columns)["priority_rank"]

    rng = np.random.default_rng(seed)
    rank_samples: list[pd.Series] = []
    for _ in range(max(iterations, 1)):
        perturbed = frame.copy()
        for criterion in criteria:
            values = pd.to_numeric(perturbed[criterion], errors="raise").astype(float)
            scale = values.std(ddof=0)
            noise_scale = 0.05 * scale if scale > 0 else 0.0
            perturbed[criterion] = values + rng.normal(0, noise_scale, len(values))
        ranked = run_hybrid_topsis(
            perturbed,
            id_columns=id_columns,
            criteria=criteria,
            directions=directions,
            alpha=alpha,
        ).ranking.set_index(id_columns)["priority_rank"]
        rank_samples.append(ranked)

    ranks = pd.concat(rank_samples, axis=1)
    summary = baseline_index.rename("baseline_rank").to_frame()
    summary["mean_rank"] = ranks.mean(axis=1)
    summary["rank_std"] = ranks.std(axis=1, ddof=0)
    summary["best_rank"] = ranks.min(axis=1)
    summary["worst_rank"] = ranks.max(axis=1)
    summary["top_10_probability"] = (ranks <= 10).mean(axis=1)
    return summary.reset_index().sort_values("baseline_rank").reset_index(drop=True)
