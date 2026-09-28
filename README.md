# Uncertainty-aware life-cycle modelling for building renovation

**Parisa Hosseini | Python research demonstrator | v3.2.0 bounded research release | 28 September 2026**

A reproducible research framework for comparing illustrative building-renovation packages under economic and lifecycle uncertainty. The project combines Monte Carlo life-cycle costing, stochastic component renewals, stakeholder accounting, explicit 30/50/60-year reference-study-period logic, traceable lifecycle-carbon consequences, operational-energy accounting, end-of-life modelling, and machine-readable module-coverage gating.

The purpose is to demonstrate **modelling readiness, traceability, and transparent reasoning**. The supplied building budgets, lifetime ranges, multipliers, thresholds, and environmental inventories are illustrative or intentionally unpopulated where source-backed case data are unavailable. This is **not** a calibrated building model, an empirical climate-resilience study, or a certified standards-compliance assessment.

## v3.2.0 research release

The v3.2.0 release closes the bounded lifecycle-carbon architecture of the demonstrator. It integrates:

| Area | Implemented scope |
|---|---|
| Economic decision core | Monte Carlo life-cycle costing, stakeholder perspectives, uncertainty and robustness diagnostics |
| Lifecycle architecture | Canonical component events, retained-vs-new state logic, replacement generations, RSP boundary state, 30/50/60-year horizons |
| A1–A3 | Initial product-stage `GWP_TOTAL` consequences |
| A4 | Initial transport to site |
| A5.1 | Pre-construction removal of existing works, including explicitly mapped removal, transport and treatment flows |
| A5.2–A5.3 | Construction/installation and current-construction waste |
| B4 | Complete replacement-event family: product, inbound transport, installation, removal, outbound waste transport, processing and disposal |
| B6 | Operational-energy GWP from explicit physical imported-energy flows and annual carrier factor schedules |
| C1–C4 | Terminal deconstruction/demolition, transport, waste processing and disposal from explicit end-of-life assignments |
| D1/D2 | Separate beyond-boundary material-recovery and exported-energy results; never silently netted into A–C |
| Coverage gate | Explicit module applicability, assessment status, lifecycle aggregation and Whole-Life Carbon claim guard |

The bounded release explicitly defers B1, B2, B3, B5, B7 and B8. A5.4 worker transport, environmental-factor uncertainty sampling, carbon discounting, calibrated case-specific LCA, and certified EN 15978 compliance claims also remain outside the current release.

See [`docs/release/IMPLEMENTED_SCOPE.md`](docs/release/IMPLEMENTED_SCOPE.md) for the concise implemented/deferred scope.

## Scientific accounting guardrails

The project is intentionally conservative about evidence and aggregation:

- **Missing evidence is never interpreted as zero.** Unpopulated production inventories return explicit not-assessed or blocked states.
- The **RSP boundary is a state, not a demolition event**. Reaching 30, 50 or 60 years does not by itself generate C1–C4.
- Terminal C/D consequences are created only from **explicit source-backed assignments**.
- B4 replacement waste and A5.1 pre-construction removal are not duplicated in terminal C-stage accounting.
- Replacement-attributable product, transport, installation, removal and waste-treatment consequences remain reported in **B4**, while source-process provenance is retained.
- B6 uses **physical energy flows**, not the legacy economic `annual_energy_savings_kwh` proxy.
- `IMPORTED` energy is the executable B6 carbon flow. `GENERATED`, `SELF_CONSUMED` and `EXPORTED` are tracked separately for physical bookkeeping.
- Exported energy is not represented as negative imported energy and is not silently credited inside B6.
- Module D is reported **separately** and is never automatically subtracted from A–C.
- Carbon engines do not resample service life; they attach consequences to the canonical lifecycle architecture.
- No carbon discounting or environmental-factor uncertainty sampling is applied in this release.
- The model does not produce a Whole-Life Carbon headline when required module coverage is incomplete.

## Default release behaviour

The public repository intentionally leaves environmental and terminal production inputs unpopulated where no source-backed case data are available. Typical default statuses therefore include:

- `NO_ASSESSMENT_BOQ_LINES` for absent executable product inventory;
- `NO_OPERATIONAL_ENERGY_FLOWS` for absent source-backed B6 carrier flows;
- `NO_END_OF_LIFE_OR_D_ASSIGNMENTS` for absent terminal C/D assignments;
- `EXPLICIT_COVERAGE_GATE_ACTIVE` for lifecycle aggregation and claim control.

These statuses mean **not assessed**, not zero impact.

