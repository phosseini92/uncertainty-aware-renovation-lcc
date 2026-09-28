# V2.1 assumption register

## Evidence status

The original 24-dwelling scenario budgets and economic distributions were supplied
with the July 2026 demonstrator. Component allocations and lifetimes were added
as illustrative assumptions during the September revision. The stress multipliers
follow the proposed numerical examples, with labels explicitly changed to proxies.
No authoritative lifetime database, measured building dataset or climate projection
was used to establish these values. They must not be cited as empirical evidence.

## Core accounting

- Horizon 30 years; all values are incremental to the reference.
- Owner energy-bill savings share defaults to zero; tenants receive those savings.
- Owner pays initial net investment, routine maintenance and subsequent renewals.
- Rent increments are transfers and cancel in the combined private account.
- Initial grants apply to cost-adjusted investment; no grants are assumed on renewals.
- Nominal first-year annual amounts occur at year 1 end. Growth starts affecting
  them in year 2. The nominal discount rate is fixed within each future.
- The EUR 6 million terminal reference value is a hypothetical end-horizon nominal
  property value, not a current property value that is escalated by the model.
- Terminal premium represents post-horizon asset value, separate from rent within
  the horizon. This assumption needs real valuation evidence before an application.
- No taxes, debt, vacancy, moving costs, subsidies' public financing or household
  heterogeneity are modelled. Combined private is not social welfare.

```text
PV of annual amount A = sum t=1..T [A*(1+g)^(t-1)/(1+r)^t]
Renewal time k        = sum of sampled service lives 1..k
Nominal renewal cost  = component initial-cost allocation * replacement factor
                        * sampled capital-cost factor * (1+replacement growth)^time
PV renewal cost       = nominal renewal cost / (1+discount rate)^time
```

Only times strictly less than T incur renewals. Continuous timing is intentional;
there is no annual rounding. A failure is represented as the end of service life
followed by immediate renewal. Failure probabilities, repair states, outages and
physical degradation are not independently modelled.

## Component budgets and lifetimes

| Package | Component | Initial allocation, EUR | Life min/mode/max, years | Replacement fraction | Annual maintenance allocation, EUR |
|---|---|---:|---|---:|---:|
| Envelope | Insulation | 200,000 | 30 / 40 / 50 | 0.70 | 1,200 |
| Envelope | Windows | 140,000 | 20 / 30 / 40 | 0.85 | 1,600 |
| Envelope | Facade finish | 60,000 | 15 / 22 / 30 | 1.00 | 700 |
| Envelope + heat pump | Insulation | 200,000 | 30 / 40 / 50 | 0.70 | 1,000 |
| Envelope + heat pump | Windows | 140,000 | 20 / 30 / 40 | 0.85 | 1,500 |
| Envelope + heat pump | Facade finish | 60,000 | 15 / 22 / 30 | 1.00 | 500 |
| Envelope + heat pump | Heat pump | 400,000 | 12 / 18 / 25 | 0.80 | 4,500 |
| Deep + PV | Insulation | 500,000 | 30 / 40 / 50 | 0.70 | 1,500 |
| Deep + PV | Windows | 300,000 | 20 / 30 / 40 | 0.85 | 2,200 |
| Deep + PV | Facade finish | 200,000 | 15 / 22 / 30 | 1.00 | 800 |
| Deep + PV | Heat pump | 450,000 | 12 / 18 / 25 | 0.80 | 4,500 |
| Deep + PV | PV modules | 280,000 | 20 / 25 / 35 | 0.70 | 2,500 |
| Deep + PV | Inverter | 70,000 | 10 / 12 / 15 | 0.90 | 1,000 |

All default lives are triangular. These allocations are not equipment quotations;
they reconcile to illustrative incremental package CAPEX of EUR 400k / 800k / 1.8m
and maintenance of EUR 3.5k / 7.5k / 12.5k per year. The program checks both totals.
Maintenance is already charged by the scenario model and is not added again by
the component model. Initial allocations likewise are not added to CAPEX again.

