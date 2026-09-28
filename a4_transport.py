"""M2.2: documented initial transport only; no replacement transport or RNG.

One active, single-leg route carries the full documented mass of each assessment
BoQ line. Load/return assumptions belong to the sourced per-tonne-km factor;
they are checked, recorded, and never applied again as multipliers.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_consequences import (
    CARBON_CONSEQUENCE_COLUMNS, _stable_id,
    empty_carbon_consequence_ledger, validate_carbon_consequence_ledger,
)
from environmental_factors import (
    ENVIRONMENTAL_FACTOR_COLUMNS, validate_environmental_factors,
    resolve_boq_declared_unit_compatibility, _parse_bool,
)
from identity import validate_stable_id, validate_unique_ids

TRANSPORT_SCENARIO_COLUMNS = (
    "transport_scenario_id", "origin_scope", "destination_scope", "distance_km",
    "transport_mode", "vehicle_class", "load_factor_basis", "source_status",
    "source_reference", "retrieval_date", "notes",
)
TRANSPORT_FACTOR_METADATA_COLUMNS = (
    "transport_mode", "vehicle_class", "load_factor_basis",
    "factor_system_boundary", "retrieval_date",
)
TRANSPORT_FACTOR_COLUMNS = ENVIRONMENTAL_FACTOR_COLUMNS + TRANSPORT_FACTOR_METADATA_COLUMNS
BOQ_TRANSPORT_ASSIGNMENT_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "transport_scenario_id",
    "transport_flow_id", "factor_set_id", "active", "initial_transport_basis",
    "mapping_basis", "mapping_reference", "notes",
)
A4_COMPATIBILITY_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "component_instance_id",
    "comparison_lineage_id", "initial_component_state", "initial_transport_basis",
    "transport_scenario_id", "transport_flow_id", "factor_set_id", "factor_record_id",
    "origin_scope", "destination_scope", "transport_mode", "vehicle_class",
    "load_factor_basis", "factor_system_boundary", "boq_quantity", "boq_unit",
    "resolved_mass_kg", "mass_conversion_method", "mass_source_reference",
    "distance_km", "distance_source_reference", "distance_retrieval_date",
    "factor_retrieval_date", "resolved_activity_quantity", "resolved_activity_unit",
    "compatibility_gate_status", "reason",
)
A4_COVERAGE_COLUMNS = (
    "boq_line_id", "scenario_id", "component_instance_id", "initial_component_state",
    "assignment_id", "compatibility_gate_status", "reason",
)
A4_SUMMARY_COLUMNS = (
    "future_id", "scenario_id", "assessment_scope", "reported_module",
    "assessed_gwp_kgco2e", "consequence_row_count", "assessment_label",
)
SOURCE_STATUSES = {"DOCUMENTED_PROJECT_DATA", "PUBLIC_DOCUMENTED_DATA", "TEST_ONLY_SYNTHETIC"}
MAPPING_BASES = {"DOCUMENTED_TRANSPORT_PROCESS", "DOCUMENTED_PROXY", "TEST_ONLY_SYNTHETIC"}
INITIAL_BASES = {"NEW_INSTALLATION", "DOCUMENTED_RETAINED_T0_TRANSPORT"}


def _schema(table, columns, label):
    missing, extra = set(columns) - set(table), set(table) - set(columns)
    if missing or extra:
        raise ValueError(f"{label} schema: missing={sorted(missing)}, extra={sorted(extra)}")
    return table.loc[:, columns].copy()


def _required(table, fields):
    for field in fields:
        if table[field].isna().any() or table[field].astype(str).str.strip().eq("").any():
            raise ValueError(f"Transport input requires nonempty {field}.")
        table[field] = table[field].astype(str).str.strip()


def _dates(table, field):
    _required(table, [field])
    for value in table[field]:
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO YYYY-MM-DD date.") from exc


def _ids(table, fields, unique):
    for field in fields:
        table[field] = [validate_stable_id(v, field) for v in table[field]]
    validate_unique_ids(table[unique], unique)


def validate_transport_scenarios(table):
    out = _schema(table, TRANSPORT_SCENARIO_COLUMNS, "Transport scenario")
    if out.empty:
        return out
    _ids(out, ["transport_scenario_id"], "transport_scenario_id")
    _required(out, ["origin_scope", "destination_scope", "transport_mode", "vehicle_class",
                    "load_factor_basis", "source_status", "source_reference"])
    _dates(out, "retrieval_date")
    if not out.destination_scope.eq("PROJECT_SITE").all():
        raise ValueError("M2.2 destination_scope must be PROJECT_SITE.")
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError("Unsupported transport scenario source_status.")
    # Blank distance is a coverage block, never a default. Invalid supplied
    # distances are hard failures; documented zero distance is a valid zero.
    out["distance_km"] = pd.to_numeric(out.distance_km, errors="raise")
    supplied = out.distance_km.notna()
    if (~np.isfinite(out.loc[supplied, "distance_km"])).any() or (out.loc[supplied, "distance_km"] < 0).any():
        raise ValueError("distance_km must be finite and nonnegative when supplied.")
    out["notes"] = out.notes.fillna("")
    return out


def load_transport_scenarios(path: Path):
    return validate_transport_scenarios(pd.read_csv(path))


def validate_transport_factors(table):
    raw = _schema(table, TRANSPORT_FACTOR_COLUMNS, "Transport factor")
    if raw.empty:
        return raw
    base = validate_environmental_factors(raw.loc[:, ENVIRONMENTAL_FACTOR_COLUMNS])
    meta = raw.loc[:, TRANSPORT_FACTOR_METADATA_COLUMNS].copy()
    _required(meta, TRANSPORT_FACTOR_METADATA_COLUMNS)
    _dates(meta, "retrieval_date")
    out = pd.concat([base, meta], axis=1)
    if (out.indicator_value < 0).any():
        raise ValueError("M2.2 transport factors cannot contain negative/credit values.")
    for _, group in out.groupby("factor_set_id"):
        if any(group[field].nunique(dropna=False) != 1 for field in TRANSPORT_FACTOR_METADATA_COLUMNS):
            raise ValueError("Transport factor-set metadata must be consistent.")
    return out


def load_transport_factors(path: Path):
    return validate_transport_factors(pd.read_csv(path))


def validate_boq_transport_assignments(table, component_boq, scenarios, factors):
    out = _schema(table, BOQ_TRANSPORT_ASSIGNMENT_COLUMNS, "Transport assignment")
    if out.empty:
        return out
    _ids(out, ["assignment_id", "boq_line_id", "scenario_id", "transport_scenario_id",
               "transport_flow_id", "factor_set_id"], "assignment_id")
    out["active"] = [_parse_bool(v, "active") for v in out.active]
    _required(out, ["initial_transport_basis", "mapping_basis", "mapping_reference"])
    if not out.initial_transport_basis.isin(INITIAL_BASES).all():
        raise ValueError("Unsupported initial_transport_basis; replacement transport is out of scope.")
    if not out.mapping_basis.isin(MAPPING_BASES).all():
        raise ValueError("Unsupported transport mapping_basis.")
    active = out.loc[out.active]
    if active.boq_line_id.duplicated().any():
        raise ValueError("Each BoQ line permits at most one active transport assignment.")
    if active.duplicated(["scenario_id", "transport_flow_id"]).any():
        raise ValueError("Duplicate active transport flow in the same scenario.")
    for field, available in (("boq_line_id", component_boq.boq_line_id),
                             ("transport_scenario_id", scenarios.transport_scenario_id),
                             ("factor_set_id", factors.factor_set_id)):
        if not set(out[field]).issubset(set(available)):
            raise ValueError(f"Unknown transport assignment {field}.")
    boq = component_boq.set_index("boq_line_id")
    factor_sets = factors.drop_duplicates("factor_set_id").set_index("factor_set_id")
    routes = scenarios.set_index("transport_scenario_id")
    for row in out.itertuples(index=False):
        b, f, s = boq.loc[row.boq_line_id], factor_sets.loc[row.factor_set_id], routes.loc[row.transport_scenario_id]
        if row.scenario_id != b.scenario_id:
            raise ValueError("Transport assignment scenario_id conflicts with BoQ parent; scope leakage blocked.")
        if b.assessment_role != "ASSESSMENT_INVENTORY":
            raise ValueError("INFORMATION_ONLY BoQ lines cannot receive transport assignments.")
        synthetic = (f.source_type == "TEST_ONLY_SYNTHETIC" or s.source_status == "TEST_ONLY_SYNTHETIC"
                     or b.source_status == "TEST_ONLY_SYNTHETIC")
        if synthetic and row.mapping_basis != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic transport data require TEST_ONLY_SYNTHETIC mapping.")
    out["notes"] = out.notes.fillna("")
    return out


def load_boq_transport_assignments(path: Path, component_boq, scenarios, factors):
    return validate_boq_transport_assignments(pd.read_csv(path), component_boq, scenarios, factors)


def _states(components):
    if components.component_instance_id.duplicated().any():
        raise ValueError("Ambiguous component identity in transport scope.")
    out = components.copy()
    if "initial_component_state" not in out:
        out["initial_component_state"] = "NEW_AT_T0"
    # Mirrors the legacy NEW_AT_T0 compatibility contract without deriving age.
    out["initial_component_state"] = out.initial_component_state.fillna("NEW_AT_T0").replace("", "NEW_AT_T0")
    if not out.initial_component_state.isin({"NEW_AT_T0", "RETAINED_EXISTING"}).all():
        raise ValueError("Unsupported initial_component_state in transport scope.")
    return out.set_index("component_instance_id", drop=False)


def build_a4_transport_compatibility(components, component_boq, scenarios, factors, assignments):
    """Resolve mass, route, factor and initial-event semantics before arithmetic."""
    parents = _states(components)
    rows = []
    routes = scenarios.set_index("transport_scenario_id", drop=False)
    boq = component_boq.set_index("boq_line_id", drop=False)
    for a in assignments.loc[assignments.active.eq(True)].itertuples(index=False):
        b = boq.loc[a.boq_line_id]
        if b.component_instance_id not in parents.index:
            continue  # Calling a specific inventory never imports another scope.
        p = parents.loc[b.component_instance_id]
        if b.scenario_id != p.scenario_id or b.comparison_lineage_id != p.comparison_lineage_id:
            raise ValueError("Transport BoQ identity conflicts with component parent.")
        s = routes.loc[a.transport_scenario_id]
        fs = factors.loc[factors.factor_set_id.eq(a.factor_set_id)]
        f = fs.iloc[0]
        gwp = fs.loc[fs.indicator_id.eq("GWP_TOTAL") & fs.module_scope.eq("A4")]
        mass = resolve_boq_declared_unit_compatibility(b, "kg")
        kg = float(mass["resolved_activity_quantity"])
        if mass["unit_compatibility_status"] != "INCOMPATIBLE_UNIT" and (not np.isfinite(kg) or kg <= 0):
            raise ValueError("Resolved transport mass must be finite and positive.")
        status, reason = "PASS_INITIAL_TRANSPORT", "Explicit initial transport, mass, distance and GWP_TOTAL factor gates pass."
        if p.initial_component_state == "RETAINED_EXISTING" and a.initial_transport_basis != "DOCUMENTED_RETAINED_T0_TRANSPORT":
            status, reason = "BLOCKED_RETAINED_NO_DOCUMENTED_T0_TRANSPORT", "Historical retained components receive no inferred initial transport."
        elif p.initial_component_state == "NEW_AT_T0" and a.initial_transport_basis != "NEW_INSTALLATION":
            status, reason = "BLOCKED_INITIAL_STATE_BASIS_CONFLICT", "Retained transport declaration conflicts with NEW_AT_T0 component."
        elif mass["unit_compatibility_status"] == "INCOMPATIBLE_UNIT":
            status, reason = "BLOCKED_MASS_MISSING", "No mass-unit quantity or documented total-mass bridge."
        elif pd.isna(s.distance_km):
            status, reason = "BLOCKED_DISTANCE_MISSING", "Explicit distance_km is missing; no default is allowed."
        elif f.declared_unit != "tkm":
            status, reason = "BLOCKED_TRANSPORT_FACTOR_UNIT", "Transport factor must use kgCO2e per tonne-km."
        elif not fs.indicator_id.eq("GWP_TOTAL").any():
            status, reason = "BLOCKED_GWP_TOTAL_MISSING", "Disaggregated indicators are never implicitly summed."
        elif len(gwp) != 1:
            status, reason = "BLOCKED_A4_FACTOR_SCOPE", "Exactly one GWP_TOTAL A4 transport-process record is required."
        elif any(s[field] != f[field] for field in ("transport_mode", "vehicle_class", "load_factor_basis")):
            status, reason = "BLOCKED_TRANSPORT_FACTOR_BASIS", "Route mode, vehicle and load basis must match the documented factor basis."
        tkm = kg / 1000.0 * float(s.distance_km) if status.startswith("PASS_") else np.nan
        if status.startswith("PASS_") and not np.isfinite(tkm):
            raise ValueError("Nonfinite tonne-km activity.")
        rows.append(dict(zip(A4_COMPATIBILITY_COLUMNS, (
            a.assignment_id, b.boq_line_id, b.scenario_id, b.component_instance_id,
            b.comparison_lineage_id, p.initial_component_state, a.initial_transport_basis,
            s.transport_scenario_id, a.transport_flow_id, a.factor_set_id,
            gwp.iloc[0].factor_record_id if len(gwp) == 1 else pd.NA,
            s.origin_scope, s.destination_scope, s.transport_mode, s.vehicle_class,
            s.load_factor_basis, f.factor_system_boundary, b.quantity, b.quantity_unit,
            kg, mass["conversion_method"], b.source_reference, s.distance_km,
            s.source_reference, s.retrieval_date, f.retrieval_date, tkm, "tkm", status, reason,
        ))))
    return pd.DataFrame(rows, columns=A4_COMPATIBILITY_COLUMNS)


def build_a4_transport_coverage(components, component_boq, compatibility):
    parents = _states(components)
    gates = compatibility.set_index("boq_line_id", drop=False)
    rows = []
    for b in component_boq.loc[component_boq.assessment_role.eq("ASSESSMENT_INVENTORY")].itertuples(index=False):
        if b.component_instance_id not in parents.index:
            continue
        state = parents.loc[b.component_instance_id].initial_component_state
        if b.boq_line_id in gates.index:
            g = gates.loc[b.boq_line_id]
            assignment, status, reason = g.assignment_id, g.compatibility_gate_status, g.reason
        elif state == "RETAINED_EXISTING":
            assignment, status, reason = pd.NA, "NOT_APPLICABLE_RETAINED_NO_T0_TRANSPORT", "No t=0 movement is documented; historical A4 excluded."
        else:
            assignment, status, reason = pd.NA, "BLOCKED_TRANSPORT_ASSIGNMENT_MISSING", "No active explicit transport assignment."
        rows.append((b.boq_line_id, b.scenario_id, b.component_instance_id, state, assignment, status, reason))
    return pd.DataFrame(rows, columns=A4_COVERAGE_COLUMNS)


def build_a4_transport_consequences(component_boq, factors, assignments, compatibility, future_ids):
    ids = list(future_ids)
    if any(isinstance(v, (bool, np.bool_)) or not np.isfinite(v) or int(v) != v or v < 0 for v in ids):
        raise ValueError("Transport future IDs must be nonnegative integers.")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate future IDs would double-count initial transport.")
    boq = component_boq.set_index("boq_line_id", drop=False)
    fl = factors.set_index("factor_record_id", drop=False)
    al = assignments.set_index("assignment_id", drop=False)
    rows = []
    for c in compatibility.loc[compatibility.compatibility_gate_status.str.startswith("PASS_")].itertuples(index=False):
        b, f, a = boq.loc[c.boq_line_id], fl.loc[c.factor_record_id], al.loc[c.assignment_id]
        for fid in ids:
            rows.append({
                "carbon_consequence_id": _stable_id("cc", "A4_T0", int(fid), c.component_instance_id,
                                                    c.boq_line_id, c.transport_flow_id, f.factor_record_id),
                "future_id": int(fid), "scenario_id": c.scenario_id,
                "component_instance_id": c.component_instance_id, "comparison_lineage_id": c.comparison_lineage_id,
                "component_generation": 0, "consequence_type": "INITIAL_TRANSPORT_TO_SITE",
                "lifecycle_event_id": pd.NA, "source_event_type": "T0_INITIAL_TRANSPORT",
                "event_time_years": 0.0, "boq_line_id": b.boq_line_id,
                "material_or_product_id": b.material_or_product_id, "assignment_id": a.assignment_id,
                "factor_set_id": f.factor_set_id, "factor_record_id": f.factor_record_id,
                "dataset_id": f.dataset_id, "factor_product_or_process_id": f.product_or_process_id,
                "factor_declared_unit": f.declared_unit, "factor_reference_year": int(f.reference_year),
                "indicator_id": "GWP_TOTAL", "source_factor_module_scope": "A4", "reported_module": "A4",
                "boq_quantity": float(b.quantity), "boq_unit": b.quantity_unit,
                "resolved_activity_quantity": float(c.resolved_activity_quantity), "resolved_activity_unit": "tkm",
                "indicator_value_per_declared_unit": float(f.indicator_value), "indicator_unit": f.indicator_unit,
                "gwp_kgco2e": float(c.resolved_activity_quantity) * float(f.indicator_value),
                "mapping_basis": a.mapping_basis, "conversion_method": c.mass_conversion_method + "_X_KM_DIV_1000",
                "source_type": f.source_type, "source_citation": f.source_citation,
                "verification_status": f.verification_status, "data_quality_status": f.data_quality_status,
                "license_status": f.license_status, "redistribution_allowed": bool(f.redistribution_allowed),
                "factor_uncertainty_mode": f.uncertainty_mode, "factor_uncertainty_semantics": f.uncertainty_semantics,
                "factor_uncertainty_applied": False, "factor_temporal_basis": "STATIC_REFERENCE_FACTOR",
                "provenance_status": "CENTRAL_FACTOR_VALUE_ONLY",
            })
    return validate_a4_transport_ledger(pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS))


def validate_a4_transport_ledger(ledger):
    out = _schema(ledger, CARBON_CONSEQUENCE_COLUMNS, "A4 consequence")
    if out.empty:
        return out
    if out.carbon_consequence_id.duplicated().any() or out.duplicated(["future_id", "scenario_id", "boq_line_id"]).any():
        raise ValueError("Duplicate initial A4 consequence/flow.")
    expected = {"consequence_type": "INITIAL_TRANSPORT_TO_SITE", "reported_module": "A4",
                "source_factor_module_scope": "A4", "source_event_type": "T0_INITIAL_TRANSPORT",
                "event_time_years": 0.0, "component_generation": 0, "indicator_id": "GWP_TOTAL",
                "factor_declared_unit": "tkm", "resolved_activity_unit": "tkm", "indicator_unit": "kgco2e",
                "factor_uncertainty_applied": False, "factor_temporal_basis": "STATIC_REFERENCE_FACTOR"}
    for field, value in expected.items():
        if not out[field].eq(value).all():
            raise ValueError(f"Invalid A4 {field}.")
    if out.lifecycle_event_id.notna().any():
        raise ValueError("Initial A4 cannot reference a replacement event.")
    for field in ("future_id", "boq_quantity", "resolved_activity_quantity", "indicator_value_per_declared_unit", "gwp_kgco2e"):
        if not np.isfinite(out[field].to_numpy(dtype=float)).all() or (out[field] < 0).any():
            raise ValueError(f"Nonfinite or negative A4 {field}.")
    if (out.boq_quantity <= 0).any() or ((out.future_id % 1) != 0).any():
        raise ValueError("Invalid A4 BoQ quantity or future identity.")
    if not np.allclose(out.resolved_activity_quantity * out.indicator_value_per_declared_unit,
                       out.gwp_kgco2e, rtol=1e-12, atol=1e-12):
        raise ValueError("A4 impact does not reconcile to tonne-km times factor.")
    return out


def append_a4_to_product_ledger(product_ledger, a4_ledger):
    # Validation is deliberately separate: the frozen M2.1 validator remains
    # product-only, and no A4 row can leak into a product summary.
    validate_carbon_consequence_ledger(product_ledger)
    validate_a4_transport_ledger(a4_ledger)
    if a4_ledger.empty:
        return product_ledger.copy()
    combined = pd.concat([t for t in (product_ledger, a4_ledger) if not t.empty], ignore_index=True)
    if combined.carbon_consequence_id.duplicated().any():
        raise ValueError("Product/A4 consequence ID collision.")
    return combined


def build_a4_transport_summary(ledger):
    if ledger.empty:
        return pd.DataFrame(columns=A4_SUMMARY_COLUMNS)
    validate_a4_transport_ledger(ledger)
    out = ledger.groupby(["future_id", "scenario_id", "reported_module"], as_index=False).agg(
        assessed_gwp_kgco2e=("gwp_kgco2e", "sum"), consequence_row_count=("carbon_consequence_id", "count"))
    out["assessment_scope"] = "INITIAL_TRANSPORT_TO_SITE_ONLY"
    out["assessment_label"] = "ASSESSED_A4_TRANSPORT_ONLY_NOT_WHOLE_LIFE_CARBON"
    return out.loc[:, A4_SUMMARY_COLUMNS].sort_values(["future_id", "scenario_id"]).reset_index(drop=True)


def a4_transport_engine_status(coverage, ledger):
    passed = int(coverage.compatibility_gate_status.str.startswith("PASS_").sum())
    blocked = int(coverage.compatibility_gate_status.str.startswith("BLOCKED_").sum())
    na = int(coverage.compatibility_gate_status.str.startswith("NOT_APPLICABLE_").sum())
    status = ("NO_ASSESSMENT_BOQ_LINES" if coverage.empty else
              "NOT_APPLICABLE_NO_INITIAL_TRANSPORT" if na == len(coverage) else
              "NO_EXECUTABLE_A4_TRANSPORT_MAPPING" if passed == 0 else
              "PARTIAL_EXECUTABLE_A4_TRANSPORT_MAPPING" if blocked else "EXECUTABLE_A4_TRANSPORT_MAPPING_AVAILABLE")
    return {"status": status, "assessment_boq_lines": len(coverage), "gate_pass_lines": passed,
            "blocked_lines": blocked, "not_applicable_lines": na, "carbon_consequence_rows": len(ledger),
            "implemented_modules": ["A4_INITIAL_TRANSPORT"], "executed_indicator": "GWP_TOTAL",
            "replacement_transport_included": False, "carbon_discounting_applied": False,
            "factor_uncertainty_applied": False, "missing_data_treated_as_zero": False,
            "whole_life_carbon_generated": False, "headline_carbon_generated": False,
            "coverage_denominator_scope": "CURRENT_ASSESSMENT_BOQ_LINES_ONLY",
            "claim": "Assessed initial A4 transport only; missing routes/mass/factors remain unassessed. No whole-building coverage or whole-life carbon claim."}


def assess_initial_transport(components, component_boq, scenarios, factors, assignments, future_ids):
    """Validated public entry point; no lifecycle event input or random draws."""
    scenarios = validate_transport_scenarios(scenarios)
    factors = validate_transport_factors(factors)
    assignments = validate_boq_transport_assignments(assignments, component_boq, scenarios, factors)
    gates = build_a4_transport_compatibility(components, component_boq, scenarios, factors, assignments)
    coverage = build_a4_transport_coverage(components, component_boq, gates)
    ledger = build_a4_transport_consequences(component_boq, factors, assignments, gates, future_ids)
    return gates, coverage, ledger, build_a4_transport_summary(ledger), a4_transport_engine_status(coverage, ledger)
