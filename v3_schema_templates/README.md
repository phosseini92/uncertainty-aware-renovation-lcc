# V3 schema templates

These files are **design-only headers/skeletons**. They are not production inputs and contain no claimed empirical environmental data. They exist to freeze field names, module boundaries, and validation intent before coding.

M1.5 adds `components_m1_5.csv` as a schema-only template for explicit initial component state and separate remaining/full service-life models. The production legacy-compatible `inputs/components.csv` is intentionally unchanged so the default 30-year run remains byte-identical to M1.4. Absence of `initial_component_state` in that legacy-compatible file is interpreted as `NEW_AT_T0`; a retained component must explicitly declare `RETAINED_EXISTING` and a documented remaining-life model. `age_at_t0_years` is provenance metadata only and is not converted into remaining life.

M1.7 adds production `inputs/component_boq.csv` and `inputs/reference_component_presence.csv` as executable evidence gates. The BoQ input is intentionally header-only until source-backed quantities are available. Reference presence is explicitly declared for all known intervention lineages; `UNKNOWN` is a valid evidence state and must not be silently converted to zero or absence. Event and boundary quantity mappings are one-to-many bridge tables rather than scalar quantities embedded in lifecycle events.

## M2.2 transport inputs

`transport_scenarios.csv`, `transport_factors.csv` and
`boq_transport_assignments.csv` define the separate initial-A4 pathway.
See `docs/M2.2_INPUT_GUIDE.md` for units, provenance, flow identity and scope rules.
All three production inputs are header-only. Populated synthetic data are kept
exclusively in `tests/fixtures/m22_transport_synthetic/`.


## M3.1 operational-energy inputs

The executable B6 schemas are now frozen in production `inputs/operational_energy_flows.csv` and `inputs/operational_energy_factor_schedule.csv`; matching header-only copies are retained here. The earlier conceptual `energy_carbon_factors.csv` skeleton is superseded for executable M3.1 runs by the factor-schedule schema plus the central `environmental_factors.csv` registry.
