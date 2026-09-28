"""M2.6: completion of process consequences attributable to B4 replacement events.

Adds installation, removal, outbound waste transport, waste processing, and
disposal consequences attributable to canonical B4 replacement events. Source
process module scopes are retained in provenance, while every consequence is
reported in B4 to preserve event ownership and avoid A/C double counting.

No service-life resampling occurs here. Missing mappings remain not assessed,
not zero. Environmental-factor uncertainty is retained as metadata but is not
sampled in this milestone.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_consequences import CARBON_CONSEQUENCE_COLUMNS, _stable_id, empty_carbon_consequence_ledger
from environmental_factors import normalize_declared_unit, _parse_bool
from identity import validate_stable_id, validate_unique_ids

B4_EVENT_PROCESS_ASSIGNMENT_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "b4_flow_id", "process_role",
    "factor_registry", "factor_set_id", "expected_source_module", "quantity_basis",
    "activity_quantity", "activity_unit", "distance_km", "active", "mapping_basis",
    "mapping_reference", "source_status", "source_reference", "retrieval_date", "notes",
)
B4_EVENT_PROCESS_COMPATIBILITY_COLUMNS = (
    "assignment_id", "boq_line_id", "scenario_id", "component_instance_id", "comparison_lineage_id",
    "b4_flow_id", "process_role", "factor_registry", "factor_set_id", "factor_record_id",
    "expected_source_module", "factor_declared_unit", "quantity_basis", "activity_quantity",
    "activity_unit", "distance_km", "resolved_quantity_per_event", "resolved_unit",
    "compatibility_gate_status", "reason",
)
B4_EVENT_PROCESS_COVERAGE_COLUMNS = (
    "boq_line_id", "scenario_id", "component_instance_id", "assignment_id", "b4_flow_id",
    "process_role", "replacement_event_count", "compatibility_gate_status", "reason",
)
B4_EVENT_PROCESS_SUMMARY_COLUMNS = (
    "future_id", "scenario_id", "assessment_scope", "reported_module",
    "assessed_gwp_kgco2e", "consequence_row_count", "assessment_label",
)

ROLES = {
    "INSTALLATION": {"registry": "ENVIRONMENTAL", "modules": {"A5.2"}, "ctype": "B4_REPLACEMENT_INSTALLATION"},
    "REMOVAL": {"registry": "ENVIRONMENTAL", "modules": {"A5.1", "C1"}, "ctype": "B4_REPLACEMENT_REMOVAL"},
    "OUTBOUND_WASTE_TRANSPORT": {"registry": "TRANSPORT", "modules": {"A4"}, "ctype": "B4_REPLACEMENT_WASTE_TRANSPORT"},
    "WASTE_PROCESSING": {"registry": "ENVIRONMENTAL", "modules": {"C3"}, "ctype": "B4_REPLACEMENT_WASTE_PROCESSING"},
    "WASTE_DISPOSAL": {"registry": "ENVIRONMENTAL", "modules": {"C4"}, "ctype": "B4_REPLACEMENT_WASTE_DISPOSAL"},
}
QUANTITY_BASES = {"EXPLICIT_ACTIVITY", "BOQ_QUANTITY", "BOQ_MASS", "BOQ_TONNE_KM"}
MAPPING_BASES = {"DOCUMENTED_PROCESS", "DOCUMENTED_PROXY", "TEST_ONLY_SYNTHETIC"}
SOURCE_STATUSES = {"DOCUMENTED_PROJECT_DATA", "PUBLIC_DOCUMENTED_DATA", "TEST_ONLY_SYNTHETIC"}


def _schema(table, cols, label):
    missing, extra = set(cols)-set(table), set(table)-set(cols)
    if missing or extra:
        raise ValueError(f"{label} schema: missing={sorted(missing)}, extra={sorted(extra)}")
    return table.loc[:, cols].copy()


def _factor_row(registry, factor_set_id, expected_module):
    rows = registry.loc[(registry.factor_set_id.eq(factor_set_id)) &
                        (registry.indicator_id.eq("GWP_TOTAL")) &
                        (registry.module_scope.eq(expected_module))]
    if len(rows) != 1:
        return None
    return rows.iloc[0]


def validate_b4_event_process_assignments(table, component_boq, environmental_factors, transport_factors):
    out = _schema(table, B4_EVENT_PROCESS_ASSIGNMENT_COLUMNS, "B4 event process assignment")
    if out.empty:
        return out
    for f in ("assignment_id","boq_line_id","scenario_id","b4_flow_id","factor_set_id"):
        out[f] = [validate_stable_id(v, f) for v in out[f]]
    validate_unique_ids(out.assignment_id, "assignment_id")
    out["active"] = [_parse_bool(v, "active") for v in out.active]
    for f in ("process_role","factor_registry","expected_source_module","quantity_basis","mapping_basis",
              "mapping_reference","source_status","source_reference","retrieval_date"):
        if out[f].isna().any() or out[f].astype(str).str.strip().eq("").any():
            raise ValueError(f"B4 event process assignment requires nonempty {f}.")
        out[f] = out[f].astype(str).str.strip()
    out.process_role = out.process_role.str.upper()
    out.factor_registry = out.factor_registry.str.upper()
    out.expected_source_module = out.expected_source_module.str.upper()
    out.quantity_basis = out.quantity_basis.str.upper()
    out.mapping_basis = out.mapping_basis.str.upper()
    out.source_status = out.source_status.str.upper()
    if not out.process_role.isin(ROLES).all(): raise ValueError("Unsupported B4 process_role.")
    if not out.quantity_basis.isin(QUANTITY_BASES).all(): raise ValueError("Unsupported B4 quantity_basis.")
    if not out.mapping_basis.isin(MAPPING_BASES).all(): raise ValueError("Unsupported B4 mapping_basis.")
    if not out.source_status.isin(SOURCE_STATUSES).all(): raise ValueError("Unsupported B4 source_status.")
    for d in out.retrieval_date:
        if date.fromisoformat(d).isoformat() != d: raise ValueError("retrieval_date must be ISO YYYY-MM-DD.")
    out["activity_quantity"] = pd.to_numeric(out.activity_quantity, errors="coerce")
    out["distance_km"] = pd.to_numeric(out.distance_km, errors="coerce")
    out["activity_unit"] = out.activity_unit.fillna("").astype(str).str.strip()
    out["notes"] = out.notes.fillna("")
    boq = component_boq.set_index("boq_line_id", drop=False)
    env_ids, tf_ids = set(environmental_factors.factor_set_id), set(transport_factors.factor_set_id)
    active = out.loc[out.active]
    if active.duplicated(["scenario_id","b4_flow_id"]).any():
        raise ValueError("Duplicate active B4 event process flow in the same scenario.")
    for r in out.itertuples(index=False):
        if r.boq_line_id not in boq.index: raise ValueError("Unknown B4 event process boq_line_id.")
        b = boq.loc[r.boq_line_id]
        if r.scenario_id != b.scenario_id: raise ValueError("B4 event process scenario scope leakage blocked.")
        if b.assessment_role != "ASSESSMENT_INVENTORY": raise ValueError("INFORMATION_ONLY BoQ cannot receive B4 process assignments.")
        spec = ROLES[r.process_role]
        if r.factor_registry != spec["registry"]: raise ValueError("B4 process_role conflicts with factor_registry.")
        if r.expected_source_module not in spec["modules"]: raise ValueError("B4 process_role conflicts with expected_source_module.")
        ids = env_ids if r.factor_registry == "ENVIRONMENTAL" else tf_ids
        if r.factor_set_id not in ids: raise ValueError("Unknown B4 process factor_set_id.")
        if r.quantity_basis == "EXPLICIT_ACTIVITY":
            if pd.isna(r.activity_quantity) or not np.isfinite(r.activity_quantity) or r.activity_quantity < 0 or not r.activity_unit:
                raise ValueError("EXPLICIT_ACTIVITY requires finite nonnegative activity_quantity and activity_unit.")
            normalize_declared_unit(r.activity_unit)
            if pd.notna(r.distance_km): raise ValueError("EXPLICIT_ACTIVITY cannot declare distance_km.")
        elif r.quantity_basis in {"BOQ_QUANTITY","BOQ_MASS"}:
            if pd.notna(r.activity_quantity) or r.activity_unit or pd.notna(r.distance_km):
                raise ValueError(f"{r.quantity_basis} derives quantity from BoQ and cannot carry explicit activity/distance.")
        else: # BOQ_TONNE_KM
            if pd.notna(r.activity_quantity) or r.activity_unit:
                raise ValueError("BOQ_TONNE_KM cannot carry explicit activity quantity/unit.")
            if pd.isna(r.distance_km) or not np.isfinite(r.distance_km) or r.distance_km < 0:
                raise ValueError("BOQ_TONNE_KM requires finite nonnegative distance_km.")
        synthetic = b.source_status == "TEST_ONLY_SYNTHETIC" or r.source_status == "TEST_ONLY_SYNTHETIC"
        if synthetic and r.mapping_basis != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic B4 mapping requires TEST_ONLY_SYNTHETIC mapping_basis.")
    return out


def load_b4_event_process_assignments(path: Path, component_boq, environmental_factors, transport_factors):
    return validate_b4_event_process_assignments(pd.read_csv(path), component_boq, environmental_factors, transport_factors)


def _resolve_quantity(a, b, factor_unit):
    if a.quantity_basis == "EXPLICIT_ACTIVITY":
        unit = normalize_declared_unit(a.activity_unit)
        if unit != factor_unit: return None, None, "BLOCKED_B4_PROCESS_UNIT_MISMATCH", "Explicit activity unit does not match factor declared unit."
        return float(a.activity_quantity), unit, "PASS_B4_PROCESS_EXPLICIT_ACTIVITY", "Explicit per-event activity quantity."
    if a.quantity_basis == "BOQ_QUANTITY":
        bu = normalize_declared_unit(b.quantity_unit)
        if bu == factor_unit:
            return float(b.quantity), bu, "PASS_B4_PROCESS_BOQ_QUANTITY", "BoQ quantity used per replacement event."
        if {bu,factor_unit} == {"kg","t"}:
            q=float(b.quantity)/1000 if bu=="kg" else float(b.quantity)*1000
            return q, factor_unit, "PASS_B4_PROCESS_BOQ_MASS_CONVERSION", "Explicit kg/t conversion."
        return None,None,"BLOCKED_B4_PROCESS_UNIT_MISMATCH","BoQ quantity unit incompatible with factor."
    mass = float(b.mass_kg) if pd.notna(b.mass_kg) else (float(b.quantity) if str(b.quantity_unit).lower()=="kg" else float(b.quantity)*1000 if str(b.quantity_unit).lower() in {"t","tonne","tonnes"} else np.nan)
    if not np.isfinite(mass) or mass < 0:
        return None,None,"BLOCKED_B4_PROCESS_MASS_MISSING","Documented mass is required."
    if a.quantity_basis == "BOQ_MASS":
        if factor_unit == "kg": return mass,"kg","PASS_B4_PROCESS_BOQ_MASS","Documented BoQ mass."
        if factor_unit == "t": return mass/1000,"t","PASS_B4_PROCESS_BOQ_MASS","Documented BoQ mass converted to tonnes."
        return None,None,"BLOCKED_B4_PROCESS_UNIT_MISMATCH","BOQ_MASS requires kg/t factor."
    if factor_unit != "tkm": return None,None,"BLOCKED_B4_PROCESS_UNIT_MISMATCH","BOQ_TONNE_KM requires tkm factor."
    return mass/1000*float(a.distance_km),"tkm","PASS_B4_PROCESS_TONNE_KM","Documented mass x distance."


def build_b4_event_process_compatibility(component_boq, environmental_factors, transport_factors, assignments):
    rows=[]; boq=component_boq.set_index("boq_line_id",drop=False)
    for a in assignments.loc[assignments.active].itertuples(index=False):
        b=boq.loc[a.boq_line_id]; reg=environmental_factors if a.factor_registry=="ENVIRONMENTAL" else transport_factors
        f=_factor_row(reg,a.factor_set_id,a.expected_source_module)
        if f is None:
            rows.append({"assignment_id":a.assignment_id,"boq_line_id":a.boq_line_id,"scenario_id":a.scenario_id,
                "component_instance_id":b.component_instance_id,"comparison_lineage_id":b.comparison_lineage_id,
                "b4_flow_id":a.b4_flow_id,"process_role":a.process_role,"factor_registry":a.factor_registry,
                "factor_set_id":a.factor_set_id,"factor_record_id":"","expected_source_module":a.expected_source_module,
                "factor_declared_unit":"","quantity_basis":a.quantity_basis,"activity_quantity":a.activity_quantity,
                "activity_unit":a.activity_unit,"distance_km":a.distance_km,"resolved_quantity_per_event":np.nan,
                "resolved_unit":"","compatibility_gate_status":"BLOCKED_B4_PROCESS_GWP_TOTAL_MISSING",
                "reason":"Exact GWP_TOTAL source factor for expected module is missing."})
            continue
        q,u,status,reason=_resolve_quantity(a,b,str(f.declared_unit))
        rows.append({"assignment_id":a.assignment_id,"boq_line_id":a.boq_line_id,"scenario_id":a.scenario_id,
            "component_instance_id":b.component_instance_id,"comparison_lineage_id":b.comparison_lineage_id,
            "b4_flow_id":a.b4_flow_id,"process_role":a.process_role,"factor_registry":a.factor_registry,
            "factor_set_id":a.factor_set_id,"factor_record_id":f.factor_record_id,"expected_source_module":a.expected_source_module,
            "factor_declared_unit":f.declared_unit,"quantity_basis":a.quantity_basis,"activity_quantity":a.activity_quantity,
            "activity_unit":a.activity_unit,"distance_km":a.distance_km,"resolved_quantity_per_event":q,
            "resolved_unit":u or "","compatibility_gate_status":status,"reason":reason})
    return pd.DataFrame(rows,columns=B4_EVENT_PROCESS_COMPATIBILITY_COLUMNS)


def build_b4_event_process_coverage(component_boq, compatibility, event_boq_quantities):
    rows=[]
    if event_boq_quantities.empty:
        event_counts = {}
    else:
        b4_events = event_boq_quantities.loc[event_boq_quantities.event_type.eq("B4_REPLACEMENT")]
        event_counts = b4_events.groupby("boq_line_id").event_id.nunique().to_dict()
    boq=component_boq.set_index("boq_line_id",drop=False)
    for c in compatibility.itertuples(index=False):
        b=boq.loc[c.boq_line_id]; n=int(event_counts.get(c.boq_line_id,0)); status=c.compatibility_gate_status; reason=c.reason
        if n==0 and status.startswith("PASS_"):
            status="NOT_APPLICABLE_NO_B4_EVENTS_WITHIN_RSP"; reason="No canonical B4 replacement event occurs within the selected RSP."
        rows.append({"boq_line_id":c.boq_line_id,"scenario_id":c.scenario_id,"component_instance_id":b.component_instance_id,
                     "assignment_id":c.assignment_id,"b4_flow_id":c.b4_flow_id,"process_role":c.process_role,
                     "replacement_event_count":n,"compatibility_gate_status":status,"reason":reason})
    return pd.DataFrame(rows,columns=B4_EVENT_PROCESS_COVERAGE_COLUMNS)


def build_b4_event_process_ledger(lifecycle_event_ledger,event_boq_quantities,component_boq,environmental_factors,transport_factors,assignments,compatibility):
    if compatibility.empty or event_boq_quantities.empty: return empty_carbon_consequence_ledger()
    passing=compatibility.loc[compatibility.compatibility_gate_status.str.startswith("PASS_")]
    if passing.empty:return empty_carbon_consequence_ledger()
    comp=passing.set_index("assignment_id",drop=False); ass=assignments.set_index("assignment_id",drop=False)
    boq=component_boq.set_index("boq_line_id",drop=False); evsrc=lifecycle_event_ledger.set_index("event_id",drop=False)
    env=environmental_factors.set_index("factor_record_id",drop=False); tf=transport_factors.set_index("factor_record_id",drop=False)
    by_boq={k:g for k,g in passing.groupby("boq_line_id")}; rows=[]
    for ev in event_boq_quantities.itertuples(index=False):
        if ev.boq_line_id not in by_boq:
            continue
        if ev.event_id not in evsrc.index:
            raise ValueError("B4 process bridge references unknown canonical event.")
        source=evsrc.loc[ev.event_id]
        for field, left, right in (
            ("future_id", int(ev.future_id), int(source.future_id)),
            ("scenario_id", str(ev.scenario_id), str(source.scenario_id)),
            ("component_instance_id", str(ev.component_instance_id), str(source.component_instance_id)),
            ("comparison_lineage_id", str(ev.comparison_lineage_id), str(source.comparison_lineage_id)),
            ("component_generation", int(ev.component_generation), int(source.component_generation)),
            ("event_type", str(ev.event_type), str(source.event_type)),
        ):
            if left != right:
                raise ValueError(f"B4 event-BoQ bridge conflicts with canonical lifecycle event for field: {field}")
        if source.event_type!="B4_REPLACEMENT":
            continue
        b=boq.loc[ev.boq_line_id]
        if str(ev.scenario_id) != str(b.scenario_id) or str(ev.component_instance_id) != str(b.component_instance_id) or str(ev.comparison_lineage_id) != str(b.comparison_lineage_id):
            raise ValueError("B4 event-process BoQ scope conflicts with documented component identity.")
        if str(ev.material_or_product_id) != str(b.material_or_product_id):
            raise ValueError("B4 event-process material/product identity conflicts with BoQ line.")
        for c in by_boq[ev.boq_line_id].itertuples(index=False):
            a=ass.loc[c.assignment_id]; f=(env if a.factor_registry=="ENVIRONMENTAL" else tf).loc[c.factor_record_id]
            impact=float(c.resolved_quantity_per_event)*float(f.indicator_value)
            rows.append({
                "carbon_consequence_id":_stable_id("cc","B4_EVENT_PROCESS",source.event_id,a.b4_flow_id,f.factor_record_id),
                "future_id":int(source.future_id),"scenario_id":str(source.scenario_id),"component_instance_id":str(source.component_instance_id),
                "comparison_lineage_id":str(source.comparison_lineage_id),"component_generation":int(source.component_generation),
                "consequence_type":ROLES[a.process_role]["ctype"],"lifecycle_event_id":str(source.event_id),"source_event_type":"B4_REPLACEMENT",
                "event_time_years":float(source.event_time_years),"boq_line_id":str(ev.boq_line_id),"material_or_product_id":str(b.material_or_product_id),
                "assignment_id":str(a.assignment_id),"factor_set_id":str(f.factor_set_id),"factor_record_id":str(f.factor_record_id),
                "dataset_id":str(f.dataset_id),"factor_product_or_process_id":str(f.product_or_process_id),"factor_declared_unit":str(f.declared_unit),
                "factor_reference_year":int(f.reference_year),"indicator_id":"GWP_TOTAL","source_factor_module_scope":str(f.module_scope),"reported_module":"B4",
                "boq_quantity":float(ev.quantity),"boq_unit":str(b.quantity_unit),"resolved_activity_quantity":float(c.resolved_quantity_per_event),
                "resolved_activity_unit":str(c.resolved_unit),"indicator_value_per_declared_unit":float(f.indicator_value),"indicator_unit":str(f.indicator_unit),
                "gwp_kgco2e":impact,"mapping_basis":str(a.mapping_basis),"conversion_method":str(a.quantity_basis),"source_type":str(f.source_type),
                "source_citation":str(f.source_citation),"verification_status":str(f.verification_status),"data_quality_status":str(f.data_quality_status),
                "license_status":str(f.license_status),"redistribution_allowed":bool(f.redistribution_allowed),"factor_uncertainty_mode":str(f.uncertainty_mode),
                "factor_uncertainty_semantics":str(f.uncertainty_semantics),"factor_uncertainty_applied":False,"factor_temporal_basis":"STATIC_REFERENCE_FACTOR",
                "provenance_status":"CENTRAL_FACTOR_VALUE_ONLY",
            })
    out=pd.DataFrame(rows,columns=CARBON_CONSEQUENCE_COLUMNS)
    if not out.empty:
        if out.carbon_consequence_id.duplicated().any(): raise ValueError("Duplicate B4 event-process consequence ID.")
        if not out.reported_module.eq("B4").all() or out.lifecycle_event_id.isna().any(): raise ValueError("Invalid B4 event-process reporting/linkage.")
    return out if not out.empty else empty_carbon_consequence_ledger()


def build_b4_event_process_summary(ledger):
    if ledger.empty:return pd.DataFrame(columns=B4_EVENT_PROCESS_SUMMARY_COLUMNS)
    out=ledger.groupby(["future_id","scenario_id","reported_module"],as_index=False).agg(assessed_gwp_kgco2e=("gwp_kgco2e","sum"),consequence_row_count=("carbon_consequence_id","count"))
    out["assessment_scope"]="B4_REPLACEMENT_EVENT_PROCESSES_ONLY"; out["assessment_label"]="ASSESSED_B4_EVENT_PROCESSES_ONLY_NOT_WHOLE_LIFE_CARBON"
    return out.loc[:,B4_EVENT_PROCESS_SUMMARY_COLUMNS]


def assess_b4_event_processes(component_boq,lifecycle_event_ledger,event_boq_quantities,environmental_factors,transport_factors,assignments):
    assignments=validate_b4_event_process_assignments(assignments,component_boq,environmental_factors,transport_factors)
    comp=build_b4_event_process_compatibility(component_boq,environmental_factors,transport_factors,assignments)
    cov=build_b4_event_process_coverage(component_boq,comp,event_boq_quantities)
    ledger=build_b4_event_process_ledger(lifecycle_event_ledger,event_boq_quantities,component_boq,environmental_factors,transport_factors,assignments,comp)
    passed=int(cov.compatibility_gate_status.str.startswith("PASS_").sum()) if not cov.empty else 0
    blocked=int(cov.compatibility_gate_status.str.startswith("BLOCKED_").sum()) if not cov.empty else 0
    status="NO_B4_EVENT_PROCESS_ASSIGNMENTS" if cov.empty else "NO_EXECUTABLE_B4_EVENT_PROCESS_MAPPING" if passed==0 else "PARTIAL_EXECUTABLE_B4_EVENT_PROCESS_MAPPING" if blocked else "EXECUTABLE_B4_EVENT_PROCESS_MAPPING_AVAILABLE"
    meta={"status":status,"assessment_rows":len(cov),"gate_pass_rows":passed,"blocked_rows":blocked,"carbon_consequence_rows":len(ledger),
          "implemented_modules":["B4_EVENT_PROCESSES"],"reported_module":"B4","factor_uncertainty_applied":False,"missing_data_treated_as_zero":False,
          "whole_life_carbon_generated":False,"headline_carbon_generated":False,
          "claim":"Installation/removal/outbound-waste-transport/waste-treatment attributable to canonical replacement events; all reported in B4."}
    return comp,cov,ledger,build_b4_event_process_summary(ledger),meta


def append_b4_event_processes(combined,ledger):
    if ledger.empty:return combined.copy()
    out=pd.concat([combined,ledger],ignore_index=True)
    if out.carbon_consequence_id.duplicated().any(): raise ValueError("Carbon consequence ID collision after B4 event-process append.")
    return out
