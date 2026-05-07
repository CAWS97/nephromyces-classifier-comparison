#!/usr/bin/env python3
"""
01_parse_kraken.py

Parse a Kraken2 report file into a tidy pandas DataFrame and write it to CSV.

This script is invoked once per database. The database name (used as a
label in downstream tables) and the path to its Kraken2 report file are
passed as CLI arguments so the same script can handle all three databases
without modification.

Kraken2 report format (tab-separated, no header):
    1. Percentage of reads covered by the clade rooted at this taxon
    2. Number of reads covered by the clade rooted at this taxon
    3. Number of reads assigned directly to this taxon
    4. Rank code (U, R, D, K, P, C, O, F, G, S, ...)
    5. NCBI taxonomic ID
    6. Indented scientific name

Usage:
    python scripts/01_parse_kraken.py \
        --config config/config.yaml \
        --db-name pluspf
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
import yaml


# Column names matching the Kraken2 report layout.
KRAKEN_COLUMNS = [
    "percent",
    "reads_clade",
    "reads_taxon",
    "rank",
    "taxid",
    "name",
]


def load_config(config_path: str) -> dict:
    """Load a YAML config file and return it as a dict."""
    if not os.path.isfile(config_path):
        sys.exit(f"ERROR: Config file not found: {config_path}")
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def find_db_entry(cfg: dict, db_name: str) -> dict:
    """Look up a database entry by `name` in the config."""
    for entry in cfg.get("databases", []):
        if entry.get("name") == db_name:
            return entry
    available = [e.get("name") for e in cfg.get("databases", [])]
    sys.exit(
        f"ERROR: db-name '{db_name}' not found in config. "
        f"Available: {available}"
    )


def parse_kraken_report(report_path: str) -> pd.DataFrame:
    """Read a Kraken2 report into a tidy DataFrame."""
    if not os.path.isfile(report_path):
        sys.exit(f"ERROR: Kraken2 report not found: {report_path}")

    df = pd.read_csv(
        report_path,
        sep="\t",
        header=None,
        names=KRAKEN_COLUMNS,
        dtype={
            "percent": float,
            "reads_clade": int,
            "reads_taxon": int,
            "rank": str,
            "taxid": int,
            "name": str,
        },
    )

    # The `name` column is indented to reflect tree depth; we want the bare name.
    df["name"] = df["name"].str.strip()

    # Sanity check.
    if (df["percent"] > 100.5).any():
        sys.exit("ERROR: Kraken2 report contains percent values > 100.")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        help="Path to YAML config file (e.g. config/config.yaml)",
    )
    parser.add_argument(
        "--db-name",
        required=True,
        help="Name of the database in config.yaml (e.g. 'pluspf')",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_entry = find_db_entry(cfg, args.db_name)

    report_path = db_entry["report"]
    tables_dir = cfg["output"]["tables"]
    os.makedirs(tables_dir, exist_ok=True)

    print(f"[01_parse_kraken] db={args.db_name}  report={report_path}")
    df = parse_kraken_report(report_path)

    # Tag every row with the database name so downstream merges are unambiguous.
    df["db_name"] = args.db_name

    out_path = os.path.join(tables_dir, f"kraken_parsed_{args.db_name}.csv")
    df.to_csv(out_path, index=False)
    print(f"[01_parse_kraken] Wrote {len(df):,} rows -> {out_path}")


if __name__ == "__main__":
    main()
