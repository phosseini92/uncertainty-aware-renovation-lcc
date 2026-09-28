# V3.0 Scientific Specification — Audited Section 1

## Project title

**Uncertainty-Aware Whole-Life Carbon, Cost & Value Decision Framework for Building Renovation**

**Subtitle:** A reproducible Python framework for component-level lifecycle carbon, lifecycle cost, stakeholder value allocation, and robust renovation decision support under uncertainty.

**Status:** Audit-corrected scientific design candidate, 27 September 2026. No v3 production code has been implemented in this package.

---

## 1. Standards basis and claim boundary

The primary lifecycle architecture is **EN 15978:2026-informed**, because EN 15978:2026 supersedes EN 15978:2011 and is the current European standard for building-level environmental performance assessment. The design also uses **RICS Whole Life Carbon Assessment, 2nd edition** and the European Commission **Level(s)** framework as complementary reporting and methodological references.

The framework shall **not** claim formal compliance or certification with EN 15978:2026, RICS WLCA, Level(s), EN 15804, or any national implementation unless all required data, procedures, reporting fields, verification steps, and convention-specific requirements are implemented and independently confirmed.

The framework is a research demonstrator and decision-support environment. The default illustrative dataset shall not be described as:

- a calibrated real-building model;
- a certified or formally compliant whole-life carbon assessment;
- a complete Level(s) assessment;
- a formal Social LCA;
- a full multi-impact environmental LCA;
- an empirically validated real-estate business model; or
- a nationally representative building-stock model.

The implemented environmental scope in v3.0 is **whole-life GWP/carbon focused**. The data architecture shall be multi-indicator-ready so that later environmental-LCA extensions do not require a structural redesign.

---

## 2. Research questions

**RQ1 — Carbon–cost trade-off.** How do alternative renovation strategies differ in assessed lifecycle GWP and lifecycle economic outcomes when component service lives, renewal events, economic parameters, and documented environmental parameters are uncertain?

**RQ2 — Shared-event representation.** How do results from a shared stochastic physical lifecycle-event representation differ from a predeclared deterministic benchmark using central service-life, economic, and environmental inputs?

**RQ3 — Stakeholder value allocation.** How do alternative, explicitly illustrative allocations of investment, savings, replacement responsibility, residual value, service fees, and selected risks redistribute financial outcomes among owners, tenants, third-party service providers, and the public sector?

**RQ4 — Robustness across separate decision views.** How stable are conclusions when carbon, economic robustness, and stakeholder-distribution views are examined separately and together, without collapsing them into a single hidden-preference score or a high-dimensional “overall winner” metric?

### RQ implementation guard

RQ2 requires a deterministic benchmark run. RQ3 is a **stakeholder value-allocation scenario analysis**, not a claim of validated business-model simulation. RQ4 shall use separate carbon-cost, economic-robustness, and stakeholder-distribution outputs rather than a single mega-Pareto across all dimensions.

---

## 3. Assessment object and inventory scope

The v2.1 demonstrator uses an illustrative 24-dwelling residential case. V3 retains it as a methodological benchmark unless a documented building dataset is supplied.

Required inventory-scope values:

- `WHOLE_BUILDING`
- `RENOVATION_DECISION_SCOPE`
- `PARTIAL_COMPONENT_SET`

The current v2.1 `components.csv` is a cost allocation rather than a bill of quantities. Therefore the default v3 demonstrator must not be labelled a complete whole-building WLCA unless a complete physical inventory and required operational inputs are actually supplied.

---

## 4. Functional equivalence

All compared alternatives shall maintain the same declared residential function and occupancy capacity for the same reference asset over the selected reference study period unless a documented planned change is explicitly modelled.

Each alternative must meet or exceed the declared minimum technical and functional requirements of the reference. Energy, comfort, durability, or other performance improvements may be claimed only when the metric is explicitly modelled or supplied from a traceable source.

Comparisons with different physical scope, floor area, or functional service must be flagged as not directly comparable unless an explicit equivalency rationale is supplied.

---

## 5. Reference study periods and assessment convention

V3 supports three declared horizons:

- **50 years** — primary Level(s)-aligned research horizon;
- **30 years** — legacy v2.1 continuity run;
- **60 years** — optional RICS WLCA comparison horizon.

