# Active release: v3.2.0 — bounded lifecycle-carbon architecture complete

**Release/freeze status: PASS.** The active release integrates A1-A3, A4, A5.1-A5.3, the complete B4 replacement-event family, B6 operational energy, terminal C1-C4, separate D1/D2 and an explicit module-applicability/coverage aggregation gate. M3.1.1 is retained as the hard-frozen pre-C/D provenance baseline.

Production environmental inputs remain intentionally unpopulated where no source-backed case inventory exists. Therefore architecture implementation must not be confused with a calibrated whole-building LCA result. B1/B2/B3/B5/B7/B8 are explicitly deferred/not assessed and the default release does not emit a Whole-Life Carbon headline.

# V3 implementation status

The audited v3 scientific/data design remains under `docs/`, and non-production schema templates remain under `v3_schema_templates/`.

## Implemented lineage: M1.1–M1.8 + M2.1–M2.6 + M3.1/M3.1.1 + M4 + M5

The staged production migration now has a canonical lifecycle-event ledger,
explicit stable identity/comparison lineage, and configurable 30/50/60-year
reference-study-period profiles without changing the legacy 30-year economic
results.

- `lifecycle_events.py` defines and validates the canonical lifecycle-event ledger.
- `component_lifecycle.py` represents B4 replacement timing in that canonical ledger before adapting events back to the exact v2.1 replacement-event schema.
- `identity.py` validates explicit stable IDs and provides deterministic, clearly prefixed fallbacks for legacy files.
- `horizon.py` defines named runtime profiles `legacy_30`, `levels_50`, and `rics_60`.
- `inputs/model_config.json` remains unchanged at `analysis_years = 30`; named profiles override only the runtime copy.
- `renovation_lcc.py --horizon-mode ...` selects a named profile and writes `resolved_horizon.json`.
- Event boundary semantics remain strict: `event_time_years < analysis_years`; events exactly at the horizon are excluded.
- Results are re-simulated for each RSP; no linear scaling between horizons is allowed.
- Stable event IDs do not include horizon length, so logical events shared by shorter/longer horizons retain the same IDs and physical timing records.
- Retained-component remaining-life semantics are now implemented, but no retained rows are inserted into the supplied demonstrator without documented input.
- Product and initial-A4 consequence engines are implemented. Production environmental inputs remain unpopulated; no calendar-year factor mapping, whole-life total or stakeholder-carbon allocation is calculated.

### M1.4 verification

- 20/20 original v2.1 tests pass.
- 17 migration/ledger/identity/horizon tests pass.
- Total current suite: **37/37 pass**.
- Python byte-compilation: successful.
- 10,000-future M1.3 -> M1.4 default 30-year parity: all 19 common CSV files are byte-identical.
- `resolved_config.json` and `analysis_report.txt` are also byte-identical to M1.3 in the default 30-year run.
- 10,000-future event counts: 30 years = 94,164; 50 years = 209,348; 60 years = 256,953; each ledger has unique event IDs and no event at/after its horizon.
- Event-set nesting is exact: the 30-year event set is a strict subset of the 50-year set, which is a strict subset of the 60-year set.
- For events shared across horizons, identity, timing, generation, random-stream key and sampled service life are exactly unchanged.

### M1.5 verification

- Separate `REMAINING_LIFE` and `FULL_SERVICE_LIFE` event provenance implemented.
- No age-derived remaining-life formula or silent fallback.
- 47/47 tests pass.
- 10,000-future 30/50/60 parity: every common file except the intentionally updated run manifest is byte-identical to M1.4.
- Supplied `inputs/components.csv` remains unchanged and therefore preserves the legacy-compatible NEW_AT_T0 path.

### M1.6 verification

- RSP boundary state is represented in a separate state ledger rather than as a fictitious physical event.
- One boundary row is produced for every future/component stream; generation, next replacement time and remaining life reconcile exactly.
- 62/62 tests pass.
- 10,000-future 30/50/60 parity: all 22 common non-manifest outputs are byte-identical to M1.5.
- Cross-horizon reconciliation is exact: every next replacement identified at 30 years that occurs before 50 years appears as the matching 50-year event; the same holds from 50 to 60 years.
- The production physical-reference inventory remains intentionally empty because the v2.1 source package supplies no documented existing-building component quantities, ages or remaining-life evidence.
- A strict executable reference schema, gap register, and synthetic test fixture path are implemented; no reference component is inferred from intervention lineages.