Renewal growth is 2% nominal annually. Replacements use the same capital-cost
factor as the initial investment, giving perfect within-future cost-factor
dependence. Fresh lifetimes are sampled after each renewal. Equal uncertainty
keys couple component types across alternatives, but successive renewals and
distinct keys are independent. Technology-specific failure dependence remains
outside scope.

These are assumed incremental renewal obligations. In a real case, common
reference replacements and avoided maintenance must be modelled or subtracted;
using gross retrofit replacements as incremental costs can overstate costs.
Near-horizon renewals receive no remaining-life credit, potentially penalizing
such options. The separate property premium does not resolve component-level
residual value automatically. Both limits are disclosed rather than calibrated away.

## Economic uncertainty

| Parameter | Distribution |
|---|---|
| Discount rate | Triangular 0.02 / 0.035 / 0.06 |
| Effective energy price | Lognormal median 0.28 EUR/kWh, log sigma 0.18 |
| Energy-price growth | Triangular -0.005 / 0.02 / 0.06 |
| Rent growth | Triangular 0 / 0.015 / 0.035 |
| Initial grant share | Normal mean 0.20, SD 0.08, clipped to [0,0.40] |
| Capital-cost factor | Lognormal median 1.05, log sigma 0.12 |
| Savings performance factor | Normal mean 0.95, SD 0.10, clipped to [0.65,1.15] |
| Terminal-value factor | Normal mean 1, SD 0.18, clipped to [0.55,1.35] |

Clipping creates probability mass at bounds; it is not a renormalized truncated
normal. Lognormal parameters are medians. The capital-cost factor allows both
underruns and overruns. Economic marginals are independent; the same future is
applied across all packages. Growth rates do not fluctuate year by year.

Annual kWh savings remain proxies. Electricity/fuel substitution, COP, PV yield,
export prices, storage and weather dependence are not resolved. The lifetime
extension does not add any of these physical mechanisms.

## Preference and numerical tolerances

Fixed utility bounds and weights are in `model_config.json`. Bounds are budget-scale
illustrations declared before inspecting V2.1 outputs; there is no claim that a
stakeholder chose them. A changed criterion or value boundary should be reported
as a preference change. Saturating utilities can create ties; raw metrics remain
available and take precedence in scientific interpretation.

Convergence tolerances (EUR 10k mean; 1 percentage point positive frequency;
EUR 20k P10; EUR 30k lower tail/P95 regret) are declared numerical targets.
They must not be adjusted after the run to force all cases to pass. The five
independent seed ranges describe finite sampling variation, not input-model validity.

## Stress inputs and thresholds

| Proxy case | Retained savings multiplier | Equipment factor | Routine maintenance | Terminal premium |
|---|---|---:|---:|---:|
| Baseline | 1.00 | 1.00 | 1.00 | 1.00 |
| Moderate | 0.95 | 0.95 | 1.10 | 0.98 |
| Severe | 0.85 | 0.85 | 1.25 | 0.90 |
| Energy disruption | Uniform [0.80,1.10] | 0.90 | 1.15 | 0.95 |

These are hypothetical input perturbations, not historical/warming predictions.
The savings and equipment factors multiply the sampled savings-performance factor.
The joint product is a normalized energy-savings proxy, not equipment reliability
or thermal comfort. Renewal timing and costs are held paired across these cases.

Financial screen: median >= 0; positive frequency >= 0.70; P95 regret <= EUR 500k.
Performance proxy screen: at least 90% of draws retain 75% of the assumed annual
savings target. Count-based robustness: both screens pass in at least 3 of 4 cases.
These thresholds are illustrative and were declared before inspecting results.
Case counts are not probabilities. Zero-savings references have no applicable
performance target and do not automatically pass.

## V3 M1.4 horizon architecture

M1.4 separates runtime reference-study-period selection from the historical
30-year default without changing any economic equation or service-life model.
The named profiles are methodological run modes, not claims of formal standards
compliance:

- `legacy_30` = 30 years, exact v2.1 continuity horizon;
- `levels_50` = 50 years, primary Level(s)-aligned research horizon;
- `rics_60` = 60 years, optional RICS-WLCA-aligned comparison horizon.

