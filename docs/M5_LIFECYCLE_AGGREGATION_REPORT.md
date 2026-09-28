# M5 — Module applicability, coverage and lifecycle aggregation gate

## Purpose

M5 prevents a numerically partial assessment from being presented as complete Whole-Life Carbon. It adds an explicit module-applicability declaration and machine-readable coverage matrix for every scenario.

## Declared scope

The current research release declares 19 module positions for each of four scenarios (76 declarations total). The implemented architecture supports A1–A3, A4, A5.1–A5.3, B4, B6, C1–C4 and separate D1/D2. B1, B2, B3, B5, B7 and B8 are explicitly `DEFERRED_NOT_ASSESSED` in the bounded release; their absence is not converted to zero or `NOT_APPLICABLE`.

For the reference/no-additional-intervention scenario, current-intervention A-stage modules are explicitly declared not applicable at t0. All other non-applicable classifications require an explicit declaration and rationale.

## Coverage behavior

Each scenario/module receives a status derived from both applicability and actual consequence evidence, including:

- `ASSESSED`
- `NOT_APPLICABLE`
- `NOT_ASSESSED_MISSING_DATA`
- `NOT_ASSESSED_SCOPE`
- `NOT_ASSESSED_OPTIONAL`
- conflict/missing-declaration states

A numeric A–C sum may be produced as an **assessed partial lifecycle-carbon result**, but it is labelled:

`PARTIAL_ASSESSED_A_C_CARBON_WITH_EXPLICIT_COVERAGE_NOT_WHOLE_LIFE`

unless all required/relevant A–C coverage rules are satisfied. Module D is aggregated only in `separate_module_d_summary.csv` and is never netted into A–C.

## Default production result

Because the inherited demonstrator intentionally lacks source-backed BoQ/factor/operational/end-of-life inventories, the coverage gate correctly leaves `whole_life_carbon_generated = false`. This is a research-integrity feature rather than a missing implementation: the architecture is present, while unavailable evidence is surfaced as unavailable.