### Current scope boundary

Historical M3.1 implemented A1-A3 initial product, initial A4 transport, A5.1/A5.2/A5.3 initial-construction consequences, an event-complete B4 replacement family, and B6 operational-energy GWP from explicit imported-energy flows plus explicit annual calendar-mapped factor schedules. At that checkpoint, terminal C-stage and D1/D2 were still deferred; v3.2.0 subsequently implements those layers. A5.4, B1/B2/B3/B5/B7/B8, residual value, factor-uncertainty sampling and complete Whole-Life Carbon labelling remain outside the bounded release unless explicit evidence/scope is supplied.

### M1.7 verification

- Physical quantity / BoQ mapping is now a separate, validated layer; cost is never used as a quantity proxy.
- `inputs/component_boq.csv` is intentionally empty because the source package contains no documented intervention quantities.
- `inputs/reference_component_presence.csv` explicitly covers all six known intervention lineages and marks all six `UNKNOWN`; this is a machine-readable evidence gap, not an assumed absence.
- The event ledger remains scalar-quantity neutral. One event may map to multiple BoQ lines through `lifecycle_event_boq_quantities.csv`; boundary states use the analogous `rsp_boundary_boq_state.csv`.
- Production quantity coverage reports 13/13 intervention component instances as `BOQ_MISSING`; no percentage is interpreted as whole-building completeness.
- Production reference coverage reports 6/6 known intervention lineages as `REFERENCE_PRESENCE_UNRESOLVED`, with denominator scope `KNOWN_INTERVENTION_LINEAGES_ONLY`.
- 76/76 tests pass without warnings; Python byte-compilation succeeds.
- Independent 10,000-future M1.6 -> M1.7 parity at 30, 50 and 60 years preserves all 27 common non-manifest outputs byte-for-byte.
- A full default 10,000-future run with convergence diagnostics and charts completes successfully.
- No carbon calculation or undocumented physical quantity has been introduced.
### M1.8 verification

- Environmental-factor records are long-form and source-module aware; one factor set cannot silently mix datasets, products, declared units, geography, source provenance or licensing basis.
- GWP indicator units are normalized to `kgco2e`; unsupported indicator units fail rather than being converted implicitly.
- Source module scopes use a controlled lifecycle vocabulary. Overlapping combined/disaggregated scopes for one factor-set/indicator fail validation.
- Executable BoQ lines require explicit factor assignments; no factor is selected automatically from `material_or_product_id`.
- Exact product mappings must match identity. `DOCUMENTED_PROXY` mappings may differ only with an explicit mapping reference.
- Unit compatibility permits exact units, explicit kg↔tonne conversion, or a documented `mass_kg` bridge. Area↔volume, area↔mass without documented mass, and other implicit conversions are blocked.
- `GWP_TOTAL` is required for future headline GWP readiness and is never reconstructed from `GWP_FOSSIL`, `GWP_BIOGENIC`, or `GWP_LULUC`.
- Production `environmental_factors.csv`, `boq_environmental_factor_assignments.csv`, and `component_boq.csv` are empty; `environmental_registry_status.json` therefore reports `NO_ASSESSMENT_BOQ_LINES`, not zero carbon.
- 98/98 tests pass. Python byte-compilation succeeds.
- Independent 10,000-future M1.7→M1.8 runs at `legacy_30`, `levels_50`, and `rics_60` preserve all 36 common non-manifest files byte-for-byte.
- Full default 10,000-future run with convergence diagnostics and charts completes successfully.
- No carbon consequence or headline kgCO2e result is calculated.



### M2.1 verification

