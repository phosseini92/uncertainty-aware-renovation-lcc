"""Product-stage carbon consequence engine for v3 M2.1.

Scope is deliberately narrow:
- initial product-stage GWP (A1-A3) for components that are NEW_AT_T0;
- product-stage GWP associated with canonical B4 replacement events;
- GWP_TOTAL only;
- central environmental-factor values only (factor uncertainty is not sampled yet).

Out of scope: A4, A5, B1-B3, B5-B8, C1-C4, D1-D2, residual value,
abatement cost, whole-life-carbon claims, and stakeholder carbon allocation.

The engine consumes the M1 canonical lifecycle event ledger, M1.7 physical BoQ
mapping, and M1.8 explicit environmental-factor registry/unit gate.  It never
resamples component life and never infers quantities or factors from labels or
costs.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
import pandas as pd


CARBON_CONSEQUENCE_COLUMNS = (
    "carbon_consequence_id",
    "future_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "component_generation",
    "consequence_type",
    "lifecycle_event_id",
    "source_event_type",
    "event_time_years",
    "boq_line_id",
    "material_or_product_id",
    "assignment_id",
    "factor_set_id",
    "factor_record_id",
    "dataset_id",
    "factor_product_or_process_id",
    "factor_declared_unit",
    "factor_reference_year",
    "indicator_id",
    "source_factor_module_scope",
    "reported_module",
    "boq_quantity",
    "boq_unit",
    "resolved_activity_quantity",
    "resolved_activity_unit",
    "indicator_value_per_declared_unit",
    "indicator_unit",
    "gwp_kgco2e",
    "mapping_basis",
    "conversion_method",
    "source_type",
    "source_citation",
    "verification_status",
    "data_quality_status",
    "license_status",
    "redistribution_allowed",
    "factor_uncertainty_mode",
    "factor_uncertainty_semantics",
    "factor_uncertainty_applied",
    "factor_temporal_basis",
    "provenance_status",
)

PRODUCT_CARBON_SUMMARY_COLUMNS = (
    "future_id",
    "scenario_id",
    "assessment_scope",
    "reported_module",
    "assessed_gwp_kgco2e",
    "consequence_row_count",
    "assessment_label",
)

PRODUCT_CARBON_COVERAGE_COLUMNS = (
    "boq_line_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "material_or_product_id",
    "compatibility_gate_status",
    "initial_component_state",
    "initial_a1_a3_status",
    "b4_product_status",
    "calculation_status",
    "reason",
)

PASS_GATE_PREFIX = "PASS_"
PRODUCT_STAGE_SCOPES = {"A1-A3", "A1", "A2", "A3"}
ALLOWED_CONSEQUENCE_TYPES = {
    "INITIAL_PRODUCT_STAGE",
    "B4_REPLACEMENT_PRODUCT_STAGE",
}


def empty_carbon_consequence_ledger() -> pd.DataFrame:
    return pd.DataFrame(columns=CARBON_CONSEQUENCE_COLUMNS)


def empty_product_carbon_summary() -> pd.DataFrame:
    return pd.DataFrame(columns=PRODUCT_CARBON_SUMMARY_COLUMNS)


def _stable_id(prefix: str, *parts: object) -> str:
    key = "|".join("" if pd.isna(part) else str(part) for part in parts)
    return f"{prefix}_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _component_state_lookup(components: pd.DataFrame) -> dict[str, str]:
    if components.empty:
        return {}
    states = {}
    has_state = "initial_component_state" in components.columns
    for row in components.itertuples(index=False):
        state = str(getattr(row, "initial_component_state", "NEW_AT_T0") if has_state else "NEW_AT_T0").strip()
        if not state or state.lower() == "nan":
            state = "NEW_AT_T0"
        if state not in {"NEW_AT_T0", "RETAINED_EXISTING"}:
            raise ValueError(f"Unsupported initial_component_state for carbon consequences: {state}")
        states[str(row.component_instance_id)] = state
    return states


def _passing_compatibility(compatibility: pd.DataFrame) -> pd.DataFrame:
    if compatibility.empty:
        return compatibility.copy()
    return compatibility.loc[
        compatibility.compatibility_gate_status.astype(str).str.startswith(PASS_GATE_PREFIX)
    ].copy()


def _product_stage_gwp_records(factors: pd.DataFrame) -> pd.DataFrame:
    if factors.empty:
        return factors.copy()
    return factors.loc[
        factors.indicator_id.eq("GWP_TOTAL") & factors.module_scope.isin(PRODUCT_STAGE_SCOPES)
    ].copy()


def _build_initial_rows(
    *,
    components: pd.DataFrame,
    component_boq: pd.DataFrame,
    factors: pd.DataFrame,
    assignments: pd.DataFrame,
    compatibility: pd.DataFrame,
    future_ids: Iterable[int],
) -> list[dict]:
    if components.empty or component_boq.empty or assignments.empty or compatibility.empty or factors.empty:
        return []
    states = _component_state_lookup(components)
    component_lookup = components.set_index("component_instance_id", drop=False)
    compat = _passing_compatibility(compatibility)
    if compat.empty:
        return []
    assign_lookup = assignments.set_index("boq_line_id", drop=False)
    boq_lookup = component_boq.set_index("boq_line_id", drop=False)
    product_records = _product_stage_gwp_records(factors)
    rows: list[dict] = []
    ids = [int(v) for v in future_ids]

    for c in compat.itertuples(index=False):
        component_id = str(c.component_instance_id)
        if component_id not in states:
            continue
        if states[component_id] != "NEW_AT_T0":
            continue
        if c.boq_line_id not in assign_lookup.index or c.boq_line_id not in boq_lookup.index:
            continue
        assignment = assign_lookup.loc[c.boq_line_id]
        boq = boq_lookup.loc[c.boq_line_id]
        factor_rows = product_records.loc[product_records.factor_set_id.eq(c.factor_set_id)]
        if factor_rows.empty:
            raise ValueError(
                f"Compatibility gate passed for {c.boq_line_id!r} but no executable GWP_TOTAL product-stage records were found."
            )
        resolved_qty = float(c.resolved_activity_quantity)
        for fid in ids:
            for factor in factor_rows.itertuples(index=False):
                impact = resolved_qty * float(factor.indicator_value)
                rows.append({
                    "carbon_consequence_id": _stable_id(
                        "cc", "T0", fid, component_id, c.boq_line_id, factor.factor_record_id
                    ),
                    "future_id": fid,
                    "scenario_id": str(c.scenario_id),
                    "component_instance_id": component_id,
                    "comparison_lineage_id": str(c.comparison_lineage_id),
                    "component_generation": 0,
                    "consequence_type": "INITIAL_PRODUCT_STAGE",
                    "lifecycle_event_id": pd.NA,
                    "source_event_type": "T0_INITIAL_PRODUCT",
                    "event_time_years": 0.0,
                    "boq_line_id": str(c.boq_line_id),
                    "material_or_product_id": str(boq.material_or_product_id),
                    "assignment_id": str(assignment.assignment_id),
                    "factor_set_id": str(c.factor_set_id),
                    "factor_record_id": str(factor.factor_record_id),
                    "dataset_id": str(factor.dataset_id),
                    "factor_product_or_process_id": str(factor.product_or_process_id),
                    "factor_declared_unit": str(factor.declared_unit),
                    "factor_reference_year": int(factor.reference_year),
                    "indicator_id": "GWP_TOTAL",
                    "source_factor_module_scope": str(factor.module_scope),
                    "reported_module": "A1-A3",
                    "boq_quantity": float(boq.quantity),
                    "boq_unit": str(c.boq_unit),
                    "resolved_activity_quantity": resolved_qty,
                    "resolved_activity_unit": str(c.resolved_activity_unit),
                    "indicator_value_per_declared_unit": float(factor.indicator_value),
                    "indicator_unit": str(factor.indicator_unit),
                    "gwp_kgco2e": float(impact),
                    "mapping_basis": str(assignment.mapping_basis),
                    "conversion_method": str(c.conversion_method),
                    "source_type": str(factor.source_type),
                    "source_citation": str(factor.source_citation),
                    "verification_status": str(factor.verification_status),
                    "data_quality_status": str(factor.data_quality_status),
                    "license_status": str(factor.license_status),
                    "redistribution_allowed": bool(factor.redistribution_allowed),
                    "factor_uncertainty_mode": str(factor.uncertainty_mode),
                    "factor_uncertainty_semantics": str(factor.uncertainty_semantics),
                    "factor_uncertainty_applied": False,
                    "factor_temporal_basis": "STATIC_REFERENCE_FACTOR",
                    "provenance_status": "CENTRAL_FACTOR_VALUE_ONLY",
                })
    return rows


def _build_b4_rows(
    *,
    lifecycle_event_ledger: pd.DataFrame,
    event_boq_quantities: pd.DataFrame,
    component_boq: pd.DataFrame,
    factors: pd.DataFrame,
    assignments: pd.DataFrame,
    compatibility: pd.DataFrame,
) -> list[dict]:
    if lifecycle_event_ledger.empty or event_boq_quantities.empty or component_boq.empty or assignments.empty or compatibility.empty or factors.empty:
        return []
    events = event_boq_quantities.loc[event_boq_quantities.event_type.eq("B4_REPLACEMENT")].copy()
    if events.empty:
        return []
    compat = _passing_compatibility(compatibility)
    if compat.empty:
        return []
    assign_lookup = assignments.set_index("boq_line_id", drop=False)
    compat_lookup = compat.set_index("boq_line_id", drop=False)
    lifecycle_lookup = lifecycle_event_ledger.set_index("event_id", drop=False)
    product_records = _product_stage_gwp_records(factors)
    rows: list[dict] = []

    for event in events.itertuples(index=False):
        if event.event_id not in lifecycle_lookup.index:
            raise ValueError(f"Event-BoQ bridge references unknown canonical lifecycle event {event.event_id!r}.")
        source_event = lifecycle_lookup.loc[event.event_id]
        consistency = {
            "future_id": int(event.future_id) == int(source_event.future_id),
            "scenario_id": str(event.scenario_id) == str(source_event.scenario_id),
            "component_instance_id": str(event.component_instance_id) == str(source_event.component_instance_id),
            "component_generation": int(event.component_generation) == int(source_event.component_generation),
            "event_type": str(event.event_type) == str(source_event.event_type),
        }
        if not all(consistency.values()):
            bad = [k for k, ok in consistency.items() if not ok]
            raise ValueError(f"Event-BoQ bridge conflicts with canonical lifecycle event for fields: {bad}")
        if event.boq_line_id not in compat_lookup.index:
            continue
        c = compat_lookup.loc[event.boq_line_id]
        if event.boq_line_id not in assign_lookup.index:
            continue
        assignment = assign_lookup.loc[event.boq_line_id]
        factor_rows = product_records.loc[product_records.factor_set_id.eq(c.factor_set_id)]
        if factor_rows.empty:
            raise ValueError(
                f"Compatibility gate passed for {event.boq_line_id!r} but no executable GWP_TOTAL product-stage records were found."
            )
        resolved_qty = float(c.resolved_activity_quantity)
        for factor in factor_rows.itertuples(index=False):
            impact = resolved_qty * float(factor.indicator_value)
            rows.append({
                "carbon_consequence_id": _stable_id(
                    "cc", event.event_id, event.boq_line_id, factor.factor_record_id
                ),
                "future_id": int(event.future_id),
                "scenario_id": str(event.scenario_id),
                "component_instance_id": str(event.component_instance_id),
                "comparison_lineage_id": str(event.comparison_lineage_id),
                "component_generation": int(event.component_generation),
                "consequence_type": "B4_REPLACEMENT_PRODUCT_STAGE",
                "lifecycle_event_id": str(event.event_id),
                "source_event_type": "B4_REPLACEMENT",
                "event_time_years": float(source_event.event_time_years),
                "boq_line_id": str(event.boq_line_id),
                "material_or_product_id": str(event.material_or_product_id),
                "assignment_id": str(assignment.assignment_id),
                "factor_set_id": str(c.factor_set_id),
                "factor_record_id": str(factor.factor_record_id),
                "dataset_id": str(factor.dataset_id),
                "factor_product_or_process_id": str(factor.product_or_process_id),
                "factor_declared_unit": str(factor.declared_unit),
                "factor_reference_year": int(factor.reference_year),
                "indicator_id": "GWP_TOTAL",
                "source_factor_module_scope": str(factor.module_scope),
                "reported_module": "B4",
                "boq_quantity": float(event.quantity),
                "boq_unit": str(c.boq_unit),
                "resolved_activity_quantity": resolved_qty,
                "resolved_activity_unit": str(c.resolved_activity_unit),
                "indicator_value_per_declared_unit": float(factor.indicator_value),
                "indicator_unit": str(factor.indicator_unit),
                "gwp_kgco2e": float(impact),
                "mapping_basis": str(assignment.mapping_basis),
                "conversion_method": str(c.conversion_method),
                "source_type": str(factor.source_type),
                "source_citation": str(factor.source_citation),
                "verification_status": str(factor.verification_status),
                "data_quality_status": str(factor.data_quality_status),
                "license_status": str(factor.license_status),
                "redistribution_allowed": bool(factor.redistribution_allowed),
                "factor_uncertainty_mode": str(factor.uncertainty_mode),
                "factor_uncertainty_semantics": str(factor.uncertainty_semantics),
                "factor_uncertainty_applied": False,
                "factor_temporal_basis": "STATIC_REFERENCE_FACTOR",
                "provenance_status": "CENTRAL_FACTOR_VALUE_ONLY",
            })
    return rows


def validate_carbon_consequence_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    missing = set(CARBON_CONSEQUENCE_COLUMNS) - set(ledger.columns)
    if missing:
        raise ValueError(f"Missing carbon consequence columns: {sorted(missing)}")
    extra = set(ledger.columns) - set(CARBON_CONSEQUENCE_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected carbon consequence columns: {sorted(extra)}")
    out = ledger.loc[:, CARBON_CONSEQUENCE_COLUMNS].copy()
    if out.empty:
        return out
    if out.carbon_consequence_id.duplicated().any():
        raise ValueError("carbon_consequence_id values must be unique.")
    if not out.consequence_type.isin(ALLOWED_CONSEQUENCE_TYPES).all():
        raise ValueError("Unsupported carbon consequence type.")
    if not out.indicator_id.eq("GWP_TOTAL").all():
        raise ValueError("M2.1 executes GWP_TOTAL only.")
    if not out.reported_module.isin({"A1-A3", "B4"}).all():
        raise ValueError("M2.1 reported_module must be A1-A3 or B4.")
    if not out.source_factor_module_scope.isin(PRODUCT_STAGE_SCOPES).all():
        raise ValueError("M2.1 carbon consequences may only use product-stage source factor modules.")
    numeric_fields = (
        "future_id", "component_generation", "event_time_years", "boq_quantity",
        "resolved_activity_quantity", "indicator_value_per_declared_unit", "gwp_kgco2e",
    )
    for field in numeric_fields:
        out[field] = pd.to_numeric(out[field], errors="raise")
        if not np.isfinite(out[field].to_numpy(dtype=float)).all():
            raise ValueError(f"Nonfinite carbon consequence field: {field}")
    if (out.resolved_activity_quantity <= 0).any() or (out.boq_quantity <= 0).any():
        raise ValueError("Carbon consequence quantities must be positive.")
    expected = out.resolved_activity_quantity * out.indicator_value_per_declared_unit
    if not np.allclose(expected, out.gwp_kgco2e, rtol=1e-12, atol=1e-12):
        raise ValueError("gwp_kgco2e does not reconcile to activity quantity × factor value.")
    initial = out.consequence_type.eq("INITIAL_PRODUCT_STAGE")
    if not out.loc[initial, "reported_module"].eq("A1-A3").all():
        raise ValueError("Initial product-stage consequences must report to A1-A3.")
    if not out.loc[initial, "event_time_years"].eq(0.0).all():
        raise ValueError("Initial product-stage consequences must occur at t=0.")
    if not out.loc[initial, "component_generation"].eq(0).all():
        raise ValueError("Initial product-stage consequences must use component_generation=0.")
    b4 = out.consequence_type.eq("B4_REPLACEMENT_PRODUCT_STAGE")
    if not out.loc[b4, "reported_module"].eq("B4").all():
        raise ValueError("Replacement product-stage consequences must report to B4.")
    if out.loc[b4, "lifecycle_event_id"].isna().any():
        raise ValueError("B4 carbon consequences require a canonical lifecycle_event_id.")
    if not out.factor_uncertainty_applied.eq(False).all():
        raise ValueError("M2.1 must not sample environmental-factor uncertainty.")
    if not out.factor_temporal_basis.eq("STATIC_REFERENCE_FACTOR").all():
        raise ValueError("M2.1 uses static reference environmental factors across replacement years.")
    return out


def build_carbon_consequence_ledger(
    *,
    components: pd.DataFrame,
    component_boq: pd.DataFrame,
    lifecycle_event_ledger: pd.DataFrame,
    factors: pd.DataFrame,
    assignments: pd.DataFrame,
    compatibility: pd.DataFrame,
    event_boq_quantities: pd.DataFrame,
    future_ids: Iterable[int],
) -> pd.DataFrame:
    rows = []
    rows.extend(_build_initial_rows(
        components=components,
        component_boq=component_boq,
        factors=factors,
        assignments=assignments,
        compatibility=compatibility,
        future_ids=future_ids,
    ))
    rows.extend(_build_b4_rows(
        lifecycle_event_ledger=lifecycle_event_ledger,
        event_boq_quantities=event_boq_quantities,
        component_boq=component_boq,
        factors=factors,
        assignments=assignments,
        compatibility=compatibility,
    ))
    if not rows:
        return empty_carbon_consequence_ledger()
    return validate_carbon_consequence_ledger(pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS))


def build_product_carbon_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return empty_product_carbon_summary()
    grouped = (
        ledger.groupby(["future_id", "scenario_id", "reported_module"], as_index=False)
        .agg(
            assessed_gwp_kgco2e=("gwp_kgco2e", "sum"),
            consequence_row_count=("carbon_consequence_id", "count"),
        )
    )
    grouped["assessment_scope"] = grouped.reported_module.map({
        "A1-A3": "INITIAL_PRODUCT_STAGE_ONLY",
        "B4": "REPLACEMENT_PRODUCT_STAGE_ONLY",
    })
    grouped["assessment_label"] = "ASSESSED_PRODUCT_AND_REPLACEMENT_CARBON_ONLY_NOT_WHOLE_LIFE_CARBON"
    return grouped.loc[:, PRODUCT_CARBON_SUMMARY_COLUMNS].sort_values(
        ["future_id", "scenario_id", "reported_module"]
    ).reset_index(drop=True)


def build_product_carbon_coverage(
    *,
    components: pd.DataFrame,
    boq_factor_coverage: pd.DataFrame,
) -> pd.DataFrame:
    if boq_factor_coverage.empty:
        return pd.DataFrame(columns=PRODUCT_CARBON_COVERAGE_COLUMNS)
    states = _component_state_lookup(components)
    rows = []
    for row in boq_factor_coverage.itertuples(index=False):
        state = states.get(str(row.component_instance_id), "RETAINED_EXISTING")
        gate = str(row.compatibility_gate_status)
        passes = gate.startswith(PASS_GATE_PREFIX)
        if state == "NEW_AT_T0":
            a_status = "CALCULABLE" if passes else "BLOCKED_BY_ENVIRONMENTAL_GATE"
        else:
            a_status = "NOT_APPLICABLE_RETAINED_HISTORICAL_A1_A3_EXCLUDED"
        b4_status = "CALCULABLE_WHEN_REPLACEMENT_EVENT_OCCURS" if passes else "BLOCKED_BY_ENVIRONMENTAL_GATE"
        if passes:
            calculation_status = "EXECUTABLE_PRODUCT_CARBON_MAPPING"
            reason = "Explicit factor assignment and unit/product-stage GWP gates pass."
        else:
            calculation_status = "BLOCKED"
            reason = str(row.reason)
        rows.append({
            "boq_line_id": row.boq_line_id,
            "scenario_id": row.scenario_id,
            "component_instance_id": row.component_instance_id,
            "comparison_lineage_id": row.comparison_lineage_id,
            "material_or_product_id": row.material_or_product_id,
            "compatibility_gate_status": gate,
            "initial_component_state": state,
            "initial_a1_a3_status": a_status,
            "b4_product_status": b4_status,
            "calculation_status": calculation_status,
            "reason": reason,
        })
    return pd.DataFrame(rows, columns=PRODUCT_CARBON_COVERAGE_COLUMNS)


def carbon_engine_status(
    *,
    component_boq: pd.DataFrame,
    boq_factor_coverage: pd.DataFrame,
    consequence_ledger: pd.DataFrame,
    product_summary: pd.DataFrame,
) -> dict:
    assessment_lines = (
        component_boq.loc[component_boq.assessment_role.eq("ASSESSMENT_INVENTORY")]
        if not component_boq.empty else component_boq
    )
    pass_lines = 0
    if not boq_factor_coverage.empty:
        pass_lines = int(
            boq_factor_coverage.compatibility_gate_status.astype(str).str.startswith(PASS_GATE_PREFIX).sum()
        )
    if assessment_lines.empty:
        status = "NO_ASSESSMENT_BOQ_LINES"
        claim = "No assessment-inventory BoQ lines are available; no product carbon is calculated and missing data are not treated as zero."
    elif pass_lines == 0:
        status = "NO_EXECUTABLE_PRODUCT_CARBON_MAPPING"
        claim = "Assessment BoQ exists, but no line passes the explicit factor/unit/product-stage GWP gate; no product carbon is calculated."
    elif pass_lines < len(assessment_lines):
        status = "PARTIAL_EXECUTABLE_PRODUCT_CARBON_MAPPING"
        claim = "Product carbon is calculated only for explicitly mapped/gated BoQ lines; uncovered lines remain missing and no whole-life-carbon claim is permitted."
    else:
        status = "EXECUTABLE_PRODUCT_CARBON_MAPPING_AVAILABLE"
        claim = "All current assessment BoQ lines pass the M2.1 product-stage mapping gate; results remain limited to A1-A3 initial product and B4 replacement product consequences."
    return {
        "status": status,
        "assessment_boq_lines": int(len(assessment_lines)),
        "gate_pass_lines": pass_lines,
        "carbon_consequence_rows": int(len(consequence_ledger)),
        "summary_rows": int(len(product_summary)),
        "executed_indicator": "GWP_TOTAL",
        "implemented_modules": ["A1-A3_INITIAL_PRODUCT", "B4_REPLACEMENT_PRODUCT"],
        "excluded_modules": ["A4", "A5", "B1", "B2", "B3", "B5", "B6", "B7", "B8", "C1", "C2", "C3", "C4", "D1", "D2"],
        "factor_uncertainty_applied": False,
        "future_product_factor_policy": "STATIC_REFERENCE_FACTOR_ACROSS_REPLACEMENT_YEARS",
        "carbon_discounting_applied": False,
        "whole_life_carbon_generated": False,
        "headline_carbon_generated": False,
        "missing_data_treated_as_zero": False,
        "claim": claim,
    }
