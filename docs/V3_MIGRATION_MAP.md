# V2.1 → V3.0 Migration Map — Audited Revision

> **Historical migration record.** This file preserves the staged v2.1→v3 implementation history. The active release is v3.2.0, which has progressed beyond the early deferred items below and now includes A-stage, complete B4, B6, terminal C1–C4, separate D1/D2 and the lifecycle coverage gate. For current scope use `README.md`, `V3_DESIGN_STATUS.md` and `docs/release/IMPLEMENTED_SCOPE.md`.


## Baseline verification

Source package: `uncertainty-aware-renovation-lcc-v2.1.zip`

SHA-256 of supplied ZIP:

`3e6208c636c1791501bf486b79f8df3d97d8648421379db7a8d0da384ec5b882`

Baseline verification: **20/20 existing tests pass**.

The audited design has now entered controlled implementation. M1.1/M1.2 introduces the canonical lifecycle-event ledger and a compatibility adapter while preserving v2.1 economic results exactly. Later v3 consequence engines remain unimplemented.

---


## Current implementation checkpoint

### M1.1 — canonical event schema + validation — IMPLEMENTED

- Added `lifecycle_events.py`.
- Added `future_id` to the canonical ledger because Monte Carlo events cannot be reconciled without it.
- Validator enforces event schema, unique IDs, supported event types, positive continuous event time/service-life values and unique generation identity.
- Missing physical/calendar data from v2.1 remain null; no values are invented.

### M1.2 — legacy replacement adapter — IMPLEMENTED

- Existing service-life sampling/economic equations remain unchanged.
- B4 replacement timing is represented in the canonical ledger first.
- The public v2.1 `lifecycle_replacements.csv` is reconstructed from that ledger.
- `renovation_lcc.py` additionally writes `lifecycle_event_ledger.csv`.
- 24/24 tests pass; 18 common CSV outputs are byte-identical to the audited v2.1 baseline in a 10,000-future parity run.

### M1.3 — stable IDs + explicit comparison lineage — IMPLEMENTED

- Default scenario/component inputs now carry explicit stable IDs.
- Canonical event identity is independent of display labels.
- Explicit comparison lineage validates one component family and one lifetime stream.
- 30/30 tests passed at the M1.3 checkpoint with documented 10,000-future parity.

### M1.4 — configurable 30/50/60-year horizons — IMPLEMENTED

- Added `horizon.py` with `legacy_30`, `levels_50` and `rics_60` profiles.
- Preserved the source configuration at 30 years; runtime profile resolution changes only an isolated copy.
- Added CLI selection and `resolved_horizon.json`.
- Preserved strict exclusion of events exactly at the horizon.
- 37/37 tests pass; 10,000-future 30-year outputs remain byte-identical to M1.3.
- Event sets are exactly nested across 30/50/60-year runs for common seeds.

### M1.5 — retained remaining life vs replacement full life — IMPLEMENTED

- optional explicit `initial_component_state` supports `NEW_AT_T0` and `RETAINED_EXISTING`;
- retained generation 0 requires an explicit remaining-life model;
- all installed/replacement generations use the full service-life model;
- `age_at_t0_years` is metadata only and is not converted to remaining life;
- remaining/full uncertainty streams are distinct and recorded in the event ledger;
- legacy component files with no M1.5 fields retain exact v2.1 full-life streams;
- default 30/50/60 results remain byte-identical to M1.4 except the run manifest.

**Gate:** PASS — 47/47 tests; 10,000-future parity verified at all three horizon profiles.

### Still deferred within Milestone 1

- RSP-boundary states and physical quantities;
- assessment calendar-year mapping;
- documented physical reference inventory.

## Migration principles

1. Preserve v2.1 outputs before adding carbon.
2. Extract physical lifecycle events before changing consequence accounting.
3. Add schema fields in a backward-compatible loader stage where practical.
4. Do not change lifecycle timing, economic accounting, and carbon accounting in one uncheckpointed step.
5. Treat current EN 15978:2026 as the primary lifecycle architecture reference while keeping no-compliance wording.
6. Build convention/applicability/coverage logic before allowing complete-WLC labels.

---

## Corrected forensic findings

### Existing strengths to preserve

- deterministic keyed random streams;
- continuous service-life sampling and multiple renewals;
- exclusion of events exactly at the horizon;
- owner/tenant/combined-private accounting identity;
- convergence/seed checks;
- stress interfaces with explicit proxy limitations;
- resolved inputs, hashes and manifests.

### Conflicts/blockers resolved in design

