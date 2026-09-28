# Uncertainty-aware life-cycle modelling for building renovation

**Parisa Hosseini | Python research demonstrator | v3.2.0 bounded research release | economic core v2.1 | 28 September 2026**

A reproducible computational example comparing three illustrative renovation
packages with an explicit reference across owner, tenant and combined-private
perspectives. The model combines Monte Carlo life-cycle costing, uncertain
component renewals, stakeholder accounting, fixed-anchor preference diagnostics,
sample-size and seed checks, and an external performance-stress interface.

The purpose is to demonstrate modelling readiness and transparent reasoning.
All building budgets, lifetime ranges, multipliers and thresholds are illustrative.
This is not a calibrated building model or an empirical climate-resilience study.

## v3.2.0 research release — lifecycle-carbon architecture closure

The v3.2.0 release closes the bounded lifecycle-carbon architecture needed for this research demonstrator. In addition to the frozen A1–A3, A4, A5.1–A5.3, complete B4 replacement-event family and B6 operational-energy layer, the model now includes **explicit terminal C1–C4 accounting**, **separate D1/D2 beyond-boundary reporting**, and an **applicability/coverage aggregation gate**.

Terminal C/D consequences are created only from explicit source-backed assignments. Reaching the 30/50/60-year reference-study-period boundary does not itself create a demolition event. B4 replacement waste and A5.1 pre-construction removal are not duplicated in terminal C-stage accounting, and Module D is never silently netted into A–C.

The default environmental/terminal inputs remain intentionally unpopulated where source-backed case data are unavailable. Accordingly, the release can report assessed partial lifecycle GWP with explicit coverage, but it does **not** label the default result Whole-Life Carbon. B1, B2, B3, B5, B7 and B8 remain explicitly `DEFERRED_NOT_ASSESSED`, rather than being treated as zero or automatically not applicable.

Release validation on the final code tree: **236/236 tests PASS in five warnings-as-errors chunks**; direct 10,000-future parity against the M3.1.1 hard-frozen baseline preserves **81/81 common non-manifest outputs byte-for-byte** at each 30/50/60-year horizon, with lifecycle-event counts unchanged at **94,164 / 209,348 / 256,953**; and a fresh default 10,000-future run with convergence diagnostics and charts passes.

See `docs/M4_END_OF_LIFE_MODULE_D_REPORT.md`, `docs/M5_LIFECYCLE_AGGREGATION_REPORT.md`, `docs/M4_M5_TEST_RESULT.txt`, `docs/M4_M5_PARITY_DETAILS.json`, and `docs/release/IMPLEMENTED_SCOPE.md`.

## Historical checkpoint — M3.1 / M3.1.1 B6

**M3.1.1 hardening patch:** the numerical B6 equations are unchanged. Runtime metadata now explicitly declares `assessment_convention`, `generated_energy_reporting_approach`, and `factor_extrapolation_policy`; the current supported B6 policy remains `ERROR_IF_MISSING` with no interpolation/extrapolation and no D2/export credit **inside B6**. Separate D2 reporting was added later in v3.2.0 and remains outside A–C. Public version metadata, validation summaries, checksum placement, and evidence links were synchronized for release consistency.

M3.1 adds **B6 operational-energy GWP** through an explicit physical-flow and calendar-year factor-schedule layer. Imported energy is the only flow that creates B6 consequences. Onsite `GENERATED`, `SELF_CONSUMED`, and `EXPORTED` flows are tracked separately for physical bookkeeping; exported energy is not a negative B6 flow, receives no credit in this milestone, and is not netted into A–C.

The engine does not use the legacy `annual_energy_savings_kwh` economic proxy for carbon. Every executable imported flow requires complete in-RSP annual factor coverage using exact `GWP_TOTAL`, `B6`, `kwh` factors. Missing future factor years block calculation; there is no interpolation, extrapolation, or assumed grid decarbonisation. Factor uncertainty metadata is retained but not sampled.

Production operational inputs are intentionally header-only because the inherited demonstrator contains no source-backed carrier flows or calendar-year factors. The default status `NO_OPERATIONAL_ENERGY_FLOWS` therefore means **not assessed**, not zero. Dedicated M3.1 tests are 19/19 PASS; 10,000-future 30/50/60-year parity preserves all 76 common non-manifest M2.6 outputs byte-for-byte; and a full default 10,000-future run with convergence/charts passes.