Results must be re-simulated for each horizon; they must never be linearly scaled from another RSP.

The configuration shall include an `assessment_convention` field. Initial allowed values:

- `EN15978_2026_INFORMED`
- `LEVELS_1_2`
- `RICS_WLCA_2E`
- `CUSTOM_RESEARCH`

This field controls expected modules, normalization/reporting rules, and output labels. It does **not** by itself establish standards compliance.

An RSP is an accounting horizon, not a prediction that demolition physically occurs at its end.

---

## 6. Floor-area normalization

Required metadata:

- `floor_area_value_m2`
- `floor_area_basis`

Allowed basis values include:

- `LEVELS_USEFUL_INTERNAL_FLOOR_AREA`
- `RICS_GIA`
- `OTHER_DOCUMENTED_AREA`
- `NOT_AVAILABLE`

Asset-level results remain available without floor area. Area-normalized outputs are generated only when the basis is documented. Level(s) useful internal floor area and RICS GIA must never be treated as synonyms.

---

## 7. Time mapping and calendar-year policy

`t = 0` is the renovation decision / commencement of the assessed intervention.

Lifecycle events retain continuous event time in years. A separate calendar-year mapping shall be recorded for time-dependent environmental and energy factors. The default mapping shall be explicitly configurable, for example:

`calendar_year = base_calendar_year + floor(event_time_years)`

No hidden extrapolation of time-series factors is allowed. The configuration shall require a `factor_extrapolation_policy`, with default `ERROR_IF_MISSING`. Other policies, such as `HOLD_LAST_VALUE`, require explicit user selection and must be reported.

---

## 8. Treatment of existing, retained, removed, and new elements

Historical impacts before `t = 0` are sunk for the comparative retrofit decision unless a separate reporting purpose explicitly requires them.

### 8.1 New-at-t0 elements

New material installed at `t = 0` generates applicable module-A impacts and future B/C consequences.

### 8.2 Retained-existing elements

For retained elements:

- historical A1–A5 are excluded from the current retrofit assessment;
- future B2/B3/B4/B5 consequences are assessed where applicable;
- C-stage consequences are assessed where within scope; and
- D consequences are separately reported where assessed.

Retained components require a **remaining-service-life** model distinct from full service life after replacement. The data model shall provide separate uncertainty keys for remaining life and full replacement life.

### 8.3 Removed-at-t0 elements — corrected A5.1 rule

For retrofit/refurbishment, pre-construction demolition/deconstruction/strip-out of existing works is reported in `A5.1`.

Within the adopted research architecture, A5.1 includes the impacts attributable to that pre-construction removal activity, including:

- deconstruction/strip-out activity;
- transport of removed material from the site; and
- waste processing/disposal attributable to the removed pre-existing material.

Any recovery benefit/load beyond the system boundary is reported separately in `D1`.

`A5.3` is reserved for waste arising from the **current construction/installation process**, such as product wastage and packaging, and must not duplicate the pre-existing material already accounted for in A5.1.

---

## 9. Reference scenario

The physical reference is a **Minimum-Intervention Continued-Use Reference**. It may include:

- retained existing components;
- normal maintenance;
- necessary functional/safety replacements;
- baseline operational energy/water where supplied; and
- end-of-study/end-of-life accounting under the same RSP.

### 9.1 v2.1 compatibility

The verified v2.1 economics remain incremental relative to a zero-cash-flow reference in compatibility mode. V3 therefore separates:

1. physical reference accounting for carbon and baseline renewals; and
2. incremental private financial decision accounting.

Reference component renewal costs can support incremental/avoided-renewal calculations without redefining the reference decision NPV.

**M1.6 source-data gate.** The supplied v2.1 package does not contain a documented existing-building physical component inventory, quantities/units, installation ages or remaining-life evidence. The executable physical-reference schema is implemented, but the production inventory is intentionally empty until source-backed rows are supplied. Intervention components are not inferred to exist in the reference building. A separate gap register records unresolved comparison lineages without treating them as physical evidence.

The RSP boundary is represented as a **state observation**, not a physical lifecycle event. For each simulated component stream the model records the generation in service at the RSP, the next modeled replacement time and remaining life. This state may later support residual-value and environmental accounting, but no residual-value credit is introduced at M1.6.