1. Reference components are currently forbidden but v3 needs a physical reference inventory.
2. Reference financial inputs are zero by design; compatibility mode remains incremental.
3. Existing component rows lack physical quantities and environmental mappings.
4. Replacement cost basis is tied to initial-cost allocation and must be generalized.
5. Retained components need separate remaining-life semantics.
6. RSP-boundary component state is not currently represented.
7. Current energy-savings proxy has no carrier and cannot become B6 automatically.
8. PV/exported energy needs explicit physical flow accounting and convention-aware reporting.
9. Existing terminal property uplift may overlap with component residual value.
10. Default case has no documented floor area/complete material inventory.
11. A5.1 needed correction: removed-existing transport/waste handling belongs to the pre-construction removal accounting adopted for A5.1, not generic A5.3.
12. B2, B3 and B5 require actual event/scenario tables, not placeholder IDs only.
13. Missing input cannot be equated to `NOT_APPLICABLE`; an applicability layer is required.
14. Financial stakeholder sign convention must avoid signed-flow × signed-coefficient ambiguity.
15. Environmental factors should be long-form/multi-indicator-ready rather than hard-coded to one GWP-total scalar.
16. Continuous event times need explicit calendar-year mapping and factor-extrapolation policy.
17. RQ2 requires a deterministic comparator; RQ3/RQ4 wording must match the implementable scope.

---

## Existing file migration

| File | Action | Audited v3 treatment |
|---|---|---|
| `renovation_lcc.py` | REFACTOR | Keep CLI/orchestrator compatibility; new engines live in dedicated modules. |
| `component_lifecycle.py` | REFACTOR + WRAPPER | Extract physical event generation; retain legacy `renewal_costs()` wrapper until equivalence tests pass. |
| `random_streams.py` | KEEP / EXTEND | Preserve keyed/prefix-invariant RNG; add separate remaining-life/full-life and environmental keys. |
| `robustness.py` | KEEP / EXTEND | Preserve economic robustness. Do not merge all new dimensions into one preference score. |
| `convergence.py` | KEEP / EXTEND | Add carbon convergence only where carbon inputs are genuinely probabilistic. |
| `performance_stress.py` | KEEP, BOUNDED | Never auto-promote savings proxy to B6. |
| `charts.py` | EXTEND | Module carbon, event timeline, carbon-cost frontier, coverage, stakeholder views. |
| `inputs/model_config.json` | EXTEND | Add convention, RSP, time mapping, factor policy, economic metadata, residual-value guards. |
| `inputs/renovation_scenarios.csv` | EXTEND | Stable IDs/roles, physical-reference link, energy/value-allocation mapping. |
| `inputs/components.csv` | MAJOR MIGRATION | Physical quantity/state, lineage, remaining/full life, environmental/event mappings. |
| `inputs/climate_stress_scenarios.csv` | KEEP | Remains distinct from lifecycle-carbon inputs. |
| root docs | PRESERVE UNTIL RELEASE | Keep v2.1 baseline documentation intact while v3 design/code is under development. |
| `CITATION.cff` | RELEASE-ONLY | Update only after v3 implementation and validation. |

---

## New input/data files

- `building_metadata.json`
- `environmental_factors.csv`
- `transport_scenarios.csv`
- `construction_process_scenarios.csv`
- `preconstruction_removal_scenarios.csv`
- `maintenance_scenarios.csv`
- `repair_scenarios.csv`
- `planned_refurbishment_events.csv`
- `end_of_life_scenarios.csv`
- `operational_energy_flows.csv`
- `energy_carbon_factors.csv`
- `direct_emissions.csv` (optional B1)
- `operational_water.csv` (optional B7)
- `module_applicability.csv`
- `business_models.csv`
- `stakeholder_allocations.csv`

---

## New Python modules recommended

### `lifecycle_events.py`

Single source of truth for:

- t0 retained/removed/new states;
- remaining-life and full-life sampling;
- B2/B3 schedules where configured;
- B4 replacement timing;
- B5 planned refurbishment;
- component generation/state at RSP boundary;
- continuous event time and calendar-year mapping.

### `environmental_factors.py`

Loads/validates long-form indicator data, units, provenance, licensing, uncertainty semantics, and future-factor policy.

### `carbon.py`

Maps activities/events to module-coded environmental consequences. Never resamples service life.

### `energy_flows.py`

Validates imported/generated/self-consumed/exported physical flows and applies selected reporting adapter.

### `economics.py`

Retains v2.1 incremental accounting; adds explicit replacement-cost basis and optional residual value under guard.

### `stakeholder_value.py`

Allocates non-negative base-flow magnitudes using shares and role/direction semantics. Physical carbon remains separate.

### `coverage.py`

Combines assessment convention, module applicability, method implementation, input status, and calculation status to produce permissible labels.

### `decision_metrics.py`

Calculates carbon-cost non-dominance, private net cost per tCO2e avoided, deterministic-vs-stochastic comparison, and cross-view summaries without a hidden overall score.

---

## Implementation sequence with regression gates

### Milestone 0 — design freeze

- accept audited Section 1 and Section 2;
- select default generated-energy reporting approach for PV demo;
- choose redistributable/illustrative factor-data strategy;
- keep 20/20 v2.1 tests passing.

### Milestone 1 — stable IDs and compatibility loaders — IMPLEMENTED THROUGH M1.3

