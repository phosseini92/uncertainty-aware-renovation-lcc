# Output policy

This directory retains the compact summary tables, resolved inputs, run manifest,
analysis report and publication-ready PNG/SVG figures from the documented v2.1
run.

Four large row-level files are reproducible generated data and are intentionally
excluded from version control:

- `simulation_results.csv`
- `sampled_futures.csv`
- `component_lifecycle_draws.csv`
- `lifecycle_replacements.csv`

Run `python renovation_lcc.py` to recreate the complete output set. For local
experiments, prefer a separate directory, for example:

```sh
python renovation_lcc.py --output-dir outputs_new
```

The inputs are illustrative and the outputs are conditional model results, not
empirical findings for a measured building.
