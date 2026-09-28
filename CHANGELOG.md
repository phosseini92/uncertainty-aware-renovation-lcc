## v3.2.0 research release — terminal C/D + lifecycle coverage gate — 2026-09-28

- Added explicit terminal C1 deconstruction, C2 transport, C3 processing and C4 disposal consequence architecture from source-backed end-of-life assignments.
- Added D1 material recovery and D2 exported-energy consequence paths as separate beyond-boundary results; Module D is never netted into A-C.
- Added `module_applicability.csv`, a scenario/module coverage matrix, partial A-C aggregation and a hard label gate that prevents incomplete results from being called Whole-Life Carbon.
- B1/B2/B3/B5/B7/B8 remain explicitly deferred/not assessed in the bounded research release; missing evidence is never zero.
- Added 20 M4/M5/release-gate tests; final static inventory is 236 tests and all 236 pass in five warnings-as-errors chunks.
- Direct 10,000-future M3.1.1→v3.2.0 parity preserves 81/81 common non-manifest outputs byte-for-byte at 30/50/60 years, with lifecycle-event counts unchanged.
- Fresh final-tree 10,000-future run with convergence diagnostics and charts passes. Final release audit also removed duplicate manifest keys so dynamic coverage-gate headline flags are emitted exactly once; numerical outputs remain unchanged.

## v3 migration checkpoint M3.1.1 — hardening / release consistency — 2026-09-28

- Added explicit runtime metadata for `assessment_convention`, `generated_energy_reporting_approach`, and `factor_extrapolation_policy` without changing B6 arithmetic.
- Current operational policy is explicitly `PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED` with `ERROR_IF_MISSING`; no interpolation, extrapolation, carry-forward, D2 credit or export netting is introduced.
- Clarified that operational schedule `calendar_year` is the factor application year, while environmental-factor `reference_year` is dataset/source reference vintage.
- Synchronized README, CITATION, VALIDATION and public release metadata with the active v3-M3.1.1 research checkpoint while preserving v2.1 as the economic-core lineage.
- Removed broken README links to uncommitted `outputs/` artefacts and documented that generated outputs are reproduced locally.
- Archived historical milestone checksum manifests under `provenance/historical_checksums/`; current-tree integrity remains at repository root.
- No lifecycle, economic, random-stream or carbon arithmetic equation is changed by this patch.

## v3 migration checkpoint M3.1 — B6 operational energy — 2026-09-28

- Added `b6_operational.py`, `inputs/operational_energy_flows.csv`, and `inputs/operational_energy_factor_schedule.csv`.
- Added explicit `IMPORTED`, `GENERATED`, `SELF_CONSUMED`, and `EXPORTED` physical energy-flow bookkeeping with year-by-year balance guards.
- Added exact analysis-year/calendar-year B6 factor scheduling with `ERROR_IF_MISSING` semantics and no interpolation/extrapolation.
- Added B6 consequence rows for imported energy only; export is tracked but not credited or netted into A–C, and D2 remains deferred.
- Confirmed the legacy `annual_energy_savings_kwh` economic proxy cannot influence B6 consequences.
- Added 19 dedicated M3.1 tests, including populated full-run integration and legacy-proxy isolation.
- Verified 10,000-future M2.6→M3.1 parity at 30/50/60 years: 76/76 common non-manifest outputs are byte-identical for each horizon.
- Completed a full default 10,000-future run with convergence diagnostics and charts.
- Production B6 inputs remain header-only; default status is `NO_OPERATIONAL_ENERGY_FLOWS`, meaning not assessed rather than zero.

## v3 migration checkpoint M2.6 — 2026-09-28

- Added `b4_event_processes.py` and explicit `inputs/b4_event_process_assignments.csv`.
- Added B4-attributable installation, removal, outbound waste transport, waste processing and disposal consequences linked to canonical `B4_REPLACEMENT` events.
- Preserved native source-process scopes in provenance while reporting all replacement-event consequences in B4 to prevent A/C double counting.
- Added strict event-BoQ/canonical-event identity reconciliation and explicit quantity/unit/mass/tonne-km gates.
- Added 17 M2.6 tests; repository test inventory is now 192. New and affected test chunks pass.
- Verified 10,000-future M2.5→M2.6 parity at 30/50/60 years: all 71 common non-manifest outputs are byte-for-byte identical at every horizon.
- Completed a full default 10,000-future run with convergence diagnostics and charts.
- Production M2.6 input remains header-only; default result is not assessed rather than zero.


## v3 migration checkpoint M1.8 — 2026-09-27

