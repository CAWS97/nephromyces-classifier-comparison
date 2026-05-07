
# Nephromyces Classifier Comparison

A reproducible pipeline that runs the same metagenomic FASTQ input through Kraken2 against three different reference databases, then compares the results to quantify how database choice affects taxonomic interpretation in a *Nephromyces*-containing sample.

The three databases compared are:

| Database | Scope |
|---|---|
| `kraken2_basic` | Bacteria + archaea + viruses (no eukaryotes) |
| `PlusPF` | Standard build + RefSeq protozoa + fungi |
| `PrackenDB` | GenBank + RefSeq bacteria/archaea/protists/fungi + human + viral + UniVec |


```

## Repository Structure

nephromyces-classifier-comparison/
├── README.md                       ← this file
├── environment.yml                 ← Python dependencies (conda)
├── run_pipeline.sh                 ← main pipeline (called by SLURM)
├── submit_pipeline.sh              ← SLURM submission wrapper
│
├── config/
│   └── config.yaml                 ← all paths and parameters
│
├── data/
│   └── raw/                        ← input FASTQ + Kraken2 reports
│
├── scripts/
│   ├── 01_parse_kraken.py          ← parse Kraken2 report into tidy CSV
│   ├── 03_standardize_taxa.py      ← group taxa into shared categories
│   ├── 04_compare_databases.py     ← merge per-database summaries + deltas
│   └── 05_plot_results.py          ← bar + stacked-bar figures
│
├── results/
│   ├── tables/                     ← CSV outputs
│   └── figures/                    ← PNG + PDF figures
│
├── logs/                           ← SLURM .out and .err logs
│
├── paper/
│   └── final_paper.pdf             ← writeup of methods and results
│
└── ai_statement/
	└── ai_use_statement.pdf        ← statement on AI tool usage

```

## Input Requirements

The pipeline accepts **single-end FASTQ data**:

- **Oxford Nanopore long reads** (PromethION/MinION) — the format the pipeline was built and validated against.
- **Illumina short reads** in single-end format also work, since Kraken2 is read-length agnostic.
- **Paired-end Illumina** reads need to be concatenated into a single file (`cat R1.fastq R2.fastq > reads.fastq`) before running.
- The input file must be **uncompressed** (`.fastq`, not `.fastq.gz`). Decompress with `zcat` first if needed.

The expected input location is `data/raw/reads.fastq`. Edit `config/config.yaml` to point elsewhere.

---

## Installation

Designed for the **URI Unity supercluster**, but adaptable to any Linux/HPC system with Kraken2 installed and access to Kraken2 databases.

```bash
git clone git@github.com:CAWS97/nephromyces-classifier-comparison.git
cd nephromyces-classifier-comparison
```

Python dependencies (`pandas`, `matplotlib`, `pyyaml`) are auto-installed into the user's local Python environment on first run.

A conda environment file is also provided as a fallback:

```bash
conda env create -f environment.yml
conda activate nephromyces-compare
```

---

## How to Run

### On URI Unity (recommended)

The full pipeline is launched as a single SLURM job:

```bash
sbatch submit_pipeline.sh
```

`submit_pipeline.sh` handles module loading (`python/3.10.14`, `kraken2/2.1.2`), runs Kraken2 against all three databases, and runs the Python analysis scripts in order. Logs go to `logs/nephromyces-<jobid>.out` and `.err`.

Default SLURM resources (modify in `submit_pipeline.sh` if needed):

- 8 CPUs
- 200 GB memory (required for PrackenDB)
- 48 hours wall-clock cap
- CPU partition with avx512

### Watching progress

```bash
squeue -u $USER                                  # check job status
tail -f logs/nephromyces-<jobid>.out             # follow live output
```

### Analysis-only mode (skip Kraken2)

If Kraken2 reports for all three databases already exist in `data/raw/`:

```bash
module load python/3.10.14
python scripts/01_parse_kraken.py     --config config/config.yaml --db-name kraken2_basic
python scripts/01_parse_kraken.py     --config config/config.yaml --db-name pluspf
python scripts/01_parse_kraken.py     --config config/config.yaml --db-name prackendb
python scripts/03_standardize_taxa.py --config config/config.yaml
python scripts/04_compare_databases.py --config config/config.yaml
python scripts/05_plot_results.py     --config config/config.yaml
```

---

## Configuration

All paths and parameters live in `config/config.yaml`. There are no hardcoded paths in any of the scripts.

`config.yaml` controls:

- The location of input reads
- The location of each Kraken2 database (defaults to URI Unity paths under `/datasets/bio/kraken2/`)
- Where Kraken2 reports get written
- Where final tables and figures get written
- The taxonomic rank used for the standardization step

---

## Pipeline Steps
data/raw/reads.fastq
│
├─► Kraken2 (kraken2_basic)  ──► data/raw/kraken_report_basic.txt
├─► Kraken2 (PlusPF)          ──► data/raw/kraken_report_pluspf.txt
└─► Kraken2 (PrackenDB)       ──► data/raw/kraken_report_prackendb.txt
│
▼
[01] parse Kraken2 reports (one per database)
[03] standardize taxa into shared categories
[04] merge into long + wide comparison tables
[05] generate bar + stacked-bar figures
│
▼
results/tables/ + results/figures/
| Script | Purpose |
|---|---|
| `01_parse_kraken.py` | Reads a Kraken2 report into a tidy CSV. Invoked once per database. |
| `03_standardize_taxa.py` | Groups taxa from each report into shared biological categories: Unclassified, Host/Chordata, Bacteria, Apicomplexa/Nephromyces-related, Other Eukaryotes, Other. |
| `04_compare_databases.py` | Merges all three standardized summaries into long and wide tables, with pairwise deltas. |
| `05_plot_results.py` | Generates classified-vs-unclassified bar plot and stacked-bar of taxonomic composition (PNG + PDF). |

---

## Outputs
---

## Reproducibility Notes

- All file paths are read from `config/config.yaml`; nothing is hardcoded.
- The submission script anchors itself to the repo root via `$SLURM_SUBMIT_DIR`, so the pipeline runs correctly regardless of where the repo is cloned.
- No random number generation is used in the analysis steps, so output is deterministic given the same inputs and database versions.
- Kraken2 databases on the URI Unity cluster are updated periodically; record database modification dates when reporting results.

---

## Caveats

This pipeline reports what each Kraken2 database *says* about the data, not ground truth.

- **Unclassified reads are not assumed to be *Nephromyces***. They could come from many sources: sequencing artifacts, host regions absent from the database, uncharacterized bacteria, divergent eukaryotes, etc.
- **Differences between databases reflect both reference scope and curation depth**, not pure biology. Broader databases generally classify more reads but may include more spurious low-confidence assignments.
- **Single-sample, single-run analysis** — no statistical claims about classification accuracy can be made from this design alone. Key apicomplexan assignments should be validated with orthogonal methods (BLAST, read-level assembly, etc.).

---

## Citation

- **Kraken2**: Wood, D.E., Lu, J. & Langmead, B. *Improved metagenomic analysis with Kraken 2*. Genome Biol 20, 257 (2019). https://doi.org/10.1186/s13059-019-1891-0