A future `ABSOLUTE_LCC` mode requires complete baseline cost data and separate validation.

---

## 10. Lifecycle-module boundary

### A0 — pre-construction

`A0` is recognized in the architecture. It is not assessed by default. Its status must be explicit rather than silently absent.

### A1–A5 — initial intervention

- `A1-A3` — product stage for new products installed at t0.
- `A4` — transport of new products to the site.
- `A5.1` — pre-construction removal of existing works, including associated transport and waste processing/disposal for those removed works in the adopted research split.
- `A5.2` — construction/installation activities.
- `A5.3` — waste arising from the current installation/construction process.
- `A5.4` — worker transport, optional where assessed.

### B1–B8 — use stage

- `B1` — direct in-use emissions/removals where applicable.
- `B2` — maintenance, driven by an explicit maintenance-event schedule.
- `B3` — repair, driven by an explicit repair-event schedule or documented allowance method.
- `B4` — like-for-like replacement. A B4 event includes manufacture, transport, installation, relevant losses, removal, and end-of-life treatment attributable to the replacement event. These impacts remain reported in B4 rather than being duplicated in A or C.
- `B5` — predeclared future refurbishment/alteration that changes performance or function. B5 is not a synonym for B4 and requires its own event definition.
- `B6` — operational energy using physical energy flows and documented carrier-specific time series.
- `B7` — operational water through an external interface when assessed.
- `B8` — recognized; normally `NOT_ASSESSED_OUTSIDE_CURRENT_DEMONSTRATOR_SCOPE` in the default residential case unless a dedicated user-activity scenario is supplied.

### C1–C4 — end of life

- `C1` deconstruction/demolition;
- `C2` transport;
- `C3` waste processing;
- `C4` disposal.

C-stage scenarios at the RSP boundary are accounting scenarios and are not claims that the building will physically be demolished at that date.

### D1–D2 — beyond system boundary

- `D1` material reuse/recycling/recovery benefits or loads;
- `D2` exported energy/utilities where applicable under the selected reporting convention.

D remains separate from A–C and must never be silently netted against A–C to create a more favourable “net carbon” headline.

**v3.2.0 implementation:** terminal C1–C4 are generated only from explicit end-of-life assignments at the RSP accounting boundary. D1 material recovery and D2 exported-energy consequences are available only through explicit separate assignments/factor schedules and remain outside A–C. Default production terminal inputs are unpopulated where source-backed data are unavailable.

---

## 11. Building-integrated/site-generated energy and PV

The existing `Deep renovation + PV` case requires explicit physical energy-flow accounting.

V3 shall represent at least:

- imported energy;
- on-site generation;
- self-consumed generation; and
- exported energy.

Negative delivered energy is prohibited as a shortcut for export.

The configuration shall record a `generated_energy_reporting_approach`. The architecture shall support transparent reporting adapters for EN 15978:2026-informed generated-energy treatment and, where separately requested, RICS-style D2 reporting. The selected approach and its implications must be printed in the run manifest/report.

No carbon benefit from exported energy is claimed unless the selected convention and factor basis explicitly support it.

**M3.1.1 implemented adapter:** `generated_energy_reporting_approach=PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED` records generation/self-consumption/export for physical bookkeeping, calculates B6 from imported energy only, and defers D2. The active `factor_extrapolation_policy` is `ERROR_IF_MISSING`.

---

## 12. Shared lifecycle-event principle

A physical component event is represented once and can produce multiple consequences. Service life must never be resampled separately for carbon and cost.

Example:

```text
B4 replacement @ t = 27.4 y
    -> economic replacement flow
    -> B4 product/transport/installation consequences
    -> B4 removal and waste-treatment consequences
    -> optional D1 consequence reported separately
    -> stakeholder responsibility/allocation
```

The event ledger is the source of truth for event timing, component generation, and state at the RSP boundary.

---

## 13. Maintenance, repair, and planned-refurbishment requirements

`B2`, `B3`, and `B5` are not considered implemented merely because IDs exist in a component table.

V3 shall define explicit scenario tables for:

- maintenance activities (`B2`);
- repair activities (`B3`); and
- planned future refurbishment (`B5`).

If those tables are absent, the relevant modules must be labelled `NOT_ASSESSED_*` or `NOT_APPLICABLE` only when applicability is explicitly documented.