At that historical checkpoint, M3.1 did **not** generate Whole-Life Carbon. Terminal C1–C4, separate Module D and module-applicability coverage aggregation were added later in v3.2.0; B1/B2/B3/B5/B7/B8, residual value, carbon discounting and environmental-factor uncertainty sampling remain outside the bounded release.

See `docs/M3.1_IMPLEMENTATION_REPORT.md`, `docs/M3.1_INPUT_GUIDE.md`, `docs/M3.1_TEST_RESULT.txt`, and `docs/M3.1_PARITY_DETAILS.json`.

## V3 migration checkpoint — M2.6

M2.6 completes the **process consequences attributable to canonical B4 replacement events**. In addition to the already frozen B4 replacement-product and inbound replacement-transport layers, B4 can now carry explicitly mapped installation, removal, outbound removed-material transport, waste processing and disposal consequences. Every M2.6 row links to the same canonical `B4_REPLACEMENT` event that triggered the replacement.

Source-process module provenance remains visible (`A5.2`, `A5.1`/`C1`, `A4`, `C3`, or `C4` as appropriate), while `reported_module` remains `B4`. This prevents replacement-event consequences from being silently reclassified into initial A-stage or terminal C-stage totals. No service-life resampling, factor-uncertainty sampling, carbon discounting or whole-life-carbon headline is introduced.

`inputs/b4_event_process_assignments.csv` is intentionally header-only in the production demonstrator because no source-backed replacement installation/removal/waste-process dataset is available. The default status `NO_B4_EVENT_PROCESS_ASSIGNMENTS` therefore means **not assessed**, not zero carbon. M2.6 is additive: 10,000-future 30/50/60-year parity preserves all 71 common non-manifest M2.5 outputs byte-for-byte.

See `docs/M2.6_IMPLEMENTATION_REPORT.md`, `docs/M2.6_TEST_RESULT.txt`, and `docs/M2.6_PARITY_DETAILS.json`.

## Historical checkpoint — M2.5

M2.5 adds independently gated **A5.1 pre-construction removal of existing works** at t0. The dedicated removal inventory keeps removed-existing material separate from current-construction A5.3 waste. Three subflows can be assessed: removal/deconstruction activity, outbound transport of removed material, and its explicit waste processing/disposal route.

Source-process provenance is preserved: removal activity uses an A5.1 factor; outbound transport may use an A4 transport-process factor but reports to A5.1; waste processing/disposal may use a C3/C4 process factor but reports to A5.1 under the adopted retrofit split. No C-stage duplicate is generated and D1 remains separately deferred.

Production removal inputs are header-only because no source-backed removed-existing inventory exists in the inherited demonstrator. Default status is `NO_PRECONSTRUCTION_REMOVAL_INVENTORY`, meaning not assessed rather than zero carbon. M2.5 leaves A1-A3, A4, B4 product/transport, A5.2/A5.3, lifecycle, economics and random streams unchanged.

See `docs/M2.5_IMPLEMENTATION_REPORT.md`, `docs/M2.5_TEST_RESULT.txt`, and `docs/M2.5_PARITY_DETAILS.json`.

## Historical checkpoint — M2.4

M2.4 adds an independently gated **initial A5.2 construction/installation** and
**A5.3 current-construction waste** consequence layer. It does not alter the
frozen A1-A3 product, A4 initial transport, B4 replacement-product, B4
replacement-transport, lifecycle, economic or random-stream engines.

`construction_process_scenarios.csv` is a process registry linked explicitly to
A5.2 GWP_TOTAL factor sets. `boq_construction_process_assignments.csv` supplies
the t0 activity quantity and, where documented, either a BoQ waste rate or an
explicit current-construction waste quantity for A5.3. Missing process, waste,
unit or factor evidence is blocked rather than interpreted as zero.

This milestone deliberately **does not implement A5.1**. The audited v3 design
requires a separate pre-construction removal inventory because removal of
pre-existing works, its outbound transport and waste treatment must not be
duplicated as A5.3 current-construction waste. A5.4 worker transport and B4
installation/waste also remain deferred. Production A5 inputs are header-only,
so the default result is not assessed rather than zero carbon.

