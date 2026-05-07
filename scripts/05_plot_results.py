#!/usr/bin/env python3
"""
05_plot_results.py

Generate publication-quality figures comparing the three Kraken2 databases:

    1. classified_vs_unclassified.{png,pdf}
       Bar plot showing % classified vs. % unclassified for each database.

    2. taxonomic_composition.{png,pdf}
       Stacked bar plot showing the full categorical breakdown for each
       database.

The number of databases is taken from config.yaml -- if you add or remove
entries under `databases`, the figures regenerate accordingly.

Usage:
    python scripts/05_plot_results.py --config config/config.yaml
"""

from __future__ import annotations

import argparse
import os
import sys

import matplotlib.pyplot as plt
import pandas as pd
import yaml


# Consistent, color-blind-friendly palette in canonical category order.
CATEGORY_ORDER = [
    "Unclassified",
    "Host/Chordata",
    "Bacteria",
    "Apicomplexa/Nephromyces-related",
    "Other Eukaryotes",
    "Other",
]

CATEGORY_COLORS = {
    "Unclassified": "#BDBDBD",
    "Host/Chordata": "#1F77B4",
    "Bacteria": "#2CA02C",
    "Apicomplexa/Nephromyces-related": "#D62728",
    "Other Eukaryotes": "#9467BD",
    "Other": "#8C564B",
}


def load_config(config_path: str) -> dict:
    """Load a YAML config file and return it as a dict."""
    if not os.path.isfile(config_path):
        sys.exit(f"ERROR: Config file not found: {config_path}")
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def save_figure(fig, base_path: str) -> None:
    """Save a figure as both PNG and PDF."""
    fig.savefig(base_path + ".png", dpi=300, bbox_inches="tight")
    fig.savefig(base_path + ".pdf", bbox_inches="tight")
    plt.close(fig)


def load_long_table(tables_dir: str) -> pd.DataFrame:
    """Load the long-form comparison table written by step 04."""
    path = os.path.join(tables_dir, "database_comparison_long.csv")
    if not os.path.isfile(path):
        sys.exit(
            f"ERROR: Required input not found: {path}. "
            f"Did you run 04_compare_databases.py first?"
        )
    return pd.read_csv(path)


def plot_classified_vs_unclassified(
    long_df: pd.DataFrame,
    db_order: list[str],
    db_labels: dict[str, str],
    out_base: str,
) -> None:
    """Stacked bar (classified vs unclassified) for every database."""
    classified, unclassified = [], []
    for name in db_order:
        sub = long_df[long_df["db_name"] == name]
        unc = sub.loc[sub["category"] == "Unclassified", "percent"].sum()
        unclassified.append(unc)
        classified.append(100.0 - unc)

    x_labels = [db_labels[n] for n in db_order]

    # Width scales gently with number of databases for readability.
    fig, ax = plt.subplots(figsize=(max(6, 1.6 * len(db_order)), 5))

    bars_class = ax.bar(x_labels, classified, label="Classified", color="#4C78A8")
    bars_unc = ax.bar(
        x_labels, unclassified, bottom=classified,
        label="Unclassified", color="#BDBDBD",
    )

    # Annotate each segment with its percentage where there's room.
    for bars, values in ((bars_class, classified), (bars_unc, unclassified)):
        for bar, val in zip(bars, values):
            if val < 1.5:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%",
                ha="center",
                va="center",
                color="white",
                fontsize=10,
                fontweight="bold",
            )

    ax.set_ylabel("Percent of reads")
    ax.set_ylim(0, 100)
    ax.set_title("Classified vs. unclassified reads by Kraken2 database")
    ax.legend(loc="upper right", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Rotate long labels so they don't overlap.
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")

    save_figure(fig, out_base)


def plot_stacked_composition(
    long_df: pd.DataFrame,
    db_order: list[str],
    db_labels: dict[str, str],
    out_base: str,
) -> None:
    """Stacked bar of the full taxonomic composition per database."""
    # Pivot to wide form: rows = category, columns = db_name, values = percent.
    wide = (
        long_df.pivot(index="category", columns="db_name", values="percent")
        .reindex(index=[c for c in CATEGORY_ORDER if c in long_df["category"].unique()],
                 columns=db_order)
        .fillna(0.0)
    )

    x_labels = [db_labels[n] for n in db_order]
    fig, ax = plt.subplots(figsize=(max(7, 1.8 * len(db_order)), 5))

    bottoms = [0.0] * len(db_order)
    for category in wide.index:
        values = wide.loc[category].tolist()
        ax.bar(
            x_labels,
            values,
            bottom=bottoms,
            label=category,
            color=CATEGORY_COLORS.get(category, "#7F7F7F"),
            edgecolor="white",
            linewidth=0.5,
        )
        # Annotate slices >= 3% so the figure stays legible.
        for i, v in enumerate(values):
            if v >= 3.0:
                ax.text(
                    i,
                    bottoms[i] + v / 2,
                    f"{v:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="white",
                    fontweight="bold",
                )
        bottoms = [b + v for b, v in zip(bottoms, values)]

    ax.set_ylabel("Percent of reads")
    ax.set_ylim(0, 100)
    ax.set_title("Taxonomic composition by Kraken2 database")
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        title="Category",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")

    save_figure(fig, out_base)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tables_dir = cfg["output"]["tables"]
    figures_dir = cfg["output"]["figures"]
    os.makedirs(figures_dir, exist_ok=True)

    db_entries = cfg.get("databases", [])
    if not db_entries:
        sys.exit("ERROR: No databases defined in config.yaml under 'databases'.")

    db_order = [e["name"] for e in db_entries]
    db_labels = {e["name"]: e.get("label", e["name"]) for e in db_entries}

    long_df = load_long_table(tables_dir)

    fig1 = os.path.join(figures_dir, "classified_vs_unclassified")
    fig2 = os.path.join(figures_dir, "taxonomic_composition")

    plot_classified_vs_unclassified(long_df, db_order, db_labels, fig1)
    print(f"[05_plot_results] Wrote {fig1}.png and {fig1}.pdf")

    plot_stacked_composition(long_df, db_order, db_labels, fig2)
    print(f"[05_plot_results] Wrote {fig2}.png and {fig2}.pdf")


if __name__ == "__main__":
    main()