The default configuration remains 30 years. A profile override changes only the
runtime `analysis_years` value in a copy of the configuration. Every horizon is
re-simulated from the underlying cash-flow and lifecycle equations; results are
never linearly scaled from another horizon. Replacement events occur only when
`event_time_years < analysis_years`; an event exactly at the RSP boundary is
excluded, preserving the v2.1 convention.

Longer-horizon outputs must not be interpreted as forecasts of demolition or
building closure at year 50 or 60. The RSP is an accounting boundary. M1.4 also
does not yet introduce retained-component remaining-life assumptions, a physical
reference inventory, environmental factors or calendar-year mapping.

## V3 M1.5 retained-component life semantics

M1.5 distinguishes an existing retained component's **remaining service life at `t=0`** from the **full service life** of a newly installed/replacement generation.

- `NEW_AT_T0`: first and later renewal intervals use full service life.
- `RETAINED_EXISTING`: the first renewal interval uses an explicit remaining-life model; later generations use full service life.
- Remaining life is never inferred as `full life - age`. `age_at_t0_years`, when supplied, is metadata only.
- A retained component without an explicit remaining-life model is rejected rather than silently falling back to full service life.
- Remaining-life and full-life uncertainty keys are separate. The supplied legacy-compatible inventory has no retained rows and therefore retains its exact pre-M1.5 lifetime streams.

Only `fixed` and `triangular` life models are implemented at this checkpoint. No conditional survival/reliability model, inspection-conditioned remaining life, degradation state, residual value or physical reference inventory is introduced. A real retained-component analysis must replace illustrative/test inputs with documented condition/lifetime evidence.



## M1.6 physical reference and RSP-boundary assumptions

The RSP boundary is an accounting observation point, not a physical replacement or end-of-life event. A component due for replacement exactly at the boundary remains the in-service generation at the boundary with zero modeled remaining life because the event rule is strictly `event_time < RSP`.

The v2.1 package does not document the existing building's component-level physical inventory, quantities, units, installation ages or remaining-life evidence. M1.6 therefore does not infer a physical reference from intervention rows. The production `physical_reference_inventory.csv` is intentionally empty until source-backed data are supplied. This prevents renovation-option component families from being silently treated as baseline components.

Reference lifecycle rows, when supplied, remain physically simulated but cost-neutral in compatibility mode; they do not redefine the verified incremental reference NPV.

## M1.7 physical quantity and BoQ assumptions

- Economic cost fields are never converted into material/product quantities.
- The canonical lifecycle event is a component-level physical event; because one component may contain multiple product/material lines, the authoritative one-to-many quantity mapping is kept in separate event/BoQ bridge tables.
- `event_quantity` / `event_unit` remain nullable in the canonical ledger and must not be interpreted as zero.
- BoQ rows must have a positive documented quantity, explicit unit, stable parent identity, and provenance. `DERIVED_FROM_DOCUMENTED_GEOMETRY` additionally requires a stated derivation method.
- M1.7 performs lexical unit normalization only (for example `m²` to `m2`); it performs no physical unit conversion.
- `ASSESSMENT_INVENTORY` and `INFORMATION_ONLY` rows are distinct so future carbon calculation cannot silently count both a component-level information quantity and its material sublines.
- Reference presence is not inferred from renovation-option lineages. A documented absence is distinct from unknown presence and from a present component with missing BoQ data.
- The reference coverage skeleton is limited to known intervention lineages and is not a whole-building completeness metric.
## M1.8 environmental-factor assumptions and non-assumptions

- The production environmental-factor registry is empty because no source-backed factor dataset is bundled in the v2.1 project snapshot. Missing factors are not interpreted as zero impacts.
- Environmental factors are never inferred from component cost, component labels, material names, or nearest-name matches. Every executable BoQ line requires an explicit factor assignment.
- `DOCUMENTED_PROXY` factor assignments are permitted only with an explicit mapping reference; they remain proxies and must not be presented as exact product EPD matches.
- GWP indicators are stored separately. `GWP_TOTAL` is not generated by adding `GWP_FOSSIL`, `GWP_BIOGENIC`, and `GWP_LULUC`.
- M1.8 performs no impact calculation. The compatibility gate may resolve an activity quantity in the factor declared unit, but it never multiplies that quantity by an environmental factor.
- Allowed physical reconciliation is intentionally narrow: exact-unit use, explicit kg↔tonne conversion, or use of a documented total `mass_kg` already present on the BoQ line. No density, thickness, geometry, or cost conversion is inferred.
- Combined source modules such as `A1-A3` cannot overlap with source-disaggregated `A1`, `A2`, or `A3` records for the same factor-set/indicator. This is a double-counting guard, not a standards-compliance claim.
- Restricted or unknown environmental datasets are not assumed redistributable. Test-only synthetic factors are structurally valid fixtures only and are not empirical evidence.