See `docs/M2.4_IMPLEMENTATION_REPORT.md`, `docs/M2.4_TEST_RESULT.txt`, and
`docs/M2.4_PARITY_DETAILS.json`.

## V3 migration checkpoint — M2.3

M2.3 adds **transport attributable to canonical B4 replacement events** without
changing the frozen M2.2 initial A4 layer or the M2.1 product-stage subengine.
Each replacement-transport consequence is attached to the same canonical
`B4_REPLACEMENT` event that drives replacement-product carbon, retains the
transport process factor provenance, and is **reported to B4 rather than A4**.

Replacement transport uses documented BoQ mass, explicit route distance and a
GWP_TOTAL transport factor expressed per tonne-km. A separate
`boq_replacement_transport_assignments.csv` prevents initial and replacement
transport semantics from being conflated. No replacement route, mass, distance
or factor is inferred from the initial A4 assignment. Production replacement
transport assignments remain empty, so the default run is unassessed rather
than zero-carbon.

M2.3 introduces no A5, B6, C/D, residual value, factor uncertainty, transport
uncertainty, carbon discounting, or whole-life-carbon headline. See
`docs/M2.3_IMPLEMENTATION_REPORT.md` and `docs/M2.3_TEST_RESULT.txt`.

## V3 migration checkpoint — M2.2

M2.2 adds independently gated **initial A4 transport to site** to the existing
A1-A3 initial-product and B4 replacement-product engine. The canonical lifecycle,
economic model, random streams and product factors are unchanged. Every initial
A4 consequence occurs at t=0, generation 0, once per future/BoQ line. No
replacement transport, A5/C/D, B6, residual value or whole-life-carbon total is
calculated.

`a4_transport.py` resolves `documented mass_kg / 1000 * distance_km` to tonne-km,
then multiplies by the explicitly assigned GWP_TOTAL transport factor. Mass comes
only from kg/tonne BoQ or the existing documented total-mass bridge. Missing
mass/distance/GWP, incompatible units, mismatched transport bases and ambiguous
assignments cannot generate an impact. Load and return assumptions are recorded
as part of the factor basis, with no additional multiplier or uncertainty draw.

The product subengine and its summary/status outputs remain separately scoped.
Only validated A4 rows are appended to `carbon_consequence_ledger.csv`; A4 has its
own module summary, coverage, compatibility and status files. Retained historical
components receive no initial A4 unless an explicit documented t=0 movement is
assigned.

Production BoQ, product factors and transport inputs remain intentionally empty
because documented project data are unavailable. `NO_ASSESSMENT_BOQ_LINES` means
**not assessed**, not zero carbon. Populated synthetic verification inputs live
only under `tests/fixtures/m22_transport_synthetic/`.

See `docs/M2.2_IMPLEMENTATION_REPORT.md` for audit results and
`docs/M2.2_INPUT_GUIDE.md` for schemas, limits and run commands. Older milestone
reports remain historical records.

## Results and evidence

The public source package does **not** commit generated `outputs/` files. They are regenerated by `python renovation_lcc.py` and excluded through `.gitignore` so the repository does not mix source code with large run artefacts.

For audited evidence, use:

- `VALIDATION.md` — current verification summary and release qualifications;
- `docs/M4_END_OF_LIFE_MODULE_D_REPORT.md` — terminal C1–C4 and separate D1/D2 semantics;
- `docs/M5_LIFECYCLE_AGGREGATION_REPORT.md` — module applicability, coverage and aggregation gate;
- `docs/M4_M5_TEST_RESULT.txt` — final 235-test and full-run evidence;
- `docs/M4_M5_PARITY_DETAILS.json` — direct 30/50/60-year M3.1.1→v3.2.0 parity evidence;
- `docs/release/IMPLEMENTED_SCOPE.md` — concise implemented/deferred scope;
- `docs/M3.1_IMPLEMENTATION_REPORT.md` — B6 implementation scope and semantics;
- `docs/M3.1_TEST_RESULT.txt` — M3.1 test evidence;
- `docs/M3.1_PARITY_DETAILS.json` — 30/50/60-year 10,000-future parity evidence;
- `docs/M3.1.1_HARDENING_REPORT.md` — release-consistency hardening audit;
- `ASSUMPTIONS.md` — accounting boundary, assumptions and scientific limitations.

