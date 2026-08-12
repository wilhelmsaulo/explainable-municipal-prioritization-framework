from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

RATE = "rate_selected_vaw_records_per_100k_women"


def spearman(left: pd.Series, right: pd.Series) -> float:
    return float(left.rank(method="average").corr(right.rank(method="average")))


def build_profiles(priority: pd.DataFrame, contextual: pd.DataFrame) -> pd.DataFrame:
    annual_median = contextual.groupby("year")[RATE].median()
    rows = []
    for municipality_code, annual in contextual.groupby("municipality_code", sort=True):
        annual = annual.sort_values("year")
        priority_row = priority.loc[priority["municipality_code"].eq(municipality_code)].iloc[0]
        rates = annual[RATE].to_numpy(dtype=float)
        years = annual["year"].to_numpy(dtype=float)
        mean_rate = float(rates.mean())
        rate_sd = float(rates.std(ddof=0))
        rows.append(
            {
                "municipality_code": municipality_code,
                "municipality": priority_row["municipality"],
                "mean_priority_score": priority_row["mean_priority_score"],
                "mean_priority_rank": priority_row["mean_priority_rank"],
                "top_quartile_frequency": priority_row["top_quartile_frequency"],
                "priority_stability_profile": priority_row["priority_stability_profile"],
                "female_population_2022": annual["female_population_2022"].iloc[0],
                "selected_vaw_records_2022_2025": annual["selected_vaw_records"].sum(),
                "mean_annual_selected_vaw_rate_per_100k_women": mean_rate,
                **{
                    f"rate_{year}": annual.loc[annual["year"].eq(year), RATE].iloc[0]
                    for year in range(2022, 2026)
                },
                "rate_linear_slope_per_year": float(np.polyfit(years, rates, 1)[0]),
                "rate_cv": rate_sd / mean_rate if mean_rate else 0.0,
                "years_at_or_above_state_median": int(
                    sum(
                        rate >= annual_median.loc[year]
                        for rate, year in zip(rates, years, strict=True)
                    )
                ),
            }
        )
    profiles = pd.DataFrame(rows)
    median_rate = profiles["mean_annual_selected_vaw_rate_per_100k_women"].median()
    high_priority = profiles["top_quartile_frequency"].ge(0.75)
    high_rate = profiles["mean_annual_selected_vaw_rate_per_100k_women"].ge(median_rate)
    profiles["contextual_pattern"] = np.select(
        [high_priority & high_rate, high_priority & ~high_rate, ~high_priority & high_rate],
        [
            "higher_priority_higher_observed_rate",
            "higher_priority_lower_observed_rate",
            "other_priority_higher_observed_rate",
        ],
        default="other_priority_lower_observed_rate",
    )
    return profiles.sort_values("mean_priority_rank").reset_index(drop=True)


def build_summary(
    profiles: pd.DataFrame,
    contextual: pd.DataFrame,
    multimethod: pd.DataFrame,
) -> dict[str, object]:
    rate_by_code = profiles.set_index("municipality_code")[
        "mean_annual_selected_vaw_rate_per_100k_women"
    ]
    associations = {
        "additive_mean_priority_score_vs_mean_selected_rate_spearman": spearman(
            profiles["mean_priority_score"],
            profiles["mean_annual_selected_vaw_rate_per_100k_women"],
        ),
        "additive_mean_priority_rank_vs_mean_selected_rate_spearman": spearman(
            profiles["mean_priority_rank"],
            profiles["mean_annual_selected_vaw_rate_per_100k_women"],
        ),
    }
    for method, method_rows in multimethod.groupby("method"):
        method_rates = method_rows["municipality_code"].map(rate_by_code)
        associations[f"{method}_mean_score_vs_mean_selected_rate_spearman"] = spearman(
            method_rows["mean_score"], method_rates
        )
    yearly = {}
    priority_score = profiles.set_index("municipality_code")["mean_priority_score"]
    for year, annual in contextual.groupby("year"):
        annual_priority = annual["municipality_code"].map(priority_score)
        yearly[str(year)] = spearman(annual_priority, annual[RATE])
    return {
        "schema_version": "1.0",
        "scope": "contextual analysis only; primary score unchanged",
        "municipalities": int(len(profiles)),
        "years": [2022, 2023, 2024, 2025],
        "state_annual_median_selected_rate_per_100k_women": contextual.groupby("year")[
            RATE
        ].median().to_dict(),
        "municipal_mean_rate_median": float(
            profiles["mean_annual_selected_vaw_rate_per_100k_women"].median()
        ),
        "associations": associations,
        "year_specific_additive_score_associations": yearly,
        "patterns": profiles["contextual_pattern"].value_counts().to_dict(),
        "interpretation_limits": [
            "Administrative records do not estimate incidence, hidden violence, individual risk, or underreporting.",
            "Associations are descriptive and do not establish causality.",
            "Observed rates may reflect reporting access, service availability, recording practices, and institutional capacity.",
            "Contextual results do not alter indicators, weights, scores, ranks, or profiles.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build contextual VAW priority analysis.")
    parser.add_argument("--priority-profiles", type=Path, required=True)
    parser.add_argument("--contextual-data", type=Path, required=True)
    parser.add_argument("--multimethod-profiles", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/results"))
    args = parser.parse_args()
    priority = pd.read_csv(args.priority_profiles, dtype={"municipality_code": str})
    contextual = pd.read_csv(args.contextual_data, dtype={"municipality_code": str})
    multimethod = pd.read_csv(args.multimethod_profiles, dtype={"municipality_code": str})
    profiles = build_profiles(priority, contextual)
    summary = build_summary(profiles, contextual, multimethod)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(args.output_dir / "contextual_vaw_priority_profiles.csv", index=False)
    (args.output_dir / "contextual_vaw_priority_analysis.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