---

## 14. Assessment coverage and module applicability

Missing data is not equivalent to zero and is not equivalent to not-applicable.

Coverage statuses:

- `ASSESSED`
- `PARTIALLY_ASSESSED`
- `NOT_APPLICABLE`
- `NOT_ASSESSED_MISSING_INPUT`
- `NOT_ASSESSED_OUTSIDE_SCOPE`
- `NOT_ASSESSED_METHOD_NOT_IMPLEMENTED`

A separate applicability declaration/rule layer shall distinguish true non-applicability from missing evidence.

Coverage logic shall be **convention-aware**. The selected `assessment_convention` determines the expected module set and reporting basis. Result labels are then constrained by actual coverage.

If required coverage is incomplete, the software shall use labels such as:

- `Assessed lifecycle GWP — specified modules`
- `A1–A5 + B4 + C1–C4 assessed GWP`

rather than `Whole-Life Carbon`.

**v3.2.0 implementation:** `module_applicability.csv` declares scenario/module scope explicitly; `lifecycle_module_coverage.csv` derives assessment status from actual consequence evidence; `lifecycle_carbon_aggregation.csv` permits partial A–C numeric reporting but sets `whole_life_carbon_label_allowed=false` whenever deferred, missing or conflicting coverage remains. D is summarized separately.

---

## 15. Environmental indicators and factor architecture

The v3 calculation scope is GWP/carbon focused, but the factor schema is multi-indicator-ready.

Initial supported indicator IDs:

- `GWP_TOTAL`
- `GWP_FOSSIL`
- `GWP_BIOGENIC`
- `GWP_LULUC`

The architecture shall not hard-code one `gwp_kgco2e_per_declared_unit` column as the permanent data model. Indicator value, unit, declared unit, module scope, source, geography, reference year, data-quality status, and uncertainty basis must be explicit.

Biogenic GWP shall not be silently merged into fossil GWP when the source provides disaggregated indicators.

---

## 16. Future product-factor policy

Replacement events may occur decades after t0. The framework shall therefore declare whether product environmental factors are:

- static across replacement years;
- supplied as time-dependent future factors; or
- scenario-dependent.

The default research demonstrator may use static factors only if this assumption is printed and disclosed. Silent future manufacturing decarbonisation assumptions are prohibited.

---

## 17. Uncertainty semantics

Distribution shape and uncertainty meaning are distinct.

Each stochastic/variable input shall record an `uncertainty_semantics` value:

- `ALEATORY`
- `EPISTEMIC`
- `SCENARIO_NONPROBABILISTIC`
- `NONE`

Non-probabilistic scenarios must not be mixed into Monte Carlo outputs and then described as probabilities.

Environmental uncertainty shall not be invented. Where a source does not provide a defensible uncertainty basis, the factor remains deterministic and is marked `NOT_QUANTIFIED`.

---

## 18. Economic boundary and sign convention

V2.1 incremental private appraisal remains the default compatibility mode.

Economic metadata must include at least:

- `currency`
- `price_base_year`
- `price_basis` (nominal/real)
- `tax_status`
- `escalation_basis`

Carbon is never financially discounted.

### Financial ledger sign rule

The base economic ledger shall use **non-negative flow magnitudes** plus an explicit direction/type field, e.g. `COST`, `BENEFIT`, or `TRANSFER`. Stakeholder allocations then use non-negative shares. Signed base flows and signed allocation coefficients must not be combined because that creates sign ambiguity/double inversion.

The owner/tenant/combined-private identity from v2.1 must remain a regression requirement.

---

## 19. Residual value and double-counting guard

Component residual value may be introduced only with an explicit method and sensitivity treatment.

If component-level residual value and the existing terminal property-value uplift are both enabled, the model must require a declaration showing that they represent non-overlapping value mechanisms. Otherwise the run must fail or disable one mechanism.

---

## 20. Stakeholder value-allocation boundary

The v3 stakeholder module represents **illustrative value-allocation scenarios**, not validated business models.

It may allocate:

- investment costs;
- energy-cost savings;
- maintenance/replacement responsibility;
- service fees;
- residual value; and
- selected contractual/performance-risk indicators.

