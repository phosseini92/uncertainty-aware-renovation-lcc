# Current release validation — v3.2.0

The bounded v3.2.0 research release closes terminal C1-C4, separate D1/D2 and the module-applicability/coverage aggregation gate without changing the hard-frozen M3.1.1 economic/lifecycle behavior.

Final-tree evidence:

- **236/236 test methods PASS**, executed in five warnings-as-errors chunks (99 + 56 + 27 + 47 + 7).
- Direct 10,000-future parity versus M3.1.1, seed `20260726`: **81/81 common non-manifest files byte-identical** at 30, 50 and 60 years; unexpected common-output differences = 0.
- Lifecycle-event rows remain **94,164 / 209,348 / 256,953** for 30/50/60 years.
- Fresh default 10,000-future run with convergence diagnostics and charts: **PASS**.
- Default terminal C/D status: `NO_END_OF_LIFE_OR_D_ASSIGNMENTS` (not assessed, not zero).
- Coverage gate status: `EXPLICIT_COVERAGE_GATE_ACTIVE`.
- Default `whole_life_carbon_generated = false`; incomplete/deferred modules prevent a Whole-Life Carbon headline.
- D1/D2 are summarized separately and are never netted into A-C.

See `docs/M4_M5_TEST_RESULT.txt`, `docs/M4_M5_PARITY_DETAILS.json`, `docs/M4_END_OF_LIFE_MODULE_D_REPORT.md` and `docs/M5_LIFECYCLE_AGGREGATION_REPORT.md`.

---

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


## V3 migration checkpoint M1.1 + M1.2

The canonical lifecycle-event ledger was introduced under a strict regression gate.

- Pre-existing v2.1 tests: 20/20 pass unchanged.
- New lifecycle-ledger tests: 4/4 pass.
- Total current test suite: 24/24 pass.
- 10,000-future parity check: 18 common CSV outputs between the audited v2.1 baseline and M1 implementation were byte-identical.
- New output only: `lifecycle_event_ledger.csv`.
- Documented 10,000-future ledger: 94,164 rows, 94,164 unique event IDs, all `B4_REPLACEMENT`.
- Full default run with convergence diagnostics and charts completed successfully.

At this checkpoint, nullable calendar year, event quantity/unit and physical state are intentional because the legacy v2.1 inputs do not contain a documented assessment base year or physical bill of quantities. No environmental calculation is performed.


## V3 migration checkpoint M1.3 — stable IDs and explicit comparison lineage

M1.3 replaced the default run's transitional identity proxies with explicit migrated IDs while keeping the economic model unchanged.

- Original v2.1 tests: **20/20 pass**.
- Migration/ledger/identity tests: **10/10 pass**.
- Total current test suite: **30/30 pass**.
- Python byte-compilation: successful.
- Full default run with convergence diagnostics and charts: successful.
- 10,000-future parity against M1.1/M1.2: `lifecycle_replacements.csv` and all 16 economic/diagnostic CSVs intended to remain unchanged are byte-identical.
- `resolved_scenarios.csv` and `resolved_components.csv`: all pre-M1.3 columns are exactly identical; differences are the new explicit identity columns only.
- `lifecycle_event_ledger.csv`: 94,164 rows in both runs; every non-identity field is exactly identical. Identity fields intentionally changed from transitional proxies to explicit stable IDs.
- Migrated default ledger: 94,164 unique event IDs; no stable scenario/component/lineage field uses a `legacy_` prefix.
- Display-label invariance: renaming scenario/component display text while retaining explicit IDs produces an exactly identical canonical ledger.
- Legacy compatibility: files without the new identity columns still load and receive deterministic compatibility IDs visibly prefixed `legacy_`.

M1.3 therefore passes the stable-identity/lineage gate without changing any documented economic result.

## V3 migration checkpoint M1.4 — configurable 30/50/60-year horizons

M1.4 separated runtime horizon selection from the historical 30-year default under a strict regression gate.

