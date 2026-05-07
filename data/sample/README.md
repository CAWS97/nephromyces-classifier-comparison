# Sample Test Data

A small subset (10,000 ONT reads, ~8.6 MB) for verifying the pipeline runs end-to-end. Not for biological inference — the full dataset is not publicly distributed and produces different results.

## Use it

Edit `config/config.yaml` to point at this file:

```yaml
input:
  reads: "data/sample/sample_reads.fastq"
```

Then run `sbatch submit_pipeline.sh`.

## Make your own subset

```bash
head -n 40000 your_data.fastq > data/sample/sample_reads.fastq
```

Note: anything saved under `data/raw/` is gitignored by default (so personal data doesn't get committed accidentally). Saving subsets under `data/sample/` keeps them tracked.
