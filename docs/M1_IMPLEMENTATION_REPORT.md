# M1.1 + M1.2 implementation and parity audit

## Scope

This checkpoint introduces a canonical physical lifecycle-event ledger and a backward-compatible adapter for the existing v2.1 B4 replacement stream. It intentionally does **not** add carbon calculations, environmental factors, new physical quantities, new calendar-year assumptions, stakeholder allocation, or retained remaining-life semantics.

## Code changes

- Added `lifecycle_events.py`: canonical ledger schema, validation, canonical B4 replacement-event construction, and legacy adapter.
- Refactored `component_lifecycle.py` internally so retained replacement timing is represented canonically before the v2.1 event table is emitted.
- Preserved the public `renewal_costs()` return contract.
- Added `renewal_costs_with_ledger()` for the orchestrator.
- Updated `renovation_lcc.py` to write `lifecycle_event_ledger.csv` while retaining all prior outputs.
- Added `tests/test_lifecycle_event_ledger.py` with four M1-specific regression/validation tests.

## Regression results

- Original pre-M1 tests: **20/20 pass**.
- New M1 tests: **4/4 pass**.
- Current suite: **24/24 pass**.
- Python byte-compilation of the changed modules succeeds.
- Full default run (10,000 main futures, convergence diagnostics and charts) completes successfully.

## 10,000-future strict parity run

Both the audited v2.1 baseline and M1 implementation were run with `simulations=10000`, `seed=20260726`, charts disabled and convergence disabled for a direct output comparison.

**Result: all 18 common CSV outputs are byte-identical.**

| CSV | Baseline SHA-256 | M1 SHA-256 | Identical |
|---|---|---|---|
| `allocation_sensitivity.csv` | `f655ed28c2eb749f6248991e810b758bef08dd4a4cd79dafe8a614eb16cfbd10` | `f655ed28c2eb749f6248991e810b758bef08dd4a4cd79dafe8a614eb16cfbd10` | YES |
| `climate_stress_summary.csv` | `304ad8f7097ece18ab0caa73bffb8952c5d2145fbf71c8896825491fe22d08b6` | `304ad8f7097ece18ab0caa73bffb8952c5d2145fbf71c8896825491fe22d08b6` | YES |
| `component_lifecycle_draws.csv` | `6dcfd82e252f2f5f28b54206354261b0413ad225b2e8720eafede26f011b1108` | `6dcfd82e252f2f5f28b54206354261b0413ad225b2e8720eafede26f011b1108` | YES |
| `component_summary.csv` | `fd06981a2bc97c2f6281e5592c20d2ba40fdce892a0183067295c66631272a34` | `fd06981a2bc97c2f6281e5592c20d2ba40fdce892a0183067295c66631272a34` | YES |
| `lifecycle_replacements.csv` | `14fae8c32037469a0e7d423e0789e653a5fec4b73f84cb4d825a3a3a36345f8f` | `14fae8c32037469a0e7d423e0789e653a5fec4b73f84cb4d825a3a3a36345f8f` | YES |
| `option_set_sensitivity.csv` | `36b960e0eb520e75af5d71fee099c90a3b9ca3969f29e275a9c8640623c359db` | `36b960e0eb520e75af5d71fee099c90a3b9ca3969f29e275a9c8640623c359db` | YES |
| `resolved_components.csv` | `bd207f8213678601aef9a009c6b151fd79faedb21c246c6086b008c8276c4707` | `bd207f8213678601aef9a009c6b151fd79faedb21c246c6086b008c8276c4707` | YES |
| `resolved_scenarios.csv` | `bff0faf04db31665704b46cc23ee80c1ead973ff20288590f8f4dd4732c81646` | `bff0faf04db31665704b46cc23ee80c1ead973ff20288590f8f4dd4732c81646` | YES |
| `resolved_stress_cases.csv` | `96e3fe19b0c09794cfea3d09c5c4171ad2b566b26cc8b5dd94ea1c45b4c77b84` | `96e3fe19b0c09794cfea3d09c5c4171ad2b566b26cc8b5dd94ea1c45b4c77b84` | YES |
| `robust_across_stress_cases.csv` | `7841a8a146eb2a6ae72b592da65b30746573a5014ce93aad2297df6c5a77a00e` | `7841a8a146eb2a6ae72b592da65b30746573a5014ce93aad2297df6c5a77a00e` | YES |
| `sampled_futures.csv` | `94466172d46179cd5e5d570e82716d561fb240a9bed632ae398a787bb686db89` | `94466172d46179cd5e5d570e82716d561fb240a9bed632ae398a787bb686db89` | YES |
| `scenario_summary.csv` | `d5af44064e01655436259d69c789c21e7711069b7dcf3fbcd0822991d7ac5fba` | `d5af44064e01655436259d69c789c21e7711069b7dcf3fbcd0822991d7ac5fba` | YES |
| `sensitivity_oat.csv` | `f674c01c6e00000b44330071c6e795de96be2bbf813b7492173a51e3ad750656` | `f674c01c6e00000b44330071c6e795de96be2bbf813b7492173a51e3ad750656` | YES |
| `sensitivity_rank_correlations.csv` | `feef279a588fbb211e438290bab0ad7e4cc8c766d420fe97f21c375f0987624c` | `feef279a588fbb211e438290bab0ad7e4cc8c766d420fe97f21c375f0987624c` | YES |
| `simulation_results.csv` | `53e958309d9ad745cb21b6d50ecd9d5a50b22ff58dceaece2e299f4f11cd4eaf` | `53e958309d9ad745cb21b6d50ecd9d5a50b22ff58dceaece2e299f4f11cd4eaf` | YES |
| `stress_test_summary.csv` | `ae639c9d31586dd7aee272685b9288eb493cafea9bd22761019bea5c600e8342` | `ae639c9d31586dd7aee272685b9288eb493cafea9bd22761019bea5c600e8342` | YES |
| `uncertainty_summary.csv` | `be7180254b1cf33676a0fb09a61e6e6cb5d0549a0dd629add18f547c4a60d8c8` | `be7180254b1cf33676a0fb09a61e6e6cb5d0549a0dd629add18f547c4a60d8c8` | YES |
| `weight_sensitivity.csv` | `d18545a899c0bf9892c98e940c38eea245607b0043c9b638f111865e2606f56c` | `d18545a899c0bf9892c98e940c38eea245607b0043c9b638f111865e2606f56c` | YES |

New M1-only output: `lifecycle_event_ledger.csv`.

## Canonical ledger audit (documented 10,000-future run)

- Rows: **94,164**
- Unique event IDs: **94,164**
- Event types: **B4_REPLACEMENT=94,164**
- `calendar_year` entirely missing by design: **True**
- `event_quantity` entirely missing by design: **True**

The missing calendar/physical fields are deliberate: v2.1 does not contain a documented assessment base year or physical bill of quantities. M1 does not fabricate them.

## Important design note found during implementation

The first design draft omitted `future_id` from the canonical event schema. M1.1 corrects this: a Monte Carlo event ledger cannot be uniquely queried or reconciled across futures without an explicit future identifier. The audited data-architecture document has been updated accordingly.

## Gate conclusion

**M1.1 + M1.2 PASS.** The new ledger is additive and backward-compatible. No economic CSV changed, including `lifecycle_replacements.csv`, and no carbon calculation has been introduced.