- Original v2.1 tests: **20/20 pass**.
- Total suite after horizon tests: **37/37 pass**.
- Python byte-compilation: successful.
- `inputs/model_config.json` remains unchanged at 30 years.
- Default/no-override M1.4 and explicit `legacy_30` runs generate identical CSV outputs and identical `resolved_config.json` / `analysis_report.txt`.
- 10,000-future parity against M1.3 at seed `20260726`: all 19 common CSV outputs are byte-for-byte identical; `resolved_config.json` and `analysis_report.txt` are byte-identical.
- Named 10,000-future runs complete successfully for 50 and 60 years.
- Canonical ledger event counts: 30 years = 94,164; 50 years = 209,348; 60 years = 256,953.
- Maximum event times remain strictly below each boundary: approximately 29.9991, 49.9995 and 59.9998 years respectively.
- Event-set nesting: `legacy_30` is a strict subset of `levels_50`, and `levels_50` is a strict subset of `rics_60`.
- Shared events retain exactly the same stable event ID, component/scenario identity, event time, generation, lifetime stream and sampled service-life value across longer horizons.
- Fixed-lifetime boundary tests confirm that events exactly at 30, 50 or 60 years are excluded.
- Each horizon is re-evaluated from model equations; no linear scaling is used.

M1.4 makes no formal standards-compliance claim. Profile names document the intended comparison convention only. Retained-component remaining-life semantics, physical quantities, assessment calendar mapping and environmental consequences remain deferred.

## V3 migration checkpoint M1.5 — remaining life vs full service life

M1.5 adds retained-component lifecycle semantics under the frozen M1.4 horizon architecture.

- Pre-M1.5 tests: **37/37 pass**.
- New remaining-life/full-life tests: **10/10 pass**.
- Total suite: **47/47 pass**.
- Python byte-compilation: successful.
- Fixed golden retained fixture reproduces years `7, 27` at 30 years and `7, 27, 47` at both 50 and 60 years for 7-year remaining life followed by 20-year full life.
- `REMAINING_LIFE` is permitted only for replacement generation 1; later generations must use `FULL_SERVICE_LIFE`.
- Changing `age_at_t0_years` does not alter event timing, proving age is not used as an implicit remaining-life formula.
- Missing retained remaining-life input is a hard failure.
- Separate remaining/full random streams are verified; changing the full-life stream does not change first retained replacement timing.
- 10,000-future parity against M1.4 at seed `20260726` was verified for `legacy_30`, `levels_50` and `rics_60`: all common files except the intentionally updated `run_manifest.json` are byte-identical.

See `docs/M1.5_IMPLEMENTATION_REPORT.md`, `docs/M1.5_TEST_RESULT.txt` and `docs/M1.5_UNIT_TEST_LOG.txt`.



## V3 migration checkpoint M1.6 — physical reference gate and RSP boundary state

- Pre-M1.6 suite: **47/47 pass**.
- New boundary/reference tests: **15/15 pass**.
- Total suite: **62/62 pass**.
- Python byte-compilation: successful.
- Full default 10,000-future run with convergence diagnostics and charts: successful.
- 10,000-future parity versus M1.5 at seed `20260726`: for 30, 50 and 60 years, all **22 common non-manifest output files are byte-for-byte identical**.
- Additive M1.6 outputs: `rsp_boundary_state.csv`, `reference_lifecycle_event_ledger.csv`, `reference_rsp_boundary_state.csv`, `resolved_physical_reference_inventory.csv`, and `reference_inventory_status.json`.
- Boundary-state row count is 130,000 at each RSP (10,000 futures × 13 intervention component instances), with 130,000 unique boundary IDs and one state per future/component.
- Event ledgers remain unchanged: 94,164 events at 30 years, 209,348 at 50 years, and 256,953 at 60 years.
- Cross-horizon validation: 106,613 30-year boundary states have a next replacement before year 50 and every one reconciles exactly to the matching 50-year event; 47,605 50-year states similarly reconcile to the 60-year event ledger.
- Exact-boundary golden tests confirm that a replacement due exactly at the RSP is excluded from the event ledger but represented with zero remaining life and `replacement_due_at_boundary = true`.
- The default physical-reference inventory is empty by design because source-backed physical reference data are absent; tests verify that executable retained reference rows require quantity/unit, source reference, explicit remaining life, and explicit full life.

