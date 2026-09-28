# V3.0 Carbon Methodology & Data Architecture — Audited Section 2

**Status:** Audit-corrected design candidate. Schemas in this document are design contracts, not yet production inputs.

---

## 1. Architectural principles

1. **One physical event, many consequences.** Lifecycle event timing is generated once and reused by carbon, economics, and stakeholder accounting.
2. **No silent zeros.** Missing, not-applicable, not-implemented, and assessed-zero are distinct states.
3. **No silent convention switching.** Assessment convention, RSP, area basis, generated-energy approach, and factor policies are explicit run metadata.
4. **No double counting.** A5.1/A5.3, B4/C, D, residual values, and financial transfers have explicit guards.
5. **Provenance before precision.** Unsupported uncertainty is not invented.
6. **GWP-focused but multi-indicator-ready.** The calculation engine initially supports GWP indicators while preserving a generic indicator table.
7. **V2.1 compatibility first.** Existing 20 tests remain passing before carbon is allowed to influence results.

---

## 2. `inputs/model_config.json` — extended configuration

New v3 fields (illustrative structure):

```json
{
  "base_calendar_year": 2026,
  "analysis_years": 50,
  "assessment_convention": "EN15978_2026_INFORMED",
  "inventory_scope": "RENOVATION_DECISION_SCOPE",
  "floor_area_value_m2": null,
  "floor_area_basis": "NOT_AVAILABLE",
  "generated_energy_reporting_approach": "NOT_CONFIGURED",
  "factor_extrapolation_policy": "ERROR_IF_MISSING",
  "future_product_factor_policy": "STATIC_DOCUMENTED_FACTORS",
  "economic_mode": "INCREMENTAL_PRIVATE_COMPATIBILITY",
  "currency": "EUR",
  "price_base_year": 2026,
  "price_basis": "NOMINAL",
  "tax_status": "ILLUSTRATIVE_UNSPECIFIED",
  "escalation_basis": "CONFIGURED_NOMINAL_GROWTH",
  "component_residual_value_method": "DISABLED",
  "terminal_property_uplift_enabled": true,
  "deterministic_benchmark_enabled": true
}
```

Required validation:

- supported RSP/convention combination is declared, not inferred;
- floor-area-normalized results require non-null area and documented basis;
- component residual value plus terminal property uplift triggers a double-counting declaration/guard;
- time-series factors must cover the required calendar years unless a non-default extrapolation policy is explicitly selected.

---

## 3. `inputs/building_metadata.json` — new

Purpose: identify the assessment object independently from economic configuration.

Recommended fields:

- `building_id`
- `description`
- `number_of_dwellings`
- `building_use`
- `base_calendar_year`
- `floor_area_value_m2`
- `floor_area_basis`
- `inventory_scope`
- `geography`
- `data_status`
- `source_citation`

The default case must remain `ILLUSTRATIVE` unless project evidence is supplied.

---

## 4. `inputs/renovation_scenarios.csv` — extended

Keep existing v2.1 financial columns for compatibility and add stable identity fields:

- `scenario_id`
- `scenario_name`
- `scenario_role` (`REFERENCE`, `OPTION`)
- existing v2.1 financial fields
- `physical_reference_id`
- `operational_energy_scenario_id`
- `business_model_id` (optional)
- `notes`

The legacy string name remains display text; code joins use stable IDs.

---

## 5. `inputs/components.csv` — major schema migration

The current v2.1 file is cost-centric. V3 needs a physical component-instance table.

Recommended fields:

### Identity and lineage
- `component_instance_id`
- `scenario_id`
- `comparison_lineage_id`
- `component_type_id`
- `component_name`

`comparison_lineage_id` links corresponding component families across reference and options for common-random-number pairing and delta analysis.


### M1.5 implementation compatibility note