- Added `environmental_factors.py` with a strict environmental-factor registry, provenance/license validation, controlled GWP indicator vocabulary, declared-unit normalization, module-scope validation, and overlap guards.
- Added empty production `inputs/environmental_factors.csv` and `inputs/boq_environmental_factor_assignments.csv`; no environmental factor is fabricated or inferred from cost, labels, or product-name similarity.
- Added explicit BoQ-to-factor assignments with `EXACT_PRODUCT_ID`, `DOCUMENTED_PROXY`, and `TEST_ONLY_SYNTHETIC` mapping bases. Proxy mappings require evidence.
- Added BoQ/declared-unit compatibility gate supporting exact units, explicit kg↔tonne conversion, and a documented total-mass bridge only. No implicit density/geometry conversion is permitted.
- Added source-module overlap protection so combined and disaggregated records such as `A1-A3` and `A1` cannot coexist for the same factor-set/indicator and later be double counted.
- Added `GWP_TOTAL`, `GWP_FOSSIL`, `GWP_BIOGENIC`, and `GWP_LULUC` registry support. `GWP_TOTAL` is never reconstructed by summing disaggregated indicators.
- Added `environmental_factor_set_summary.csv`, `boq_factor_compatibility.csv`, `boq_factor_coverage.csv`, resolved registry/assignment snapshots, and `environmental_registry_status.json`.
- Added 22 M1.8 tests; total suite is 98/98 passing.
- Independent 10,000-future parity runs at 30, 50 and 60 years preserve all 36 common non-manifest outputs byte-for-byte relative to M1.7. Six M1.8 outputs are additive.
- Full default 10,000-future run with convergence diagnostics and charts completed successfully.
- No kgCO2e consequence, carbon aggregation, Module-D calculation, or headline carbon result is produced in M1.8.


## v3 migration checkpoint M1.7 — 2026-09-27

- Added `physical_quantities.py` with strict physical-quantity / BoQ validation, explicit unit normalization, stable BoQ-line identity, provenance requirements, and one-to-many lifecycle-event quantity bridges.
- Added empty production `inputs/component_boq.csv`; no physical quantity is inferred from component cost, labels, service life, or scenario budgets.
- Added machine-readable `inputs/reference_component_presence.csv` covering all six known intervention lineages. Every supplied production declaration is `UNKNOWN` because the v2.1 source package does not document reference-side presence/absence.
- Added `physical_quantity_coverage.csv` and `reference_coverage_skeleton.csv`; the latter is explicitly limited to `KNOWN_INTERVENTION_LINEAGES_ONLY` and does not report a misleading whole-building coverage percentage.
- Added `lifecycle_event_boq_quantities.csv` and `rsp_boundary_boq_state.csv` plus reference equivalents. The canonical lifecycle-event ledger remains component-event based; one-to-many physical quantity lines are carried in bridge tables rather than forced into a scalar event quantity.
- Added strict distinction between `ASSESSMENT_INVENTORY` and `INFORMATION_ONLY` BoQ rows to reduce future double-counting risk.
- Added 14 M1.7 tests; total suite is 76/76 passing with no warnings.
- Independent 10,000-future parity runs at 30, 50 and 60 years preserve all 27 common non-manifest outputs byte-for-byte relative to M1.6; nine new M1.7 outputs are additive.
- Full default 10,000-future run with convergence diagnostics and charts completed successfully.
- No carbon factor, GWP calculation, implicit unit conversion, or reference quantity assumption was introduced.


## V3 migration checkpoint M1.6

- Added `boundary_state.py` and `rsp_boundary_state.csv` with one non-event RSP state per future/component.
- Added exact generation/remaining-life/next-replacement reconciliation at 30/50/60-year boundaries.
- Added `reference_inventory.py`, strict physical-reference schema, empty production inventory, and explicit source-data-absence status.
- Added `reference_inventory_gap_register.csv`; intervention lineages are listed only as unresolved evidence gaps, never inferred as reference components.
- Added optional physical-reference lifecycle simulation through the shared lifecycle engine without changing the zero-cash-flow reference NPV.
- Removed `RSP_BOUNDARY_STATE` from physical event types: an assessment boundary is a state observation, not a physical event.
- 62/62 tests pass; 30/50/60 10,000-future common-output parity with M1.5 is exact.

# Unreleased v3 migration — M1.5


## v3 migration checkpoint M1.5 — 2026-09-27

