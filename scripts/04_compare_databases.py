#!/usr/bin/env python3
"""
04_compare_databases.py

Merge the standardized Kraken2 summaries from all three databases into a
single side-by-side comparison table.

Output (long form), one row per (database, category):
    db_name, category, percent

Also writes a wide-form table with one row per category and one column per
database, plus per-pair deltas:

    category
    <db_a>_percent
    <db_b>_percent
    <db_c>_percent
    delta_<db_b>_minus_<db_a>
    delta_<db_c>_minus_<db_a>
    delta_<db_c>_minus_<db_b>
    max_abs_delta              (used for sorting; largest disagreement on top)

Usage:
    python scripts/04_compare_databases.py --config config/config.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from itertools import combinations

import pandas as pd
import yaml


def load_config(config_path: str) -> dict:
    """Load a YAML config file and return it as a dict."""
    if not os.path.isfile(config_path):
        sys.exit(f"ERROR: Config file not found: {config_path}")
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tables_dir = cfg["output"]["tables"]
    os.makedirs(tables_dir, exist_ok=True)

    db_entries = cfg.get("databases", [])
    if not db_entries:
        sys.exit("ERROR: No databases defined in config.yaml under 'databases'.")

    # ---------------------------------------------------------------------
    # Load standardized summaries for every database.
    # ---------------------------------------------------------------------
    summaries: list[pd.DataFrame] = []
    for entry in db_entries:
        db_name = entry["name"]
        in_path = os.path.join(tables_dir, f"kraken_standardized_{db_name}.csv")
        if not os.path.isfile(in_path):
            sys.exit(
                f"ERROR: Required input not found: {in_path}. "
                f"Did you run 03_standardize_taxa.py first?"
            )
        df = pd.read_csv(in_path)
        summaries.append(df)

    # ---------------------------------------------------------------------
    # Long-form output: every (db, category, percent) triple stacked.
    # Easy to plot or join in any downstream tool.
    # ---------------------------------------------------------------------
    long_df = pd.concat(summaries, ignore_index=True)
    long_path = os.path.join(tables_dir, "database_comparison_long.csv")
    long_df.to_csv(long_path, index=False)
    print(f"[04_compare_databases] Wrote long-form: {long_path}")

    # ---------------------------------------------------------------------
    # Wide-form output: one row per category, one column per database,
    # plus pairwise deltas.
    # ---------------------------------------------------------------------
    wide = long_df.pivot(index="category", columns="db_name", values="percent")
    wide.columns = [f"{c}_percent" for c in wide.columns]
    wide = wide.reset_index().fillna(0.0)

    db_names = [e["name"] for e in db_entries]
    delta_cols: list[str] = []
    for a, b in combinations(db_names, 2):
        col = f"delta_{b}_minus_{a}"
        wide[col] = (wide[f"{b}_percent"] - wide[f"{a}_percent"]).round(4)
        delta_cols.append(col)

    # Sort by largest absolute disagreement across any pair.
    if delta_cols:
        wide["max_abs_delta"] = wide[delta_cols].abs().max(axis=1)
        wide = wide.sort_values("max_abs_delta", ascending=False).reset_index(drop=True)

    wide_path = os.path.join(tables_dir, "database_comparison_wide.csv")
    wide.to_csv(wide_path, index=False)
    print(f"[04_compare_databases] Wrote wide-form: {wide_path}")

    print()
    print(wide.to_string(index=False))


if __name__ == "__main__":
    main()