- `carbon_consequences.py` calculates GWP_TOTAL consequences only for initial A1-A3 product stage and B4 replacement product stage.
- B4 consequence timing is inherited from canonical lifecycle event IDs; no lifecycle resampling exists in the carbon engine.
- Retained-existing historical A1-A3 is excluded.
- Product-stage source modules remain traceable through `source_factor_module_scope`; replacement product impacts report to B4 and are not duplicated in A1-A3.
- Environmental factor uncertainty is not sampled. Future B4 replacements use the source dataset's static reference factor and each row records `factor_temporal_basis=STATIC_REFERENCE_FACTOR`.
- The production environmental inputs remain empty, so the default carbon ledger is empty with status `NO_ASSESSMENT_BOQ_LINES`, not zero carbon.
- 109/109 tests pass; Python byte-compilation succeeds.
- Full default 10,000-future run with convergence/charts succeeds.
- Independent 10,000-future M1.8→M2.1 parity at 30/50/60 years preserves all 42 common non-manifest outputs byte-for-byte.
- No Whole-Life Carbon, A-C total, A4/A5/C/D, B6, MAC, or stakeholder-carbon allocation is produced.

## M2.3 status — replacement transport inside B4

**PASS / freeze-ready for implemented scope.** Replacement transport is event-linked to canonical B4 replacements, uses the existing transport factor registry and unit gate, and is reported in B4. Initial A4 and product-stage consequences remain independently validated and unchanged. Production data remain unpopulated. A5, operational carbon, end-of-life, Module D, residual value and headline whole-life carbon remain deferred.


## M2.4 status — initial construction / installation consequences

**PASS / freeze-ready for implemented scope.** Initial A5.2 construction/installation and A5.3 current-construction waste are now independently gated and traceable. The layer is additive: A1-A3, A4 and both existing B4 consequence types remain unchanged. A5.1 is intentionally deferred to a dedicated pre-construction removal inventory to protect the A5.1/A5.3 double-counting boundary; A5.4 and B4 installation/waste remain deferred. Production A5 data remain unpopulated.


## M2.5 status — A5.1 pre-construction removal

**PASS / freeze-ready for implemented scope.** A5.1 removal activity, outbound removed-material transport and removed-material waste processing/disposal are independently gated and report to A5.1 while retaining source-process provenance. Removed-at-t0 inventory identities are structurally disjoint from current-construction A5.3 identities, and M2.5 generates no C-stage duplicate or D1 credit. Production removal inputs remain unpopulated. 175/175 tests pass in verified chunks; 10,000-future 30/50/60 parity preserves all 64 common non-manifest M2.4 outputs byte-for-byte.


## M2.6 status — B4 replacement-event process completion

**PASS / freeze-ready for implemented scope.** Canonical B4 replacement events can now own product, inbound transport, installation, removal, outbound removed-material transport, waste processing and disposal consequences without reclassifying them into A or terminal C modules. Source-process module provenance remains explicit. Production M2.6 assignments are unpopulated; missing replacement-process data remain not assessed. Seventeen dedicated M2.6 tests pass, a full default 10,000-future run completes successfully, and 30/50/60-year M2.5→M2.6 parity preserves all 71 common non-manifest outputs byte-for-byte.


## M3.1 / M3.1.1 status — B6 operational energy + release hardening

**HARD-FROZEN baseline after M3.1.1 hardening.** The M3.1 numerical B6 implementation remains unchanged; M3.1.1 makes the reporting convention, generated-energy approach and factor extrapolation policy explicit runtime metadata and synchronizes release documentation/integrity records.

**PASS / freeze-ready for implemented scope.** B6 operational GWP now uses explicit imported-energy flows and exact annual analysis-year/calendar-year factor schedules. Generated, self-consumed and exported onsite energy remain separately visible physical flows; export is not credited or netted into A–C in B6. At M3.1 D2 remained deferred; v3.2.0 adds it only as a separate explicit beyond-boundary layer. Production B6 inputs are intentionally unpopulated. Nineteen dedicated M3.1 tests pass, a full default 10,000-future run with convergence/charts completes successfully, and 30/50/60-year M2.6→M3.1 parity preserves all 76 common non-manifest outputs byte-for-byte.