- Added explicit `NEW_AT_T0` versus `RETAINED_EXISTING` lifecycle semantics while leaving the supplied default inventory in legacy-compatible `NEW_AT_T0` mode.
- Added optional separate remaining-life and full-life distributions/uncertainty keys. A retained component must provide an explicit remaining-life model; no `full life - age` inference or silent fallback is allowed.
- The first replacement of a retained component records `service_life_basis = REMAINING_LIFE`; all later installed generations use `FULL_SERVICE_LIFE`.
- Added explicit random-stream provenance for remaining-life versus full-life draws while preserving the exact legacy full-life random keys for the default inventory.
- Strengthened comparison-lineage validation so paired rows use one effective full-life stream; retained paired rows must also share the remaining-life stream.
- Added 10 M1.5 tests; total suite is 47/47 passing.
- 10,000-future parity against M1.4 was verified at 30, 50 and 60 years: every common file except the intentionally changed `run_manifest.json` is byte-identical.
- Added schema-only `v3_schema_templates/components_m1_5.csv`; no undocumented remaining-life data were inserted into the main demonstrator.

## v3 migration checkpoint M1.4 — 2026-09-27

- Added `horizon.py` with three explicit runtime reference-study-period profiles: `legacy_30`, `levels_50`, and `rics_60`.
- Preserved `inputs/model_config.json` and its 30-year `analysis_years` value unchanged so the default run remains the exact legacy continuity path.
- Added optional `--horizon-mode` CLI selection; named profiles override only the runtime `analysis_years` value in an isolated config copy.
- Added `resolved_horizon.json` and manifest horizon metadata so every run declares the horizon mode, years, source, strict boundary rule, and no-linear-scaling rule.
- Preserved the existing strict event boundary: events exactly at or beyond the horizon are excluded.
- Verified nested event identity across 30/50/60-year runs: every 30-year event persists unchanged in the 50-year run, and every 50-year event persists unchanged in the 60-year run.
- Expanded the suite from 30 to 37 tests; all pass.
- Verified a 10,000-future 30-year parity run against M1.3: all 19 common CSV outputs, `resolved_config.json`, and `analysis_report.txt` are byte-identical.
- No retained-component remaining-life semantics, physical quantities, carbon factors, calendar-year mapping, environmental calculation, or economic equation was introduced or changed.

## v3 migration checkpoint M1.3 — 2026-09-27

- Added explicit stable `scenario_id`, `component_instance_id`, `component_type_id` and `comparison_lineage_id` fields to the migrated default inputs.
- Added `identity.py` with strict stable-ID validation and deterministic `legacy_` fallbacks for old input files.
- Canonical lifecycle-event IDs now depend on stable IDs rather than scenario/component display labels.
- Added lineage validation: one lineage must map to one component type and one lifetime uncertainty stream.
- Preserved all v2.1 economic equations, random streams, replacement timing and legacy replacement output.
- Expanded the suite to 30 tests; all pass.
- Verified 10,000-future parity against M1.1/M1.2: all economic/diagnostic CSVs intended to remain stable are byte-identical; resolved metadata changed only by added identity columns; non-identity ledger fields are exactly unchanged.
- No carbon calculation, physical quantity, assessment calendar, retained remaining-life or new economic assumption was introduced.


- Added `lifecycle_events.py` with a canonical lifecycle-event schema and strict validator.
- Routed B4 replacement timing through the canonical physical event ledger while preserving the exact v2.1 replacement-event interface.
- Added `lifecycle_event_ledger.csv` as a new generated output.
- Added four lifecycle-ledger tests; 24/24 tests now pass.
- Verified 18 common CSV outputs are byte-identical to the audited v2.1 baseline in a 10,000-future parity run.
- Added no carbon calculation and invented no missing physical quantities, calendar years or component states.

# V2.1 - four bounded methodological upgrades

The version was implemented through an iterative technical review of the
demonstrator, including AI-assisted debugging, testing and documentation support.
V2 and the original July folder were preserved. The author remains responsible
for the model, assumptions and interpretation.

1. Added reconciled component budgets, sampled service lives, repeated renewals,
   continuous event times, nominal escalation, discounting and event-level output.
2. Removed within-set min-max normalization. Individual metrics/Pareto trade-offs
   lead the report. An optional fixed-anchor score uses three independent metrics;
   regret remains a separate live-choice-set diagnostic. Added removal, duplicate
   and dominated-addition tests and output.
3. Added nested sample-size streams and five-seed convergence diagnostics, Wilson
   frequency intervals, cross-seed ranges and predeclared numerical tolerances.
4. Added a configurable external performance-stress interface and separate financial
   and retained-savings screens, with an explicitly conditional case-count flag.

## Why results differ from V2

V2.1 includes costs that V2 omitted. The random-stream scheme also changed to
make sample-size prefixes invariant, so a same-number seed no longer reproduces
the V2 draws. The version and sampling scheme are recorded in the manifest.
Preference criteria, normalization and naming changed. No claim of unchanged
rankings or economic conclusions is appropriate.