Generated files such as `scenario_summary.csv`, `carbon_consequence_ledger.csv`, `convergence_plot.png`, and `lifecycle_replacement_costs.png` appear in the selected run output directory after execution; they are not links to committed repository files.

## Run and reproduce

The delivered run used Python 3.12 and the exact versions recorded in
`requirements-reproduced.txt`. Prefer a fresh environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-reproduced.txt
python -m unittest discover -s tests -v
python renovation_lcc.py
```

Windows activation: `.venv\Scripts\activate`.
`requirements.txt` specifies compatible ranges for other environments; it is not
the exact reproducibility lock. Python 3.10+ is supported by the source syntax,
but exact pinned packages may require a newer interpreter/platform.

```sh
python renovation_lcc.py --input inputs/renovation_scenarios.csv \
  --components inputs/components.csv --config inputs/model_config.json \
  --stress-cases inputs/climate_stress_scenarios.csv \
  --simulations 10000 --seed 20260726 --output-dir outputs_new
```

`--no-charts` avoids Matplotlib imports; `--skip-convergence` omits the expensive
multi-size/seed diagnostic. Neither option is used for the delivered full run.
Use a fresh output folder for each experiment to avoid confusing older files
with the current run. Convergence sizes and seeds are configured separately
from the main-run `--simulations` and `--seed`.

## Accounting and time

Every scenario input is a difference from the reference. Zero reference cash
flows do not mean an existing building has no operating expenses. The example
assumes the reference is admissible; regulations and minimum intervention
requirements have not been assessed.

```text
E = present value of avoided energy bills
R = present value of additional rent transferred from tenant to owner
V = discounted terminal property premium
C = initial investment after grants
M = discounted incremental routine maintenance
Q = discounted incremental component renewal costs
a = owner's share of E (default 0: tenants pay the energy bills)