The production migration currently uses the narrower transitional field `initial_component_state` with values `NEW_AT_T0` and `RETAINED_EXISTING` solely to separate remaining-life and full-life renewal semantics. The richer physical `t0_state` taxonomy above remains the target for the later physical-inventory migration (retained/removed/new/not-present). Legacy lifetime columns remain accepted as the effective full-life model when explicit `full_life_*` fields are absent, preserving v2.1 parity. A retained row must provide explicit `remaining_life_*` fields; no remaining life is inferred from age.

### Physical quantity
- `quantity`
- `quantity_unit`
- `mass_kg` (optional where derivable/available)
- `material_or_product_id`

### State at t0
- `t0_state` (`EXISTING_RETAINED`, `EXISTING_REMOVED`, `NEW_INSTALLED`, `NOT_PRESENT`)
- `t0_action_id` (optional link to A5/installation process)

### Full service life for new/replacement generations
- `full_life_distribution`
- `full_life_min_years`
- `full_life_mode_years`
- `full_life_max_years`
- `full_life_fixed_years` (used for `fixed`; min/mode/max may be blank or equal)
- `full_life_uncertainty_key`

### Remaining service life for retained existing generation
- `remaining_life_distribution`
- `remaining_life_min_years`
- `remaining_life_mode_years`
- `remaining_life_max_years`
- `remaining_life_fixed_years` (used for `fixed`; min/mode/max may be blank or equal)
- `remaining_life_uncertainty_key`
- `remaining_life_basis` / provenance note where available

### Economic mapping
- `initial_cost_eur`
- `replacement_cost_eur` or a documented cost basis
- `replacement_cost_factor` retained only for compatibility
- `maintenance_cost_eur` retained only for compatibility until B2 migration

### Environmental/event mapping
- `product_factor_set_id`
- `a4_transport_scenario_id`
- `a5_installation_scenario_id`
- `b2_maintenance_scenario_id`
- `b3_repair_scenario_id`
- `eol_scenario_id`
- `b1_direct_emission_scenario_id`

No environmental quantity may be inferred from `initial_cost_eur`.

---

## 6. `inputs/environmental_factors.csv` — new, long-form and multi-indicator-ready

Purpose: avoid hard-coding a single total-GWP column.

Recommended columns:

- `factor_record_id`
- `factor_set_id`
- `dataset_id`
- `product_or_process_id`
- `indicator_id`
- `indicator_value`
- `indicator_unit`
- `declared_unit`
- `module_scope`
- `geography`
- `reference_year`
- `source_type` (`EPD`, `GENERIC_DATABASE`, `LITERATURE`, `ILLUSTRATIVE`)
- `source_citation`
- `verification_status`
- `data_quality_status`
- `license_status`
- `redistribution_allowed`
- `uncertainty_mode`
- `uncertainty_semantics`
- `uncertainty_parameter_1`
- `uncertainty_parameter_2`
- `uncertainty_parameter_3`
- `uncertainty_basis`
- `notes`

Initial supported `indicator_id` values:

- `GWP_TOTAL`
- `GWP_FOSSIL`
- `GWP_BIOGENIC`
- `GWP_LULUC`

The calculation release may focus on `GWP_TOTAL`, but disaggregated indicators are retained when provided. Restricted data are not committed to the public repository.

**M1.8 implementation note.** The registry is now executable through `environmental_factors.py`. A factor set is constrained to one dataset/product/process identity, one declared unit and one provenance/licensing basis; source-module overlaps for the same indicator are rejected. `GWP_TOTAL` is never reconstructed from disaggregated GWP indicators. BoQ factor use is selected through explicit `inputs/boq_environmental_factor_assignments.csv`, not by name matching. The unit gate allows exact units, explicit kg↔tonne conversion, or a documented total-mass bridge already present on the BoQ row. M1.8 stops before impact calculation.

---

## 7. `inputs/transport_scenarios.csv` — new

Recommended columns:

- `transport_scenario_id`
- `leg_id`
- `purpose` (`A4_NEW_PRODUCT`, `A5_1_REMOVED_EXISTING`, `B4_REPLACEMENT`, `C2_END_OF_LIFE`)
- `mode`
- `distance_km`
- `load_factor`
- `return_trip_basis`
- `factor_set_id`
- `source_citation`
- `data_status`
- `uncertainty_mode`
- `uncertainty_semantics`
- `uncertainty_basis`

Transport consequences are generated only in the reporting module appropriate to the physical event. A removed-at-t0 item must not simultaneously generate A5.1 transport and C2 transport for the same removal event.

---

## 8. `inputs/construction_process_scenarios.csv` — new

Purpose: A5.2 and current-construction A5.3 only.

Recommended fields:

- `construction_process_scenario_id`
- `activity_id`
- `activity_type`
- `activity_quantity`
- `activity_unit`
- `factor_set_id`
- `waste_rate` (where relevant)
- `waste_factor_set_id`
- `source_citation`
- `data_status`

**Guard:** Pre-existing material removed to facilitate retrofit belongs to A5.1 under the adopted design and must not be duplicated in A5.3. A5.3 is for waste arising from the current construction/installation process.

---

## 9. `inputs/preconstruction_removal_scenarios.csv` — new

Purpose: explicit A5.1 accounting for existing works removed at t0.

Recommended fields:

- `removal_scenario_id`
- `component_instance_id`
- `removal_activity_factor_set_id`
- `removed_quantity`
- `removed_quantity_unit`
- `transport_scenario_id`
- `waste_route_scenario_id`
- `d1_recovery_scenario_id` (optional, separate reporting)
- `source_citation`
- `data_status`

This table prevents A5.1 from being reduced to “strip-out energy only”.

---

## 10. `inputs/maintenance_scenarios.csv` — new (B2)

Recommended fields:

- `maintenance_scenario_id`
- `activity_id`
- `interval_years`
- `first_event_year`
- `end_rule`
- `activity_quantity`
- `activity_unit`
- `factor_set_id`
- `economic_cost_eur`
- `cost_base_year`
- `source_citation`
- `data_status`
- `uncertainty_mode`
- `uncertainty_semantics`
- uncertainty parameters/basis

Maintenance event times are generated explicitly. Existing v2.1 annual maintenance may remain in compatibility mode, but it must not simultaneously coexist with detailed B2 economic maintenance without a reconciliation rule.

---

## 11. `inputs/repair_scenarios.csv` — new (B3)

Recommended fields:

- `repair_scenario_id`
- `repair_method` (`SCHEDULED`, `ALLOWANCE`, `EXTERNAL_EVENTS`)
- `interval_years` or `annual_rate` where method permits
- `repair_fraction_of_component`
- `material_factor_set_id`
- `transport_scenario_id`
- `process_factor_set_id`
- `economic_cost_eur`
- `source_citation`
- `data_status`
- `uncertainty_mode`
- `uncertainty_semantics`
- uncertainty basis

The default illustrative release may leave B3 not assessed if no defensible repair scenario exists. An empty table is not interpreted as zero repair.

---

## 12. `inputs/planned_refurbishment_events.csv` — new (B5)

Recommended fields:

- `refurbishment_event_id`
- `scenario_id`
- `event_year`
- `action_type`
- `target_component_instance_id`
- `replacement_or_added_component_id`
- `quantity`
- `quantity_unit`
- `performance_change_id` (optional)
- `economic_flow_id` (optional)
- `source_citation`
- `data_status`

A B5 event is planned at assessment outset and changes the asset beyond like-for-like B4 replacement. Reporting adapters may require a separate comparison scenario depending on the selected convention.

---

## 13. `inputs/end_of_life_scenarios.csv` — new

Recommended fields:

- `eol_scenario_id`
- `material_or_product_id`
- `reuse_fraction`
- `recycling_fraction`
- `recovery_fraction`
- `disposal_fraction`
- `c1_factor_set_id`
- `c2_transport_scenario_id`
- `c3_factor_set_id`
- `c4_factor_set_id`
- `d1_factor_set_id`
- `source_citation`
- `data_status`