The reported V2 rank reversal was independently reproduced before revision:
with all options the combined-private score led with Envelope + heat pump;
removing Deep renovation + PV led with Reference. This arose from within-set
scaling and was not fixed merely by renaming the score.

V2.1 keeps regret outside the score because its benchmark changes with the option
set. Fixed anchors alone would not make a regret-based score set-independent.
The new diagnostic tests retained-option score values and pairwise order, rather
than requiring ordinal ranks or live-set regret to remain unchanged.

## Deferred work

Measured building calibration, physical failure/downtime, component residuals,
reference replacement schedules, temperature/comfort simulation, multiple energy
carriers, environmental LCA, empirical correlations and a dashboard are outside
this revision.


## v3 migration checkpoint M2.1 — 2026-09-27

- Added `carbon_consequences.py` as the first executable carbon consequence engine.
- Added A1-A3 initial product-stage GWP for `NEW_AT_T0` components only.
- Added B4 replacement product-stage GWP driven exclusively by canonical lifecycle events and M1.7/M1.8 BoQ/factor gates.
- Excluded historical A1-A3 for retained existing components.
- Preserved source factor module scope while reporting replacement product impacts to B4, preventing future replacement manufacturing from being double counted in A1-A3.
- Added central/static-factor provenance; environmental-factor uncertainty and future manufacturing decarbonisation remain unmodeled.
- Added `carbon_consequence_ledger.csv`, `assessed_product_carbon_by_module.csv`, `product_carbon_coverage.csv`, and `carbon_engine_status.json`.
- Added 11 carbon-engine tests; total suite now 109 tests.
- Verified 10,000-future 30/50/60-year parity against M1.8 for all pre-existing common non-manifest outputs.
- No A4/A5/C/D, B6 operational carbon, residual value, abatement cost, or whole-life-carbon claim introduced.

## v3 migration checkpoint M2.3 — 2026-09-28

- Added `b4_transport.py` and a separate replacement-transport assignment schema.
- Added B4 replacement transport consequences linked one-for-one to canonical B4 lifecycle events where an executable BoQ/route/factor mapping exists.
- Preserved the source transport process factor scope (`A4`) while reporting the consequence to `B4`; replacement transport is never added to the initial A4 summary.
- Added compatibility, coverage, module summary, resolved assignment and engine-status outputs for replacement transport.
- Added 10 M2.3 tests; total suite is 152 tests, all passing when executed in verified chunks.
- Verified Python byte-compilation, full default 10,000-future execution with convergence/charts, and 10,000-future 30/50/60 parity against frozen M2.2 hashes for all 46 pre-M2.3 common non-manifest outputs.
- Production replacement transport remains unpopulated; no route, distance, mass or factor was invented.


## v3 migration checkpoint M2.4 — 2026-09-28

- Added `a5_construction.py` for initial A5.2 construction/installation and A5.3 current-construction-waste consequences.
- Added header-only production inputs `construction_process_scenarios.csv` and `boq_construction_process_assignments.csv`; no project activity or waste data were fabricated.
- Added explicit activity, waste-rate/explicit-waste, unit, module-scope, duplicate-flow and scenario-scope gates.
- Kept A5.1 pre-construction removal, A5.4 worker transport and B4 installation/waste explicitly deferred.
- Added 10 M2.4 tests; complete project suite is 162 tests, all verified passing in module chunks.
- Verified Python byte-compilation and a full default 10,000-future run with convergence diagnostics and charts.
- Verified 10,000-future parity against M2.3 for 30/50/60-year profiles: all 58 common non-manifest outputs are byte-for-byte identical at every horizon.

## v3 migration checkpoint M2.5 — 2026-09-28

- Added `a5_1_removal.py` for A5.1 pre-construction removal of existing works at t0.
- Added header-only production inputs `preconstruction_removal_scenarios.csv`, `removal_transport_scenarios.csv`, and `preconstruction_waste_routes.csv`; no removal data were fabricated.
- Added independently traceable A5.1 removal-activity, removed-material outbound-transport, and removed-material waste-processing/disposal consequences.
- Preserved source-factor scope while reporting physical ownership to A5.1: A5.1 removal activity, A4 transport-process source, and C3/C4 waste-process source.
- Added structural A5.1/A5.3 anti-double-counting through disjoint removed-inventory and current-construction identities; no C-stage duplicate is generated for t0 removed quantities.
- D1 recovery declarations may be retained as metadata, but no D1 consequence is calculated.
- Added 13 M2.5 tests; complete project suite is 175 tests, all verified passing in module chunks.
- Verified Python byte-compilation and a full default 10,000-future run with convergence diagnostics and charts.
- Verified 10,000-future M2.4→M2.5 parity for 30/50/60-year profiles: all 64 common non-manifest outputs are byte-for-byte identical at every horizon.