- explicit stable scenario/component/type IDs and comparison lineage added to migrated default inputs;
- loaders accept legacy v2.1 files or migrated files;
- canonical event IDs no longer depend on display labels;
- numerical v2.1 outputs unchanged.

**Gate:** PASS — 20/20 legacy tests plus migration tests pass; 10,000-future economic parity verified.

### Milestone 2 — physical lifecycle-event ledger — PARTIALLY IMPLEMENTED (M1.1/M1.2)

- extract event timing from `component_lifecycle.py`;
- retained remaining life vs new full life — implemented in M1.5;
- preserve `renewal_costs()` as wrapper;
- add RSP-boundary state — implemented in M1.6 as a separate state ledger.

**Gate:** legacy replacement timing/cost outputs equivalent.

### Milestone 3 — reference inventory + applicability/coverage skeleton — PARTIALLY IMPLEMENTED (M1.6)

- executable physical-reference schema/gate implemented; production inventory remains empty because source-backed building data are absent;
- physical reference components, when supplied, use the shared lifecycle engine without changing reference decision NPV;
- add module applicability and convention metadata;
- coverage engine emits statuses before carbon exists.

**Gate:** no module can be labelled assessed without method/input evidence.

### Milestone 4 — deterministic carbon core

- long-form factor loader;
- unit conversion/validation;
- A1–A4, corrected A5.1/A5.2/A5.3;
- B4 consequence coupling;
- C/D separation;
- deterministic toy hand-calculation tests.

**Gate:** no event double counting; exact toy outputs.

### Milestone 5 — B2/B3/B5 and operational interfaces

- maintenance/repair/planned-refurbishment event tables;
- B1 optional direct emissions;
- B6 physical energy flows and time-dependent factors;
- PV generation/self-use/export reporting adapter;
- B7 optional water interface.

**Gate:** coverage labels respond correctly to each omitted/supplied module.

### Milestone 6 — stochastic environmental inputs

- only source-supported uncertainty;
- semantics-aware treatment of aleatory/epistemic/scenario uncertainty;
- future product-factor policy;
- calendar-year/extrapolation validation.

**Gate:** no non-probabilistic scenario is reported as probability.

### Milestone 7 — economics/residuals/stakeholder allocation

- generalized replacement-cost basis;
- residual-value option with terminal-value overlap guard;
- non-negative flow magnitude + direction convention;
- stakeholder shares and transfer reconciliation.

**Gate:** owner/tenant/provider identities and no value creation by allocation.

### Milestone 8 — deterministic benchmark and decision metrics

- deterministic comparator for RQ2;
- carbon-cost Pareto/non-dominance;
- private net cost per tCO2e avoided;
- cross-view robustness summary.

**Gate:** unit/edge-case tests pass; no mega-Pareto overall winner.

### Milestone 9 — release validation

- legacy regression;
- hand calculations;
- stochastic reproducibility/prefix checks;
- row-order invariance;
- full coverage/label tests;
- documentation and claim-boundary audit;
- public-data licensing check.

Only after this gate should README/CITATION/version be changed to v3.0.

---

## Explicit non-goals for v3.0

- formal certification/compliance claim;
- full multi-impact environmental LCA implementation;
- formal Social LCA;
- calibrated EnergyPlus/BEM model;
- nationally representative Finnish building stock;
- empirically validated ESCO/commercial business model;
- hidden overall ranking of renovation alternatives.

## M1.7 completed — physical quantity / BoQ bridge

- **ADD `physical_quantities.py`:** strict BoQ, unit, provenance, reference-presence and bridge-table validation.
- **ADD `inputs/component_boq.csv`:** production physical quantity mapping; intentionally header-only until documented quantities are supplied.
- **ADD `inputs/reference_component_presence.csv`:** machine-readable presence/absence/unknown declaration for every known intervention lineage.
- **ADD outputs:** physical quantity coverage, reference coverage skeleton, event/BoQ and RSP/BoQ bridges plus reference equivalents.
- **KEEP canonical lifecycle timing unchanged:** M1.7 quantities join to stable event/state identity and do not alter service-life draws, replacement schedules or economic consequences.
- **DEFER factor mapping:** no environmental factor ID or GWP calculation is introduced until the next carbon-data milestone.

## M2.5 completed — corrected A5.1 pre-construction removal core

- Added a dedicated removed-at-t0 inventory rather than reusing current-construction BoQ.
- Added A5.1 removal/deconstruction activity, outbound removed-material transport, and waste processing/disposal consequence paths.
- Preserved source-process factor provenance while assigning reporting ownership to A5.1 under the adopted retrofit split.
- Added structural A5.1/A5.3 identity separation and no-C-duplicate validation.
- Kept D1 recovery beyond the system boundary separately deferred.
- Deterministic-carbon Milestone 4 is now complete for A1-A4, corrected A5.1/A5.2/A5.3, and B4 product/transport coupling; C/D separation is architected but C/D consequence engines remain to be implemented.