## M1.7 physical quantity / BoQ validation

The M1.7 gate adds 14 tests for parent identity, quantity/provenance validity, explicit unit handling, one-to-many event/BoQ expansion, reference-presence evidence states, and run-level additive outputs. Current suite: **76/76 passing** with no warnings. Python byte-compilation succeeds.

Independent 10,000-future parity runs (`seed = 20260726`, no charts, no convergence) were performed against M1.6 for `legacy_30`, `levels_50`, and `rics_60`. For each horizon, all **27 common non-manifest output files are byte-for-byte identical**. The nine M1.7 files are additive only: `resolved_component_boq.csv`, `resolved_reference_component_presence.csv`, `physical_boq_status.json`, `physical_quantity_coverage.csv`, `reference_coverage_skeleton.csv`, `lifecycle_event_boq_quantities.csv`, `rsp_boundary_boq_state.csv`, `reference_lifecycle_event_boq_quantities.csv`, and `reference_rsp_boundary_boq_state.csv`.

A full default 10,000-future run including convergence diagnostics and chart generation also completed successfully. The production BoQ is empty; therefore both event/BoQ bridge outputs are header-only and no quantity is fabricated. Production coverage truthfully reports all 13 intervention component instances as missing assessment BoQ and all six known reference lineages as unresolved presence.
## M1.8 environmental-factor registry and unit gate

M1.8 adds 19 tests covering environmental-factor provenance, stable record identity, factor-set consistency, GWP indicator units, source-module overlap rejection, explicit product/proxy assignments, assessment-inventory-only execution, exact-unit compatibility, kg↔tonne conversion, documented total-mass bridging, incompatible-unit blocking, missing-`GWP_TOTAL` blocking, missing product-stage scope blocking, assignment coverage, and run-level no-carbon outputs. Current suite: **98/98 passing**.

Independent 10,000-future parity runs (`seed = 20260726`, no charts, no convergence) were performed against M1.7 for `legacy_30`, `levels_50`, and `rics_60`. For every horizon, all **36 common non-manifest files are byte-for-byte identical**. The six additive M1.8 run outputs are `resolved_environmental_factors.csv`, `resolved_boq_environmental_factor_assignments.csv`, `environmental_factor_set_summary.csv`, `boq_factor_compatibility.csv`, `boq_factor_coverage.csv`, and `environmental_registry_status.json`.

A full default 10,000-future run including convergence diagnostics and chart generation completed successfully. The production BoQ and environmental-factor registry are both empty, so the registry status is `NO_ASSESSMENT_BOQ_LINES`. This status is a data-readiness statement and must not be interpreted as zero environmental impact. M1.8 generates no kgCO2e consequence or headline carbon result.



## M2.1 — product-stage carbon consequence engine

Validation gates added in M2.1:

- closed-form quantity × factor validation (`10 m2 × 2.5 kgCO2e/m2 = 25 kgCO2e`) for both initial A1-A3 and one B4 replacement;
- `NEW_AT_T0` initial product consequence occurs once per Monte Carlo future at t=0;
- `RETAINED_EXISTING` receives no historical A1-A3;
- every B4 product consequence traces to an existing canonical B4 event ID and its event time;
- combined A1-A3 and disaggregated A1/A2/A3 factor records are handled without overlap/double counting;
- explicit kg↔tonne activity conversion is respected in the consequence calculation;
- missing GWP_TOTAL remains blocked and is never reconstructed from disaggregated GWP indicators;
- duplicate BoQ-factor assignments remain a hard validation error;
- B4 carbon event sets remain nested with lifecycle events across 30/50/60-year horizons;
- intervention/reference component sets cannot leak initial A1-A3 consequences into one another;
- production empty BoQ/factor inputs produce empty non-assessed carbon outputs rather than zero-carbon claims.