Validation:

`reuse + recycling + recovery + disposal = 1` within tolerance.

C and D remain separately reported.

---

## 14. `inputs/operational_energy_flows.csv` — new

Purpose: replace the ambiguous “negative delivered energy” pattern and support PV transparently.

Recommended columns:

- `operational_energy_scenario_id`
- `year`
- `energy_carrier`
- `imported_kwh`
- `onsite_generated_kwh`
- `self_consumed_kwh`
- `exported_kwh`
- `purpose`
- `source_citation`
- `data_status`

Validation examples:

- all quantities non-negative;
- `self_consumed_kwh <= onsite_generated_kwh`;
- `exported_kwh <= onsite_generated_kwh`;
- physical-balance checks appropriate to the input convention.

The selected `generated_energy_reporting_approach` determines how these physical flows are mapped to B6/D2/additional reporting. Physical flows remain unchanged by the reporting adapter.

---

## 15. `inputs/energy_carbon_factors.csv` — new

Recommended columns:

- `factor_scenario_id`
- `calendar_year`
- `energy_carrier`
- `indicator_id`
- `factor_value`
- `factor_unit`
- `geography`
- `source_citation`
- `data_status`
- `uncertainty_mode`
- `uncertainty_semantics`
- uncertainty parameters/basis

Default extrapolation policy: `ERROR_IF_MISSING`.

No silent carry-forward of a 2050 grid factor to 2076 is permitted.

---

## 16. Optional direct-emission and water interfaces

### `inputs/direct_emissions.csv` — B1

- `scenario_id`
- `component_instance_id`
- `event_time_years` or `calendar_year`
- `substance`
- `mass_emitted_kg`
- `factor_set_id`
- provenance fields

### `inputs/operational_water.csv` — B7

- scenario/year/water-flow quantities
- purpose
- factor mapping
- provenance

B1/B7 missing inputs are not zero unless applicability is explicitly `NOT_APPLICABLE`.

---

## 17. `inputs/module_applicability.csv` — new

Purpose: distinguish `NOT_APPLICABLE` from missing evidence.

Recommended fields:

- `scenario_id`
- `component_instance_id` or `*`
- `module`
- `applicability` (`APPLICABLE`, `NOT_APPLICABLE`, `UNKNOWN`)
- `reason`
- `evidence_source`
- `review_status`

Coverage engine logic combines this table with data presence and implementation status.

---

## 18. `inputs/business_models.csv` — renamed conceptual role

This table defines **illustrative delivery/value-allocation archetypes**, not empirically validated business models.

Recommended fields:

- `business_model_id`
- `business_model_name`
- `description`
- `scenario_id` or `*`
- `financing_actor`
- `replacement_responsibility_actor`
- `residual_value_actor`
- `performance_risk_actor`
- `evidence_status`
- `notes`

Default archetypes may include owner-funded, split-incentive, service-provider, and circular/take-back arrangements, all labelled `ILLUSTRATIVE` unless sourced.

---

## 19. `inputs/stakeholder_allocations.csv` — corrected sign design

The base economic ledger uses non-negative magnitudes plus flow direction. Therefore allocations use non-negative shares.

Recommended columns:

- `business_model_id`
- `flow_type`
- `stakeholder`
- `share`
- `boundary`
- `notes`

Validation:

- `0 <= share <= 1`;
- required allocation shares for an allocatable flow sum to 1 within tolerance;
- transfers reconcile across payer/recipient ledgers without creating or destroying value.

Do **not** combine signed base cash flows with signed allocation coefficients.

---

## 20. Internal `lifecycle_event_ledger`

Core fields:

- `event_id`
- `future_id` — required for Monte Carlo event identity and reconciliation
- `scenario_id`
- `component_instance_id`
- `comparison_lineage_id`
- `component_generation`
- `event_type`
- `event_time_years`
- `calendar_year`
- `event_quantity`
- `event_unit`
- `physical_state_before`
- `physical_state_after`
- `source_event_id` (for derived sub-events)
- `random_stream_key`
- `sampled_service_life_years`
- `service_life_basis` (`FULL_SERVICE_LIFE` / later `REMAINING_SERVICE_LIFE`)

M1.3 implementation note: the migrated default inputs now carry explicit stable `scenario_id`, `component_instance_id`, `component_type_id` and `comparison_lineage_id` values. Canonical event identity uses those IDs and is invariant to display-label edits. Legacy files without explicit IDs remain accepted through deterministic compatibility IDs prefixed `legacy_`; those fallbacks are intentionally not presented as durable project identifiers. `calendar_year`, physical event quantity/unit and physical state remain null rather than being fabricated.

Core event types:

- `T0_RETAINED_STATE`
- `T0_REMOVAL`
- `T0_INSTALL`
- `MAINTENANCE`
- `REPAIR`
- `B4_REPLACEMENT`
- `B5_REFURBISHMENT`

The event ledger is the only source of physical lifecycle-event timing used by carbon and economic consequence engines. The **RSP boundary is not a physical event**: M1.6 represents it in a separate `rsp_boundary_state.csv` state ledger containing the installed generation, current interval, next replacement time and remaining life. This prevents an accounting observation point from being misclassified as a lifecycle event.

---

## 21. Carbon consequence ledger

Recommended fields:

- `carbon_consequence_id`
- `event_id`
- `scenario_id`
- `module`
- `submodule`
- `indicator_id`
- `indicator_value`
- `indicator_unit`
- `factor_record_id`
- `quantity_used`
- `quantity_unit`
- `calendar_year`
- `coverage_status`
- `source_citation`

D1/D2 records remain separate and are not included in A–C totals.

---

## 22. Economic consequence ledger — corrected sign convention

Recommended fields:

- `economic_consequence_id`
- `event_id` (nullable for annual/scenario-level flows)
- `scenario_id`
- `flow_type`
- `flow_direction` (`COST`, `BENEFIT`, `TRANSFER`)
- `flow_amount_eur` (non-negative magnitude)
- `nominal_or_real`
- `calendar_year`
- `price_base_year`
- `discount_rate_used`
- `present_value_eur`
- `boundary`

Stakeholder allocation is applied after this base flow is defined.

---

## 23. Stakeholder consequence ledger

Recommended fields:

- `stakeholder_consequence_id`
- `economic_consequence_id`
- `business_model_id`
- `stakeholder`
- `share`
- `allocated_amount_eur`
- `role` (`PAYER`, `RECIPIENT`, `RESPONSIBLE_ACTOR`)
- `boundary`

A transfer requires matched payer/recipient treatment so aggregate private-account identities remain testable.

---

## 24. Coverage matrix and permitted labels

Output: `assessment_coverage.csv`

Recommended columns:

- `scenario_id`
- `assessment_convention`
- `module`
- `expected_under_convention`
- `applicability`
- `method_implemented`
- `input_status`
- `coverage_status`
- `reason`

Coverage status is derived from:

1. convention expectation;
2. module applicability;
3. method implementation;
4. input availability/quality; and
5. successful calculation.

Only coverage-aware labels may be emitted. A partial assessment cannot be labelled complete WLCA merely because unassessed modules are numerically absent.

---

## 25. Deterministic benchmark architecture

Output: `deterministic_vs_stochastic_comparison.csv`

Deterministic benchmark rules are declared, not inferred:

- central service-life value;
- central economic inputs;
- central documented environmental factors;
- fixed scenario pathways.

Fields include:

- scenario
- metric
- deterministic_value
- stochastic_median
- stochastic_mean
- selected percentile interval
- absolute_difference
- relative_difference
- interpretation_flag

---

## 26. Environmental factor equations

For a factor record compatible with the component/process declared unit:

```text
impact = activity_quantity * indicator_factor
```

Unit conversion must occur through an explicit conversion layer; no implicit conversion from cost to quantity is allowed.

For module totals:

```text
GWP_module = sum(event consequences mapped to that module)
GWP_A_to_C = sum(A0/A1-A5/B1-B8/C1-C4 as required by selected reporting convention and actual assessed coverage)
```

D is reported separately.

If a reporting convention excludes a recognized module from a headline metric, the report must state that convention rather than silently discarding the module.

---

## 27. B4 replacement coupling

A B4 physical event is generated from the shared lifecycle engine. It can produce:

- replacement product impact;
- replacement transport;
- installation/activity impact;
- replacement-related waste/loss impact;
- removal/waste-treatment impact of the displaced generation;
- separate D1 record where applicable;
- replacement economic flow;
- stakeholder responsibility/allocation.

These are **subconsequences of one B4 event** and remain reported in B4 for lifecycle-carbon reporting. They must not also be counted in A or C for the same event.

---

## 28. A5.1/A5.3 double-counting guard

For a component with `t0_state = EXISTING_REMOVED`:

- its t0 removal, removed-material transport, and removed-material waste-processing/disposal route are assigned to A5.1 in the adopted architecture;
- the same removed quantity cannot also generate C1–C4 or A5.3 at t0;
- D1 may be generated separately where recovery beyond the boundary applies.

A5.3 is used for current-construction waste such as new-product wastage/packaging.

A validation test shall assert that each physical waste quantity has exactly one in-boundary lifecycle-module owner for the same event.

---

## 29. Future product-factor policy

`future_product_factor_policy` controls environmental factors for replacement generations:

- `STATIC_DOCUMENTED_FACTORS`
- `TIME_SERIES_FACTORS`
- `SCENARIO_FACTORS`

Default demonstrator behaviour may be static, but the assumption must be printed in the report and manifest.

---

## 30. Uncertainty implementation

Each uncertain field separates:

- distribution/mode (`FIXED`, `TRIANGULAR`, `LOGNORMAL`, etc.);
- semantics (`ALEATORY`, `EPISTEMIC`, `SCENARIO_NONPROBABILISTIC`, `NONE`);
- basis/source.

Non-probabilistic pathway scenarios are enumerated/sensitivity-tested rather than randomly sampled as if they had probabilities.

Common-random-number pairing uses `comparison_lineage_id` plus separate `remaining_life_uncertainty_key` and `full_life_uncertainty_key` where appropriate.

---

## 31. Data-quality and licensing outputs

Output: `environmental_data_quality.csv`

Recommended columns:

- factor_record_id
- source_type
- geography
- reference_year
- verification_status
- uncertainty_basis
- license_status
- redistribution_allowed
- data_quality_status
- notes

The public example repository shall use only data that may legally be redistributed or clearly marked illustrative values.

---

## 32. Validation invariants required before v3 release

At minimum:

1. all 20 v2.1 tests remain passing;
2. extracted lifecycle-event ledger reproduces v2.1 replacement timing/costs in compatibility mode;
3. deterministic toy factor gives exact `quantity x factor` result;
4. same B4 event drives both cost and carbon without resampling life;
5. no replacement occurs exactly at horizon, preserving v2.1 rule;
6. retained initial component uses remaining life, later generations use full life;
7. A5.1 removal cannot be duplicated in A5.3/C;
8. B4 consequences cannot be duplicated in A/C;
9. EOL shares sum to one;
10. imported/generated/self-consumed/exported energy passes physical consistency checks;
11. missing required year in time-series factor fails under default extrapolation policy;
12. Module D is excluded from A–C totals;
13. assessment coverage cannot classify missing input as not-applicable without applicability evidence;
14. unsupported module prevents complete-WLC label;
15. owner + tenant (+ provider, where in boundary) transfers reconcile;
16. economic base-flow sign convention cannot double-invert allocation signs;
17. residual-value/property-uplift double-counting guard works;
18. kg-to-tonne carbon cost metric conversion is correct;
19. zero/positive/near-zero delta-GWP edge cases return defined statuses;
20. option reorder does not alter paired random draws;
21. factor indicator unit mismatch is rejected;
22. disaggregated GWP indicators are not silently summed into total unless source methodology permits;
23. non-probabilistic scenario uncertainty is not reported as probability;
24. deterministic benchmark is reproducible;
25. coverage/report labels are stable under row reorder.