The default demonstrator can therefore report assessed partial lifecycle GWP with explicit coverage, but it does **not** label the default result Whole-Life Carbon.

## Validation and release evidence

The final v3.2.0 code tree was validated with:

- **236/236 tests PASS**, executed in five warnings-as-errors chunks: `99 + 56 + 27 + 47 + 7`;
- Python byte-compilation: **PASS**;
- direct 10,000-future parity against the M3.1.1 hard-frozen baseline with seed `20260726`;
- **81/81 common non-manifest outputs byte-identical** at each 30/50/60-year horizon;
- unchanged lifecycle-event counts of **94,164 / 209,348 / 256,953** for 30/50/60 years;
- zero unexpected common-output differences;
- a fresh default **10,000-future run with convergence diagnostics and charts: PASS**.

Primary evidence:

- [`VALIDATION.md`](VALIDATION.md) — current verification summary and release qualifications;
- [`docs/FINAL_RELEASE_INTEGRITY.md`](docs/FINAL_RELEASE_INTEGRITY.md) — final release-integrity audit;
- [`docs/M4_END_OF_LIFE_MODULE_D_REPORT.md`](docs/M4_END_OF_LIFE_MODULE_D_REPORT.md) — terminal C1–C4 and separate D1/D2 semantics;
- [`docs/M5_LIFECYCLE_AGGREGATION_REPORT.md`](docs/M5_LIFECYCLE_AGGREGATION_REPORT.md) — applicability, coverage and aggregation gate;
- [`docs/M4_M5_TEST_RESULT.txt`](docs/M4_M5_TEST_RESULT.txt) — final 236-test and full-run evidence;
- [`docs/M4_M5_PARITY_DETAILS.json`](docs/M4_M5_PARITY_DETAILS.json) — direct 30/50/60-year M3.1.1 → v3.2.0 parity evidence;
- [`ASSUMPTIONS.md`](ASSUMPTIONS.md) — accounting boundary, assumptions and scientific limitations;
- [`RELEASE_NOTES.md`](RELEASE_NOTES.md) — v3.2.0 release summary.

## Architecture

```text
Illustrative renovation scenarios
        │
        ├── Monte Carlo economic futures
        │       ├── owner
        │       ├── tenant
        │       └── combined-private
        │
        ├── Canonical lifecycle architecture
        │       ├── component state
        │       ├── replacement generations
        │       ├── lifecycle-event ledger
        │       └── RSP boundary state
        │
        ├── Physical / evidence gates
        │       ├── BoQ and reference inventory
        │       ├── environmental-factor registry
        │       ├── unit compatibility
        │       └── explicit assignments
        │
        ├── Lifecycle-carbon consequence engines
        │       ├── A1–A3 / A4 / A5.1–A5.3
        │       ├── B4 / B6
        │       ├── C1–C4
        │       └── D1 / D2 kept separate
        │
        └── Module applicability + coverage gate
                ├── assessed partial A–C carbon
                ├── separate Module D summary
                └── Whole-Life Carbon claim guard
```

## Run and reproduce

The validated release used Python 3.12 and the exact package versions recorded in [`requirements-reproduced.txt`](requirements-reproduced.txt).

Prefer a fresh environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-reproduced.txt
python -m unittest discover -s tests -v
python renovation_lcc.py
```

Windows activation:

```text
.venv\Scripts\activate
```

`requirements.txt` specifies compatible ranges for other environments; it is not the exact reproducibility lock.

Example 10,000-future run:

```sh
python renovation_lcc.py \
  --input inputs/renovation_scenarios.csv \
  --components inputs/components.csv \
  --config inputs/model_config.json \
  --stress-cases inputs/climate_stress_scenarios.csv \
  --simulations 10000 \
  --seed 20260726 \
  --output-dir outputs_new
```

Useful options:

- `--horizon-mode legacy_30`
- `--horizon-mode levels_50`
- `--horizon-mode rics_60`
- `--no-charts` to avoid chart generation;
- `--skip-convergence` to omit the expensive multi-size/seed convergence diagnostic.

Use a fresh output directory for each experiment.

## Reference-study-period profiles

The project supports three explicit research horizons:

- `legacy_30` — 30-year continuity horizon;
- `levels_50` — 50-year Level(s)-aligned research horizon;
- `rics_60` — 60-year RICS-WLCA-aligned comparison horizon.

The profile names document methodological alignment only; they do **not** claim formal standards compliance.

Lifecycle events exactly at or beyond the selected horizon remain excluded from within-RSP event totals. Boundary state is recorded separately.

## Economic accounting core

Every scenario input is a difference from the reference. Zero reference cash flows do not mean that an existing building has no operating expenses.

```text
E = present value of avoided energy bills
R = present value of additional rent transferred from tenant to owner
V = discounted terminal property premium
C = initial investment after grants
M = discounted incremental routine maintenance
Q = discounted incremental component renewal costs
a = owner's share of E