Current suite: **109/109 tests pass**. Python byte-compilation succeeds. A full default 10,000-future run with convergence diagnostics and charts completes successfully. Independent M1.8→M2.1 10,000-future parity runs with seed `20260726` at `legacy_30`, `levels_50`, and `rics_60` preserve all 42 common non-manifest outputs byte-for-byte; the four additive outputs are the product-carbon ledger, module summary, coverage table, and engine-status JSON.

## M2.3 — B4 replacement transport validation

M2.3 adds 10 tests for event linkage, B4 reporting, A4 isolation, closed-form tonne-km impact, horizon nesting, zero-distance handling, replacement-basis validation, scope leakage, duplicate active mappings and product-subengine isolation. The complete suite contains **152 tests**; all passed in verified module chunks. Python byte-compilation passed.

Independent 10,000-future runs (`seed = 20260726`, no charts/convergence) were compared directly with the stored M2.2 audit hashes. For `legacy_30`, `levels_50`, and `rics_60`, all **46/46 pre-M2.3 common non-manifest outputs are byte-for-byte identical**. Lifecycle-event counts remain 94,164 / 209,348 / 256,953. A full default 10,000-future run including convergence diagnostics and chart generation also completed successfully.

Production replacement-transport assignment data are empty, so the M2.3 engine produces no replacement-transport consequence rows by default and does not interpret missing data as zero.


## M2.4 — A5.2 construction/installation and A5.3 current-construction waste validation

Ten M2.4 tests cover closed-form A5.2 and A5.3 calculations, explicit waste quantity versus BoQ waste-rate equivalence, no-waste semantics, missing mass blocking, exact A5.2/A5.3 factor-scope gates, duplicate-flow and scenario-scope failures, t0/horizon invariance, frozen product/lifecycle isolation, and production `NOT_ASSESSED` behavior.

The complete repository contains **162 tests**. The suite was verified in module chunks because long integration modules can exceed a single interactive command timeout: A4 33/33; M2.4 A5 10/10; B4 transport 10/10; product/environmental/physical/reference 55/55; remaining-life/robustness/convergence 15/15; boundary/component/horizon/lifecycle/model/performance 39/39. Python byte-compilation passed.

Independent M2.3→M2.4 parity runs used `seed=20260726`, 10,000 futures and no charts/convergence. For `legacy_30`, `levels_50`, and `rics_60`, **58/58 common non-manifest outputs are byte-for-byte identical**. Six additive M2.4 outputs are introduced: A5 compatibility, A5 coverage, A5 module summary, A5 engine-status JSON, and two resolved A5 input tables.

A full default 10,000-future run including convergence diagnostics and chart generation completed successfully. Production A5 process/assignment inputs are empty, so the default A5 status is `NO_ASSESSMENT_BOQ_LINES`; this is not a zero-carbon result.

## M2.5 — A5.1 pre-construction removal validation

Thirteen M2.5 tests verify the three A5.1 subconsequences, source-factor/reporting-module separation, t0 ownership, no lifecycle-event reuse, no C-stage duplicate, mass/distance gates, documented-zero-distance semantics, exact A5.1/C3/C4 source-scope gates, structural A5.1/A5.3 identity separation, reference-scope rejection, D1-deferred metadata, horizon invariance, and production `NOT_ASSESSED` behavior.

The complete repository contains **175 tests**, verified in module chunks. Python byte-compilation succeeds. The golden synthetic fixture produces 10 kgCO2e removal activity + 10 kgCO2e outbound transport + 200 kgCO2e waste processing = **220 kgCO2e A5.1 per future**.

Independent M2.4→M2.5 parity runs used `seed=20260726`, 10,000 futures, no charts and no convergence. For `legacy_30`, `levels_50`, and `rics_60`, all **64 common non-manifest outputs are byte-for-byte identical**. Seven M2.5 outputs are additive only: compatibility, coverage, A5.1 module summary, engine-status JSON, and three resolved input tables.

A full default 10,000-future run including convergence diagnostics and charts completes successfully. Production A5.1 inputs are empty and status is `NO_PRECONSTRUCTION_REMOVAL_INVENTORY`; missing removal evidence is not interpreted as zero carbon.


