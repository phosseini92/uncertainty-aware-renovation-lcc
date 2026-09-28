"""M2.3: replacement-transport carbon consequences reported inside B4.

This module is deliberately separate from M2.2 A4 initial transport. It reuses
validated transport routes/factors, but replacement transport is attached to the
canonical B4 replacement event and reported to B4 rather than reclassified to A4.
No service-life resampling, transport uncertainty, A5/C/D, or headline whole-life
carbon is introduced here.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from a4_transport import (
    MAPPING_BASES,
    _ids,
    _required,
    _schema,
    validate_transport_scenarios,
    validate_transport_factors,
)
from carbon_consequences import (
    CARBON_CONSEQUENCE_COLUMNS,
    _stable_id,
    empty_carbon_consequence_ledger,
    validate_carbon_consequence_ledger,
)
from environmental_factors import resolve_boq_declared_unit_compatibility, _parse_bool


BOQ_REPLACEMENT_TRANSPORT_ASSIGNMENT_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "transport_scenario_id",
    "transport_flow_id", "factor_set_id", "active", "replacement_transport_basis",
    "mapping_basis", "mapping_reference", "notes",
)
B4_TRANSPORT_COMPATIBILITY_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "component_instance_id",
    "comparison_lineage_id", "replacement_transport_basis", "transport_scenario_id",
    "transport_flow_id", "factor_set_id", "factor_record_id", "origin_scope",
    "destination_scope", "transport_mode", "vehicle_class", "load_factor_basis",
    "factor_system_boundary", "boq_quantity", "boq_unit", "resolved_mass_kg",
    "mass_conversion_method", "mass_source_reference", "distance_km",
    "distance_source_reference", "distance_retrieval_date", "factor_retrieval_date",
    "resolved_activity_quantity", "resolved_activity_unit", "compatibility_gate_status",
    "reason",
)
B4_TRANSPORT_COVERAGE_COLUMNS = (
    "boq_line_id", "scenario_id", "component_instance_id", "comparison_lineage_id",
    "assignment_id", "replacement_event_count", "compatibility_gate_status", "reason",
)
B4_TRANSPORT_SUMMARY_COLUMNS = (
    "future_id", "scenario_id", "assessment_scope", "reported_module",
    "assessed_gwp_kgco2e", "consequence_row_count", "assessment_label",
)
REPLACEMENT_BASES = {"DOCUMENTED_REPLACEMENT_TRANSPORT"}


def validate_boq_replacement_transport_assignments(table, component_boq, scenarios, factors):
    out = _schema(table, BOQ_REPLACEMENT_TRANSPORT_ASSIGNMENT_COLUMNS, "Replacement transport assignment")
    if out.empty:
        return out
    _ids(out, ["assignment_id", "boq_line_id", "scenario_id", "transport_scenario_id",
               "transport_flow_id", "factor_set_id"], "assignment_id")
    out["active"] = [_parse_bool(v, "active") for v in out.active]
    _required(out, ["replacement_transport_basis", "mapping_basis", "mapping_reference"])
    if not out.replacement_transport_basis.isin(REPLACEMENT_BASES).all():
        raise ValueError("Unsupported replacement_transport_basis.")
    if not out.mapping_basis.isin(MAPPING_BASES).all():
        raise ValueError("Unsupported replacement transport mapping_basis.")
    active = out.loc[out.active]
    if active.boq_line_id.duplicated().any():
        raise ValueError("Each BoQ line permits at most one active replacement transport assignment.")
    if active.duplicated(["scenario_id", "transport_flow_id"]).any():
        raise ValueError("Duplicate active replacement transport flow in the same scenario.")
    for field, available in (("boq_line_id", component_boq.boq_line_id),
                             ("transport_scenario_id", scenarios.transport_scenario_id),
                             ("factor_set_id", factors.factor_set_id)):
        if not set(out[field]).issubset(set(available)):
            raise ValueError(f"Unknown replacement transport assignment {field}.")
    boq = component_boq.set_index("boq_line_id")
    factor_sets = factors.drop_duplicates("factor_set_id").set_index("factor_set_id")
    routes = scenarios.set_index("transport_scenario_id")
    for row in out.itertuples(index=False):
        b, f, s = boq.loc[row.boq_line_id], factor_sets.loc[row.factor_set_id], routes.loc[row.transport_scenario_id]
        if row.scenario_id != b.scenario_id:
            raise ValueError("Replacement transport assignment scenario_id conflicts with BoQ parent; scope leakage blocked.")
        if b.assessment_role != "ASSESSMENT_INVENTORY":
            raise ValueError("INFORMATION_ONLY BoQ lines cannot receive replacement transport assignments.")
        synthetic = (f.source_type == "TEST_ONLY_SYNTHETIC" or s.source_status == "TEST_ONLY_SYNTHETIC"
                     or b.source_status == "TEST_ONLY_SYNTHETIC")
        if synthetic and row.mapping_basis != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic replacement transport data require TEST_ONLY_SYNTHETIC mapping.")
    out["notes"] = out.notes.fillna("")
    return out


def load_boq_replacement_transport_assignments(path: Path, component_boq, scenarios, factors):
    return validate_boq_replacement_transport_assignments(pd.read_csv(path), component_boq, scenarios, factors)


def build_b4_transport_compatibility(components, component_boq, scenarios, factors, assignments):
    scenarios = validate_transport_scenarios(scenarios)
    factors = validate_transport_factors(factors)
    assignments = validate_boq_replacement_transport_assignments(assignments, component_boq, scenarios, factors)
    if components.component_instance_id.duplicated().any():
        raise ValueError("Ambiguous component identity in replacement transport scope.")
    parents = components.set_index("component_instance_id", drop=False)
    boq = component_boq.set_index("boq_line_id", drop=False)
    routes = scenarios.set_index("transport_scenario_id", drop=False)
    rows = []
    for a in assignments.loc[assignments.active.eq(True)].itertuples(index=False):
        b = boq.loc[a.boq_line_id]
        if b.component_instance_id not in parents.index:
            continue
        p = parents.loc[b.component_instance_id]
        if b.scenario_id != p.scenario_id or b.comparison_lineage_id != p.comparison_lineage_id:
            raise ValueError("Replacement transport BoQ identity conflicts with component parent.")
        s = routes.loc[a.transport_scenario_id]
        fs = factors.loc[factors.factor_set_id.eq(a.factor_set_id)]
        f = fs.iloc[0]
        gwp = fs.loc[fs.indicator_id.eq("GWP_TOTAL") & fs.module_scope.eq("A4")]
        mass = resolve_boq_declared_unit_compatibility(b, "kg")
        kg = float(mass["resolved_activity_quantity"])
        if mass["unit_compatibility_status"] != "INCOMPATIBLE_UNIT" and (not np.isfinite(kg) or kg <= 0):
            raise ValueError("Resolved replacement transport mass must be finite and positive.")
        status, reason = "PASS_B4_REPLACEMENT_TRANSPORT", "Explicit replacement transport, mass, distance and GWP_TOTAL factor gates pass."
        if mass["unit_compatibility_status"] == "INCOMPATIBLE_UNIT":
            status, reason = "BLOCKED_MASS_MISSING", "No mass-unit quantity or documented total-mass bridge."
        elif pd.isna(s.distance_km):
            status, reason = "BLOCKED_DISTANCE_MISSING", "Explicit distance_km is missing; no default is allowed."
        elif f.declared_unit != "tkm":
            status, reason = "BLOCKED_TRANSPORT_FACTOR_UNIT", "Transport factor must use kgCO2e per tonne-km."
        elif not fs.indicator_id.eq("GWP_TOTAL").any():
            status, reason = "BLOCKED_GWP_TOTAL_MISSING", "Disaggregated indicators are never implicitly summed."
        elif len(gwp) != 1:
            status, reason = "BLOCKED_A4_FACTOR_SCOPE", "Exactly one GWP_TOTAL A4 transport-process record is required as the source process."
        elif any(s[field] != f[field] for field in ("transport_mode", "vehicle_class", "load_factor_basis")):
            status, reason = "BLOCKED_TRANSPORT_FACTOR_BASIS", "Route mode, vehicle and load basis must match the documented factor basis."
        tkm = kg / 1000.0 * float(s.distance_km) if status.startswith("PASS_") else np.nan
        if status.startswith("PASS_") and not np.isfinite(tkm):
            raise ValueError("Nonfinite replacement tonne-km activity.")
        rows.append(dict(zip(B4_TRANSPORT_COMPATIBILITY_COLUMNS, (
            a.assignment_id, b.boq_line_id, b.scenario_id, b.component_instance_id,
            b.comparison_lineage_id, a.replacement_transport_basis, s.transport_scenario_id,
            a.transport_flow_id, a.factor_set_id, gwp.iloc[0].factor_record_id if len(gwp) == 1 else pd.NA,
            s.origin_scope, s.destination_scope, s.transport_mode, s.vehicle_class,
            s.load_factor_basis, f.factor_system_boundary, b.quantity, b.quantity_unit,
            kg, mass["conversion_method"], b.source_reference, s.distance_km,
            s.source_reference, s.retrieval_date, f.retrieval_date, tkm, "tkm", status, reason,
        ))))
    return pd.DataFrame(rows, columns=B4_TRANSPORT_COMPATIBILITY_COLUMNS)


def build_b4_transport_coverage(components, component_boq, compatibility, event_boq_quantities):
    parents = components.set_index("component_instance_id", drop=False) if not components.empty else pd.DataFrame()
    gates = compatibility.set_index("boq_line_id", drop=False) if not compatibility.empty else pd.DataFrame()
    counts = {}
    if not event_boq_quantities.empty:
        ev = event_boq_quantities.loc[event_boq_quantities.event_type.eq("B4_REPLACEMENT")]
        counts = ev.groupby("boq_line_id").size().to_dict()
    rows = []
    for b in component_boq.loc[component_boq.assessment_role.eq("ASSESSMENT_INVENTORY")].itertuples(index=False):
        if components.empty or b.component_instance_id not in parents.index:
            continue
        n = int(counts.get(b.boq_line_id, 0))
        if n == 0:
            aid, status, reason = pd.NA, "NOT_APPLICABLE_NO_B4_EVENTS_WITHIN_RSP", "No canonical B4 replacement event for this BoQ line within the current RSP."
        elif not compatibility.empty and b.boq_line_id in gates.index:
            g = gates.loc[b.boq_line_id]
            aid, status, reason = g.assignment_id, g.compatibility_gate_status, g.reason
        else:
            aid, status, reason = pd.NA, "BLOCKED_REPLACEMENT_TRANSPORT_ASSIGNMENT_MISSING", "B4 events exist but no active explicit replacement transport assignment is available."
        rows.append((b.boq_line_id, b.scenario_id, b.component_instance_id, b.comparison_lineage_id,
                     aid, n, status, reason))
    return pd.DataFrame(rows, columns=B4_TRANSPORT_COVERAGE_COLUMNS)


def build_b4_transport_consequences(lifecycle_event_ledger, event_boq_quantities, component_boq,
                                    factors, assignments, compatibility):
    if lifecycle_event_ledger.empty or event_boq_quantities.empty or component_boq.empty or assignments.empty or compatibility.empty or factors.empty:
        return empty_carbon_consequence_ledger()
    events = event_boq_quantities.loc[event_boq_quantities.event_type.eq("B4_REPLACEMENT")].copy()
    if events.empty:
        return empty_carbon_consequence_ledger()
    compat = compatibility.loc[compatibility.compatibility_gate_status.str.startswith("PASS_")]
    if compat.empty:
        return empty_carbon_consequence_ledger()
    compat_lookup = compat.set_index("boq_line_id", drop=False)
    assignment_lookup = assignments.set_index("assignment_id", drop=False)
    factor_lookup = factors.set_index("factor_record_id", drop=False)
    lifecycle_lookup = lifecycle_event_ledger.set_index("event_id", drop=False)
    rows = []
    for event in events.itertuples(index=False):
        if event.event_id not in lifecycle_lookup.index:
            raise ValueError(f"Event-BoQ bridge references unknown canonical lifecycle event {event.event_id!r}.")
        source = lifecycle_lookup.loc[event.event_id]
        for field, left, right in (
            ("future_id", int(event.future_id), int(source.future_id)),
            ("scenario_id", str(event.scenario_id), str(source.scenario_id)),
            ("component_instance_id", str(event.component_instance_id), str(source.component_instance_id)),
            ("component_generation", int(event.component_generation), int(source.component_generation)),
            ("event_type", str(event.event_type), str(source.event_type)),
        ):
            if left != right:
                raise ValueError(f"Event-BoQ bridge conflicts with canonical lifecycle event for field: {field}")
        if event.boq_line_id not in compat_lookup.index:
            continue
        c = compat_lookup.loc[event.boq_line_id]
        a = assignment_lookup.loc[c.assignment_id]
        f = factor_lookup.loc[c.factor_record_id]
        impact = float(c.resolved_activity_quantity) * float(f.indicator_value)
        rows.append({
            "carbon_consequence_id": _stable_id("cc", "B4_TRANSPORT", event.event_id, event.boq_line_id, c.transport_flow_id, f.factor_record_id),
            "future_id": int(event.future_id), "scenario_id": str(event.scenario_id),
            "component_instance_id": str(event.component_instance_id), "comparison_lineage_id": str(event.comparison_lineage_id),
            "component_generation": int(event.component_generation), "consequence_type": "B4_REPLACEMENT_TRANSPORT",
            "lifecycle_event_id": str(event.event_id), "source_event_type": "B4_REPLACEMENT",
            "event_time_years": float(source.event_time_years), "boq_line_id": str(event.boq_line_id),
            "material_or_product_id": str(event.material_or_product_id), "assignment_id": str(a.assignment_id),
            "factor_set_id": str(f.factor_set_id), "factor_record_id": str(f.factor_record_id),
            "dataset_id": str(f.dataset_id), "factor_product_or_process_id": str(f.product_or_process_id),
            "factor_declared_unit": str(f.declared_unit), "factor_reference_year": int(f.reference_year),
            "indicator_id": "GWP_TOTAL", "source_factor_module_scope": "A4", "reported_module": "B4",
            "boq_quantity": float(event.quantity), "boq_unit": str(c.boq_unit),
            "resolved_activity_quantity": float(c.resolved_activity_quantity), "resolved_activity_unit": "tkm",
            "indicator_value_per_declared_unit": float(f.indicator_value), "indicator_unit": str(f.indicator_unit),
            "gwp_kgco2e": float(impact), "mapping_basis": str(a.mapping_basis),
            "conversion_method": str(c.mass_conversion_method) + "_X_KM_DIV_1000",
            "source_type": str(f.source_type), "source_citation": str(f.source_citation),
            "verification_status": str(f.verification_status), "data_quality_status": str(f.data_quality_status),
            "license_status": str(f.license_status), "redistribution_allowed": bool(f.redistribution_allowed),
            "factor_uncertainty_mode": str(f.uncertainty_mode), "factor_uncertainty_semantics": str(f.uncertainty_semantics),
            "factor_uncertainty_applied": False, "factor_temporal_basis": "STATIC_REFERENCE_FACTOR",
            "provenance_status": "CENTRAL_FACTOR_VALUE_ONLY",
        })
    return validate_b4_transport_ledger(pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS)) if rows else empty_carbon_consequence_ledger()


def validate_b4_transport_ledger(ledger):
    out = _schema(ledger, CARBON_CONSEQUENCE_COLUMNS, "B4 replacement transport consequence")
    if out.empty:
        return out
    if out.carbon_consequence_id.duplicated().any() or out.duplicated(["lifecycle_event_id", "boq_line_id", "assignment_id"]).any():
        raise ValueError("Duplicate B4 replacement transport consequence/flow.")
    expected = {
        "consequence_type": "B4_REPLACEMENT_TRANSPORT", "reported_module": "B4",
        "source_factor_module_scope": "A4", "source_event_type": "B4_REPLACEMENT",
        "indicator_id": "GWP_TOTAL", "factor_declared_unit": "tkm", "resolved_activity_unit": "tkm",
        "indicator_unit": "kgco2e", "factor_uncertainty_applied": False,
        "factor_temporal_basis": "STATIC_REFERENCE_FACTOR",
    }
    for field, value in expected.items():
        if not out[field].eq(value).all():
            raise ValueError(f"Invalid B4 replacement transport {field}.")
    if out.lifecycle_event_id.isna().any():
        raise ValueError("B4 replacement transport requires a canonical lifecycle_event_id.")
    if (out.component_generation < 1).any() or (out.event_time_years <= 0).any():
        raise ValueError("B4 replacement transport must occur on a positive-time replacement generation.")
    for field in ("future_id", "boq_quantity", "resolved_activity_quantity", "indicator_value_per_declared_unit", "gwp_kgco2e"):
        vals = pd.to_numeric(out[field], errors="raise")
        if not np.isfinite(vals.to_numpy(dtype=float)).all() or (vals < 0).any():
            raise ValueError(f"Nonfinite or negative B4 replacement transport {field}.")
    if (out.boq_quantity <= 0).any() or (out.resolved_activity_quantity < 0).any():
        raise ValueError("Invalid B4 replacement transport quantity.")
    if not np.allclose(out.resolved_activity_quantity * out.indicator_value_per_declared_unit,
                       out.gwp_kgco2e, rtol=1e-12, atol=1e-12):
        raise ValueError("B4 replacement transport impact does not reconcile to tonne-km times factor.")
    return out


def append_b4_transport_to_combined_ledger(combined_ledger, b4_transport_ledger):
    # Validate the frozen subledgers without changing their rules.
    product = combined_ledger.loc[combined_ledger.consequence_type.isin({"INITIAL_PRODUCT_STAGE", "B4_REPLACEMENT_PRODUCT_STAGE"})]
    a4 = combined_ledger.loc[combined_ledger.consequence_type.eq("INITIAL_TRANSPORT_TO_SITE")]
    if not product.empty:
        validate_carbon_consequence_ledger(product)
    if not a4.empty:
        from a4_transport import validate_a4_transport_ledger
        validate_a4_transport_ledger(a4)
    validate_b4_transport_ledger(b4_transport_ledger)
    if b4_transport_ledger.empty:
        return combined_ledger.copy()
    out = pd.concat([combined_ledger, b4_transport_ledger], ignore_index=True)
    if out.carbon_consequence_id.duplicated().any():
        raise ValueError("Carbon consequence ID collision after B4 transport append.")
    return out


def build_b4_transport_summary(ledger):
    if ledger.empty:
        return pd.DataFrame(columns=B4_TRANSPORT_SUMMARY_COLUMNS)
    validate_b4_transport_ledger(ledger)
    out = ledger.groupby(["future_id", "scenario_id", "reported_module"], as_index=False).agg(
        assessed_gwp_kgco2e=("gwp_kgco2e", "sum"), consequence_row_count=("carbon_consequence_id", "count"))
    out["assessment_scope"] = "B4_REPLACEMENT_TRANSPORT_ONLY"
    out["assessment_label"] = "ASSESSED_B4_REPLACEMENT_TRANSPORT_ONLY_NOT_WHOLE_LIFE_CARBON"
    return out.loc[:, B4_TRANSPORT_SUMMARY_COLUMNS].sort_values(["future_id", "scenario_id"]).reset_index(drop=True)


def b4_transport_engine_status(coverage, ledger):
    passed = int(coverage.compatibility_gate_status.str.startswith("PASS_").sum()) if not coverage.empty else 0
    blocked = int(coverage.compatibility_gate_status.str.startswith("BLOCKED_").sum()) if not coverage.empty else 0
    na = int(coverage.compatibility_gate_status.str.startswith("NOT_APPLICABLE_").sum()) if not coverage.empty else 0
    status = ("NO_ASSESSMENT_BOQ_LINES" if coverage.empty else
              "NOT_APPLICABLE_NO_B4_EVENTS_WITHIN_RSP" if na == len(coverage) else
              "NO_EXECUTABLE_B4_REPLACEMENT_TRANSPORT_MAPPING" if passed == 0 else
              "PARTIAL_EXECUTABLE_B4_REPLACEMENT_TRANSPORT_MAPPING" if blocked else
              "EXECUTABLE_B4_REPLACEMENT_TRANSPORT_MAPPING_AVAILABLE")
    return {
        "status": status, "assessment_boq_lines": len(coverage), "gate_pass_lines": passed,
        "blocked_lines": blocked, "not_applicable_lines": na, "carbon_consequence_rows": len(ledger),
        "implemented_modules": ["B4_REPLACEMENT_TRANSPORT"], "executed_indicator": "GWP_TOTAL",
        "reported_module": "B4", "source_transport_factor_scope": "A4_PROCESS_FACTOR",
        "carbon_discounting_applied": False, "factor_uncertainty_applied": False,
        "missing_data_treated_as_zero": False, "whole_life_carbon_generated": False,
        "headline_carbon_generated": False,
        "claim": "Assessed transport attributable to canonical B4 replacement events only; transport is reported in B4 and is not reclassified to A4.",
    }


def assess_b4_replacement_transport(components, component_boq, lifecycle_event_ledger,
                                    event_boq_quantities, scenarios, factors, assignments):
    scenarios = validate_transport_scenarios(scenarios)
    factors = validate_transport_factors(factors)
    assignments = validate_boq_replacement_transport_assignments(assignments, component_boq, scenarios, factors)
    compatibility = build_b4_transport_compatibility(components, component_boq, scenarios, factors, assignments)
    coverage = build_b4_transport_coverage(components, component_boq, compatibility, event_boq_quantities)
    ledger = build_b4_transport_consequences(lifecycle_event_ledger, event_boq_quantities, component_boq,
                                             factors, assignments, compatibility)
    return compatibility, coverage, ledger, build_b4_transport_summary(ledger), b4_transport_engine_status(coverage, ledger)
