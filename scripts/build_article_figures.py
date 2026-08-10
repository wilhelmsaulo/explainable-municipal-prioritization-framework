"""Build manuscript figures from the frozen capacity-priority outputs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"
OUTPUT = ROOT / "docs" / "article" / "figures"

COLORS = {
    "blue": "#2F6690",
    "green": "#3A7D44",
    "orange": "#D97706",
    "purple": "#7C3AED",
    "rose": "#BE476F",
    "gray": "#64748B",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def _save(fig: plt.Figure, stem: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(OUTPUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def stability_profiles() -> None:
    frame = pd.read_csv(RESULTS / "integrated_capacity_priority_profiles.csv")
    order = [
        "robust_higher_capacity_strengthening_priority",
        "scenario_sensitive_higher_priority",
        "intermediate_or_scenario_sensitive",
        "robust_lower_relative_priority",
    ]
    labels = [
        "Robust higher\npriority",
        "Scenario-sensitive\nhigher priority",
        "Intermediate or\nscenario-sensitive",
        "Robust lower\nrelative priority",
    ]
    counts = frame["priority_stability_profile"].value_counts().reindex(order).fillna(0)
    shares = 100 * counts / len(frame)

    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    bars = ax.bar(
        labels,
        counts,
        color=[COLORS["blue"], COLORS["orange"], COLORS["gray"], COLORS["green"]],
        width=0.68,
    )
    for bar, count, share in zip(bars, counts, shares, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.2,
            f"{int(count)} ({share:.1f}%)",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    ax.set_ylabel("Municipalities")
    ax.set_ylim(0, max(counts) * 1.18)
    ax.set_title(
        "Municipal stability profiles across 48 configurations",
        loc="left",
        weight="bold",
        pad=14,
    )
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)
    _save(fig, "figure_02_stability_profiles")


def scenario_agreement() -> None:
    frame = pd.read_csv(RESULTS / "capacity_scenario_agreement.csv")
    frame = frame.loc[frame["scenario"] != frame["reference_scenario"]].copy()
    palette = {
        "equal_dimensions": COLORS["blue"],
        "institutional_emphasis": COLORS["purple"],
        "service_network_emphasis": COLORS["green"],
        "transport_emphasis": COLORS["orange"],
    }
    labels = {
        "equal_dimensions": "Equal dimensions",
        "institutional_emphasis": "Institutional emphasis",
        "service_network_emphasis": "Service-network emphasis",
        "transport_emphasis": "Transport emphasis",
    }

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.7), constrained_layout=True)
    ax = axes[0]
    for name, group in frame.groupby("macro_weight_scenario", sort=False):
        ax.scatter(
            group["rank_correlation"],
            100 * group["top_quartile_overlap_fraction"],
            s=52,
            alpha=0.82,
            color=palette[name],
            label=labels[name],
            edgecolor="white",
            linewidth=0.5,
        )
    ax.set_xlabel("Spearman rank correlation with reference")
    ax.set_ylabel("Top-quartile overlap with reference (%)")
    ax.set_title("A  Ranking and group agreement", loc="left", weight="bold")
    ax.grid(color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="lower right")

    ax = axes[1]
    modal_order = ["equal_modes", "road_emphasis", "water_emphasis", "air_emphasis"]
    modal_labels = ["Equal modes", "Road emphasis", "Waterway emphasis", "Air emphasis"]
    modal = frame["transport_scenario"].str.split("__").str[0]
    groups = [frame.loc[modal.eq(name), "maximum_absolute_rank_shift"].to_numpy() for name in modal_order]
    plot = ax.boxplot(groups, patch_artist=True, tick_labels=modal_labels, widths=0.62)
    for patch, color in zip(
        plot["boxes"],
        [COLORS["blue"], COLORS["green"], COLORS["orange"], COLORS["purple"]],
        strict=True,
    ):
        patch.set_facecolor(color)
        patch.set_alpha(0.72)
    for median in plot["medians"]:
        median.set_color("white")
        median.set_linewidth(2)
    ax.set_ylabel("Maximum absolute rank shift")
    ax.set_title("B  Rank-shift range by modal structure", loc="left", weight="bold")
    ax.tick_params(axis="x", rotation=18)
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)

    fig.suptitle(
        "Agreement of 47 alternative configurations with the T1 × W1 reference",
        x=0.01,
        ha="left",
        fontsize=13,
        fontweight="bold",
    )
    _save(fig, "figure_03_scenario_agreement")


def dimension_composition() -> None:
    frame = pd.read_csv(RESULTS / "capacity_municipality_explanations.csv")
    contribution_columns = [
        "mean_institutional_contribution",
        "mean_service_network_contribution",
        "mean_transport_barrier_contribution",
    ]
    contribution_labels = ["Institutional deficit", "Service-network deficit", "Transport barrier"]
    colors = [COLORS["purple"], COLORS["green"], COLORS["orange"]]

    dominant_order = [
        "institutional",
        "service_network",
        "transport_barrier",
        "tie:institutional+transport_barrier",
        "tie:service_network+transport_barrier",
    ]
    dominant_labels = [
        "Institutional",
        "Service network",
        "Transport barrier",
        "Institutional + transport tie",
        "Service + transport tie",
    ]
    dominant_counts = (
        frame["dominant_dimension_across_scenarios"].value_counts().reindex(dominant_order).fillna(0)
    )

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8), constrained_layout=True)
    ax = axes[0]
    data = [frame[column].to_numpy() for column in contribution_columns]
    plot = ax.boxplot(data, patch_artist=True, tick_labels=contribution_labels, widths=0.62)
    for patch, color in zip(plot["boxes"], colors, strict=True):
        patch.set_facecolor(color)
        patch.set_alpha(0.72)
    for median in plot["medians"]:
        median.set_color("white")
        median.set_linewidth(2)
    ax.set_ylabel("Mean weighted contribution")
    ax.set_title("A  Contribution distributions", loc="left", weight="bold")
    ax.tick_params(axis="x", rotation=15)
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)

    ax = axes[1]
    y = np.arange(len(dominant_labels))
    bars = ax.barh(
        y,
        dominant_counts,
        color=[COLORS["purple"], COLORS["green"], COLORS["orange"], COLORS["gray"], COLORS["gray"]],
        alpha=0.82,
    )
    ax.set_yticks(y, dominant_labels)
    ax.invert_yaxis()
    ax.set_xlabel("Municipalities")
    ax.set_title("B  Most frequently dominant dimension", loc="left", weight="bold")
    for bar, count in zip(bars, dominant_counts, strict=True):
        ax.text(count + 1, bar.get_y() + bar.get_height() / 2, str(int(count)), va="center")
    ax.set_xlim(0, max(dominant_counts) * 1.18)
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)

    fig.suptitle(
        "Composition of municipal scores across the three macro-dimensions",
        x=0.01,
        ha="left",
        fontsize=13,
        fontweight="bold",
    )
    _save(fig, "figure_04_dimension_composition")


def main() -> None:
    _style()
    stability_profiles()
    scenario_agreement()
    dimension_composition()


if __name__ == "__main__":
    main()