## M2.6 — B4 replacement-event process validation

Seventeen dedicated M2.6 tests verify complete event linkage, source-module/reporting-module separation, installation/removal/waste-process arithmetic, tonne-km arithmetic, mass and unit gates, GWP_TOTAL-only execution, duplicate-flow rejection, scenario/BoQ scope protection, synthetic-source labelling, non-B4 exclusion, stable consequence identities and event-set nesting. The synthetic golden event totals **322 kgCO2e** across five process roles while every row reports to B4 and references the same canonical lifecycle event.

The repository contains 192 tests after M2.6. The interactive execution environment cannot finish the monolithic discovery command within its single-call limit, so verification was executed in module chunks. All new and affected modules passed; the frozen M2.5 baseline had already passed 175/175 tests. Python byte-compilation succeeds.

Independent M2.5→M2.6 parity runs use `seed=20260726`, 10,000 futures, charts off and convergence off. At `legacy_30`, `levels_50`, and `rics_60`, all **71 common non-manifest outputs are byte-for-byte identical**. The five M2.6 production outputs are additive only: resolved assignments, compatibility, coverage, module summary and engine-status JSON. Lifecycle-event counts remain 94,164 / 209,348 / 256,953 for 30 / 50 / 60 years.

A full default 10,000-future run with convergence diagnostics and charts completes successfully. Production M2.6 assignments remain empty and the engine reports `NO_B4_EVENT_PROCESS_ASSIGNMENTS`; no missing data are treated as zero and no whole-life-carbon headline is generated.

## M3.1 / M3.1.1 — B6 operational energy and hardening

Historical M3.1 integrates B6 operational-energy GWP using explicit physical energy flows and explicit analysis-year/calendar-year factor schedules. Only imported energy creates B6 consequences. Generated, self-consumed and exported energy are physical bookkeeping flows; export is not credited in B6. D2 was deferred at M3.1 and is introduced in v3.2.0 only through a separate explicit beyond-boundary mapping. Missing factor years block the affected imported flow and are never treated as zero.

M3.1 evidence:

- 19/19 dedicated M3.1 tests passed.
- Static repository test inventory at M3.1: 211 tests. No claim is made that a fresh monolithic 211/211 run was used as the release gate.
- Targeted current-checkpoint regression: 52/52 passed.
- Independent 10,000-future parity against M2.6 with seed `20260726`: 76/76 common non-manifest outputs byte-identical at 30, 50 and 60 years.
- Lifecycle-event row counts remained 94,164 / 209,348 / 256,953.
- Full default 10,000-future execution with convergence diagnostics and charts passed.
- Production B6 inputs are header-only; `NO_OPERATIONAL_ENERGY_FLOWS` means not assessed, not zero.

M3.1.1 is a release-consistency patch only. It changes no B6 arithmetic, economic equations, lifecycle-event generation or random streams. It makes the selected assessment convention, generated-energy reporting approach and factor extrapolation policy explicit runtime metadata; synchronizes README/CITATION/CHANGELOG/validation; clarifies factor `reference_year` semantics; and archives historical checksum manifests away from the repository root.

Fresh M3.1.1 hardening verification: **111/111 selected current regression tests passed** with warnings-as-errors (57 current B6/hardening/carbon/environmental, 42 lifecycle/economic/horizon/boundary, 12 component/convergence/performance/robustness). The static repository contains 216 test methods; no fresh monolithic 216/216 result is claimed. In direct 10,000-future M3.1→M3.1.1 parity, each 30/50/60-year run has 82 common files: exactly three intended metadata files differ (`resolved_config.json`, B6 status JSON, run manifest), while all remaining **79/79 are byte-identical** and lifecycle-event counts remain **94,164 / 209,348 / 256,953**. A fresh final-tree default 10,000-future run with convergence and charts also passed.

Factor-year semantics are explicit: `operational_energy_factor_schedule.calendar_year` is the **application year** for the operational factor, while environmental-factor `reference_year` is the **dataset/source reference vintage** and is not required to equal the application year. The factor schedule is therefore the authoritative time-mapping layer.