## M2.1 product-stage carbon assumptions

- M2.1 calculates `GWP_TOTAL` only for initial A1-A3 product consequences and product-stage consequences of canonical B4 replacement events. A4, A5, B1-B3, B5-B8, C1-C4 and D1-D2 are not calculated.
- Historical A1-A3 of `RETAINED_EXISTING` components is excluded from the post-t=0 comparative assessment boundary.
- Each B4 replacement uses the same physical lifecycle event already generated by the canonical event engine; carbon logic never redraws service life.
- Product-stage environmental factors are applied as static reference factors across future replacement years in M2.1. No future manufacturing-decarbonisation trajectory is inferred.
- Environmental-factor uncertainty metadata are preserved, but factor uncertainty is not sampled at this checkpoint.
- GWP is not financially discounted.
- Missing BoQ, factor, assignment, or unit-compatibility data remain missing and cannot become zero impact.
- The M2.1 module summary is not Whole-Life Carbon and must not be interpreted as an A-C total.

## M2.3 replacement-transport assumptions

- Replacement transport is a consequence of the canonical physical `B4_REPLACEMENT` event and is reported in **B4**, not reclassified to A4.
- Each executable replacement transport mapping requires documented mass, route distance, one active replacement transport assignment, and one explicit GWP_TOTAL transport-process factor per tonne-km.
- Initial A4 and replacement transport use separate assignment tables; no route is inherited implicitly between them.
- Central/static transport factors are used across replacement years; factor and transport uncertainty remain outside this checkpoint.
- A sourced zero-distance route is a valid zero transport activity; missing distance is not treated as zero.
- Production replacement-transport assignments are intentionally empty until source-backed project data are provided.


## M2.4 A5.2/A5.3 construction assumptions

- M2.4 assesses initial t0 A5.2 construction/installation activities and A5.3 waste arising from the current installation/construction process only.
- A5.1 pre-construction removal of existing works is explicitly deferred until a dedicated removal inventory exists; removed-existing material must not be relabeled as A5.3.
- A5.4 worker transport and B4 installation/waste consequences remain outside this checkpoint.
- A5.2 requires an explicit activity quantity and a GWP_TOTAL factor scoped exactly to A5.2. No equipment-hours, fuel, electricity or handling activity is inferred from cost or product quantity.
- A5.3 may use either a documented BoQ waste rate or an explicit waste quantity. A waste rate is applied only to documented physical BoQ quantity or documented total mass; missing mass/quantity compatibility is blocked.
- Waste-rate zero is a documented zero flow; missing waste data are not treated as zero.
- Environmental factor uncertainty, construction-process uncertainty and future decarbonisation are not sampled. Central source-factor values are used and recorded as static-reference factors.
- Production construction-process inputs remain empty because no source-backed project activity/waste data are present in the inherited package.

## M2.5 A5.1 pre-construction removal assumptions

- Removed-at-t0 existing works use a dedicated inventory that is structurally separate from current-construction BoQ/A5.3.
- A5.1 includes removal/deconstruction activity, outbound transport of the removed pre-existing material, and waste processing/disposal attributable to that removed material under the adopted research split.
- Removal activity requires an explicit activity quantity and a `GWP_TOTAL` factor scoped to A5.1.
- Outbound transport requires explicit removed mass, route distance and transport-factor basis. The source transport factor retains A4 process provenance while the consequence reports to A5.1.
- Waste processing/disposal requires an explicit route and a C3 or C4 source-process factor appropriate to the route type; the consequence reports to A5.1 and is not additionally generated in C for the same t0 removed quantity.
- A5.1 removal inventory line IDs and removed-component instance IDs must be disjoint from current-construction BoQ/component identities, preventing the same physical quantity from being owned by A5.3.
- A declared D1 recovery scenario is metadata only in M2.5. No D1 credit/load is calculated.
- No removal rate, demolition energy, distance, waste split, density, recovery rate or cost-to-quantity conversion is inferred.
- Production A5.1 inputs remain empty because source-backed removal evidence is absent; missing removal data are not zero.


