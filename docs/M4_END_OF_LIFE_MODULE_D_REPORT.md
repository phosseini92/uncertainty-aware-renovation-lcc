# M4 — Unified terminal C1–C4 and separate Module D

## Scope

M4 closes the terminal lifecycle-carbon architecture without fabricating production inventories. It adds an explicit terminal accounting layer for:

- `C1` deconstruction/demolition activity;
- `C2` transport from the project site;
- `C3` waste processing;
- `C4` disposal;
- `D1` material reuse/recycling/recovery benefits or loads; and
- `D2` exported energy/utilities under a separate, explicit factor schedule.

The RSP boundary remains an **accounting state, not a lifecycle event**. No C/D row is generated merely because the 30/50/60-year boundary is reached. A consequence exists only when an explicit source-backed assignment is supplied.

## Double-counting controls

- B4 replacement removal/waste consequences remain reported in B4 and are not regenerated in terminal C1–C4.
- A5.1 pre-construction removal remains a t0 renovation consequence and is not regenerated at the RSP boundary.
- Module D is never netted into A–C.
- No service-life resampling occurs in M4.
- No quantity is inferred from cost, geometry, density, product labels or an undocumented default waste rate.
- Missing terminal inventory/factor evidence remains not assessed, never zero.

## Terminal inventory schema

`inputs/end_of_life_assignments.csv` links an explicit BoQ line to C1/C2/C3/C4/D1 factor sets and documented activity, distance or mass fractions. Mass-based consequences use documented BoQ mass (or an explicit kg/t BoQ quantity). C2 requires a `GWP_TOTAL`, `C2`, `tkm` factor. C3/C4/D1 require exact module factors in kg or tonnes.

D2 is independent of B6. `inputs/d2_export_assignments.csv` may map only an `EXPORTED` operational-energy flow to an explicit `d2_export_factor_schedule.csv`. Missing schedule years block the entire affected flow rather than creating a partial credit. The B6 adapter therefore continues to defer export from B6; M4 evaluates D2 only in this separate beyond-boundary layer when explicit D2 inputs are supplied.

## Synthetic closed-form verification

For an explicitly declared 1,000 kg terminal inventory:

- C1: `20 kWh × 0.5 = 10 kgCO2e`
- C2: `1 t × 100 km × 0.1 = 10 kgCO2e`
- C3: `1,000 kg × 70% × 0.2 = 140 kgCO2e`
- C4: `1,000 kg × 30% × 0.05 = 15 kgCO2e`

Thus assessed C1–C4 for the fixture equals **175 kgCO2e**.

A separate D1 fixture uses `1,000 kg × 50% × -0.1 = -50 kgCO2e`; the negative result remains in Module D and is not subtracted from the 175 kgCO2e A–C result.

A D2 fixture with 100 kWh exported in two years and explicit factors `-0.05` and `-0.04 kgCO2e/kWh` yields `-9 kgCO2e` in D2, again reported separately.

## Production behavior

The three production M4 input tables are intentionally header-only because no source-backed terminal/disposition or D2 factor data exists in the inherited demonstrator. Default status is therefore:

`NO_END_OF_LIFE_OR_D_ASSIGNMENTS`

This means **not assessed**, not zero impact.
