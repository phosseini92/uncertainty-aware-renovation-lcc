"""Physical quantity / BoQ mapping and reference-coverage skeleton for v3 M1.7.

M1.7 introduces a one-to-many bridge between lifecycle component instances and
physical inventory lines without changing lifecycle timing or any verified v2.1
economic equation.  The bridge is deliberately separate from the canonical
lifecycle-event ledger: one physical component event may map to multiple
material/product quantity lines, so a single scalar event quantity would be
ambiguous and could encourage double counting.

No carbon factors are read or calculated here.  No quantity is inferred from
cost.  The production BoQ file may remain empty until documented quantities are
available; coverage outputs then report the gap explicitly.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from identity import validate_stable_id, validate_unique_ids

COMPONENT_BOQ_COLUMNS = (
    "boq_line_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "component_type_id",
    "item_label",
    "material_or_product_id",
    "assessment_role",
    "quantity",
    "quantity_unit",
    "mass_kg",
    "source_status",
    "source_reference",
    "derivation_method",
    "notes",
)

REFERENCE_PRESENCE_COLUMNS = (
    "comparison_lineage_id",
    "component_type_id",
    "reference_presence_status",
    "evidence_status",
    "evidence_source",
    "notes",
)

PHYSICAL_QUANTITY_COVERAGE_COLUMNS = (
    "scenario_id",
    "scenario_role",
    "component_instance_id",
    "comparison_lineage_id",
    "component_type_id",
    "component",
    "primary_component_quantity_available",
    "primary_component_quantity",
    "primary_component_unit",
    "boq_line_count",
    "assessment_inventory_line_count",
    "information_only_line_count",
    "boq_units",
    "boq_source_statuses",
    "quantity_mapping_status",
    "reason",
)

REFERENCE_COVERAGE_COLUMNS = (
    "comparison_lineage_id",
    "component_type_id",
    "reference_presence_status",
    "presence_evidence_status",
    "reference_inventory_rows",
    "reference_primary_quantity_rows",
    "reference_boq_line_count",
    "reference_assessment_inventory_line_count",
    "reference_lifecycle_model_status",
    "reference_quantity_mapping_status",
    "comparison_coverage_status",
    "coverage_denominator_scope",
    "reason",
)

EVENT_BOQ_COLUMNS = (
    "event_boq_id",
    "event_id",
    "future_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "component_generation",
    "event_type",
    "boq_line_id",
    "material_or_product_id",
    "assessment_role",
    "quantity",
    "quantity_unit",
    "mass_kg",
    "source_status",
    "source_reference",
)

BOUNDARY_BOQ_COLUMNS = (
    "boundary_boq_state_id",
    "boundary_state_id",
    "future_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "component_type_id",
    "component_generation_at_boundary",
    "rsp_years",
    "remaining_life_at_boundary_years",
    "boq_line_id",
    "material_or_product_id",
    "assessment_role",
    "quantity",
    "quantity_unit",
    "mass_kg",
    "source_status",
    "source_reference",
)

ALLOWED_ASSESSMENT_ROLES = {"ASSESSMENT_INVENTORY", "INFORMATION_ONLY"}
ALLOWED_BOQ_SOURCE_STATUS = {
    "DOCUMENTED_PROJECT_DATA",
    "PUBLIC_DOCUMENTED_DATA",
    "DERIVED_FROM_DOCUMENTED_GEOMETRY",
    "TEST_ONLY_SYNTHETIC",
}
ALLOWED_REFERENCE_PRESENCE = {"PRESENT_DOCUMENTED", "ABSENT_DOCUMENTED", "UNKNOWN"}
ALLOWED_PRESENCE_EVIDENCE_STATUS = {
    "DOCUMENTED_PROJECT_DATA",
    "PUBLIC_DOCUMENTED_DATA",
    "DERIVED_FROM_DOCUMENTED_EVIDENCE",
    "SOURCE_NOT_AVAILABLE_IN_V2_1",
    "TEST_ONLY_SYNTHETIC",
}

# This vocabulary is intentionally small and explicit.  M1.7 performs no unit
# conversion; future factor mapping must either match these units or use a
# dedicated, tested conversion layer.
_CANONICAL_UNITS = {"kg", "t", "m", "m2", "m3", "unit", "kwp"}
_UNIT_ALIASES = {
    "m²": "m2",
    "m^2": "m2",
    "sqm": "m2",
    "m³": "m3",
    "m^3": "m3",
    "cum": "m3",
    "tonne": "t",
    "tonnes": "t",
    "piece": "unit",
    "pieces": "unit",
    "pcs": "unit",
    "each": "unit",
    "kwp": "kwp",
    "kWp": "kwp",
}


def empty_component_boq() -> pd.DataFrame:
    return pd.DataFrame(columns=COMPONENT_BOQ_COLUMNS)


def empty_event_boq_mapping() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_BOQ_COLUMNS)


def empty_boundary_boq_mapping() -> pd.DataFrame:
    return pd.DataFrame(columns=BOUNDARY_BOQ_COLUMNS)


def normalize_physical_unit(value: object) -> str:
    if pd.isna(value):
        raise ValueError("Physical quantity unit is required.")
    raw = str(value).strip()
    if not raw:
        raise ValueError("Physical quantity unit is required.")
    normalized = _UNIT_ALIASES.get(raw, _UNIT_ALIASES.get(raw.lower(), raw.lower()))
    if normalized not in _CANONICAL_UNITS:
        raise ValueError(
            f"Unsupported physical quantity unit: {raw!r}. "
            f"Supported canonical units are {sorted(_CANONICAL_UNITS)}; no implicit conversion is performed."
        )
    return normalized


def _component_parent_table(intervention_components: pd.DataFrame, reference_inventory: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in intervention_components.itertuples(index=False):
        rows.append({
            "scenario_id": str(row.scenario_id),
            "scenario_role": "OPTION",
            "component_instance_id": str(row.component_instance_id),
            "comparison_lineage_id": str(row.comparison_lineage_id),
            "component_type_id": str(row.component_type_id),
            "component": str(row.component),
            "primary_component_quantity_available": False,
            "primary_component_quantity": np.nan,
            "primary_component_unit": pd.NA,
        })
    for row in reference_inventory.itertuples(index=False):
        rows.append({
            "scenario_id": str(row.scenario_id),
            "scenario_role": "REFERENCE",
            "component_instance_id": str(row.component_instance_id),
            "comparison_lineage_id": str(row.comparison_lineage_id),
            "component_type_id": str(row.component_type_id),
            "component": str(row.component),
            "primary_component_quantity_available": True,
            "primary_component_quantity": float(row.physical_quantity),
            "primary_component_unit": normalize_physical_unit(row.physical_unit),
        })
    if not rows:
        return pd.DataFrame(columns=[
            "scenario_id", "scenario_role", "component_instance_id", "comparison_lineage_id",
            "component_type_id", "component", "primary_component_quantity_available",
            "primary_component_quantity", "primary_component_unit",
        ])
    out = pd.DataFrame(rows)
    if out.component_instance_id.duplicated().any():
        raise ValueError("A component_instance_id cannot exist in both intervention and reference parent tables.")
    return out


def load_component_boq(
    path: Path,
    intervention_components: pd.DataFrame,
    reference_inventory: pd.DataFrame,
) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    table = pd.read_csv(path)
    missing = set(COMPONENT_BOQ_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(f"Missing component BoQ columns: {sorted(missing)}")
    extra = set(table.columns) - set(COMPONENT_BOQ_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected component BoQ columns: {sorted(extra)}")
    table = table.loc[:, COMPONENT_BOQ_COLUMNS].copy()
    if table.empty:
        return table

    for field in ("boq_line_id", "scenario_id", "component_instance_id", "comparison_lineage_id", "component_type_id"):
        table[field] = [validate_stable_id(v, field) for v in table[field]]
    validate_unique_ids(table.boq_line_id, "boq_line_id")

    if table.item_label.isna().any() or table.item_label.astype(str).str.strip().eq("").any():
        raise ValueError("Every BoQ line requires a nonempty item_label.")
    table["item_label"] = table.item_label.astype(str).str.strip()

    if table.assessment_role.isna().any() or not table.assessment_role.isin(ALLOWED_ASSESSMENT_ROLES).all():
        raise ValueError(f"assessment_role must be one of {sorted(ALLOWED_ASSESSMENT_ROLES)}")

    # Stable material/product identity is required for executable assessment
    # inventory lines. Information-only lines may use a documented descriptor,
    # but keeping a stable ID for every row makes future joins unambiguous.
    table["material_or_product_id"] = [validate_stable_id(v, "material_or_product_id") for v in table.material_or_product_id]

    table["quantity"] = pd.to_numeric(table.quantity, errors="raise")
    if not np.isfinite(table.quantity).all() or (table.quantity <= 0).any():
        raise ValueError("BoQ quantity must be finite and strictly positive.")
    table["quantity_unit"] = [normalize_physical_unit(v) for v in table.quantity_unit]

    table["mass_kg"] = pd.to_numeric(table.mass_kg, errors="coerce")
    if ((table.mass_kg.notna()) & ((~np.isfinite(table.mass_kg)) | (table.mass_kg <= 0))).any():
        raise ValueError("Optional mass_kg must be finite and strictly positive when provided.")

    if table.source_status.isna().any() or not table.source_status.isin(ALLOWED_BOQ_SOURCE_STATUS).all():
        raise ValueError(f"BoQ source_status must be one of {sorted(ALLOWED_BOQ_SOURCE_STATUS)}")
    if table.source_reference.isna().any() or table.source_reference.astype(str).str.strip().eq("").any():
        raise ValueError("Every executable BoQ row requires source_reference.")
    table["source_reference"] = table.source_reference.astype(str).str.strip()
    table["derivation_method"] = table.derivation_method.fillna("").astype(str).str.strip()
    derived = table.source_status.eq("DERIVED_FROM_DOCUMENTED_GEOMETRY")
    if table.loc[derived, "derivation_method"].eq("").any():
        raise ValueError("DERIVED_FROM_DOCUMENTED_GEOMETRY BoQ rows require derivation_method.")

    parents = _component_parent_table(intervention_components, reference_inventory)
    if parents.empty:
        raise ValueError("BoQ rows were supplied but no lifecycle component parents exist.")
    parent_map = parents.set_index("component_instance_id", drop=False)
    for row in table.itertuples(index=False):
        if row.component_instance_id not in parent_map.index:
            raise ValueError(f"BoQ line {row.boq_line_id} references unknown component_instance_id {row.component_instance_id}.")
        parent = parent_map.loc[row.component_instance_id]
        checks = {
            "scenario_id": row.scenario_id,
            "comparison_lineage_id": row.comparison_lineage_id,
            "component_type_id": row.component_type_id,
        }
        for field, supplied in checks.items():
            expected = str(parent[field])
            if str(supplied) != expected:
                raise ValueError(
                    f"BoQ line {row.boq_line_id} {field}={supplied!r} conflicts with parent component value {expected!r}."
                )
    return table.reset_index(drop=True)


def load_reference_component_presence(path: Path, intervention_components: pd.DataFrame) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    table = pd.read_csv(path)
    missing = set(REFERENCE_PRESENCE_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(f"Missing reference component-presence columns: {sorted(missing)}")
    extra = set(table.columns) - set(REFERENCE_PRESENCE_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected reference component-presence columns: {sorted(extra)}")
    table = table.loc[:, REFERENCE_PRESENCE_COLUMNS].copy()

    expected = (
        intervention_components.loc[:, ["comparison_lineage_id", "component_type_id"]]
        .drop_duplicates()
        .sort_values(["comparison_lineage_id", "component_type_id"])
        .reset_index(drop=True)
    )
    if table.empty and not expected.empty:
        raise ValueError("Reference component-presence skeleton must explicitly cover every intervention lineage.")
    for field in ("comparison_lineage_id", "component_type_id"):
        table[field] = [validate_stable_id(v, field) for v in table[field]]
    if table.comparison_lineage_id.duplicated().any():
        raise ValueError("Reference component-presence skeleton must contain one row per comparison_lineage_id.")
    if table.reference_presence_status.isna().any() or not table.reference_presence_status.isin(ALLOWED_REFERENCE_PRESENCE).all():
        raise ValueError(f"reference_presence_status must be one of {sorted(ALLOWED_REFERENCE_PRESENCE)}")
    if table.evidence_status.isna().any() or not table.evidence_status.isin(ALLOWED_PRESENCE_EVIDENCE_STATUS).all():
        raise ValueError(f"evidence_status must be one of {sorted(ALLOWED_PRESENCE_EVIDENCE_STATUS)}")
    if table.evidence_source.isna().any() or table.evidence_source.astype(str).str.strip().eq("").any():
        raise ValueError("Every reference presence declaration requires evidence_source, including explicit missing-evidence declarations.")

    observed = table.loc[:, ["comparison_lineage_id", "component_type_id"]].sort_values(
        ["comparison_lineage_id", "component_type_id"]
    ).reset_index(drop=True)
    if not observed.equals(expected):
        raise ValueError("Reference component-presence skeleton must match the complete set of intervention lineages and component types.")
    return table.reset_index(drop=True)


def validate_reference_presence_consistency(presence: pd.DataFrame, reference_inventory: pd.DataFrame) -> None:
    if presence.empty:
        return
    ref_counts = reference_inventory.groupby("comparison_lineage_id").size() if not reference_inventory.empty else pd.Series(dtype=int)
    for row in presence.itertuples(index=False):
        count = int(ref_counts.get(row.comparison_lineage_id, 0))
        if row.reference_presence_status == "PRESENT_DOCUMENTED" and count == 0:
            raise ValueError(
                f"Reference lineage {row.comparison_lineage_id} is PRESENT_DOCUMENTED but has no physical reference inventory row."
            )
        if row.reference_presence_status == "ABSENT_DOCUMENTED" and count != 0:
            raise ValueError(
                f"Reference lineage {row.comparison_lineage_id} is ABSENT_DOCUMENTED but physical reference inventory rows exist."
            )
        if row.reference_presence_status == "UNKNOWN" and count != 0:
            raise ValueError(
                f"Reference lineage {row.comparison_lineage_id} is UNKNOWN but executable physical reference inventory rows exist; declare PRESENT_DOCUMENTED."
            )


def build_physical_quantity_coverage(
    intervention_components: pd.DataFrame,
    reference_inventory: pd.DataFrame,
    boq: pd.DataFrame,
) -> pd.DataFrame:
    parents = _component_parent_table(intervention_components, reference_inventory)
    rows = []
    for parent in parents.itertuples(index=False):
        lines = boq.loc[boq.component_instance_id.eq(parent.component_instance_id)] if not boq.empty else boq
        assessment_count = int(lines.assessment_role.eq("ASSESSMENT_INVENTORY").sum()) if not lines.empty else 0
        info_count = int(lines.assessment_role.eq("INFORMATION_ONLY").sum()) if not lines.empty else 0
        units = ";".join(sorted(set(lines.quantity_unit.astype(str)))) if not lines.empty else ""
        sources = ";".join(sorted(set(lines.source_status.astype(str)))) if not lines.empty else ""
        if assessment_count > 0:
            status = "BOQ_MAPPED"
            reason = "One or more documented assessment-inventory quantity lines are mapped to this lifecycle component."
        elif bool(parent.primary_component_quantity_available):
            status = "PRIMARY_QUANTITY_ONLY_BOQ_MISSING"
            reason = (
                "A primary component quantity exists in the physical reference inventory, but no assessment BoQ line is mapped; "
                "future carbon accounting must not infer a material/product quantity from the primary quantity without an explicit mapping."
            )
        else:
            status = "BOQ_MISSING"
            reason = "No documented assessment BoQ quantity mapping is available; cost data are not used as a quantity proxy."
        rows.append({
            "scenario_id": parent.scenario_id,
            "scenario_role": parent.scenario_role,
            "component_instance_id": parent.component_instance_id,
            "comparison_lineage_id": parent.comparison_lineage_id,
            "component_type_id": parent.component_type_id,
            "component": parent.component,
            "primary_component_quantity_available": bool(parent.primary_component_quantity_available),
            "primary_component_quantity": parent.primary_component_quantity,
            "primary_component_unit": parent.primary_component_unit,
            "boq_line_count": int(len(lines)),
            "assessment_inventory_line_count": assessment_count,
            "information_only_line_count": info_count,
            "boq_units": units,
            "boq_source_statuses": sources,
            "quantity_mapping_status": status,
            "reason": reason,
        })
    return pd.DataFrame(rows, columns=PHYSICAL_QUANTITY_COVERAGE_COLUMNS)


def build_reference_coverage_skeleton(
    presence: pd.DataFrame,
    reference_inventory: pd.DataFrame,
    boq: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for declaration in presence.itertuples(index=False):
        ref_rows = reference_inventory.loc[
            reference_inventory.comparison_lineage_id.eq(declaration.comparison_lineage_id)
        ] if not reference_inventory.empty else reference_inventory
        ref_component_ids = set(ref_rows.component_instance_id.astype(str)) if not ref_rows.empty else set()
        ref_boq = boq.loc[boq.component_instance_id.isin(ref_component_ids)] if ref_component_ids and not boq.empty else boq.iloc[0:0]
        assessment_lines = int(ref_boq.assessment_role.eq("ASSESSMENT_INVENTORY").sum()) if not ref_boq.empty else 0

        if declaration.reference_presence_status == "UNKNOWN":
            lifecycle_status = "BLOCKED_PRESENCE_UNKNOWN"
            quantity_status = "BLOCKED_PRESENCE_UNKNOWN"
            comparison_status = "REFERENCE_PRESENCE_UNRESOLVED"
            reason = "The v2.1 source does not establish whether this intervention lineage exists in the continued-use reference."
        elif declaration.reference_presence_status == "ABSENT_DOCUMENTED":
            lifecycle_status = "NOT_APPLICABLE_DOCUMENTED_ABSENCE"
            quantity_status = "NOT_APPLICABLE_DOCUMENTED_ABSENCE"
            comparison_status = "REFERENCE_ABSENCE_DOCUMENTED"
            reason = "Documented absence may support a zero reference quantity for this lineage; the absence evidence remains explicit."
        else:
            lifecycle_status = "AVAILABLE" if len(ref_rows) > 0 else "MISSING_REFERENCE_INVENTORY"
            if assessment_lines > 0:
                quantity_status = "BOQ_MAPPED"
                comparison_status = "REFERENCE_QUANTITY_MAPPED"
                reason = "Reference presence, lifecycle inventory, and assessment BoQ mapping are documented for this lineage."
            else:
                quantity_status = "MISSING_BOQ"
                comparison_status = "REFERENCE_PRESENT_BOQ_MISSING"
                reason = "Reference presence/lifecycle inventory are documented, but assessment BoQ quantity mapping is still missing."
        rows.append({
            "comparison_lineage_id": declaration.comparison_lineage_id,
            "component_type_id": declaration.component_type_id,
            "reference_presence_status": declaration.reference_presence_status,
            "presence_evidence_status": declaration.evidence_status,
            "reference_inventory_rows": int(len(ref_rows)),
            "reference_primary_quantity_rows": int(len(ref_rows)),
            "reference_boq_line_count": int(len(ref_boq)),
            "reference_assessment_inventory_line_count": assessment_lines,
            "reference_lifecycle_model_status": lifecycle_status,
            "reference_quantity_mapping_status": quantity_status,
            "comparison_coverage_status": comparison_status,
            "coverage_denominator_scope": "KNOWN_INTERVENTION_LINEAGES_ONLY",
            "reason": reason,
        })
    return pd.DataFrame(rows, columns=REFERENCE_COVERAGE_COLUMNS)


def _stable_bridge_id(prefix: str, *parts: object) -> str:
    key = "|".join(str(part) for part in parts)
    return f"{prefix}_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def expand_lifecycle_events_with_boq(lifecycle_ledger: pd.DataFrame, boq: pd.DataFrame) -> pd.DataFrame:
    if lifecycle_ledger.empty or boq.empty:
        return empty_event_boq_mapping()
    merged = lifecycle_ledger.merge(
        boq.loc[:, [
            "boq_line_id", "component_instance_id", "material_or_product_id", "assessment_role",
            "quantity", "quantity_unit", "mass_kg", "source_status", "source_reference",
        ]],
        on="component_instance_id",
        how="inner",
        validate="many_to_many",
    )
    if merged.empty:
        return empty_event_boq_mapping()
    out = pd.DataFrame({
        "event_boq_id": [
            _stable_bridge_id("ebq", event_id, boq_line_id)
            for event_id, boq_line_id in zip(merged.event_id, merged.boq_line_id)
        ],
        "event_id": merged.event_id,
        "future_id": merged.future_id.astype(int),
        "scenario_id": merged.scenario_id,
        "component_instance_id": merged.component_instance_id,
        "comparison_lineage_id": merged.comparison_lineage_id,
        "component_generation": merged.component_generation.astype(int),
        "event_type": merged.event_type,
        "boq_line_id": merged.boq_line_id,
        "material_or_product_id": merged.material_or_product_id,
        "assessment_role": merged.assessment_role,
        "quantity": merged.quantity.astype(float),
        "quantity_unit": merged.quantity_unit,
        "mass_kg": merged.mass_kg,
        "source_status": merged.source_status,
        "source_reference": merged.source_reference,
    }, columns=EVENT_BOQ_COLUMNS)
    if out.event_boq_id.duplicated().any():
        raise ValueError("Expanded lifecycle-event BoQ IDs must be unique.")
    return out.reset_index(drop=True)


def expand_boundary_states_with_boq(boundary_state: pd.DataFrame, boq: pd.DataFrame) -> pd.DataFrame:
    if boundary_state.empty or boq.empty:
        return empty_boundary_boq_mapping()
    merged = boundary_state.merge(
        boq.loc[:, [
            "boq_line_id", "component_instance_id", "material_or_product_id", "assessment_role",
            "quantity", "quantity_unit", "mass_kg", "source_status", "source_reference",
        ]],
        on="component_instance_id",
        how="inner",
        validate="many_to_many",
    )
    if merged.empty:
        return empty_boundary_boq_mapping()
    out = pd.DataFrame({
        "boundary_boq_state_id": [
            _stable_bridge_id("bbq", boundary_id, boq_line_id)
            for boundary_id, boq_line_id in zip(merged.boundary_state_id, merged.boq_line_id)
        ],
        "boundary_state_id": merged.boundary_state_id,
        "future_id": merged.future_id.astype(int),
        "scenario_id": merged.scenario_id,
        "component_instance_id": merged.component_instance_id,
        "comparison_lineage_id": merged.comparison_lineage_id,
        "component_type_id": merged.component_type_id,
        "component_generation_at_boundary": merged.component_generation_at_boundary.astype(int),
        "rsp_years": merged.rsp_years.astype(float),
        "remaining_life_at_boundary_years": merged.remaining_life_at_boundary_years.astype(float),
        "boq_line_id": merged.boq_line_id,
        "material_or_product_id": merged.material_or_product_id,
        "assessment_role": merged.assessment_role,
        "quantity": merged.quantity.astype(float),
        "quantity_unit": merged.quantity_unit,
        "mass_kg": merged.mass_kg,
        "source_status": merged.source_status,
        "source_reference": merged.source_reference,
    }, columns=BOUNDARY_BOQ_COLUMNS)
    if out.boundary_boq_state_id.duplicated().any():
        raise ValueError("Expanded RSP-boundary BoQ state IDs must be unique.")
    return out.reset_index(drop=True)


def boq_status(boq: pd.DataFrame, quantity_coverage: pd.DataFrame) -> dict:
    assessment = boq.loc[boq.assessment_role.eq("ASSESSMENT_INVENTORY")] if not boq.empty else boq
    if boq.empty:
        status = "UNPOPULATED_SOURCE_DATA_ABSENT"
        claim = "The source package contains no documented physical BoQ for intervention components; no quantity is inferred from cost or labels."
    elif assessment.empty:
        status = "INFORMATION_ONLY_NO_ASSESSMENT_QUANTITIES"
        claim = "Physical quantity rows exist only as information-only records; no assessment-inventory quantity is available for environmental calculation."
    else:
        status = "ASSESSMENT_QUANTITIES_AVAILABLE"
        claim = "Documented assessment-inventory physical quantity rows are available for at least one lifecycle component."
    return {
        "status": status,
        "boq_rows": int(len(boq)),
        "assessment_boq_rows": int(len(assessment)),
        "mapped_component_instances": int(boq.component_instance_id.nunique()) if not boq.empty else 0,
        "mapped_assessment_component_instances": int(assessment.component_instance_id.nunique()) if not assessment.empty else 0,
        "components_missing_assessment_boq": int(
            quantity_coverage.quantity_mapping_status.ne("BOQ_MAPPED").sum()
        ) if not quantity_coverage.empty else 0,
        "claim": claim,
    }