## M2.6 B4 replacement-event process assumptions

- A canonical `B4_REPLACEMENT` event owns the replacement product, inbound replacement transport, installation, removal of the superseded item, outbound removed-material transport, and explicitly mapped replacement waste processing/disposal consequences.
- Source-process factor scopes remain recorded separately from the reporting module. An A5.2/A5.1-or-C1/A4/C3/C4 process factor may support a B4 consequence, but the consequence is reported in B4 because it occurs as part of the replacement event.
- No M2.6 consequence can be generated without an explicit BoQ-scoped assignment and an existing canonical B4 event.
- Activity quantities come only from explicit per-event activity, documented BoQ quantity, documented BoQ mass, or documented mass × distance. No cost, density, geometry, route or activity inference is allowed.
- Environmental factor uncertainty remains metadata only in M2.6; the central factor value is used deterministically.
- Production `b4_event_process_assignments.csv` is unpopulated. Missing replacement process data are not interpreted as zero.
- M2.6 does not implement B6 operational carbon, B2/B3/B5, terminal C1-C4, D1/D2, residual carbon/value or whole-life aggregation.


## M3.1 B6 operational-energy assumptions

- B6 carbon consumes only explicit imported-energy physical flows; `annual_energy_savings_kwh` remains an economic proxy and is never promoted to B6.
- `GENERATED`, `SELF_CONSUMED`, and `EXPORTED` flows are physical bookkeeping rows. Export is not a negative import and receives no credit in M3.1.
- B6 factor schedules are explicit by analysis year and calendar year. Missing in-RSP years are errors for execution; no interpolation, extrapolation, or automatic decarbonisation trajectory is applied.
- Executable factors require `GWP_TOTAL`, exact `B6` source scope, and `kwh` declared unit. GWP_TOTAL is never reconstructed from sub-indicators.
- Explicit documented zero import is distinct from missing data and emits no zero-impact consequence row.
- Factor uncertainty metadata is retained but central values are used deterministically in M3.1. Carbon is not discounted.
- Exported energy is reserved for a later separate Module-D accounting decision; no D2 consequence is generated here.
- Production B6 inputs are unpopulated because no source-backed operational carrier-flow/future-factor dataset is present in the inherited demonstrator.
### M3.1.1 release-policy hardening

The active production configuration explicitly declares `assessment_convention=EN15978_2026_INFORMED`, `generated_energy_reporting_approach=PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED`, and `factor_extrapolation_policy=ERROR_IF_MISSING`. These declarations document the already-implemented M3.1 behavior; they do not alter the B6 equation. Operational schedule `calendar_year` is the factor application year, while environmental-factor `reference_year` is dataset/source reference vintage.


## v3.2.0 terminal lifecycle and coverage assumptions

- The reference-study-period boundary is an accounting state, not a physical demolition event. C1-C4 are generated only from explicit terminal assignments.
- Terminal C1-C4 do not regenerate A5.1 pre-construction removal or B4 replacement-event removal/waste consequences.
- C2 uses documented terminal mass and explicit distance with a C2 GWP_TOTAL factor per tonne-km. C3/C4/D1 use documented mass fractions and exact module factors; no cost/geometry/density inference is permitted.
- D1 and D2 are beyond-boundary results and remain separate from A-C. A negative D value is never silently subtracted from A-C.
- D2 can be evaluated only for an explicit `EXPORTED` physical energy flow with a complete explicit D2 factor schedule. The B6 adapter continues to exclude export from B6.
- B1/B2/B3/B5/B7/B8 are explicitly deferred/not assessed in this bounded release. Their absence is not a zero-impact assertion.
- Numeric partial A-C totals may be reported with coverage labels, but incomplete scope cannot be labeled Whole-Life Carbon.