Owner            = a E + R + V - C - M - Q
Tenant           = (1-a) E - R
Combined private = E + V - C - M - Q = Owner + Tenant
```

Public grants remain external benefits to the private boundary. This is not a social-welfare account. Initial and replacement costs are paid by the owner; grants apply only to the initial investment.

## Component renewal model

For each component and simulated future, the model samples the relevant lifecycle interval. A life ending strictly before the horizon triggers replacement; a renewed component receives a fresh full service-life interval, allowing multiple renewals.

For `RETAINED_EXISTING` components, the first interval is an explicitly modelled remaining-life distribution. The model does not infer remaining life from component age. Subsequent replacements use full service-life distributions.

Stable uncertainty keys and independently keyed renewal streams prevent scenario reordering or option removal from silently redrawing unrelated components.

## Operational-energy layer

B6 is an **accounting layer**, not a building-energy simulation engine.

Operational inputs use explicit physical flows and carrier-specific annual factor schedules. Imported energy generates B6 GWP; on-site generation, self-consumption and export are retained as separate physical bookkeeping flows.

Missing annual factor coverage blocks calculation under the supported `ERROR_IF_MISSING` policy. There is no hidden interpolation, extrapolation, assumed grid decarbonisation, or automatic export credit inside B6.

## Terminal C-stage and Module D

Terminal C1–C4 results require explicit end-of-life assignments. The model does not assume that the building is demolished simply because the reference-study period ends.

The implemented terminal architecture supports:

- `C1` deconstruction/demolition activity;
- `C2` outbound transport;
- `C3` waste processing;
- `C4` disposal;
- `D1` material recovery/reuse/recycling benefits or loads beyond the system boundary;
- `D2` exported-energy results beyond the system boundary.

D1 and D2 are reported separately and are not netted into A–C totals.

## Lifecycle aggregation and coverage gate

The release maintains explicit module applicability and assessment status instead of interpreting missing data as zero.

The coverage layer distinguishes assessed, deferred, missing-data and applicability states and controls whether a lifecycle-carbon headline is allowed.

Key generated outputs include:

- `lifecycle_module_coverage.csv`
- `lifecycle_carbon_aggregation.csv`
- `separate_module_d_summary.csv`
- `lifecycle_aggregation_status.json`

When coverage is incomplete, the model reports partial assessed A–C carbon with explicit coverage rather than labelling the result Whole-Life Carbon.

## Key generated outputs

Generated `outputs/` files are **not committed** to the public source repository. They are regenerated locally and excluded through `.gitignore`.

| Output | Purpose |
|---|---|
| `scenario_summary.csv` | Economic outcome metrics, Pareto flag and optional preference score |
| `simulation_results.csv` | Main Monte Carlo futures/options and stakeholder cash flows |
| `sampled_futures.csv` | Economic uncertainty draws |
| `component_lifecycle_draws.csv` | First interval, renewal count and PV renewal cost per future/component |
| `lifecycle_event_ledger.csv` | Canonical intervention lifecycle-event ledger |
| `lifecycle_replacements.csv` | Replacement times and associated economic renewal costs |
| `rsp_boundary_state.csv` | RSP-boundary component state without creating a fictitious boundary event |
| `reference_lifecycle_event_ledger.csv` / `reference_rsp_boundary_state.csv` | Reference-side lifecycle outputs when documented reference inventory is supplied |
| `physical_quantity_coverage.csv` | Component-level physical-quantity coverage without cost-to-quantity inference |
| `carbon_consequence_ledger.csv` | Traceable lifecycle-carbon consequence ledger for implemented A-, B-, C-stage and separate Module D consequences |
| `assessed_product_carbon_by_module.csv` | Assessed A1–A3 and B4 product-stage GWP contributions |
| `assessed_a4_transport_carbon_by_module.csv` | Assessed A4 transport GWP contributions |
| `assessed_a5_construction_carbon_by_module.csv` | Assessed A5.2/A5.3 construction and current-construction-waste contributions |
| `assessed_a5_1_preconstruction_removal_carbon_by_module.csv` | Assessed A5.1 pre-construction removal contributions |
| `assessed_b4_replacement_transport_carbon_by_module.csv` | Assessed B4 inbound replacement-transport contributions |
| `assessed_b4_event_process_carbon_by_module.csv` | Assessed B4 installation/removal/outbound-waste/treatment contributions |
| `operational_energy_coverage.csv` | B6 physical-flow and annual factor-schedule coverage |
| `assessed_operational_carbon_by_module.csv` | Assessed B6 imported-energy GWP contribution |
| `end_of_life_coverage.csv` | Terminal C-stage/D1 assignment coverage |
| `d2_export_coverage.csv` | D2 exported-energy assignment/factor coverage |
| `assessed_end_of_life_and_module_d_carbon_by_module.csv` | Assessed C1–C4 and separate D1/D2 consequences by module |
| `lifecycle_module_coverage.csv` | Scenario/module applicability and assessment status |
| `lifecycle_carbon_aggregation.csv` | Coverage-gated lifecycle-carbon aggregation |
| `separate_module_d_summary.csv` | Module D summary kept outside A–C aggregation |
| `run_manifest.json` | Version, hashes, seed, sampling scheme and release metadata |
| `end_of_life_module_d_engine_status.json` | Terminal C/D engine status and guard metadata |
| `lifecycle_aggregation_status.json` | Coverage-gate and Whole-Life Carbon claim status |

Charts are generated as PNG/SVG when requested.

## Repository structure

```text
.
├── inputs/                       # illustrative and schema-valid production inputs
├── tests/                        # unit and integration tests
├── docs/                         # implementation, validation and parity evidence
│   └── release/                  # concise release-scope documentation
├── provenance/
│   ├── v2/                       # archived v2 source/configuration snapshot
│   └── historical_checksums/     # historical milestone checksum manifests
├── scripts/                      # audit utilities
├── v3_schema_templates/          # reusable schema templates
├── renovation_lcc.py             # command-line entry point and economic core
├── component_lifecycle.py        # lifecycle intervals and replacement schedules
├── lifecycle_events.py           # canonical lifecycle-event representation
├── carbon_consequences.py        # product-stage carbon consequences
├── b6_operational.py             # operational-energy accounting
├── end_of_life.py                # terminal C1–C4 and separate D1/D2
├── lifecycle_aggregation.py      # module coverage and aggregation gate
├── VALIDATION.md
├── ASSUMPTIONS.md
├── CHANGELOG.md
├── RELEASE_NOTES.md
└── CITATION.cff
```

## Sensitivity and robustness diagnostics

The economic demonstrator retains:

- fixed-anchor preference diagnostics;
- option-set sensitivity checks;
- nested Monte Carlo convergence analysis;
- cross-seed stability checks;
- one-at-a-time economic sensitivity;
- rank-correlation diagnostics;
- stakeholder allocation sensitivity;
- paired accounting stress tests;
- an external performance-stress interface using explicitly hypothetical proxy cases.

These diagnostics support transparent numerical reasoning. They are not empirical predictions of real-world building performance.

## Scope limitations and next research steps

Further work should be driven by access to source-backed building data or a specific research question. Current limitations include:

- no calibration against a real building;
- no direct dynamic building-energy or climate simulation;
- no indoor-comfort model;
- no multi-impact environmental LCA beyond the implemented `GWP_TOTAL` architecture;
- no empirical environmental validation;
- no B1/B2/B3/B5/B7/B8 environmental assessment in the bounded release;
- no A5.4 worker-transport assessment;
- no environmental-factor uncertainty sampling;
- no carbon discounting;
- no certified EN 15978, Level(s), or RICS WLCA compliance claim.

The current architecture is designed so that source-backed inventories, factors and explicit module assignments can be added without changing the core traceability and coverage logic.

## Release history and provenance

- `v2.1.0` — verified economic-core checkpoint preserved in Git history and under `provenance/v2/`;
- `v3.2.0` — bounded research release closing the current lifecycle-carbon architecture.

Detailed milestone history is retained in [`CHANGELOG.md`](CHANGELOG.md), `docs/`, and `provenance/historical_checksums/` rather than repeated in this README.

## Author and citation

Developed by **Parisa Hosseini**.

Research profiles:

- [ORCID](https://orcid.org/0009-0009-0168-8912)
- [Google Scholar](https://scholar.google.com/citations?user=L2dOgkkAAAAJ&hl=en)
- [LinkedIn](https://www.linkedin.com/in/parisa-hosseini-216886310)

Citation metadata are provided in [`CITATION.cff`](CITATION.cff).

The code is released under the [MIT License](LICENSE).

The project was iteratively developed and reviewed with AI-assisted debugging and documentation support; the author is responsible for the modelling choices, verification and interpretation.
