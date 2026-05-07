#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_pipeline.sh
#
# Main entry point for the Nephromyces classifier comparison pipeline.
# Runs Kraken2 once per database listed in config/config.yaml, then runs
# the Python analysis chain (parse -> standardize -> compare -> plot).
#
# Usage:
#   bash run_pipeline.sh
#   sbatch submit_pipeline.sh   (recommended on the URI Unity cluster)
# ---------------------------------------------------------------------------

set -euo pipefail

# ---------------------------------------------------------------------------
# Load required cluster modules.
# ---------------------------------------------------------------------------
echo "============================================================"
echo "[0/4] Loading modules"
echo "============================================================"

module purge
module load python/3.10.14
module load kraken2/2.1.2

# Install Python dependencies for the current user (idempotent).
python -m ensurepip --user --upgrade 2>/dev/null || true
python -m pip install --user --quiet --upgrade pip
python -m pip install --user --quiet pandas matplotlib pyyaml

# ---------------------------------------------------------------------------
# Anchor to repo root.
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CONFIG="config/config.yaml"

if [[ ! -f "${CONFIG}" ]]; then
    echo "ERROR: Config file not found at ${CONFIG}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve top-level paths and the list of databases via Python.
# Lines that come back are: <name>\t<db_path>\t<report_path>
# ---------------------------------------------------------------------------
read_yaml_value () {
    python - "$1" "$2" <<'PY'
import sys, yaml
cfg_path, key_path = sys.argv[1], sys.argv[2]
with open(cfg_path) as fh:
    cfg = yaml.safe_load(fh)
node = cfg
for k in key_path.split("."):
    node = node[k]
print(node if node is not None else "")
PY
}

list_databases () {
    python - "$1" <<'PY'
import sys, yaml
with open(sys.argv[1]) as fh:
    cfg = yaml.safe_load(fh)
for entry in cfg.get("databases", []):
    print("\t".join([entry["name"], entry["db"], entry["report"]]))
PY
}

READS=$(read_yaml_value      "${CONFIG}" "input.reads")
TABLES_DIR=$(read_yaml_value "${CONFIG}" "output.tables")
FIGURES_DIR=$(read_yaml_value "${CONFIG}" "output.figures")

mkdir -p "${TABLES_DIR}" "${FIGURES_DIR}"

THREADS="${SLURM_CPUS_PER_TASK:-4}"

# ---------------------------------------------------------------------------
# Step 1: Run Kraken2 once per database.
# ---------------------------------------------------------------------------
echo "============================================================"
echo "[1/4] Running Kraken2 against each database (threads=${THREADS})"
echo "============================================================"

while IFS=$'\t' read -r DB_NAME DB_PATH REPORT_PATH; do
    [[ -z "${DB_NAME}" ]] && continue

    echo "------------------------------------------------------------"
    echo "  database: ${DB_NAME}"
    echo "  db path : ${DB_PATH}"
    echo "  report  : ${REPORT_PATH}"
    echo "------------------------------------------------------------"

    mkdir -p "$(dirname "${REPORT_PATH}")"

    if [[ ! -d "${DB_PATH}" ]]; then
        echo "WARNING: Kraken2 DB not found at '${DB_PATH}'. Skipping ${DB_NAME}."
        echo "         (Assuming ${REPORT_PATH} already exists.)"
        continue
    fi
    if [[ ! -f "${READS}" ]]; then
        echo "WARNING: Reads file not found at '${READS}'. Skipping ${DB_NAME}."
        continue
    fi

    kraken2 \
        --db "${DB_PATH}" \
        --threads "${THREADS}" \
        --memory-mapping \
        --report "${REPORT_PATH}" \
        --output /dev/null \
        "${READS}"

done < <(list_databases "${CONFIG}")

# ---------------------------------------------------------------------------
# Step 2: Parse each Kraken2 report.
# ---------------------------------------------------------------------------
echo "============================================================"
echo "[2/4] Parsing Kraken2 reports"
echo "============================================================"

while IFS=$'\t' read -r DB_NAME DB_PATH REPORT_PATH; do
    [[ -z "${DB_NAME}" ]] && continue
    python scripts/01_parse_kraken.py --config "${CONFIG}" --db-name "${DB_NAME}"
done < <(list_databases "${CONFIG}")

# ---------------------------------------------------------------------------
# Step 3: Standardize taxa + compare across databases.
# ---------------------------------------------------------------------------
echo "============================================================"
echo "[3/4] Standardizing taxa and comparing databases"
echo "============================================================"

python scripts/03_standardize_taxa.py   --config "${CONFIG}"
python scripts/04_compare_databases.py  --config "${CONFIG}"

# ---------------------------------------------------------------------------
# Step 4: Plot.
# ---------------------------------------------------------------------------
echo "============================================================"
echo "[4/4] Generating figures"
echo "============================================================"

python scripts/05_plot_results.py --config "${CONFIG}"

echo "============================================================"
echo "Pipeline complete."
echo "  Tables:  ${TABLES_DIR}"
echo "  Figures: ${FIGURES_DIR}"
echo "============================================================"
