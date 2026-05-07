#!/usr/bin/env python3
"""
03_standardize_taxa.py

Group the parsed Kraken2 outputs (one per database) into a shared set of
biologically meaningful categories so that the three databases can be
compared on equal footing:

    - Unclassified
    - Host/Chordata
    - Bacteria
    - Apicomplexa/Nephromyces-related
    - Other Eukaryotes
    - Other

Categories are assigned by case-insensitive keyword matching against the
taxon `name`. The keyword lists are intentionally broad rather than
exhaustive; this is a *standardization* step, not a re-classification.

For each database listed in config.yaml under `databases`, this script
reads `results/tables/kraken_parsed_<db_name>.csv` and writes
`results/tables/kraken_standardized_<db_name>.csv`.

Usage:
    python scripts/03_standardize_taxa.py --config config/config.yaml
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Category definitions. Order matters: the first matching category wins,
# so more specific categories should come before more general ones.
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "Unclassified",
        ["unclassified", "cannot be assigned"],
    ),
    (
        "Apicomplexa/Nephromyces-related",
        [
            "nephromyces",
            "apicomplexa",
            "plasmodium",
            "toxoplasma",
            "cryptosporidium",
            "babesia",
            "theileria",
            "eimeria",
            "neospora",
            "gregarina",
        ],
    ),
    (
        "Host/Chordata",
        [
            "chordata",
            "vertebrata",
            "ascidiacea",
            "tunicata",
            "molgula",
            "ciona",
            "mammalia",
            "homo sapiens",
        ],
    ),
    (
        "Bacteria",
        [
            "bacteria",
            "proteobacteria",
            "firmicutes",
            "actinobacteria",
            "bacteroidetes",
            "cyanobacteria",
            "spirochaetes",
        ],
    ),
    (
        "Other Eukaryotes",
        [
            "eukaryota",
            "fungi",
            "viridiplantae",
            "metazoa",
            "stramenopiles",
            "alveolata",
            "rhizaria",
            "amoebozoa",
            "ciliophora",
        ],
    ),
]

# Final fallback bucket if nothing matched.
DEFAULT_CATEGORY = "Other"


def load_config(config_path: str) -> dict:
    """Load a YAML config file and return it as a dict."""
    if not os.path.isfile(config_path):
        sys.exit(f"ERROR: Config file not found: {config_path}")
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def assign_category(name: str) -> str:
    """Return the category label for a single taxon name."""
    haystack = (name or "").lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def standardize(df: pd.DataFrame, db_name: str, kraken_rank: str) -> pd.DataFrame:
    """
    Collapse a parsed Kraken2 table for one database into per-category
    percentages.

    Kraken2 reports include an "Unclassified" row at rank "U". To avoid
    losing it when filtering to species-level rows, we extract the
    Unclassified row separately, filter the rest to the requested rank,
    categorize, and concatenate.
    """
    if "percent" not in df.columns or "name" not in df.columns:
        sys.exit(
            f"ERROR: standardize() requires 'percent' and 'name' columns; "
            f"got {list(df.columns)}"
        )

    df = df.copy()

    # Pull out the unclassified row (rank "U") before any rank filtering,
    # so it doesn't get dropped.
    unclassified = df[df["rank"] == "U"][["percent", "name"]].copy()

    # Restrict the rest to the requested rank (default 'S' = species).
    body = df[df["rank"] == kraken_rank][["percent", "name"]].copy()

    # Combine: unclassified row + species-rank rows.
    combined = pd.concat([unclassified, body], ignore_index=True)
    combined["category"] = combined["name"].map(assign_category)

    summary = (
        combined.groupby("category", as_index=False)["percent"]
        .sum()
    )

    # Ensure every category appears (even if 0%) so the three databases
    # produce aligned tables.
    all_categories = [cat for cat, _ in CATEGORY_KEYWORDS] + [DEFAULT_CATEGORY]
    summary = (
        summary.set_index("category")
        .reindex(all_categories, fill_value=0.0)
        .reset_index()
    )
    summary["percent"] = summary["percent"].astype(float).round(4)
    summary["db_name"] = db_name

    return summary[["db_name", "category", "percent"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tables_dir = cfg["output"]["tables"]
    os.makedirs(tables_dir, exist_ok=True)

    kraken_rank = cfg.get("params", {}).get("kraken_rank", "S")

    db_entries = cfg.get("databases", [])
    if not db_entries:
        sys.exit("ERROR: No databases defined in config.yaml under 'databases'.")

    for entry in db_entries:
        db_name = entry["name"]
        in_path = os.path.join(tables_dir, f"kraken_parsed_{db_name}.csv")
        if not os.path.isfile(in_path):
            sys.exit(
                f"ERROR: Required input not found: {in_path}. "
                f"Did you run 01_parse_kraken.py for db-name='{db_name}'?"
            )

        print(f"[03_standardize_taxa] Loading {in_path}")
        parsed = pd.read_csv(in_path)
        summary = standardize(parsed, db_name, kraken_rank)

        out_path = os.path.join(tables_dir, f"kraken_standardized_{db_name}.csv")
        summary.to_csv(out_path, index=False)
        print(f"[03_standardize_taxa] Wrote {out_path}")


if __name__ == "__main__":
    main()