A future validated ESCO/business-model simulation would require financing terms, cost of capital, contract duration, savings-sharing rules, guarantees, termination logic, and empirical evidence beyond the default v3 scope.

Physical carbon remains attached to the building lifecycle rather than being arbitrarily allocated among financial actors.

---

## 21. Social boundary

The stakeholder module is not a formal Social LCA. No S-LCA terminology, social-impact characterization, or population-welfare claim shall be used unless a dedicated S-LCA method and evidence base are implemented.

---

## 22. Carbon–cost metric and unit safety

Let `delta_cost_eur` be the relevant incremental private cost and `delta_gwp_kgco2e` the option minus reference GWP.

When `delta_gwp_kgco2e < 0`, the cost-per-tonne value is:

```text
cost_per_tco2e_avoided = 1000 * delta_cost_eur / (-delta_gwp_kgco2e)
```

If `delta_gwp_kgco2e >= 0`, return `NOT_APPLICABLE_NO_CARBON_REDUCTION`.

If `abs(delta_gwp_kgco2e)` is below a declared epsilon, return `NOT_APPLICABLE_NEAR_ZERO_DENOMINATOR`.

The default label is **private net cost per tCO2e avoided**, not “marginal abatement cost”, unless the economic boundary is explicitly defined to support that term.

---

## 23. Deterministic benchmark for RQ2

V3 shall provide a deterministic benchmark using declared central inputs, for example:

- service life = distribution central/mode value;
- economic uncertainty = central configured values;
- environmental factors = documented central values;
- scenario pathways fixed.

The benchmark must be reported separately from Monte Carlo results. It exists to quantify the effect of shared stochastic lifecycle representation, not to imply that deterministic results are a gold standard.

---

## 24. Data provenance, quality, and licensing

Each external environmental dataset shall record:

- source citation/identifier;
- dataset/EPD identifier where applicable;
- geography;
- reference year;
- declared unit;
- data status/quality;
- uncertainty basis;
- redistribution/licensing status.

Only public, redistributable, or explicitly illustrative factor data may be committed to the public repository. Restricted commercial/EPD datasets must be user-supplied locally and must not be redistributed by the repository.

---

## 25. Decision outputs

V3 shall report separate views:

### Carbon view
- module-resolved GWP;
- A–C total when coverage permits;
- A-stage/upfront carbon;
- replacement carbon;
- operational carbon where assessed;
- D reported separately;
- normalization only when floor-area basis is documented.

### Economic view
- incremental lifecycle decision NPV;
- component-renewal costs;
- optional residual value;
- probability positive, downside, regret, convergence and sensitivity diagnostics.

### Stakeholder view
- owner, tenant, provider and public-sector financial allocations where configured;
- transfers reconciled explicitly;
- no conversion of physical carbon into arbitrary actor shares.

### Joint view
- carbon-cost Pareto/non-dominance;
- private net cost per tCO2e avoided where applicable;
- cross-view robustness/consistency summary;
- no hidden single “best renovation” score.

---

## 26. Freeze conditions before production coding

Section 1 is considered design-frozen only when all of the following are represented in Section 2 schemas and migration planning:

1. EN 15978:2026-informed convention basis;
2. corrected A5.1/A5.3 separation;
3. explicit B2, B3, and B5 event inputs;
4. generated/self-consumed/exported energy representation;
5. applicability-aware and convention-aware coverage logic;
6. A0 recognition;
7. deterministic benchmark for RQ2;
8. stakeholder value-allocation wording aligned with implemented scope;
9. unambiguous financial sign convention;
10. multi-indicator-ready environmental factor schema;
11. calendar-year/factor-extrapolation policy;
12. future product-factor policy;
13. separate remaining-life/full-life uncertainty keys;
14. cross-scenario component lineage; and
15. uncertainty semantics and economic metadata.

No production v3 coding should begin until these are represented consistently in the data architecture.

---

## Standards/reference notes used for this design

- BS EN 15978:2026, *Sustainability of construction works — Assessment of environmental performance of buildings — Requirements and guidance* (current European-standard adoption; supersedes EN 15978:2011).
- RICS, *Whole life carbon assessment for the built environment*, 2nd edition.
- European Commission/JRC, Level(s), Indicator 1.2 lifecycle GWP guidance and related project-setup guidance.

These sources inform architecture and terminology only; they do not establish compliance.
