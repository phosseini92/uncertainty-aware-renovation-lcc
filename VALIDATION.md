# Validation record

## Release verification

- Release: v2.1 public-repository package
- Verification date: 2026-09-04
- Baseline interpreter: Python 3.12
- Main-run seed: `20260726`
- Unit and integration tests: **20 passed**
- Compilation: all Python source and test modules compiled successfully
- Accounting identity: `owner + tenant = combined private` verified within
  floating-point tolerance
- Option-set diagnostic: retained fixed-anchor scores remained invariant and no
  pairwise preference reversal was detected
- Sampling diagnostic: smaller sample sizes are exact prefixes of larger samples
  for a fixed seed
- Cross-environment reproduction: compared with the supplied v2.1 release, the
  largest absolute difference across committed numeric CSV outputs was
  approximately `1.63e-9` EUR; categorical results and input tables were unchanged

## Convergence qualification

The documented diagnostic evaluates 1,000, 2,500, 5,000, 10,000 and 25,000 draws
under five independent seeds. At 10,000 draws, 59 of 60 scenario-perspective-metric
checks met the declared numerical tolerances. The single miss was tenant P95
regret for the reference: EUR 30,529 versus a EUR 30,000 tolerance. Tolerances
were not widened after observing the result.

## Reproducibility boundary

`requirements-reproduced.txt` records the exact package versions used for the
documented run; `requirements.txt` defines compatible ranges for other systems.
The release checksum file verifies packaged artifacts. Large row-level outputs
are omitted from version control and regenerated deterministically by the main
script using the documented inputs, configuration and seed.

## Scientific boundary

All budgets, lifetimes, distributions, thresholds and stress multipliers are
illustrative. The model has not been calibrated or validated against a measured
building. The stress interface is not a climate simulation, and its retained-
savings proxy is not an indoor-comfort metric. See `ASSUMPTIONS.md` and `README.md`
before interpreting the results.