Owner            = a E + R + V - C - M - Q
Tenant           = (1-a) E - R
Combined private = E + V - C - M - Q = Owner + Tenant
```

Public grants remain external benefits to the private boundary. This is not a
social-welfare account. Initial and replacement costs are paid by the owner;
grants apply only to the initial investment. Cash flows are nominal EUR,
discounted to time zero. Routine annual amounts are year-1 end-of-year amounts.

## Component renewal model

`components.csv` decomposes the original illustrative investment and maintenance
budgets. These totals must reconcile to each scenario; they are not charged a
second time. Replacement costs are additional and have a separate output column.
They represent assumed **incremental renewal obligations**, not a validated bill
of materials or gross replacement costs for an actual building.
The summary column `mean_pv_replacement_cost_eur` describes the package cost in
every perspective's row; it is charged only to owner and combined private NPV,
and is not a tenant expense.

For each component and future, a service life is sampled. A life ending strictly
before the horizon triggers immediate replacement; the renewed component receives
a fresh lifetime, allowing multiple renewals. Costs are escalated to the event
time and discounted to zero. A life ending exactly at the horizon is excluded.
The schedule uses continuous years. No downtime, repair states or physical
degradation is simulated.

The `uncertainty_key` couples equal component types across packages with common
random quantiles. Different keys and successive renewals have independent
streams. Thus, removing or reordering a package does not redraw other components.
No component-specific residual-value credit is applied. The hypothetical property
premium is separate; its adequacy must be reconsidered when building a real case.

## Primary decision evidence

Read median NPV, positive-outcome frequency, lower-tail mean, P95 regret and
best-option share together. `pareto_on_core_metrics` identifies nondominated
eligible options on three maximized metrics: median, positive frequency and
lower-tail mean. This Pareto definition does not imply dominance on every possible
economic, environmental or stakeholder objective.

- `probability_positive`: empirical NPV > 0 frequency.
- `probability_nonnegative`: empirical NPV >= 0 frequency, reported separately.
- `worst_decile_mean_eur`: mean of the lowest 10% empirical probability mass.
- `p95_regret_eur`: P95 of best eligible NPV minus the option NPV within each future.
- `best_option_share`: share of best outcomes, splitting numerical ties.

Regret and best-option share inherently depend on the comparison set. Removing
an option can change these quantities legitimately. They are not inputs to the
new preference score.

## Optional fixed-anchor preference diagnostic

`preference_based_score` combines clipped linear utilities on positive frequency,
lower-tail mean and median. `conditional_preference_rank` is optional, not the
headline finding. The default weights are 0.30 / 0.35 / 0.35.

| Metric | Fixed utility 0 anchor | Fixed utility 1 anchor |
|---|---:|---:|
| Positive frequency | 0 | 1 |
| Worst-decile mean | EUR -750,000 | EUR 0 |
| Median NPV | EUR -500,000 | EUR +500,000 |

These round building-budget-scale anchors were declared before inspecting V2.1
results. They are illustrative floor/aspiration preferences, not elicited utility
values, regulatory thresholds or empirical calibration. Values outside each
range saturate at 0 or 1. Changing the building scale requires reviewing them.

The zero reference receives no positive-frequency utility bonus. It can still
be attractive on downside and median criteria. For unchanged outcome distributions,
anchors and weights, removing or adding alternatives cannot change a retained
option's score or reverse its pairwise preference order. Ordinal rank numbers
can move as the population changes. Ties use a 12-decimal score comparison.

`option_set_sensitivity.csv` checks removal of each option, addition of copies,
and addition of a deliberately dominated synthetic alternative. These artificial
additions are numerical diagnostics, not extra construction designs. Live-set
regret/Pareto membership may change while the independent score stays fixed.

## Monte Carlo convergence diagnostics

The default grid is 1,000 / 2,500 / 5,000 / 10,000 / 25,000 draws under five
independent seeds. Economic parameters and lifetime streams are independently
keyed; samples at smaller N are exact prefixes of larger samples for the same
seed. The lifetime streams have the same property.

For each option, perspective and seed, the diagnostic records mean NPV, positive
frequency, P10, lower-tail mean, P95 regret and optional preference rank. It compares
each smaller N with the 25,000-draw result from that seed. The largest run is a
finite comparator, not truth. Cross-seed ranges are also saved; graph bands show
observed seed ranges, not confidence intervals.

Declared tolerances are EUR 10,000 for mean, 1 percentage point for positive
frequency, EUR 20,000 for P10 and EUR 30,000 for both lower-tail mean and P95 regret.
They are numerical precision targets for this illustrative budget, not guarantees.
Largest-N rows are marked as comparators, not counted as converged by construction.
Wilson intervals apply only to Monte Carlo positive-outcome frequencies conditional
on the specified model, not to real-world certainty or uncertain input validity.

## External performance-stress interface

The delivered CSV contains four **hypothetical proxy cases**. No case label is a
historical dataset, warming level, RCP/SSP pathway or predicted frequency.
It supports a `*` default plus optional per-scenario overrides.

Case inputs multiply retained annual energy savings, equipment performance,
routine maintenance and terminal premiums. An energy-disruption case uses a
uniform savings-factor range. Common uniforms and unchanged renewal paths provide
paired comparisons. Climate effects on lifetimes and replacement costs are not
inferred from case labels.

The retained-savings proxy is `sampled performance factor * energy-savings multiplier
* equipment-performance multiplier`, relative to the scenario's assumed nominal
annual savings. Separate multipliers should only be populated from an external
model when their meanings are distinct to avoid counting an effect twice.

The configurable screen requires median NPV >= EUR 0, positive frequency >= 70%,
P95 regret <= EUR 500,000, and at least 90% of draws retaining 75% of assumed annual
savings. An option is flagged `robust_across_stress_cases` only when both financial
and proxy-performance screens pass in at least three of the four cases.
Cases are unweighted; 3/4 is not a 75% probability of real-world success.

The reference has no incremental savings target, so its performance screen is
N/A, not an automatic pass. The financial and performance screens have explicit
separate outputs. Failure of all alternatives is an informative result and is
not corrected by adjusting inputs to produce a winner.

An actual building-simulation integration would require documented scenario
provenance, units, baselines and mapping of outputs. Indoor comfort needs its own
physical output and threshold; the current proxy must not be called thermal comfort.

## Other sensitivity diagnostics retained from V2

- Economic OAT: sampled P10/P90 inputs, with other economics at medians and all
  component lifetimes at their modes. It does not decompose lifetime effects or interactions.
- Spearman associations: ranked economic inputs versus sampled total NPV including
  renewals. These are not causal effects or variance-based indices.
- Five preference-weight profiles and owner energy-savings shares 0% / 50% / 100%.
- Paired accounting stress cases: no grants, no rent uplift, no terminal premium,
  and reduced energy price with higher capital costs. Renewal costs are included.

## Repository structure

```text
.
├── inputs/                    # illustrative model inputs and stress cases
├── outputs/                   # generated locally; not committed in the source release
├── provenance/v2/            # archived source/configuration snapshot
├── tests/                     # unit and integration tests
├── renovation_lcc.py          # command-line entry point and core economics
├── component_lifecycle.py     # stochastic lifetime and renewal schedules
├── horizon.py                 # 30/50/60-year runtime RSP profiles
├── convergence.py             # nested sample-size and seed diagnostics
├── robustness.py              # fixed-anchor and option-set diagnostics
└── performance_stress.py      # external stress/performance interface
```

## Outputs

| Output | Purpose |
|---|---|
| scenario_summary.csv | Individual outcome metrics, Pareto flag and optional preference score |
| simulation_results.csv | All main-run futures/options and stakeholder cash flows |
| sampled_futures.csv | All economic draws |
| component_lifecycle_draws.csv | First life, renewal count and PV cost per future/component |
| lifecycle_replacements.csv | Each renewal time, preceding life, nominal and discounted cost |
| rsp_boundary_state.csv | One RSP-boundary state per future and intervention component |
| reference_lifecycle_event_ledger.csv / reference_rsp_boundary_state.csv | Physical-reference lifecycle outputs when a documented reference inventory is supplied |
| reference_inventory_status.json | Explicit executable/unpopulated status of the physical reference inventory |
| resolved_component_boq.csv / physical_boq_status.json | Physical quantity mapping actually supplied and its evidence status |
| physical_quantity_coverage.csv | Component-level BoQ coverage without inferring quantity from cost |
| reference_coverage_skeleton.csv | Reference presence/quantity evidence state for known intervention lineages only |
| lifecycle_event_boq_quantities.csv / rsp_boundary_boq_state.csv | One-to-many quantity bridges for events and RSP states |
| component_summary.csv | Aggregate renewal statistics |
| option_set_sensitivity.csv | Score/order checks under removal/addition diagnostics |
| monte_carlo_convergence.csv | Nested-N comparisons, Wilson intervals and tolerance checks |
| seed_stability.csv | Cross-seed ranges and optional first-rank counts |
| climate_stress_summary.csv | Financial and proxy-performance outcomes by case |
| robust_across_stress_cases.csv | Conditional count-based proxy screen |
| sensitivity_oat.csv / sensitivity_rank_correlations.csv | Economic-input diagnostics |
| weight_sensitivity.csv / allocation_sensitivity.csv | Preferences and benefit allocation |
| stress_test_summary.csv | Accounting/input stresses with component renewals |
| resolved_*.csv / resolved_config.json | Inputs actually used |
| resolved_horizon.json | Named horizon profile, years, source and boundary/resimulation rules |
| run_manifest.json | Versions, hashes, seed and sampling scheme |
| carbon_consequence_ledger.csv | Traceable M2.1 A1-A3 initial-product and B4 replacement-product GWP consequences |
| assessed_product_carbon_by_module.csv | Per-future/per-scenario assessed product/replacement GWP only; not Whole-Life Carbon |
| product_carbon_coverage.csv | BoQ-line carbon execution/blocking status |
| carbon_engine_status.json | Machine-readable carbon scope, exclusions and no-zero/no-WLC claim guards |
| operational_energy_coverage.csv | Per-flow B6 schedule coverage, bookkeeping status and explicit no-credit export treatment |
| assessed_operational_carbon_by_module.csv | Per-future/per-scenario B6 imported-energy GWP only; not a Whole-Life Carbon total |
| b6_operational_energy_engine_status.json | B6 policy, coverage, missing-data and generated/export treatment metadata |

Charts are generated as PNG/SVG when requested. `VALIDATION.md` records the verification results. `SHA256SUMS.txt` covers the current release tree. V2 source/configuration are preserved under `provenance/v2/` for traceability; historical milestone checksum manifests are archived under `provenance/historical_checksums/` and do not validate the current tree.

## V3 migration checkpoint M1.4 — configurable horizons

The staged v3 migration now supports three explicit reference-study-period run modes without changing the legacy 30-year model path:

- `legacy_30` — exact 30-year v2.1 continuity horizon;
- `levels_50` — 50-year Level(s)-aligned research horizon;
- `rics_60` — 60-year RICS-WLCA-aligned comparison horizon.

Use `--horizon-mode <mode>` to select a named profile. Omitting the flag preserves the configured horizon exactly; the supplied configuration remains 30 years. All horizons are re-evaluated from the underlying equations, and lifecycle events exactly at or beyond the horizon remain excluded. The profile names document methodological alignment only and do not claim formal standards compliance.

M1.4 was regression-tested against M1.3 with 10,000 futures: all 19 common CSV outputs, `resolved_config.json`, and `analysis_report.txt` are byte-identical in the default 30-year run. The current suite contains 37 passing tests.


## V3 migration checkpoint M1.5 — retained remaining life vs replacement full service life

M1.5 separates the first remaining-life interval of an existing retained component from the full service life of newly installed replacement generations. Legacy-compatible component files remain valid: when `initial_component_state` is absent, the row is interpreted as `NEW_AT_T0` and the original lifetime fields/random streams are used unchanged.

A retained component must explicitly declare `RETAINED_EXISTING` and a remaining-life distribution/key. The model never derives remaining life from `age_at_t0_years`; age is provenance metadata only. Missing retained-component remaining-life input is a hard error, and remaining-life fields on a `NEW_AT_T0` row are rejected.

Canonical replacement events record whether their preceding interval came from `REMAINING_LIFE` or `FULL_SERVICE_LIFE`. The dedicated retained stream is separate from the full-life renewal stream, preventing accidental conflation of uncertainty sources. A schema-only template is provided in `v3_schema_templates/components_m1_5.csv`; the supplied production `inputs/components.csv` is intentionally unchanged so the default research demonstrator does not invent retained-component assumptions.

Regression status: **47/47 tests pass**. Independent 10,000-future runs at 30, 50 and 60 years are byte-identical to M1.4 for every common output except `run_manifest.json`, which intentionally changes because the checkpoint/source hashes changed. See `docs/M1.5_IMPLEMENTATION_REPORT.md`.

## V3 migration checkpoint M1.6 — physical-reference gate and RSP boundary state

M1.6 adds an explicit RSP-boundary **state ledger** (`rsp_boundary_state.csv`) without creating a fictitious physical event at the analysis boundary. For every simulated future and intervention component, the output records the installed generation at the boundary, the interval start/installation time where known, age within the assessment, physical age where source-backed, the next modeled replacement time, and remaining life at the boundary. This state is the later hook for residual-value and lifecycle-carbon accounting.

The physical reference is now represented by a separate executable schema (`inputs/physical_reference_inventory.csv`) and validation gate. The supplied v2.1 source package does not contain a documented existing-building component inventory, physical quantities/units, ages or remaining-life evidence. The production reference inventory is therefore intentionally empty and `reference_inventory_status.json` reports `UNPOPULATED_SOURCE_DATA_ABSENT`; no physical reference rows are inferred from renovation options. `inputs/reference_inventory_gap_register.csv` lists intervention lineages whose reference-side presence/evidence remains unresolved, but those rows are not treated as inventory evidence.

When documented reference rows are later supplied, they use the same lifecycle engine and produce `reference_lifecycle_event_ledger.csv` and `reference_rsp_boundary_state.csv` while reference decision NPV remains on the verified zero-cash-flow compatibility path. Synthetic reference rows are permitted only in tests and must be labelled `TEST_ONLY_SYNTHETIC`.

Regression status: **62/62 tests pass**. Independent 10,000-future runs at 30, 50 and 60 years preserve all 22 common non-manifest outputs byte-for-byte relative to M1.5; five new reference/boundary outputs are additive. See `docs/M1.6_IMPLEMENTATION_REPORT.md`.


## V3 migration checkpoint M1.7 — physical quantity / BoQ mapping and reference coverage

M1.7 adds a strict physical quantity layer before any carbon factor is introduced. `inputs/component_boq.csv` is the authoritative mapping from lifecycle component instances to one or more product/material quantity lines. The supplied production file is intentionally empty because the v2.1 source package does not contain documented intervention quantities; economic costs are never used as quantity proxies.

A lifecycle component may map to multiple BoQ lines, so the canonical component-event ledger is not overloaded with a single ambiguous quantity. Instead, `lifecycle_event_boq_quantities.csv` and `rsp_boundary_boq_state.csv` provide stable one-to-many quantity bridges, with analogous reference outputs when documented reference rows exist. BoQ rows distinguish `ASSESSMENT_INVENTORY` from `INFORMATION_ONLY` to avoid future double counting.

`inputs/reference_component_presence.csv` explicitly covers all six intervention lineages. In the supplied production case all are `UNKNOWN`, because the source package does not prove presence or absence in the minimum-intervention reference. `reference_coverage_skeleton.csv` therefore reports `REFERENCE_PRESENCE_UNRESOLVED` and explicitly limits its denominator to `KNOWN_INTERVENTION_LINEAGES_ONLY`; it is not a claim about whole-building coverage.

Regression status: **76/76 tests pass**. Independent 10,000-future 30/50/60-year parity runs preserve all 27 common non-manifest outputs byte-for-byte relative to M1.6. No carbon factor, GWP result, or undocumented physical quantity is introduced at this checkpoint.

## Scope and next research steps

Further work should be driven by access to building data or a concrete research
question. Calibration against real buildings, direct climate/building simulation,
indoor-comfort outputs, environmental LCA and empirical validation are outside
this version.

## Author and citation

Developed by **Parisa Hosseini**. Research profiles:
[ORCID](https://orcid.org/0009-0009-0168-8912),
[Google Scholar](https://scholar.google.com/citations?user=L2dOgkkAAAAJ&hl=en), and
[LinkedIn](https://www.linkedin.com/in/parisa-hosseini-216886310).

Citation metadata are provided in `CITATION.cff`. The code is released under the
MIT License. The project was iteratively developed and reviewed with AI-assisted
debugging and documentation support; the author is responsible for the modelling
choices, verification and interpretation.


## V3 migration checkpoint M2.1 — A1-A3 + B4 product-stage carbon consequences

M2.1 is the first executable carbon-calculation checkpoint, but its scope is intentionally narrow. `carbon_consequences.py` consumes the canonical lifecycle-event ledger, explicit M1.7 BoQ mappings, and the M1.8 environmental-factor/unit gate. It does **not** resample service lives.

Implemented consequences:

- `A1-A3` initial product-stage GWP for `NEW_AT_T0` components only;
- no historical A1-A3 for `RETAINED_EXISTING` components;
- `B4` replacement product-stage GWP generated only from canonical `B4_REPLACEMENT` events;
- replacement product manufacturing is reported in B4 and is not re-added to A1-A3;
- executable indicator is `GWP_TOTAL`; disaggregated GWP records are not reconstructed into GWP_TOTAL;
- factor uncertainty is not sampled yet; source factor values are used as central/static reference values and this temporal assumption is recorded in every consequence row.

New outputs are `carbon_consequence_ledger.csv`, `assessed_product_carbon_by_module.csv`, `product_carbon_coverage.csv`, and `carbon_engine_status.json`. These outputs are explicitly labelled as **assessed product/replacement carbon only**, never Whole-Life Carbon.

The supplied production `component_boq.csv`, `environmental_factors.csv`, and factor-assignment file remain empty because the source package contains no documented physical/product inventory for environmental calculation. Consequently the default run reports `NO_ASSESSMENT_BOQ_LINES`; an empty consequence ledger means **not assessed**, not zero kgCO2e.

Regression status: **109/109 tests pass** and Python byte-compilation succeeds. Independent 10,000-future parity runs at 30, 50, and 60 years preserve every pre-M2.1 common non-manifest output byte-for-byte relative to M1.8. See `docs/M2.1_IMPLEMENTATION_REPORT.md`.