---

## 33. No-code freeze gate

No v3 production code should be merged until:

- all schema contracts above are accepted;
- the module/applicability rules are internally consistent;
- a legal/redistributable illustrative environmental dataset strategy is chosen;
- the default generated-energy reporting approach for the PV case is selected;
- the compatibility test plan is accepted; and
- the v2.1 baseline remains unchanged and reproducible.

## M1.7 implementation note — one-to-many BoQ bridge

The audited implementation does **not** force physical quantity into the scalar `event_quantity` / `event_unit` fields when a lifecycle component may consist of multiple product/material inventory lines. M1.7 introduces `inputs/component_boq.csv` as the authoritative one-to-many quantity map and derives `lifecycle_event_boq_quantities.csv` plus `rsp_boundary_boq_state.csv` (and reference equivalents) by stable component/event identity. The scalar event fields remain nullable for compatibility and must not be interpreted as zero.

Each BoQ row carries a stable `boq_line_id`, exact parent scenario/component/lineage/type identity, material/product ID, assessment role, positive quantity, explicit normalized unit, optional mass, and provenance. `ASSESSMENT_INVENTORY` is distinct from `INFORMATION_ONLY`; later carbon calculation must only consume the intended assessment inventory and must not silently add informational totals to material/product sublines. No cost-to-quantity inference or implicit physical unit conversion is permitted.

Reference coverage is separately declared in `inputs/reference_component_presence.csv` with `PRESENT_DOCUMENTED`, `ABSENT_DOCUMENTED`, or `UNKNOWN`. `reference_coverage_skeleton.csv` combines that declaration with executable reference inventory and BoQ availability. Its denominator is explicitly `KNOWN_INTERVENTION_LINEAGES_ONLY`, so it cannot be presented as whole-building inventory completeness.

### M2.5 implementation note — A5.1 executable removal schema

The M2.5 executable schema expands the earlier conceptual `preconstruction_removal_scenarios.csv` skeleton with explicit scenario scope, removal-inventory identity, comparison lineage, material/product identity, removal activity quantity/unit, documented mass bridge, mapping/provenance fields, and active-state control. Outbound removal transport and waste-route metadata are separated into `removal_transport_scenarios.csv` and `preconstruction_waste_routes.csv` so missing distance, transport-factor basis, and waste-route source module can be gated independently. This implementation preserves the original design rule: removed-at-t0 material is owned by A5.1 and cannot also be owned by A5.3 or C for the same physical event.
### M3.1.1 factor-year semantics

For operational B6 schedules, `calendar_year` is the application year of the scheduled factor. The environmental registry field `reference_year` records dataset/source reference vintage for provenance and is not, by itself, the application year. The schedule is the authoritative time-mapping layer; no future-year meaning is inferred from `reference_year`.


## v3.2.0 terminal and coverage tables

The bounded research release adds four explicit input layers:

- `end_of_life_assignments.csv` — terminal BoQ-to-C1/C2/C3/C4/D1 mapping;
- `d2_export_assignments.csv` — explicit exported-energy-flow to D2 schedule mapping;
- `d2_export_factor_schedule.csv` — annual/calendar-year D2 factor schedule;
- `module_applicability.csv` — scenario/module applicability and bounded-scope declaration.

Corresponding outputs include terminal/D coverage, a module coverage matrix, partial lifecycle-carbon aggregation and a separate Module-D summary. Production terminal/D physical inputs are header-only unless source-backed data are supplied.
