# v3.2.0 Research Release

This release is the bounded feature-complete research demonstrator prepared for public GitHub publication and PhD-application review.

## What is implemented

- uncertainty-aware life-cycle cost and stakeholder decision core;
- 30/50/60-year nested horizon architecture and canonical replacement-event ledger;
- provenance-gated physical BoQ and environmental-factor registries;
- A1-A3, A4, A5.1-A5.3;
- complete B4 replacement family;
- B6 operational energy using explicit imported-energy flows and annual factor schedules;
- terminal C1-C4 from explicit end-of-life assignments;
- separate D1 material-recovery and D2 exported-energy reporting;
- explicit module-applicability and coverage gating;
- partial A-C aggregation that cannot be mislabeled as complete Whole-Life Carbon when coverage is incomplete.

## Deliberately deferred

B1, B2, B3, B5, B7, B8, A5.4, environmental-factor uncertainty sampling, carbon discounting and certified EN 15978 compliance are outside the bounded release. Their absence is reported explicitly and is never treated as zero.

## Validation

- 236/236 tests passed in five warnings-as-errors chunks.
- 10,000-future direct parity with M3.1.1 at 30/50/60 years: 81/81 common non-manifest outputs byte-identical at each horizon.
- Lifecycle-event counts unchanged: 94,164 / 209,348 / 256,953.
- Fresh 10,000-future default run with convergence diagnostics and charts passed.
- Module D remains separate from A-C; default Whole-Life Carbon headline generation remains disabled when evidence is incomplete.
- Final manifest audit confirms coverage/headline flags are sourced once from the lifecycle aggregation gate; no duplicate-key override remains.

See `VALIDATION.md` and `docs/release/IMPLEMENTED_SCOPE.md` for details.
