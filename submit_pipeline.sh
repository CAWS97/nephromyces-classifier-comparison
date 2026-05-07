#!/bin/bash
# ===========================================================================
# submit_pipeline.sh
#
# SLURM submission wrapper for the Nephromyces classifier comparison pipeline.
# This script is designed so anyone can run the full pipeline with a single
# command:
#
#     sbatch submit_pipeline.sh
#
# All paths used by the pipeline are relative to the directory containing
# THIS file (the repo root), so the project works regardless of where it
# was cloned. The script also auto-detects how many CPUs SLURM gave it.
#
# Logs are written to:
#     <repo_root>/logs/nephromyces-<jobid>.out
#     <repo_root>/logs/nephromyces-<jobid>.err
# ===========================================================================

# ---------------------------------------------------------------------------
# SLURM resource directives.
# Adjust these if your data is much larger / smaller than the default test.
# ---------------------------------------------------------------------------
#SBATCH --job-name=nephromyces           # name shown in `squeue`
#SBATCH --output=logs/nephromyces-%j.out # %j is replaced by the job ID
#SBATCH --error=logs/nephromyces-%j.err
#SBATCH --ntasks=1                       # one task (Kraken2 is one process)
#SBATCH --cpus-per-task=8                # threads available to the task
#SBATCH --mem=200G                       # RAM budget; PrackenDB is large
#SBATCH --time=48:00:00                  # wall-clock cap
#SBATCH --partition=cpu                  # CPU partition (no GPU needed)
#SBATCH --constraint=avx512              # match other Kraken2 jobs on Unity

# ---------------------------------------------------------------------------
# Bash safety flags:
#   -e : exit immediately on any failed command
#   -u : error on use of undefined variables
#   -o pipefail : a pipeline fails if any stage fails (not just the last)
# ---------------------------------------------------------------------------
set -euo pipefail

# ---------------------------------------------------------------------------
# Anchor everything to the repo root, regardless of where sbatch was called.
# BASH_SOURCE[0] is the path to this script; dirname + cd + pwd resolves it
# to an absolute, canonical path. That way `bash run_pipeline.sh` below
# always finds the right file.
# ---------------------------------------------------------------------------
SCRIPT_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "${SCRIPT_DIR}"

# ---------------------------------------------------------------------------
# Print a small header to the .out log so we can always tell, after the fact,
# what node the job ran on and how many CPUs it actually got.
# ---------------------------------------------------------------------------
echo "============================================================"
echo "Job ID:     ${SLURM_JOB_ID:-N/A}"
echo "Job name:   ${SLURM_JOB_NAME:-nephromyces}"
echo "Node:       $(hostname)"
echo "Repo root:  ${SCRIPT_DIR}"
echo "Started:    $(date)"
echo "CPUs:       ${SLURM_CPUS_PER_TASK:-?}"
echo "Memory:     ${SLURM_MEM_PER_NODE:-?} MB (per node)"
echo "============================================================"

# ---------------------------------------------------------------------------
# Hand off to the main pipeline. run_pipeline.sh handles:
#   - module loading (python, kraken2)
#   - reading database paths from config/config.yaml
#   - running Kraken2 once per database
#   - parsing, standardizing, comparing, and plotting via the Python scripts
# ---------------------------------------------------------------------------
bash run_pipeline.sh

echo "============================================================"
echo "Finished:   $(date)"
echo "============================================================"
