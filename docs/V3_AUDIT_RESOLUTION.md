# V3 Design Audit Resolution — 27 September 2026

This document records how the strict audit findings were resolved before production coding.

| Audit finding | Resolution | Status |
|---|---|---|
| EN 15978:2026 is now current | Primary architecture changed to EN 15978:2026-informed; no-compliance claim retained | RESOLVED |
| A5.1 vs A5.3 ambiguity | A5.1 now includes pre-existing removal plus associated removed-material transport/waste handling in adopted research split; A5.3 reserved for current-construction waste | RESOLVED |
| B2 had no event schema | Added `maintenance_scenarios.csv` contract | RESOLVED IN DESIGN |
| B3 had no event schema | Added `repair_scenarios.csv` contract | RESOLVED IN DESIGN |
| B5 had no event schema | Added `planned_refurbishment_events.csv` contract | RESOLVED IN DESIGN |
| PV/exported energy incomplete | Added physical `operational_energy_flows.csv` and reporting-approach configuration | RESOLVED IN DESIGN |
| Coverage could not distinguish N/A from missing | Added `module_applicability.csv` and convention-aware coverage matrix | RESOLVED IN DESIGN |
| A0 absent | A0 recognized with explicit coverage status | RESOLVED |
| RQ2 lacked deterministic comparator | Added deterministic benchmark requirement/output | RESOLVED |
| RQ3 overclaimed business modelling | Reframed as stakeholder value-allocation scenarios | RESOLVED |
| RQ4 risked mega-Pareto | Reframed as separate decision views + cross-view robustness | RESOLVED |
| Stakeholder cash-flow signs ambiguous | Base ledger = non-negative magnitude + direction; allocations = non-negative shares | RESOLVED |
| Factor schema hard-coded to one GWP scalar | Replaced with long-form multi-indicator-ready factor contract | RESOLVED IN DESIGN |
| Biogenic GWP could be hidden | Added GWP_TOTAL/FOSSIL/BIOGENIC/LULUC indicator IDs | RESOLVED IN DESIGN |
| Continuous event time/calendar-year mapping missing | Added explicit calendar-year mapping and default error-on-missing factor policy | RESOLVED |
| Future embodied factors unspecified | Added configurable future-product-factor policy | RESOLVED |
| Retained/full-life correlation conflated | Added separate remaining-life/full-life uncertainty keys | RESOLVED |
| Cross-scenario component pairing weak | Added `comparison_lineage_id` | RESOLVED |
| Uncertainty semantics conflated | Added ALEATORY/EPISTEMIC/SCENARIO_NONPROBABILISTIC/NONE | RESOLVED |
| Economic price metadata incomplete | Added currency/base year/nominal-real/tax/escalation metadata | RESOLVED |
| Data licensing absent | Added source/license/redistribution controls | RESOLVED |

## Remaining decisions before coding

The strict audit blockers are represented in the design, but three project choices remain to be made before Milestone 1 is merged:

1. choose the default generated-energy reporting approach for the illustrative PV case;
2. choose the public/redistributable environmental-factor dataset strategy for the demonstrator; and
3. decide whether B2/B3/B5 will be populated in the first v3 public demo or supported as explicit-but-unassessed interfaces.

These are configuration/scope decisions, not structural holes in the architecture.
