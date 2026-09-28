"""M2.5: A5.1 pre-construction removal of existing works at t0.

The adopted research split reports three independently traceable subconsequences
inside A5.1 for each documented removed-at-t0 inventory line:
- removal/deconstruction activity;
- outbound transport of the removed material from the project site; and
- waste processing or disposal attributable to that removed pre-existing material.

This module is deliberately separate from A5.3 current-construction waste and
from future C-stage end-of-life accounting. No D1 credit is calculated here.
Production inputs may remain empty; missing removal data are never treated as
zero.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from a4_transport import validate_transport_factors
from a5_construction import _convert_explicit_quantity
from carbon_consequences import (
    CARBON_CONSEQUENCE_COLUMNS,
    _stable_id,
    empty_carbon_consequence_ledger,
)
from environmental_factors import _parse_bool, normalize_declared_unit
from identity import validate_stable_id, validate_unique_ids
from physical_quantities import normalize_physical_unit


PRECONSTRUCTION_REMOVAL_COLUMNS = (
    "removal_scenario_id", "scenario_id", "removal_inventory_line_id",
    "removed_component_instance_id", "comparison_lineage_id", "material_or_product_id",
    "removal_activity_factor_set_id", "removal_activity_quantity", "removal_activity_unit",
    "removed_quantity", "removed_quantity_unit", "removed_mass_kg",
    "removal_transport_scenario_id", "waste_route_scenario_id", "d1_recovery_scenario_id",
    "active", "mapping_basis", "source_status", "source_reference", "retrieval_date",
    "data_status", "notes",
)
REMOVAL_TRANSPORT_SCENARIO_COLUMNS = (
    "removal_transport_scenario_id", "origin_scope", "destination_scope", "distance_km",
    "transport_mode", "vehicle_class", "load_factor_basis", "factor_set_id",
    "source_status", "source_reference", "retrieval_date", "notes",
)
WASTE_ROUTE_SCENARIO_COLUMNS = (
    "waste_route_scenario_id", "route_type", "expected_source_module", "factor_set_id",
    "destination_scope", "source_status", "source_reference", "retrieval_date", "notes",
)
A51_COMPATIBILITY_COLUMNS = (
    "removal_scenario_id", "scenario_id", "removal_inventory_line_id",
    "removed_component_instance_id", "comparison_lineage_id", "material_or_product_id",
    "removed_quantity", "removed_quantity_unit", "resolved_mass_kg",
    "removal_activity_factor_set_id", "removal_activity_factor_record_id",
    "removal_activity_quantity", "removal_activity_unit", "resolved_removal_activity_quantity",
    "resolved_removal_activity_unit", "removal_activity_gate_status", "removal_activity_reason",
    "removal_transport_scenario_id", "transport_factor_set_id", "transport_factor_record_id",
    "transport_distance_km", "transport_activity_tkm", "transport_gate_status", "transport_reason",
    "waste_route_scenario_id", "waste_route_type", "waste_factor_set_id", "waste_factor_record_id",
    "waste_source_module", "resolved_waste_quantity", "resolved_waste_unit",
    "waste_gate_status", "waste_reason", "d1_recovery_scenario_id",
)
A51_COVERAGE_COLUMNS = (
    "removal_scenario_id", "scenario_id", "removal_inventory_line_id",
    "removed_component_instance_id", "removal_activity_gate_status",
    "transport_gate_status", "waste_gate_status", "overall_a5_1_status", "reason",
)
A51_SUMMARY_COLUMNS = (
    "future_id", "scenario_id", "assessment_scope", "reported_module",
    "assessed_gwp_kgco2e", "consequence_row_count", "assessment_label",
)

SOURCE_STATUSES = {"DOCUMENTED_PROJECT_DATA", "PUBLIC_DOCUMENTED_DATA", "TEST_ONLY_SYNTHETIC"}
MAPPING_BASES = {"DOCUMENTED_REMOVAL_INVENTORY", "DOCUMENTED_PROXY", "TEST_ONLY_SYNTHETIC"}
DATA_STATUSES = {"DOCUMENTED", "TEST_ONLY_SYNTHETIC"}
ROUTE_TYPES = {"PROCESSING", "DISPOSAL"}
EXPECTED_ROUTE_MODULE = {"PROCESSING": "C3", "DISPOSAL": "C4"}
PASS_PREFIX = "PASS_"


def _schema(table, columns, label):
    missing, extra = set(columns) - set(table), set(table) - set(columns)
    if missing or extra:
        raise ValueError(f"{label} schema: missing={sorted(missing)}, extra={sorted(extra)}")
    return table.loc[:, columns].copy()


def _required(table, fields, label="M2.5 input"):
    for field in fields:
        if table[field].isna().any() or table[field].astype(str).str.strip().eq("").any():
            raise ValueError(f"{label} requires nonempty {field}.")
        table[field] = table[field].astype(str).str.strip()


def _dates(table, field):
    _required(table, [field])
    for value in table[field]:
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO YYYY-MM-DD date.") from exc


def _stable_optional(value, field):
    if pd.isna(value) or str(value).strip() == "":
        return ""
    return validate_stable_id(str(value).strip(), field)


def validate_removal_transport_scenarios(table, transport_factors):
    out = _schema(table, REMOVAL_TRANSPORT_SCENARIO_COLUMNS, "A5.1 removal transport scenario")
    if out.empty:
        return out
    for field in ("removal_transport_scenario_id", "factor_set_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    validate_unique_ids(out.removal_transport_scenario_id, "removal_transport_scenario_id")
    _required(out, ["origin_scope", "destination_scope", "transport_mode", "vehicle_class",
                    "load_factor_basis", "source_status", "source_reference"])
    _dates(out, "retrieval_date")
    if not out.origin_scope.eq("PROJECT_SITE").all():
        raise ValueError("A5.1 removed-material transport must originate at PROJECT_SITE.")
    if out.destination_scope.eq("PROJECT_SITE").any():
        raise ValueError("A5.1 removed-material transport destination cannot be PROJECT_SITE.")
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError("Unsupported A5.1 transport source_status.")
    out["distance_km"] = pd.to_numeric(out.distance_km, errors="raise")
    supplied = out.distance_km.notna()
    if (~np.isfinite(out.loc[supplied, "distance_km"])).any() or (out.loc[supplied, "distance_km"] < 0).any():
        raise ValueError("A5.1 transport distance_km must be finite and nonnegative when supplied.")
    if not set(out.factor_set_id).issubset(set(transport_factors.factor_set_id)):
        raise ValueError("Unknown A5.1 removal transport factor_set_id.")
    tf_lookup = transport_factors.drop_duplicates("factor_set_id").set_index("factor_set_id")
    for row in out.itertuples(index=False):
        if tf_lookup.loc[row.factor_set_id].source_type == "TEST_ONLY_SYNTHETIC" and row.source_status != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic A5.1 transport factors require TEST_ONLY_SYNTHETIC route provenance.")
    out["notes"] = out.notes.fillna("")
    return out


def load_removal_transport_scenarios(path: Path, transport_factors):
    return validate_removal_transport_scenarios(pd.read_csv(path), transport_factors)


def validate_preconstruction_waste_routes(table, environmental_factors):
    out = _schema(table, WASTE_ROUTE_SCENARIO_COLUMNS, "A5.1 waste route scenario")
    if out.empty:
        return out
    for field in ("waste_route_scenario_id", "factor_set_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    validate_unique_ids(out.waste_route_scenario_id, "waste_route_scenario_id")
    _required(out, ["route_type", "expected_source_module", "destination_scope",
                    "source_status", "source_reference"])
    _dates(out, "retrieval_date")
    out["route_type"] = out.route_type.str.upper()
    out["expected_source_module"] = out.expected_source_module.str.upper()
    if not out.route_type.isin(ROUTE_TYPES).all():
        raise ValueError("Unsupported A5.1 waste route_type.")
    for row in out.itertuples(index=False):
        if row.expected_source_module != EXPECTED_ROUTE_MODULE[row.route_type]:
            raise ValueError("A5.1 waste route_type conflicts with expected C3/C4 source-module basis.")
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError("Unsupported A5.1 waste-route source_status.")
    if not set(out.factor_set_id).issubset(set(environmental_factors.factor_set_id)):
        raise ValueError("Unknown A5.1 waste-route factor_set_id.")
    ef_lookup = environmental_factors.drop_duplicates("factor_set_id").set_index("factor_set_id")
    for row in out.itertuples(index=False):
        if ef_lookup.loc[row.factor_set_id].source_type == "TEST_ONLY_SYNTHETIC" and row.source_status != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic A5.1 waste factors require TEST_ONLY_SYNTHETIC route provenance.")
    out["notes"] = out.notes.fillna("")
    return out


def load_preconstruction_waste_routes(path: Path, environmental_factors):
    return validate_preconstruction_waste_routes(pd.read_csv(path), environmental_factors)


def validate_preconstruction_removal_scenarios(table, scenarios, component_boq,
                                                environmental_factors, removal_transport_scenarios,
                                                waste_routes):
    out = _schema(table, PRECONSTRUCTION_REMOVAL_COLUMNS, "Pre-construction removal scenario")
    if out.empty:
        return out
    for field in ("removal_scenario_id", "scenario_id", "removal_inventory_line_id",
                  "removed_component_instance_id", "comparison_lineage_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    out["removal_activity_factor_set_id"] = [
        _stable_optional(v, "removal_activity_factor_set_id") for v in out.removal_activity_factor_set_id]
    out["removal_transport_scenario_id"] = [
        _stable_optional(v, "removal_transport_scenario_id") for v in out.removal_transport_scenario_id]
    out["waste_route_scenario_id"] = [
        _stable_optional(v, "waste_route_scenario_id") for v in out.waste_route_scenario_id]
    out["d1_recovery_scenario_id"] = [
        _stable_optional(v, "d1_recovery_scenario_id") for v in out.d1_recovery_scenario_id]
    validate_unique_ids(out.removal_scenario_id, "removal_scenario_id")
    validate_unique_ids(out.removal_inventory_line_id, "removal_inventory_line_id")
    validate_unique_ids(out.removed_component_instance_id, "removed_component_instance_id")
    _required(out, ["material_or_product_id", "mapping_basis", "source_status", "source_reference", "data_status"])
    _dates(out, "retrieval_date")
    out["active"] = [_parse_bool(v, "active") for v in out.active]
    if not out.mapping_basis.isin(MAPPING_BASES).all():
        raise ValueError("Unsupported A5.1 mapping_basis.")
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError("Unsupported A5.1 source_status.")
    if not out.data_status.isin(DATA_STATUSES).all():
        raise ValueError("Unsupported A5.1 data_status.")
    out["removal_activity_quantity"] = pd.to_numeric(out.removal_activity_quantity, errors="coerce")
    out["removed_quantity"] = pd.to_numeric(out.removed_quantity, errors="raise")
    out["removed_mass_kg"] = pd.to_numeric(out.removed_mass_kg, errors="coerce")
    if (~np.isfinite(out.removed_quantity)).any() or (out.removed_quantity <= 0).any():
        raise ValueError("removed_quantity must be finite and strictly positive.")
    supplied_mass = out.removed_mass_kg.notna()
    if (~np.isfinite(out.loc[supplied_mass, "removed_mass_kg"])).any() or (out.loc[supplied_mass, "removed_mass_kg"] <= 0).any():
        raise ValueError("removed_mass_kg must be finite and strictly positive when supplied.")
    out["removed_quantity_unit"] = [normalize_physical_unit(v) for v in out.removed_quantity_unit]
    out["removal_activity_unit"] = out.removal_activity_unit.fillna("").astype(str).str.strip()
    out["material_or_product_id"] = out.material_or_product_id.astype(str).str.strip()
    out["notes"] = out.notes.fillna("")

    scenario_lookup = scenarios.set_index("scenario_id", drop=False)
    if not set(out.scenario_id).issubset(set(scenario_lookup.index)):
        raise ValueError("Unknown A5.1 scenario_id.")
    for row in out.itertuples(index=False):
        if bool(scenario_lookup.loc[row.scenario_id].is_reference):
            raise ValueError("A5.1 pre-construction removal cannot be assigned to the continued-use reference scenario.")
    # Structural anti-double-counting: removed-at-t0 inventory identities are not
    # allowed to masquerade as current-construction BoQ lines/components.
    if not component_boq.empty:
        if set(out.removal_inventory_line_id) & set(component_boq.boq_line_id):
            raise ValueError("A5.1 removal inventory line IDs must be disjoint from current-construction BoQ line IDs.")
        if set(out.removed_component_instance_id) & set(component_boq.component_instance_id):
            raise ValueError("A5.1 removed component instance IDs must be disjoint from installed/current-construction component IDs.")

    env_sets = set(environmental_factors.factor_set_id)
    trans_ids = set(removal_transport_scenarios.removal_transport_scenario_id)
    waste_ids = set(waste_routes.waste_route_scenario_id)
    active = out.loc[out.active]
    if active.duplicated(["scenario_id", "comparison_lineage_id", "material_or_product_id"]).any():
        raise ValueError("Duplicate active A5.1 removal inventory ownership in the same scenario/lineage/product scope.")
    for row in out.itertuples(index=False):
        if row.removal_activity_factor_set_id and row.removal_activity_factor_set_id not in env_sets:
            raise ValueError("Unknown A5.1 removal_activity_factor_set_id.")
        if row.removal_transport_scenario_id and row.removal_transport_scenario_id not in trans_ids:
            raise ValueError("Unknown A5.1 removal_transport_scenario_id.")
        if row.waste_route_scenario_id and row.waste_route_scenario_id not in waste_ids:
            raise ValueError("Unknown A5.1 waste_route_scenario_id.")
        if row.removal_activity_factor_set_id:
            if pd.isna(row.removal_activity_quantity) or not np.isfinite(row.removal_activity_quantity) or row.removal_activity_quantity < 0:
                raise ValueError("A5.1 removal activity factor requires finite nonnegative removal_activity_quantity.")
            if not row.removal_activity_unit:
                raise ValueError("A5.1 removal activity factor requires removal_activity_unit.")
        linked_synthetic = False
        if row.removal_activity_factor_set_id:
            linked_synthetic = linked_synthetic or environmental_factors.loc[
                environmental_factors.factor_set_id.eq(row.removal_activity_factor_set_id), "source_type"
            ].eq("TEST_ONLY_SYNTHETIC").any()
        if row.removal_transport_scenario_id:
            linked_synthetic = linked_synthetic or (
                removal_transport_scenarios.set_index("removal_transport_scenario_id").loc[row.removal_transport_scenario_id].source_status
                == "TEST_ONLY_SYNTHETIC"
            )
        if row.waste_route_scenario_id:
            linked_synthetic = linked_synthetic or (
                waste_routes.set_index("waste_route_scenario_id").loc[row.waste_route_scenario_id].source_status
                == "TEST_ONLY_SYNTHETIC"
            )
        synthetic = row.source_status == "TEST_ONLY_SYNTHETIC" or row.data_status == "TEST_ONLY_SYNTHETIC" or linked_synthetic
        if synthetic and row.mapping_basis != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic A5.1 removal data require TEST_ONLY_SYNTHETIC mapping.")
    return out


def load_preconstruction_removal_scenarios(path: Path, scenarios, component_boq, environmental_factors,
                                           removal_transport_scenarios, waste_routes):
    return validate_preconstruction_removal_scenarios(
        pd.read_csv(path), scenarios, component_boq, environmental_factors,
        removal_transport_scenarios, waste_routes)


def _gwp_env_factor(factors, factor_set_id, module):
    if not factor_set_id:
        return None
    rows = factors.loc[(factors.factor_set_id.eq(factor_set_id)) &
                       (factors.indicator_id.eq("GWP_TOTAL")) &
                       (factors.module_scope.eq(module))]
    if rows.empty:
        return None
    if len(rows) != 1:
        raise ValueError(f"A5.1 factor set {factor_set_id!r} must have exactly one GWP_TOTAL/{module} record.")
    return rows.iloc[0]


def _resolved_mass_kg(row):
    unit = normalize_physical_unit(row.removed_quantity_unit)
    q = float(row.removed_quantity)
    explicit = None if pd.isna(row.removed_mass_kg) else float(row.removed_mass_kg)
    derived = q if unit == "kg" else (q * 1000.0 if unit == "t" else None)
    if explicit is not None and derived is not None and not np.isclose(explicit, derived, rtol=1e-9, atol=1e-9):
        raise ValueError("A5.1 removed_mass_kg conflicts with mass-based removed_quantity.")
    return explicit if explicit is not None else derived


def _resolve_removed_for_factor(row, factor_unit):
    factor_unit = normalize_declared_unit(factor_unit)
    unit = normalize_physical_unit(row.removed_quantity_unit)
    q = float(row.removed_quantity)
    if unit == factor_unit:
        return q, factor_unit, "EXACT_REMOVED_QUANTITY_UNIT"
    if unit == "kg" and factor_unit == "t":
        return q / 1000.0, "t", "REMOVED_KG_TO_TONNE"
    if unit == "t" and factor_unit == "kg":
        return q * 1000.0, "kg", "REMOVED_TONNE_TO_KG"
    mass = _resolved_mass_kg(row)
    if mass is not None and factor_unit == "kg":
        return mass, "kg", "DOCUMENTED_REMOVED_MASS_BRIDGE"
    if mass is not None and factor_unit == "t":
        return mass / 1000.0, "t", "DOCUMENTED_REMOVED_MASS_KG_TO_TONNE"
    return np.nan, factor_unit, "NONE"


def build_a5_1_compatibility(removal_scenarios, environmental_factors, removal_transport_scenarios,
                             transport_factors, waste_routes):
    if removal_scenarios.empty:
        return pd.DataFrame(columns=A51_COMPATIBILITY_COLUMNS)
    routes = removal_transport_scenarios.set_index("removal_transport_scenario_id", drop=False)
    wastes = waste_routes.set_index("waste_route_scenario_id", drop=False)
    tfs = validate_transport_factors(transport_factors)
    rows = []
    for r in removal_scenarios.loc[removal_scenarios.active.eq(True)].itertuples(index=False):
        mass_kg = _resolved_mass_kg(r)
        # A5.1 removal/deconstruction activity.
        rf = _gwp_env_factor(environmental_factors, r.removal_activity_factor_set_id, "A5.1")
        if not r.removal_activity_factor_set_id or pd.isna(r.removal_activity_quantity) or not r.removal_activity_unit:
            rstat, rreason = "BLOCKED_A5_1_REMOVAL_ACTIVITY_MISSING", "Explicit removal activity quantity/unit/factor mapping is missing."
            rfid = pd.NA; raq = np.nan; rau = pd.NA
        elif rf is None:
            rstat, rreason = "BLOCKED_A5_1_REMOVAL_GWP_TOTAL_MISSING", "Removal factor set lacks GWP_TOTAL scoped exactly to A5.1."
            rfid = pd.NA; raq = np.nan; rau = pd.NA
        else:
            raq, rau, _ = _convert_explicit_quantity(r.removal_activity_quantity, r.removal_activity_unit, rf.declared_unit)
            if pd.isna(raq):
                rstat, rreason = "BLOCKED_A5_1_REMOVAL_ACTIVITY_UNIT", "Removal activity unit is incompatible with the A5.1 factor declared unit."
            else:
                rstat = "PASS_TEST_ONLY_SYNTHETIC" if r.mapping_basis == "TEST_ONLY_SYNTHETIC" else "PASS_DOCUMENTED_A5_1_REMOVAL_ACTIVITY"
                rreason = "Explicit removal activity and A5.1 GWP_TOTAL factor are executable."
            rfid = rf.factor_record_id

        # Outbound transport of removed existing material; source process factor remains A4-like,
        # but reporting ownership is A5.1 under the adopted retrofit split.
        if not r.removal_transport_scenario_id:
            tstat, treason = "BLOCKED_A5_1_REMOVAL_TRANSPORT_MISSING", "No explicit outbound removed-material transport scenario is assigned."
            tfset = tfid = pd.NA; dist = tkm = np.nan
        else:
            tr = routes.loc[r.removal_transport_scenario_id]
            tfset = tr.factor_set_id
            fs = tfs.loc[tfs.factor_set_id.eq(tfset)]
            gwp = fs.loc[fs.indicator_id.eq("GWP_TOTAL") & fs.module_scope.eq("A4")]
            tf = fs.iloc[0]
            tfid = gwp.iloc[0].factor_record_id if len(gwp) == 1 else pd.NA
            dist = tr.distance_km
            if mass_kg is None:
                tstat, treason = "BLOCKED_A5_1_REMOVAL_TRANSPORT_MASS_MISSING", "Removed material has no mass-based quantity or documented removed_mass_kg bridge."
            elif pd.isna(dist):
                tstat, treason = "BLOCKED_A5_1_REMOVAL_TRANSPORT_DISTANCE_MISSING", "Outbound distance_km is missing; no default is allowed."
            elif tf.declared_unit != "tkm":
                tstat, treason = "BLOCKED_A5_1_REMOVAL_TRANSPORT_FACTOR_UNIT", "Transport factor must use kgCO2e per tonne-km."
            elif len(gwp) != 1:
                tstat, treason = "BLOCKED_A5_1_REMOVAL_TRANSPORT_GWP", "Exactly one GWP_TOTAL/A4 transport-process record is required."
            elif any(tr[f] != tf[f] for f in ("transport_mode", "vehicle_class", "load_factor_basis")):
                tstat, treason = "BLOCKED_A5_1_REMOVAL_TRANSPORT_FACTOR_BASIS", "Route mode, vehicle and load basis must match the documented transport factor basis."
            else:
                tstat = "PASS_TEST_ONLY_SYNTHETIC" if r.mapping_basis == "TEST_ONLY_SYNTHETIC" else "PASS_DOCUMENTED_A5_1_REMOVAL_TRANSPORT"
                treason = "Removed-material mass, outbound distance and transport GWP_TOTAL factor are executable."
            tkm = mass_kg / 1000.0 * float(dist) if str(tstat).startswith(PASS_PREFIX) else np.nan

        # Waste processing/disposal of the same removed pre-existing quantity.
        if not r.waste_route_scenario_id:
            wstat, wreason = "BLOCKED_A5_1_WASTE_ROUTE_MISSING", "No explicit waste processing/disposal route is assigned."
            wrtype = wfset = wfid = wmodule = pd.NA; wqty = np.nan; wunit = pd.NA
        else:
            wr = wastes.loc[r.waste_route_scenario_id]
            wrtype, wfset, wmodule = wr.route_type, wr.factor_set_id, wr.expected_source_module
            wf = _gwp_env_factor(environmental_factors, wfset, wmodule)
            if wf is None:
                wstat, wreason = "BLOCKED_A5_1_WASTE_GWP_TOTAL_MISSING", f"Waste route factor set lacks GWP_TOTAL scoped exactly to {wmodule}."
                wfid = pd.NA; wqty = np.nan; wunit = pd.NA
            else:
                wqty, wunit, _ = _resolve_removed_for_factor(r, wf.declared_unit)
                if pd.isna(wqty):
                    wstat, wreason = "BLOCKED_A5_1_WASTE_UNIT_OR_MASS", "Removed quantity cannot be reconciled explicitly with the waste-route factor declared unit."
                else:
                    wstat = "PASS_TEST_ONLY_SYNTHETIC" if r.mapping_basis == "TEST_ONLY_SYNTHETIC" else "PASS_DOCUMENTED_A5_1_WASTE_ROUTE"
                    wreason = "Removed quantity and explicit waste processing/disposal GWP_TOTAL factor are executable."
                wfid = wf.factor_record_id

        rows.append({
            "removal_scenario_id": r.removal_scenario_id, "scenario_id": r.scenario_id,
            "removal_inventory_line_id": r.removal_inventory_line_id,
            "removed_component_instance_id": r.removed_component_instance_id,
            "comparison_lineage_id": r.comparison_lineage_id, "material_or_product_id": r.material_or_product_id,
            "removed_quantity": float(r.removed_quantity), "removed_quantity_unit": r.removed_quantity_unit,
            "resolved_mass_kg": mass_kg,
            "removal_activity_factor_set_id": r.removal_activity_factor_set_id,
            "removal_activity_factor_record_id": rfid, "removal_activity_quantity": r.removal_activity_quantity,
            "removal_activity_unit": r.removal_activity_unit, "resolved_removal_activity_quantity": raq,
            "resolved_removal_activity_unit": rau, "removal_activity_gate_status": rstat,
            "removal_activity_reason": rreason, "removal_transport_scenario_id": r.removal_transport_scenario_id,
            "transport_factor_set_id": tfset, "transport_factor_record_id": tfid,
            "transport_distance_km": dist, "transport_activity_tkm": tkm,
            "transport_gate_status": tstat, "transport_reason": treason,
            "waste_route_scenario_id": r.waste_route_scenario_id, "waste_route_type": wrtype,
            "waste_factor_set_id": wfset, "waste_factor_record_id": wfid, "waste_source_module": wmodule,
            "resolved_waste_quantity": wqty, "resolved_waste_unit": wunit,
            "waste_gate_status": wstat, "waste_reason": wreason,
            "d1_recovery_scenario_id": r.d1_recovery_scenario_id,
        })
    return pd.DataFrame(rows, columns=A51_COMPATIBILITY_COLUMNS)


def build_a5_1_coverage(removal_scenarios, compatibility):
    if removal_scenarios.empty:
        return pd.DataFrame(columns=A51_COVERAGE_COLUMNS)
    comp = compatibility.set_index("removal_scenario_id", drop=False) if not compatibility.empty else pd.DataFrame()
    rows = []
    for r in removal_scenarios.loc[removal_scenarios.active.eq(True)].itertuples(index=False):
        c = comp.loc[r.removal_scenario_id]
        statuses = [c.removal_activity_gate_status, c.transport_gate_status, c.waste_gate_status]
        if all(str(v).startswith(PASS_PREFIX) for v in statuses):
            overall = "PASS_COMPLETE_A5_1_REMOVAL_ACCOUNTING"
            reason = "Removal activity, outbound transport and waste processing/disposal gates all pass."
        elif any(str(v).startswith(PASS_PREFIX) for v in statuses):
            overall = "PARTIAL_A5_1_REMOVAL_ACCOUNTING"
            reason = "Only explicitly passing A5.1 subconsequences are calculable; missing/blocked flows are not treated as zero."
        else:
            overall = "BLOCKED_A5_1_REMOVAL_ACCOUNTING"
            reason = "No A5.1 removal subflow is executable."
        rows.append((r.removal_scenario_id, r.scenario_id, r.removal_inventory_line_id,
                     r.removed_component_instance_id, statuses[0], statuses[1], statuses[2], overall, reason))
    return pd.DataFrame(rows, columns=A51_COVERAGE_COLUMNS)


def _base_row(fid, r, factor, consequence_type, source_event_type, resolved_qty, resolved_unit,
              conversion_method, factor_set_id, factor_record_id):
    impact = float(resolved_qty) * float(factor.indicator_value)
    return {
        "carbon_consequence_id": _stable_id("cc", consequence_type, fid, r.removal_scenario_id, factor_record_id),
        "future_id": int(fid), "scenario_id": str(r.scenario_id),
        "component_instance_id": str(r.removed_component_instance_id),
        "comparison_lineage_id": str(r.comparison_lineage_id), "component_generation": 0,
        "consequence_type": consequence_type, "lifecycle_event_id": pd.NA,
        "source_event_type": source_event_type, "event_time_years": 0.0,
        "boq_line_id": str(r.removal_inventory_line_id), "material_or_product_id": str(r.material_or_product_id),
        "assignment_id": str(r.removal_scenario_id), "factor_set_id": str(factor_set_id),
        "factor_record_id": str(factor_record_id), "dataset_id": str(factor.dataset_id),
        "factor_product_or_process_id": str(factor.product_or_process_id),
        "factor_declared_unit": str(factor.declared_unit), "factor_reference_year": int(factor.reference_year),
        "indicator_id": "GWP_TOTAL", "source_factor_module_scope": str(factor.module_scope),
        "reported_module": "A5.1", "boq_quantity": float(r.removed_quantity),
        "boq_unit": str(r.removed_quantity_unit), "resolved_activity_quantity": float(resolved_qty),
        "resolved_activity_unit": str(resolved_unit), "indicator_value_per_declared_unit": float(factor.indicator_value),
        "indicator_unit": str(factor.indicator_unit), "gwp_kgco2e": impact,
        "mapping_basis": str(r.mapping_basis), "conversion_method": str(conversion_method),
        "source_type": str(factor.source_type), "source_citation": str(factor.source_citation),
        "verification_status": str(factor.verification_status), "data_quality_status": str(factor.data_quality_status),
        "license_status": str(factor.license_status), "redistribution_allowed": bool(factor.redistribution_allowed),
        "factor_uncertainty_mode": str(factor.uncertainty_mode),
        "factor_uncertainty_semantics": str(factor.uncertainty_semantics),
        "factor_uncertainty_applied": False, "factor_temporal_basis": "STATIC_REFERENCE_FACTOR",
        "provenance_status": "CENTRAL_FACTOR_VALUE_ONLY",
    }


def build_a5_1_ledger(removal_scenarios, compatibility, environmental_factors,
                      removal_transport_scenarios, transport_factors, waste_routes, future_ids):
    if removal_scenarios.empty or compatibility.empty:
        return empty_carbon_consequence_ledger()
    comp = compatibility.set_index("removal_scenario_id", drop=False)
    routes = removal_transport_scenarios.set_index("removal_transport_scenario_id", drop=False)
    wastes = waste_routes.set_index("waste_route_scenario_id", drop=False)
    tfs = validate_transport_factors(transport_factors)
    rows = []
    for r in removal_scenarios.loc[removal_scenarios.active.eq(True)].itertuples(index=False):
        c = comp.loc[r.removal_scenario_id]
        if str(c.removal_activity_gate_status).startswith(PASS_PREFIX):
            f = _gwp_env_factor(environmental_factors, r.removal_activity_factor_set_id, "A5.1")
            qty, unit, method = _convert_explicit_quantity(r.removal_activity_quantity, r.removal_activity_unit, f.declared_unit)
            for fid in future_ids:
                rows.append(_base_row(fid, r, f, "A5_1_PRECONSTRUCTION_REMOVAL_ACTIVITY",
                                      "T0_PRECONSTRUCTION_REMOVAL_ACTIVITY", qty, unit, method,
                                      r.removal_activity_factor_set_id, f.factor_record_id))
        if str(c.transport_gate_status).startswith(PASS_PREFIX):
            tr = routes.loc[r.removal_transport_scenario_id]
            fs = tfs.loc[tfs.factor_set_id.eq(tr.factor_set_id)]
            f = fs.loc[fs.indicator_id.eq("GWP_TOTAL") & fs.module_scope.eq("A4")].iloc[0]
            for fid in future_ids:
                rows.append(_base_row(fid, r, f, "A5_1_REMOVED_MATERIAL_TRANSPORT",
                                      "T0_PRECONSTRUCTION_REMOVED_MATERIAL_TRANSPORT",
                                      float(c.transport_activity_tkm), "tkm", "REMOVED_MASS_KG_X_DISTANCE_TO_TKM",
                                      tr.factor_set_id, f.factor_record_id))
        if str(c.waste_gate_status).startswith(PASS_PREFIX):
            wr = wastes.loc[r.waste_route_scenario_id]
            f = _gwp_env_factor(environmental_factors, wr.factor_set_id, wr.expected_source_module)
            _, _, method = _resolve_removed_for_factor(r, f.declared_unit)
            for fid in future_ids:
                rows.append(_base_row(fid, r, f, "A5_1_REMOVED_MATERIAL_WASTE_TREATMENT",
                                      "T0_PRECONSTRUCTION_REMOVED_MATERIAL_WASTE_TREATMENT",
                                      float(c.resolved_waste_quantity), str(c.resolved_waste_unit), method,
                                      wr.factor_set_id, f.factor_record_id))
    if not rows:
        return empty_carbon_consequence_ledger()
    return validate_a5_1_ledger(pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS))


def validate_a5_1_ledger(ledger):
    out = _schema(ledger, CARBON_CONSEQUENCE_COLUMNS, "A5.1 consequence")
    if out.empty:
        return out
    if out.carbon_consequence_id.duplicated().any():
        raise ValueError("Duplicate A5.1 carbon consequence ID.")
    allowed = {
        "A5_1_PRECONSTRUCTION_REMOVAL_ACTIVITY": ("A5.1", "T0_PRECONSTRUCTION_REMOVAL_ACTIVITY", {"A5.1"}),
        "A5_1_REMOVED_MATERIAL_TRANSPORT": ("A5.1", "T0_PRECONSTRUCTION_REMOVED_MATERIAL_TRANSPORT", {"A4"}),
        "A5_1_REMOVED_MATERIAL_WASTE_TREATMENT": ("A5.1", "T0_PRECONSTRUCTION_REMOVED_MATERIAL_WASTE_TREATMENT", {"C3", "C4"}),
    }
    if not out.consequence_type.isin(allowed).all():
        raise ValueError("Unsupported A5.1 consequence_type.")
    for ctype, (reported, event, source_modules) in allowed.items():
        rows = out.loc[out.consequence_type.eq(ctype)]
        if rows.empty:
            continue
        if not rows.reported_module.eq(reported).all() or not rows.source_event_type.eq(event).all():
            raise ValueError(f"Invalid A5.1 ownership/event semantics for {ctype}.")
        if not rows.source_factor_module_scope.isin(source_modules).all():
            raise ValueError(f"Invalid source factor module for {ctype}.")
    if out.lifecycle_event_id.notna().any():
        raise ValueError("A5.1 t0 removal consequences do not use replacement lifecycle_event_id.")
    if not out.event_time_years.eq(0.0).all() or not out.component_generation.eq(0).all():
        raise ValueError("M2.5 A5.1 consequences must occur at t0/generation 0.")
    if not out.indicator_id.eq("GWP_TOTAL").all() or not out.indicator_unit.eq("kgco2e").all():
        raise ValueError("M2.5 executes GWP_TOTAL in kgCO2e only.")
    for field in ("future_id", "boq_quantity", "resolved_activity_quantity", "indicator_value_per_declared_unit", "gwp_kgco2e"):
        vals = pd.to_numeric(out[field], errors="raise")
        if not np.isfinite(vals.to_numpy(dtype=float)).all() or (vals < 0).any():
            raise ValueError(f"Nonfinite or negative A5.1 {field}.")
    if not np.allclose(out.resolved_activity_quantity * out.indicator_value_per_declared_unit,
                       out.gwp_kgco2e, rtol=1e-12, atol=1e-12):
        raise ValueError("A5.1 impact does not reconcile to activity times factor.")
    if out.reported_module.isin({"A5.3", "C1", "C2", "C3", "C4"}).any():
        raise ValueError("Removed-at-t0 quantities cannot also be reported to A5.3/C in M2.5.")
    if not out.factor_uncertainty_applied.eq(False).all():
        raise ValueError("M2.5 must not sample environmental-factor uncertainty.")
    return out


def build_a5_1_summary(ledger):
    if ledger.empty:
        return pd.DataFrame(columns=A51_SUMMARY_COLUMNS)
    grouped = ledger.groupby(["future_id", "scenario_id", "reported_module"], as_index=False).agg(
        assessed_gwp_kgco2e=("gwp_kgco2e", "sum"),
        consequence_row_count=("carbon_consequence_id", "count"),
    )
    grouped["assessment_scope"] = "A5_1_PRECONSTRUCTION_REMOVAL_ONLY"
    grouped["assessment_label"] = "ASSESSED_A5_1_PRECONSTRUCTION_REMOVAL_ONLY_NOT_WHOLE_LIFE_CARBON"
    return grouped.loc[:, A51_SUMMARY_COLUMNS].sort_values(["future_id", "scenario_id"]).reset_index(drop=True)


def a5_1_engine_status(removal_scenarios, coverage, ledger, summary):
    active = removal_scenarios.loc[removal_scenarios.active.eq(True)] if not removal_scenarios.empty else removal_scenarios
    complete = int(coverage.overall_a5_1_status.eq("PASS_COMPLETE_A5_1_REMOVAL_ACCOUNTING").sum()) if not coverage.empty else 0
    partial = int(coverage.overall_a5_1_status.eq("PARTIAL_A5_1_REMOVAL_ACCOUNTING").sum()) if not coverage.empty else 0
    if active.empty:
        status = "NO_PRECONSTRUCTION_REMOVAL_INVENTORY"
        claim = "No documented removed-at-t0 inventory is supplied; A5.1 is not assessed and missing removal data are not treated as zero."
    elif complete == len(active):
        status = "COMPLETE_EXECUTABLE_A5_1_REMOVAL_MAPPING"
        claim = "All active removed-at-t0 inventory lines have executable removal activity, outbound transport, and waste-route mappings."
    elif complete or partial:
        status = "PARTIAL_EXECUTABLE_A5_1_REMOVAL_MAPPING"
        claim = "A5.1 is calculated only for explicitly passing removal subflows; blocked/missing subflows remain missing rather than zero."
    else:
        status = "NO_EXECUTABLE_A5_1_REMOVAL_MAPPING"
        claim = "Removed-at-t0 inventory exists but no A5.1 subflow passes its explicit gate."
    return {
        "status": status,
        "active_removal_inventory_lines": int(len(active)),
        "complete_gate_pass_lines": complete,
        "partial_gate_lines": partial,
        "carbon_consequence_rows": int(len(ledger)),
        "summary_rows": int(len(summary)),
        "executed_indicator": "GWP_TOTAL",
        "implemented_modules": ["A5.1_PRECONSTRUCTION_REMOVAL"],
        "implemented_subconsequences": [
            "REMOVAL_ACTIVITY", "REMOVED_MATERIAL_OUTBOUND_TRANSPORT", "REMOVED_MATERIAL_WASTE_PROCESSING_OR_DISPOSAL"
        ],
        "source_process_module_policy": {
            "removal_activity": "A5.1",
            "outbound_transport": "A4_SOURCE_PROCESS_REPORTED_TO_A5.1",
            "waste_processing_or_disposal": "C3_OR_C4_SOURCE_PROCESS_REPORTED_TO_A5.1",
        },
        "d1_recovery_declarations_present": int(active.d1_recovery_scenario_id.astype(str).str.strip().ne("").sum()) if not active.empty else 0,
        "d1_recovery_credit_calculated": False,
        "c_stage_consequences_generated_from_t0_removed_material": False,
        "a5_3_current_construction_waste_ownership_shared": False,
        "factor_uncertainty_applied": False,
        "carbon_discounting_applied": False,
        "whole_life_carbon_generated": False,
        "headline_carbon_generated": False,
        "missing_data_treated_as_zero": False,
        "claim": claim,
    }


def assess_a5_1(removal_scenarios, environmental_factors, removal_transport_scenarios,
                 transport_factors, waste_routes, future_ids):
    comp = build_a5_1_compatibility(removal_scenarios, environmental_factors,
                                    removal_transport_scenarios, transport_factors, waste_routes)
    coverage = build_a5_1_coverage(removal_scenarios, comp)
    ledger = build_a5_1_ledger(removal_scenarios, comp, environmental_factors,
                               removal_transport_scenarios, transport_factors, waste_routes, future_ids)
    summary = build_a5_1_summary(ledger)
    status = a5_1_engine_status(removal_scenarios, coverage, ledger, summary)
    return comp, coverage, ledger, summary, status


def append_a5_1_to_combined_ledger(combined_ledger, a5_1_ledger):
    if not a5_1_ledger.empty:
        validate_a5_1_ledger(a5_1_ledger)
    if a5_1_ledger.empty:
        out = combined_ledger.copy()
    elif combined_ledger.empty:
        out = a5_1_ledger.copy()
    else:
        out = pd.concat([combined_ledger, a5_1_ledger], ignore_index=True)
    if not out.empty and out.carbon_consequence_id.duplicated().any():
        raise ValueError("Carbon consequence ID collision after A5.1 append.")
    return out
