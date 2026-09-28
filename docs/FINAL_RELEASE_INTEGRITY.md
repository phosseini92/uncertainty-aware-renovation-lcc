# v3.2.0 final release integrity

Date: 2026-09-28

## Baseline

Hard-frozen pre-C/D baseline: `uncertainty-aware-renovation-lcc-v3-M3.1.1.zip`.

Source-diff audit shows that among the 21 top-level Python files shared with M3.1.1, only `renovation_lcc.py` changed. The two new computational modules are `end_of_life.py` and `lifecycle_aggregation.py`. B6 arithmetic and all other frozen top-level engines remain byte-identical to the M3.1.1 baseline.

## Regression

- Static final test inventory: 236 methods.
- Final-tree warnings-as-errors chunks: 99/99, 56/56, 27/27, 47/47, 7/7 — all PASS.
- Python compileall: PASS.
- CITATION.cff YAML parse/version check: PASS.
- README/validation/release-notes relative-link audit: PASS.
- Run-manifest coverage/headline flags are emitted once from `lifecycle_aggregation_meta`; duplicate literal-key audit: PASS.

## Numerical parity

Direct 10,000-future runs, seed `20260726`, M3.1.1 baseline versus v3.2.0:

- 30 years: 81/81 common non-manifest files byte-identical; 94,164 lifecycle-event rows.
- 50 years: 81/81 common non-manifest files byte-identical; 209,348 lifecycle-event rows.
- 60 years: 81/81 common non-manifest files byte-identical; 256,953 lifecycle-event rows.
- Unexpected differences among common non-manifest outputs: 0.

Twelve new M4/M5 output files are additive at each horizon.

## Full default execution

Fresh final-tree default run: 10,000 futures, seed `20260726`, convergence diagnostics enabled, charts enabled — PASS. Expected chart and convergence artefacts were generated.

Production terminal C/D inputs are unpopulated, so default status is `NO_END_OF_LIFE_OR_D_ASSIGNMENTS`; this means not assessed, not zero. The coverage gate is active and default Whole-Life Carbon headline generation remains disabled because required/deferred evidence is incomplete.

## Integrity policy

`V3.2.0_SHA256SUMS.txt` and `SHA256SUMS.txt` are the current release manifests. Historical milestone checksum manifests are retained only under `provenance/historical_checksums/`.
