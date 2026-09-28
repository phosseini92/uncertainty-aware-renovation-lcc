"""M2.4: initial A5.2 construction/installation and A5.3 current-construction waste.

Scope is deliberately narrow and additive:
- A5.2 construction/installation activities at t0;
- A5.3 waste arising from the current installation/construction process at t0;
- explicit process registry + explicit BoQ assignment;
- GWP_TOTAL, central factor values, no factor sampling;
- no A5.1 pre-construction removal, no A5.4 worker transport;
- no B4 installation/waste consequences in this milestone.

A5.1 is intentionally excluded because the audited v3 architecture requires a
separate preconstruction-removal inventory so removed existing works cannot be
double counted as current-construction waste.
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
    normalize_declared_unit, normalize_indicator_unit, _parse_bool,
)
from physical_quantities import normalize_physical_unit
from identity import validate_stable_id, validate_unique_ids

CONSTRUCTION_PROCESS_SCENARIO_COLUMNS = (
    "construction_process_scenario_id", "activity_type", "activity_unit", "factor_set_id",
    "source_status", "source_reference", "retrieval_date", "notes",
)
BOQ_CONSTRUCTION_PROCESS_ASSIGNMENT_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "construction_process_scenario_id",
    "construction_flow_id", "active", "activity_basis", "activity_quantity",
    "waste_basis", "waste_rate", "waste_quantity", "waste_unit", "waste_factor_set_id",
    "mapping_basis", "mapping_reference", "notes",
)
A5_COMPATIBILITY_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "component_instance_id",
    "comparison_lineage_id", "construction_process_scenario_id", "construction_flow_id",
    "activity_type", "activity_basis", "activity_quantity", "activity_unit",
    "process_factor_set_id", "process_factor_record_id", "process_factor_declared_unit",
    "waste_basis", "waste_rate", "waste_quantity", "waste_unit",
    "waste_factor_set_id", "waste_factor_record_id", "waste_factor_declared_unit",
    "a5_2_gate_status", "a5_2_reason", "a5_3_gate_status", "a5_3_reason",
)
A5_COVERAGE_COLUMNS = (
    "boq_line_id", "scenario_id", "component_instance_id", "assignment_id",
    "a5_2_gate_status", "a5_2_reason", "a5_3_gate_status", "a5_3_reason",
)
A5_SUMMARY_COLUMNS = (
    "future_id", "scenario_id", "assessment_scope", "reported_module",
    "assessed_gwp_kgco2e", "consequence_row_count", "assessment_label",
)

SOURCE_STATUSES = {"DOCUMENTED_PROJECT_DATA", "PUBLIC_DOCUMENTED_DATA", "TEST_ONLY_SYNTHETIC"}
MAPPING_BASES = {"DOCUMENTED_CONSTRUCTION_PROCESS", "DOCUMENTED_PROXY", "TEST_ONLY_SYNTHETIC"}
ACTIVITY_BASES = {"EXPLICIT_ACTIVITY_QUANTITY"}
WASTE_BASES = {"NONE", "BOQ_WASTE_RATE", "EXPLICIT_WASTE_QUANTITY"}
ACTIVITY_TYPES = {"ELECTRICITY", "FUEL", "EQUIPMENT", "MATERIAL_HANDLING", "GENERIC_INSTALLATION"}


def _schema(table, columns, label):
    missing, extra = set(columns) - set(table), set(table) - set(columns)
    if missing or extra:
        raise ValueError(f"{label} schema: missing={sorted(missing)}, extra={sorted(extra)}")
    return table.loc[:, columns].copy()


def _required(table, fields):
    for field in fields:
        if table[field].isna().any() or table[field].astype(str).str.strip().eq("").any():
            raise ValueError(f"A5 input requires nonempty {field}.")
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


def validate_construction_process_scenarios(table, factors):
    out = _schema(table, CONSTRUCTION_PROCESS_SCENARIO_COLUMNS, "Construction process scenario")
    if out.empty:
        return out
    _ids(out, ["construction_process_scenario_id", "factor_set_id"], "construction_process_scenario_id")
    _required(out, ["activity_type", "activity_unit", "source_status", "source_reference"])
    _dates(out, "retrieval_date")
    out["activity_type"] = out.activity_type.str.upper()
    if not out.activity_type.isin(ACTIVITY_TYPES).all():
        raise ValueError("Unsupported construction activity_type.")
    out["activity_unit"] = [normalize_declared_unit(v) for v in out.activity_unit]
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError("Unsupported construction process source_status.")
    if not set(out.factor_set_id).issubset(set(factors.factor_set_id)):
        raise ValueError("Unknown construction-process factor_set_id.")
    out["notes"] = out.notes.fillna("")
    return out


def load_construction_process_scenarios(path: Path, factors):
    return validate_construction_process_scenarios(pd.read_csv(path), factors)


def validate_boq_construction_process_assignments(table, component_boq, process_scenarios, factors):
    out = _schema(table, BOQ_CONSTRUCTION_PROCESS_ASSIGNMENT_COLUMNS, "Construction process assignment")
    if out.empty:
        return out
    _ids(out, ["assignment_id", "boq_line_id", "scenario_id", "construction_process_scenario_id",
               "construction_flow_id"], "assignment_id")
    # waste factor may be blank only for NONE
    out["active"] = [_parse_bool(v, "active") for v in out.active]
    _required(out, ["activity_basis", "waste_basis", "mapping_basis", "mapping_reference"])
    if not out.activity_basis.isin(ACTIVITY_BASES).all():
        raise ValueError("M2.4 supports EXPLICIT_ACTIVITY_QUANTITY only.")
    if not out.waste_basis.isin(WASTE_BASES).all():
        raise ValueError("Unsupported waste_basis.")
    if not out.mapping_basis.isin(MAPPING_BASES).all():
        raise ValueError("Unsupported A5 mapping_basis.")
    out["activity_quantity"] = pd.to_numeric(out.activity_quantity, errors="raise")
    if (~np.isfinite(out.activity_quantity)).any() or (out.activity_quantity <= 0).any():
        raise ValueError("activity_quantity must be finite and strictly positive.")
    out["waste_rate"] = pd.to_numeric(out.waste_rate, errors="coerce")
    out["waste_quantity"] = pd.to_numeric(out.waste_quantity, errors="coerce")
    out["waste_unit"] = out.waste_unit.fillna("").astype(str).str.strip()
    out["waste_factor_set_id"] = out.waste_factor_set_id.fillna("").astype(str).str.strip()
    out["notes"] = out.notes.fillna("")

    active = out.loc[out.active]
    if active.duplicated(["boq_line_id", "construction_process_scenario_id"]).any():
        raise ValueError("Each BoQ/process pair permits at most one active construction assignment.")
    if active.duplicated(["scenario_id", "construction_flow_id"]).any():
        raise ValueError("Duplicate active construction flow in the same scenario.")

    boq = component_boq.set_index("boq_line_id", drop=False)
    proc = process_scenarios.set_index("construction_process_scenario_id", drop=False)
    factor_ids = set(factors.factor_set_id)
    for row in out.itertuples(index=False):
        if row.boq_line_id not in boq.index:
            raise ValueError("Unknown construction assignment boq_line_id.")
        if row.construction_process_scenario_id not in proc.index:
            raise ValueError("Unknown construction_process_scenario_id.")
        b = boq.loc[row.boq_line_id]
        p = proc.loc[row.construction_process_scenario_id]
        if row.scenario_id != b.scenario_id:
            raise ValueError("Construction assignment scenario_id conflicts with BoQ parent; scope leakage blocked.")
        if b.assessment_role != "ASSESSMENT_INVENTORY":
            raise ValueError("INFORMATION_ONLY BoQ lines cannot receive construction-process assignments.")
        if row.waste_basis == "NONE":
            if pd.notna(row.waste_rate) or pd.notna(row.waste_quantity) or row.waste_unit or row.waste_factor_set_id:
                raise ValueError("waste_basis=NONE cannot carry waste quantity/rate/unit/factor.")
        elif row.waste_basis == "BOQ_WASTE_RATE":
            if pd.isna(row.waste_rate) or not np.isfinite(row.waste_rate) or row.waste_rate < 0:
                raise ValueError("BOQ_WASTE_RATE requires a finite nonnegative waste_rate.")
            if pd.notna(row.waste_quantity) or row.waste_unit:
                raise ValueError("BOQ_WASTE_RATE cannot also declare explicit waste_quantity/waste_unit.")
            if not row.waste_factor_set_id:
                raise ValueError("BOQ_WASTE_RATE requires waste_factor_set_id.")
        elif row.waste_basis == "EXPLICIT_WASTE_QUANTITY":
            if pd.isna(row.waste_quantity) or not np.isfinite(row.waste_quantity) or row.waste_quantity < 0:
                raise ValueError("EXPLICIT_WASTE_QUANTITY requires finite nonnegative waste_quantity.")
            if not row.waste_unit or not row.waste_factor_set_id:
                raise ValueError("EXPLICIT_WASTE_QUANTITY requires waste_unit and waste_factor_set_id.")
            normalize_physical_unit(row.waste_unit)
            if pd.notna(row.waste_rate):
                raise ValueError("EXPLICIT_WASTE_QUANTITY cannot also declare waste_rate.")
        if row.waste_factor_set_id and row.waste_factor_set_id not in factor_ids:
            raise ValueError("Unknown A5.3 waste_factor_set_id.")
        synthetic = (b.source_status == "TEST_ONLY_SYNTHETIC" or p.source_status == "TEST_ONLY_SYNTHETIC")
        if synthetic and row.mapping_basis != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic A5 data require TEST_ONLY_SYNTHETIC mapping.")
    return out


def load_boq_construction_process_assignments(path: Path, component_boq, process_scenarios, factors):
    return validate_boq_construction_process_assignments(
        pd.read_csv(path), component_boq, process_scenarios, factors)


def _gwp_factor(factors, factor_set_id, module):
    rows = factors.loc[(factors.factor_set_id.eq(factor_set_id)) &
                       (factors.indicator_id.eq("GWP_TOTAL")) &
                       (factors.module_scope.eq(module))]
    if rows.empty:
        return None
    if len(rows) != 1:
        raise ValueError(f"A5 factor set {factor_set_id!r} must have exactly one GWP_TOTAL/{module} record.")
    return rows.iloc[0]


def _convert_explicit_quantity(quantity, unit, factor_unit):
    unit = normalize_declared_unit(unit)
    factor_unit = normalize_declared_unit(factor_unit)
    q = float(quantity)
    if unit == factor_unit:
        return q, factor_unit, "EXACT_UNIT"
    if unit == "kg" and factor_unit == "t":
        return q / 1000.0, "t", "KG_TO_TONNE"
    if unit == "t" and factor_unit == "kg":
        return q * 1000.0, "kg", "TONNE_TO_KG"
    return np.nan, factor_unit, "NONE"


def _resolve_waste(row, boq, waste_factor):
    if row.waste_basis == "NONE":
        return None
    factor_unit = str(waste_factor.declared_unit)
    if row.waste_basis == "EXPLICIT_WASTE_QUANTITY":
        qty, unit, method = _convert_explicit_quantity(row.waste_quantity, row.waste_unit, factor_unit)
        return qty, unit, method, float(row.waste_quantity), normalize_physical_unit(row.waste_unit)
    # BOQ_WASTE_RATE: derive only from documented BoQ physical quantity/mass.
    rate = float(row.waste_rate)
    bunit = normalize_physical_unit(boq.quantity_unit)
    if factor_unit == bunit:
        base = float(boq.quantity)
        return base * rate, factor_unit, "BOQ_QUANTITY_X_WASTE_RATE", base * rate, bunit
    mass = None if pd.isna(boq.mass_kg) else float(boq.mass_kg)
    if factor_unit == "kg" and mass is not None:
        return mass * rate, "kg", "DOCUMENTED_MASS_X_WASTE_RATE", mass * rate, "kg"
    if factor_unit == "t" and mass is not None:
        return mass * rate / 1000.0, "t", "DOCUMENTED_MASS_X_WASTE_RATE_KG_TO_TONNE", mass * rate, "kg"
    if bunit == "kg" and factor_unit == "t":
        waste_kg = float(boq.quantity) * rate
        return waste_kg / 1000.0, "t", "BOQ_KG_X_WASTE_RATE_TO_TONNE", waste_kg, "kg"
    if bunit == "t" and factor_unit == "kg":
        waste_t = float(boq.quantity) * rate
        return waste_t * 1000.0, "kg", "BOQ_TONNE_X_WASTE_RATE_TO_KG", waste_t, "t"
    return np.nan, factor_unit, "NONE", np.nan, bunit


def build_a5_compatibility(component_boq, process_scenarios, factors, assignments):
    if assignments.empty:
        return pd.DataFrame(columns=A5_COMPATIBILITY_COLUMNS)
    boq = component_boq.set_index("boq_line_id", drop=False)
    proc = process_scenarios.set_index("construction_process_scenario_id", drop=False)
    rows = []
    for a in assignments.loc[assignments.active.eq(True)].itertuples(index=False):
        b = boq.loc[a.boq_line_id]
        p = proc.loc[a.construction_process_scenario_id]
        pf = _gwp_factor(factors, p.factor_set_id, "A5.2")
        if pf is None:
            a52_gate, a52_reason = "BLOCKED_A5_2_GWP_TOTAL_MISSING", "Process factor set lacks GWP_TOTAL scoped exactly to A5.2."
            pfrid = pd.NA; pfunit = pd.NA
        else:
            resolved, _, method = _convert_explicit_quantity(a.activity_quantity, p.activity_unit, pf.declared_unit)
            if pd.isna(resolved):
                a52_gate, a52_reason = "BLOCKED_A5_2_ACTIVITY_UNIT", "Explicit activity unit is incompatible with A5.2 factor declared unit."
            else:
                a52_gate = "PASS_TEST_ONLY_SYNTHETIC" if a.mapping_basis == "TEST_ONLY_SYNTHETIC" else "PASS_DOCUMENTED_A5_2_PROCESS"
                a52_reason = "Explicit construction activity and A5.2 GWP_TOTAL factor are executable."
            pfrid, pfunit = pf.factor_record_id, pf.declared_unit

        if a.waste_basis == "NONE":
            a53_gate, a53_reason = "NOT_APPLICABLE_NO_CURRENT_CONSTRUCTION_WASTE", "No A5.3 current-construction waste flow is declared."
            wfrid = pd.NA; wfunit = pd.NA
        else:
            wf = _gwp_factor(factors, a.waste_factor_set_id, "A5.3")
            if wf is None:
                a53_gate, a53_reason = "BLOCKED_A5_3_GWP_TOTAL_MISSING", "Waste factor set lacks GWP_TOTAL scoped exactly to A5.3."
                wfrid = pd.NA; wfunit = pd.NA
            else:
                w = _resolve_waste(a, b, wf)
                if w is None or pd.isna(w[0]):
                    a53_gate, a53_reason = "BLOCKED_A5_3_WASTE_UNIT_OR_MASS", "Waste quantity cannot be reconciled explicitly with the A5.3 factor declared unit."
                else:
                    a53_gate = "PASS_TEST_ONLY_SYNTHETIC" if a.mapping_basis == "TEST_ONLY_SYNTHETIC" else "PASS_DOCUMENTED_A5_3_WASTE"
                    a53_reason = "Current-construction waste quantity and A5.3 GWP_TOTAL factor are executable."
                wfrid, wfunit = wf.factor_record_id, wf.declared_unit
        rows.append({
            "assignment_id": a.assignment_id, "boq_line_id": a.boq_line_id, "scenario_id": a.scenario_id,
            "component_instance_id": b.component_instance_id, "comparison_lineage_id": b.comparison_lineage_id,
            "construction_process_scenario_id": a.construction_process_scenario_id, "construction_flow_id": a.construction_flow_id,
            "activity_type": p.activity_type, "activity_basis": a.activity_basis, "activity_quantity": float(a.activity_quantity),
            "activity_unit": p.activity_unit, "process_factor_set_id": p.factor_set_id,
            "process_factor_record_id": pfrid, "process_factor_declared_unit": pfunit,
            "waste_basis": a.waste_basis, "waste_rate": a.waste_rate, "waste_quantity": a.waste_quantity,
            "waste_unit": a.waste_unit, "waste_factor_set_id": a.waste_factor_set_id,
            "waste_factor_record_id": wfrid, "waste_factor_declared_unit": wfunit,
            "a5_2_gate_status": a52_gate, "a5_2_reason": a52_reason,
            "a5_3_gate_status": a53_gate, "a5_3_reason": a53_reason,
        })
    return pd.DataFrame(rows, columns=A5_COMPATIBILITY_COLUMNS)


def build_a5_coverage(component_boq, assignments, compatibility):
    rows = []
    active = assignments.loc[assignments.active.eq(True)] if not assignments.empty else assignments
    comp_lookup = compatibility.set_index("boq_line_id", drop=False) if not compatibility.empty else None
    assigned = set(active.boq_line_id) if not active.empty else set()
    for b in component_boq.loc[component_boq.assessment_role.eq("ASSESSMENT_INVENTORY")].itertuples(index=False):
        if b.boq_line_id not in assigned:
            rows.append({"boq_line_id": b.boq_line_id, "scenario_id": b.scenario_id,
                         "component_instance_id": b.component_instance_id, "assignment_id": pd.NA,
                         "a5_2_gate_status": "BLOCKED_CONSTRUCTION_ASSIGNMENT_MISSING",
                         "a5_2_reason": "No active construction-process assignment.",
                         "a5_3_gate_status": "BLOCKED_CONSTRUCTION_ASSIGNMENT_MISSING",
                         "a5_3_reason": "No active construction-process assignment."})
        else:
            c = comp_lookup.loc[b.boq_line_id]
            rows.append({"boq_line_id": b.boq_line_id, "scenario_id": b.scenario_id,
                         "component_instance_id": b.component_instance_id, "assignment_id": c.assignment_id,
                         "a5_2_gate_status": c.a5_2_gate_status, "a5_2_reason": c.a5_2_reason,
                         "a5_3_gate_status": c.a5_3_gate_status, "a5_3_reason": c.a5_3_reason})
    return pd.DataFrame(rows, columns=A5_COVERAGE_COLUMNS)


def _base_row(fid, b, a, factor, consequence_type, reported_module, resolved_qty, resolved_unit,
              conversion_method, source_event_type, factor_set_id, factor_record_id, mapping_basis):
    impact = float(resolved_qty) * float(factor.indicator_value)
    return {
        "carbon_consequence_id": _stable_id("cc", consequence_type, fid, b.component_instance_id, b.boq_line_id, a.assignment_id, factor_record_id),
        "future_id": int(fid), "scenario_id": str(b.scenario_id), "component_instance_id": str(b.component_instance_id),
        "comparison_lineage_id": str(b.comparison_lineage_id), "component_generation": 0,
        "consequence_type": consequence_type, "lifecycle_event_id": pd.NA, "source_event_type": source_event_type,
        "event_time_years": 0.0, "boq_line_id": str(b.boq_line_id), "material_or_product_id": str(b.material_or_product_id),
        "assignment_id": str(a.assignment_id), "factor_set_id": str(factor_set_id), "factor_record_id": str(factor_record_id),
        "dataset_id": str(factor.dataset_id), "factor_product_or_process_id": str(factor.product_or_process_id),
        "factor_declared_unit": str(factor.declared_unit), "factor_reference_year": int(factor.reference_year),
        "indicator_id": "GWP_TOTAL", "source_factor_module_scope": str(factor.module_scope), "reported_module": reported_module,
        "boq_quantity": float(b.quantity), "boq_unit": str(b.quantity_unit), "resolved_activity_quantity": float(resolved_qty),
        "resolved_activity_unit": str(resolved_unit), "indicator_value_per_declared_unit": float(factor.indicator_value),
        "indicator_unit": str(factor.indicator_unit), "gwp_kgco2e": impact, "mapping_basis": str(mapping_basis),
        "conversion_method": str(conversion_method), "source_type": str(factor.source_type), "source_citation": str(factor.source_citation),
        "verification_status": str(factor.verification_status), "data_quality_status": str(factor.data_quality_status),
        "license_status": str(factor.license_status), "redistribution_allowed": bool(factor.redistribution_allowed),
        "factor_uncertainty_mode": str(factor.uncertainty_mode), "factor_uncertainty_semantics": str(factor.uncertainty_semantics),
        "factor_uncertainty_applied": False, "factor_temporal_basis": "STATIC_REFERENCE_FACTOR",
        "provenance_status": "CENTRAL_FACTOR_VALUE_ONLY",
    }


def build_a5_ledger(component_boq, process_scenarios, factors, assignments, compatibility, future_ids):
    if assignments.empty or compatibility.empty:
        return empty_carbon_consequence_ledger()
    boq = component_boq.set_index("boq_line_id", drop=False)
    proc = process_scenarios.set_index("construction_process_scenario_id", drop=False)
    comp = compatibility.set_index("assignment_id", drop=False)
    rows = []
    for a in assignments.loc[assignments.active.eq(True)].itertuples(index=False):
        b = boq.loc[a.boq_line_id]; p = proc.loc[a.construction_process_scenario_id]; c = comp.loc[a.assignment_id]
        if str(c.a5_2_gate_status).startswith("PASS_"):
            pf = _gwp_factor(factors, p.factor_set_id, "A5.2")
            qty, unit, method = _convert_explicit_quantity(a.activity_quantity, p.activity_unit, pf.declared_unit)
            for fid in future_ids:
                rows.append(_base_row(fid, b, a, pf, "A5_2_CONSTRUCTION_INSTALLATION", "A5.2", qty, unit, method,
                                      "T0_CONSTRUCTION_INSTALLATION", p.factor_set_id, pf.factor_record_id, a.mapping_basis))
        if str(c.a5_3_gate_status).startswith("PASS_"):
            wf = _gwp_factor(factors, a.waste_factor_set_id, "A5.3")
            qty, unit, method, _, _ = _resolve_waste(a, b, wf)
            for fid in future_ids:
                rows.append(_base_row(fid, b, a, wf, "A5_3_CURRENT_CONSTRUCTION_WASTE", "A5.3", qty, unit, method,
                                      "T0_CURRENT_CONSTRUCTION_WASTE", a.waste_factor_set_id, wf.factor_record_id, a.mapping_basis))
    return validate_a5_ledger(pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS)) if rows else empty_carbon_consequence_ledger()


def validate_a5_ledger(ledger):
    out = _schema(ledger, CARBON_CONSEQUENCE_COLUMNS, "A5 consequence")
    if out.empty:
        return out
    if out.carbon_consequence_id.duplicated().any():
        raise ValueError("Duplicate A5 carbon consequence ID.")
    allowed = {
        "A5_2_CONSTRUCTION_INSTALLATION": ("A5.2", "T0_CONSTRUCTION_INSTALLATION"),
        "A5_3_CURRENT_CONSTRUCTION_WASTE": ("A5.3", "T0_CURRENT_CONSTRUCTION_WASTE"),
    }
    if not out.consequence_type.isin(allowed).all():
        raise ValueError("Unsupported A5 consequence_type.")
    for ctype, (module, event) in allowed.items():
        rows = out.loc[out.consequence_type.eq(ctype)]
        if not rows.empty:
            if not rows.reported_module.eq(module).all() or not rows.source_factor_module_scope.eq(module).all():
                raise ValueError(f"{ctype} must use and report {module}.")
            if not rows.source_event_type.eq(event).all():
                raise ValueError(f"Invalid {ctype} source_event_type.")
    if out.lifecycle_event_id.notna().any():
        raise ValueError("Initial A5 consequences are t0 process consequences and do not use replacement lifecycle_event_id.")
    if not out.event_time_years.eq(0.0).all() or not out.component_generation.eq(0).all():
        raise ValueError("M2.4 A5 consequences must occur at t0/generation 0.")
    if not out.indicator_id.eq("GWP_TOTAL").all() or not out.indicator_unit.eq("kgco2e").all():
        raise ValueError("M2.4 executes GWP_TOTAL in kgCO2e only.")
    for field in ("future_id", "boq_quantity", "resolved_activity_quantity", "indicator_value_per_declared_unit", "gwp_kgco2e"):
        vals = pd.to_numeric(out[field], errors="raise")
        if not np.isfinite(vals.to_numpy(dtype=float)).all() or (vals < 0).any():
            raise ValueError(f"Nonfinite or negative A5 {field}.")
    if (out.resolved_activity_quantity < 0).any():
        raise ValueError("A5 activity quantities must be nonnegative.")
    if not np.allclose(out.resolved_activity_quantity * out.indicator_value_per_declared_unit,
                       out.gwp_kgco2e, rtol=1e-12, atol=1e-12):
        raise ValueError("A5 impact does not reconcile to activity times factor.")
    return out


def append_a5_to_combined_ledger(combined_ledger, a5_ledger):
    # Existing subledgers remain validated under their own frozen rules.
    product = combined_ledger.loc[combined_ledger.consequence_type.isin({"INITIAL_PRODUCT_STAGE", "B4_REPLACEMENT_PRODUCT_STAGE"})]
    if not product.empty:
        validate_carbon_consequence_ledger(product)
    if not a5_ledger.empty:
        validate_a5_ledger(a5_ledger)
    out = combined_ledger.copy() if a5_ledger.empty else pd.concat([combined_ledger, a5_ledger], ignore_index=True)
    if not out.empty and out.carbon_consequence_id.duplicated().any():
        raise ValueError("Carbon consequence ID collision after A5 append.")
    return out


def build_a5_summary(ledger):
    if ledger.empty:
        return pd.DataFrame(columns=A5_SUMMARY_COLUMNS)
    validate_a5_ledger(ledger)
    out = ledger.groupby(["future_id", "scenario_id", "reported_module"], as_index=False).agg(
        assessed_gwp_kgco2e=("gwp_kgco2e", "sum"), consequence_row_count=("carbon_consequence_id", "count"))
    out["assessment_scope"] = "INITIAL_A5_2_A5_3_ONLY"
    out["assessment_label"] = "ASSESSED_INITIAL_A5_2_A5_3_ONLY_NOT_WHOLE_LIFE_CARBON"
    return out.loc[:, A5_SUMMARY_COLUMNS].sort_values(["future_id", "scenario_id", "reported_module"]).reset_index(drop=True)


def a5_engine_status(coverage, ledger):
    if coverage.empty:
        status = "NO_ASSESSMENT_BOQ_LINES"
    else:
        p52 = int(coverage.a5_2_gate_status.str.startswith("PASS_").sum())
        p53 = int(coverage.a5_3_gate_status.str.startswith("PASS_").sum())
        blocked = int(coverage.a5_2_gate_status.str.startswith("BLOCKED_").sum() + coverage.a5_3_gate_status.str.startswith("BLOCKED_").sum())
        status = "NO_EXECUTABLE_A5_MAPPING" if (p52 + p53) == 0 else "PARTIAL_EXECUTABLE_A5_MAPPING" if blocked else "EXECUTABLE_A5_MAPPING_AVAILABLE"
    return {
        "status": status,
        "assessment_boq_lines": len(coverage),
        "a5_2_gate_pass_lines": int(coverage.a5_2_gate_status.str.startswith("PASS_").sum()) if not coverage.empty else 0,
        "a5_3_gate_pass_lines": int(coverage.a5_3_gate_status.str.startswith("PASS_").sum()) if not coverage.empty else 0,
        "carbon_consequence_rows": len(ledger),
        "implemented_modules": ["A5.2_CONSTRUCTION_INSTALLATION", "A5.3_CURRENT_CONSTRUCTION_WASTE"],
        "explicitly_deferred": ["A5.1_PRECONSTRUCTION_REMOVAL", "A5.4_WORKER_TRANSPORT", "B4_INSTALLATION_AND_WASTE"],
        "executed_indicator": "GWP_TOTAL", "carbon_discounting_applied": False,
        "factor_uncertainty_applied": False, "missing_data_treated_as_zero": False,
        "whole_life_carbon_generated": False, "headline_carbon_generated": False,
        "claim": "Assessed initial A5.2 construction/installation and A5.3 current-construction waste only; A5.1 removal is excluded until a dedicated removal inventory exists.",
    }


def assess_initial_a5(component_boq, process_scenarios, factors, assignments, future_ids):
    compatibility = build_a5_compatibility(component_boq, process_scenarios, factors, assignments)
    coverage = build_a5_coverage(component_boq, assignments, compatibility)
    ledger = build_a5_ledger(component_boq, process_scenarios, factors, assignments, compatibility, future_ids)
    summary = build_a5_summary(ledger)
    return compatibility, coverage, ledger, summary, a5_engine_status(coverage, ledger)
