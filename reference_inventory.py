"""Physical reference-inventory interface for the v3 migration.

The v2.1 repository does not contain a source-backed inventory of the existing
building's physical components, quantities, ages or remaining lives.  M1.6
therefore introduces the executable schema and validation gate without
inventing those inputs.  An empty main inventory is valid and is explicitly
reported as source-data absent; synthetic fixtures are permitted only in tests.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from identity import validate_stable_id, validate_unique_ids
from component_lifecycle import _validate_m15_life_models

REFERENCE_INVENTORY_COLUMNS = (
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "component_type_id",
    "component",
    "initial_component_state",
    "physical_quantity",
    "physical_unit",
    "remaining_life_distribution",
    "remaining_life_min_years",
    "remaining_life_mode_years",
    "remaining_life_max_years",
    "remaining_life_fixed_years",
    "remaining_life_uncertainty_key",
    "full_life_distribution",
    "full_life_min_years",
    "full_life_mode_years",
    "full_life_max_years",
    "full_life_fixed_years",
    "full_life_uncertainty_key",
    "age_at_t0_years",
    "source_status",
    "source_reference",
    "notes",
)

ALLOWED_SOURCE_STATUS = {
    "DOCUMENTED_PROJECT_DATA",
    "PUBLIC_DOCUMENTED_DATA",
    "TEST_ONLY_SYNTHETIC",
}


def empty_physical_reference_inventory() -> pd.DataFrame:
    return pd.DataFrame(columns=REFERENCE_INVENTORY_COLUMNS)


def load_physical_reference_inventory(path: Path, reference_scenario_id: str) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    table = pd.read_csv(path)
    missing = set(REFERENCE_INVENTORY_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(f"Missing physical reference-inventory columns: {sorted(missing)}")
    extra = set(table.columns) - set(REFERENCE_INVENTORY_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected physical reference-inventory columns: {sorted(extra)}")
    table = table.loc[:, REFERENCE_INVENTORY_COLUMNS].copy()
    if table.empty:
        return table

    reference_scenario_id = validate_stable_id(reference_scenario_id, "reference_scenario_id")
    for field in ("scenario_id", "component_instance_id", "comparison_lineage_id", "component_type_id"):
        table[field] = [validate_stable_id(v, field) for v in table[field]]
    validate_unique_ids(table.component_instance_id, "reference component_instance_id")
    if not table.scenario_id.eq(reference_scenario_id).all():
        raise ValueError("Every physical reference-inventory row must use the declared reference scenario_id.")
    if table.component.isna().any() or table.component.astype(str).str.strip().eq("").any():
        raise ValueError("Reference component labels must be nonempty.")

    table["physical_quantity"] = pd.to_numeric(table.physical_quantity, errors="raise")
    if not np.isfinite(table.physical_quantity).all() or (table.physical_quantity <= 0).any():
        raise ValueError("Reference physical_quantity must be finite and positive.")
    if table.physical_unit.isna().any() or table.physical_unit.astype(str).str.strip().eq("").any():
        raise ValueError("Reference physical_unit is required.")
    if table.source_status.isna().any() or not table.source_status.isin(ALLOWED_SOURCE_STATUS).all():
        raise ValueError(f"source_status must be one of {sorted(ALLOWED_SOURCE_STATUS)}")
    if table.source_reference.isna().any() or table.source_reference.astype(str).str.strip().eq("").any():
        raise ValueError("source_reference is required for every executable reference component.")

    # The lifecycle validator enforces explicit remaining life for retained rows,
    # explicit full-life semantics, age provenance rules and independent keys.
    life_table = table.copy()
    # M1.5 accepts legacy lifetime fields as fallback.  The physical reference
    # must not rely on those fallbacks, so provide temporary values only after
    # confirming explicit full-life fields exist; they are never source data.
    if life_table.full_life_distribution.isna().any() or life_table.full_life_distribution.astype(str).str.strip().eq("").any():
        raise ValueError("Physical reference components require an explicit full-life model.")
    life_table["lifetime_distribution"] = life_table.full_life_distribution
    life_table["minimum_lifetime_years"] = life_table.full_life_min_years
    life_table["most_likely_lifetime_years"] = life_table.full_life_mode_years
    life_table["maximum_lifetime_years"] = life_table.full_life_max_years
    life_table["uncertainty_key"] = life_table.full_life_uncertainty_key
    _validate_m15_life_models(life_table)
    return table.reset_index(drop=True)


def reference_inventory_to_lifecycle_components(
    inventory: pd.DataFrame,
    scenario_display_name: str,
) -> pd.DataFrame:
    """Adapt validated physical reference rows to the shared lifecycle engine.

    Economic fields are set to zero deliberately: M1.6 schedules physical
    baseline renewals without redefining the verified zero-cash-flow reference
    NPV.  Later absolute/incremental baseline-cost work is a separate milestone.
    """
    if inventory.empty:
        columns = [
            "scenario_id", "component_instance_id", "comparison_lineage_id", "component_type_id",
            "scenario", "component", "uncertainty_key", "initial_cost_eur",
            "lifetime_distribution", "minimum_lifetime_years", "most_likely_lifetime_years",
            "maximum_lifetime_years", "replacement_cost_factor", "maintenance_cost_eur",
            "initial_component_state", "remaining_life_distribution", "remaining_life_min_years",
            "remaining_life_mode_years", "remaining_life_max_years", "remaining_life_fixed_years",
            "remaining_life_uncertainty_key", "full_life_distribution", "full_life_min_years",
            "full_life_mode_years", "full_life_max_years", "full_life_fixed_years",
            "full_life_uncertainty_key", "age_at_t0_years",
        ]
        return pd.DataFrame(columns=columns)

    out = inventory.copy()
    out["scenario"] = str(scenario_display_name)
    out["uncertainty_key"] = out.full_life_uncertainty_key
    out["initial_cost_eur"] = 0.0
    out["replacement_cost_factor"] = 0.0
    out["maintenance_cost_eur"] = 0.0
    out["lifetime_distribution"] = out.full_life_distribution
    out["minimum_lifetime_years"] = out.full_life_min_years
    out["most_likely_lifetime_years"] = out.full_life_mode_years
    out["maximum_lifetime_years"] = out.full_life_max_years
    keep = [
        "scenario_id", "component_instance_id", "comparison_lineage_id", "component_type_id",
        "scenario", "component", "uncertainty_key", "initial_cost_eur",
        "lifetime_distribution", "minimum_lifetime_years", "most_likely_lifetime_years",
        "maximum_lifetime_years", "replacement_cost_factor", "maintenance_cost_eur",
        "initial_component_state", "remaining_life_distribution", "remaining_life_min_years",
        "remaining_life_mode_years", "remaining_life_max_years", "remaining_life_fixed_years",
        "remaining_life_uncertainty_key", "full_life_distribution", "full_life_min_years",
        "full_life_mode_years", "full_life_max_years", "full_life_fixed_years",
        "full_life_uncertainty_key", "age_at_t0_years",
    ]
    return out.loc[:, keep].reset_index(drop=True)



def validate_reference_lineage_compatibility(reference_inventory: pd.DataFrame, intervention_components: pd.DataFrame) -> None:
    """Prevent a shared comparison lineage from silently changing physical identity.

    A reference row may introduce a new lineage, but when it reuses an
    intervention lineage it must use the same component type and effective
    full-life uncertainty stream. Otherwise the row must be assigned a distinct
    lineage rather than implying paired identity.
    """
    if reference_inventory.empty or intervention_components.empty:
        return
    ref = reference_inventory.copy()
    ints = intervention_components.copy()
    if "full_life_uncertainty_key" in ints.columns:
        explicit = ints.full_life_uncertainty_key.notna() & ints.full_life_uncertainty_key.astype(str).str.strip().ne("")
        ints["_effective_full_key"] = ints.uncertainty_key.astype(str)
        ints.loc[explicit, "_effective_full_key"] = ints.loc[explicit, "full_life_uncertainty_key"].astype(str)
    else:
        ints["_effective_full_key"] = ints.uncertainty_key.astype(str)
    for row in ref.itertuples(index=False):
        matched = ints.loc[ints.comparison_lineage_id.eq(row.comparison_lineage_id)]
        if matched.empty:
            continue
        types = set(matched.component_type_id.astype(str))
        if types != {str(row.component_type_id)}:
            raise ValueError(
                f"Reference comparison_lineage_id {row.comparison_lineage_id} conflicts with intervention component_type_id."
            )
        keys = set(matched._effective_full_key.astype(str))
        if keys != {str(row.full_life_uncertainty_key)}:
            raise ValueError(
                f"Reference comparison_lineage_id {row.comparison_lineage_id} conflicts with intervention full-life uncertainty stream."
            )

def inventory_status(inventory: pd.DataFrame) -> dict:
    return {
        "status": "EXECUTABLE" if not inventory.empty else "UNPOPULATED_SOURCE_DATA_ABSENT",
        "component_rows": int(len(inventory)),
        "claim": (
            "Physical reference inventory is executable with documented rows."
            if not inventory.empty
            else "The v2.1 source package does not provide a documented physical existing-building inventory; no component presence, quantity, age or remaining life is invented."
        ),
    }
