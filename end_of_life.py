"""Unified terminal C1-C4 and separate Module-D consequence engine.

This bounded research-release engine deliberately keeps terminal accounting
explicit and auditable:
- C1 deconstruction/demolition activity;
- C2 outbound transport from the project site;
- C3 waste processing;
- C4 disposal;
- D1 explicit material recovery/reuse/recycling benefit or load;
- D2 explicit exported-energy benefit/load under a separately documented factor
  schedule.

The RSP boundary is an accounting state, not a lifecycle event. Terminal C/D
rows are therefore generated only from explicit assignments. Module D is always
reported separately and is never netted against A-C.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_consequences import CARBON_CONSEQUENCE_COLUMNS, _stable_id, empty_carbon_consequence_ledger
from environmental_factors import normalize_declared_unit
from identity import validate_stable_id, validate_unique_ids

EOL_ASSIGNMENT_COLUMNS = (
    "eol_assignment_id", "boq_line_id", "scenario_id", "eol_flow_id",
    "c1_factor_set_id", "c1_activity_quantity", "c1_activity_unit",
    "c2_factor_set_id", "c2_distance_km",
    "c3_factor_set_id", "c3_mass_fraction",
    "c4_factor_set_id", "c4_mass_fraction",
    "d1_factor_set_id", "d1_recovery_fraction",
    "active", "mapping_basis", "source_status", "source_reference",
    "retrieval_date", "notes",
)
D2_EXPORT_ASSIGNMENT_COLUMNS = (
    "d2_assignment_id", "energy_flow_id", "scenario_id", "d2_factor_schedule_id",
    "source_status", "source_reference", "retrieval_date", "notes",
)
D2_FACTOR_SCHEDULE_COLUMNS = (
    "schedule_id", "carrier_id", "analysis_year", "calendar_year", "factor_set_id",
    "source_status", "source_reference", "retrieval_date", "notes",
)
EOL_COVERAGE_COLUMNS = (
    "eol_assignment_id", "boq_line_id", "scenario_id",
    "c1_status", "c2_status", "c3_status", "c4_status", "d1_status",
    "c_stage_status", "reason",
)
D2_COVERAGE_COLUMNS = (
    "d2_assignment_id", "energy_flow_id", "scenario_id", "carrier_id",
    "first_analysis_year", "last_analysis_year", "d2_factor_schedule_id",
    "d2_status", "reason",
)
EOL_SUMMARY_COLUMNS = (
    "future_id", "scenario_id", "assessment_scope", "reported_module",
    "assessed_gwp_kgco2e", "consequence_row_count", "assessment_label",
)

SOURCE_STATUSES = {"DOCUMENTED_PROJECT_DATA", "PUBLIC_DOCUMENTED_DATA", "TEST_ONLY_SYNTHETIC"}
MAPPING_BASES = {"DOCUMENTED_END_OF_LIFE_SCENARIO", "DOCUMENTED_PROXY", "TEST_ONLY_SYNTHETIC"}


def _schema(table: pd.DataFrame, columns: tuple[str, ...], label: str) -> pd.DataFrame:
    missing, extra = set(columns) - set(table.columns), set(table.columns) - set(columns)
    if missing or extra:
        raise ValueError(f"{label} schema: missing={sorted(missing)}, extra={sorted(extra)}")
    return table.loc[:, columns].copy()


def _iso_date(value: object) -> str:
    text = str(value).strip()
    try:
        parsed = date.fromisoformat(text)
    except Exception as exc:
        raise ValueError("retrieval_date must be ISO YYYY-MM-DD.") from exc
    if parsed.isoformat() != text:
        raise ValueError("retrieval_date must be ISO YYYY-MM-DD.")
    return text


def _parse_bool(value: object, field: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"{field} must be boolean-like true/false.")


def _exact_factor(factors: pd.DataFrame, factor_set_id: str, module: str):
    if not factor_set_id:
        return None
    rows = factors.loc[
        factors.factor_set_id.eq(factor_set_id)
        & factors.indicator_id.eq("GWP_TOTAL")
        & factors.module_scope.eq(module)
    ]
    return rows.iloc[0] if len(rows) == 1 else None


def _mass_kg(boq_row) -> float:
    if pd.notna(boq_row.mass_kg):
        return float(boq_row.mass_kg)
    unit = str(boq_row.quantity_unit).strip().lower()
    if unit == "kg":
        return float(boq_row.quantity)
    if unit in {"t", "tonne", "tonnes"}:
        return float(boq_row.quantity) * 1000.0
    return np.nan


def _mass_quantity_for_factor(mass_kg: float, factor) -> tuple[float, str]:
    unit = str(factor.declared_unit)
    if unit == "kg":
        return float(mass_kg), "kg"
    if unit == "t":
        return float(mass_kg) / 1000.0, "t"
    raise ValueError("Mass-based C3/C4/D1 factor must use kg or t declared unit.")


def validate_end_of_life_assignments(
    table: pd.DataFrame, component_boq: pd.DataFrame, environmental_factors: pd.DataFrame
) -> pd.DataFrame:
    out = _schema(table, EOL_ASSIGNMENT_COLUMNS, "End-of-life assignment")
    if out.empty:
        return out
    for field in ("eol_assignment_id", "boq_line_id", "scenario_id", "eol_flow_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    validate_unique_ids(out.eol_assignment_id, "eol_assignment_id")
    for field in ("c1_factor_set_id", "c2_factor_set_id", "c3_factor_set_id", "c4_factor_set_id", "d1_factor_set_id"):
        out[field] = out[field].fillna("").astype(str).str.strip()
        out[field] = [validate_stable_id(v, field) if v else "" for v in out[field]]
    out["active"] = [_parse_bool(v, "active") for v in out.active]
    out.c1_activity_quantity = pd.to_numeric(out.c1_activity_quantity, errors="coerce")
    out.c1_activity_unit = out.c1_activity_unit.fillna("").astype(str).str.strip()
    out.c2_distance_km = pd.to_numeric(out.c2_distance_km, errors="coerce")
    for field in ("c3_mass_fraction", "c4_mass_fraction", "d1_recovery_fraction"):
        out[field] = pd.to_numeric(out[field], errors="coerce").fillna(0.0)
        vals = out[field].to_numpy(dtype=float)
        if not np.isfinite(vals).all() or ((vals < 0) | (vals > 1)).any():
            raise ValueError(f"{field} must be finite and within [0,1].")
    if (out.c3_mass_fraction + out.c4_mass_fraction > 1.0 + 1e-12).any():
        raise ValueError("C3 + C4 mass fractions cannot exceed 1.0 for the same terminal inventory flow.")
    for field in ("mapping_basis", "source_status", "source_reference"):
        out[field] = out[field].fillna("").astype(str).str.strip()
        if out[field].eq("").any():
            raise ValueError(f"End-of-life assignment requires {field}.")
    out.mapping_basis = out.mapping_basis.str.upper()
    out.source_status = out.source_status.str.upper()
    if not out.mapping_basis.isin(MAPPING_BASES).all():
        raise ValueError(f"Unsupported EOL mapping_basis; allowed={sorted(MAPPING_BASES)}")
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError(f"Unsupported EOL source_status; allowed={sorted(SOURCE_STATUSES)}")
    out.retrieval_date = [_iso_date(v) for v in out.retrieval_date]
    out.notes = out.notes.fillna("").astype(str)

    boq = component_boq.set_index("boq_line_id", drop=False)
    if out.loc[out.active].duplicated(["scenario_id", "eol_flow_id"]).any():
        raise ValueError("Duplicate active terminal eol_flow_id within a scenario.")
    for row in out.itertuples(index=False):
        if row.boq_line_id not in boq.index:
            raise ValueError("End-of-life assignment references unknown boq_line_id.")
        b = boq.loc[row.boq_line_id]
        if str(row.scenario_id) != str(b.scenario_id):
            raise ValueError("End-of-life assignment scenario scope leakage blocked.")
        if str(b.assessment_role) != "ASSESSMENT_INVENTORY":
            raise ValueError("INFORMATION_ONLY BoQ cannot receive terminal C/D assignments.")
        if row.c1_factor_set_id:
            if pd.isna(row.c1_activity_quantity) or not np.isfinite(row.c1_activity_quantity) or row.c1_activity_quantity < 0 or not row.c1_activity_unit:
                raise ValueError("C1 requires explicit finite nonnegative activity quantity and unit.")
            normalize_declared_unit(row.c1_activity_unit)
        elif pd.notna(row.c1_activity_quantity) or row.c1_activity_unit:
            raise ValueError("C1 activity cannot be supplied without c1_factor_set_id.")
        if row.c2_factor_set_id:
            if pd.isna(row.c2_distance_km) or not np.isfinite(row.c2_distance_km) or row.c2_distance_km < 0:
                raise ValueError("C2 requires explicit finite nonnegative distance_km.")
        elif pd.notna(row.c2_distance_km):
            raise ValueError("C2 distance cannot be supplied without c2_factor_set_id.")
        if row.c3_mass_fraction > 0 and not row.c3_factor_set_id:
            raise ValueError("Positive C3 mass fraction requires c3_factor_set_id.")
        if row.c4_mass_fraction > 0 and not row.c4_factor_set_id:
            raise ValueError("Positive C4 mass fraction requires c4_factor_set_id.")
        if row.d1_recovery_fraction > 0 and not row.d1_factor_set_id:
            raise ValueError("Positive D1 recovery fraction requires d1_factor_set_id.")
        if (str(b.source_status) == "TEST_ONLY_SYNTHETIC" or row.source_status == "TEST_ONLY_SYNTHETIC") and row.mapping_basis != "TEST_ONLY_SYNTHETIC":
            raise ValueError("Synthetic EOL assignment requires TEST_ONLY_SYNTHETIC mapping_basis.")
    return out


def validate_d2_export_assignments(table: pd.DataFrame, operational_energy_flows: pd.DataFrame) -> pd.DataFrame:
    out = _schema(table, D2_EXPORT_ASSIGNMENT_COLUMNS, "D2 export assignment")
    if out.empty:
        return out
    for field in ("d2_assignment_id", "energy_flow_id", "scenario_id", "d2_factor_schedule_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    validate_unique_ids(out.d2_assignment_id, "d2_assignment_id")
    for field in ("source_status", "source_reference"):
        out[field] = out[field].fillna("").astype(str).str.strip()
        if out[field].eq("").any():
            raise ValueError(f"D2 export assignment requires {field}.")
    out.source_status = out.source_status.str.upper()
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError("Unsupported D2 assignment source_status.")
    out.retrieval_date = [_iso_date(v) for v in out.retrieval_date]
    out.notes = out.notes.fillna("").astype(str)
    flows = operational_energy_flows.set_index("energy_flow_id", drop=False)
    for row in out.itertuples(index=False):
        if row.energy_flow_id not in flows.index:
            raise ValueError("D2 assignment references unknown energy_flow_id.")
        flow = flows.loc[row.energy_flow_id]
        if str(flow.flow_type) != "EXPORTED":
            raise ValueError("D2 assignment may reference EXPORTED operational-energy flow only.")
        if str(row.scenario_id) != str(flow.scenario_id):
            raise ValueError("D2 assignment scenario conflicts with exported-energy flow.")
    if out.duplicated(["energy_flow_id"]).any():
        raise ValueError("An exported energy flow may have at most one D2 assignment.")
    return out


def validate_d2_factor_schedule(table: pd.DataFrame, environmental_factors: pd.DataFrame) -> pd.DataFrame:
    out = _schema(table, D2_FACTOR_SCHEDULE_COLUMNS, "D2 factor schedule")
    if out.empty:
        return out
    for field in ("schedule_id", "carrier_id", "factor_set_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    for field in ("analysis_year", "calendar_year"):
        out[field] = pd.to_numeric(out[field], errors="raise")
        vals = out[field].to_numpy(dtype=float)
        if not np.isfinite(vals).all() or ((vals % 1) != 0).any():
            raise ValueError(f"{field} must be integer.")
        out[field] = out[field].astype(int)
    if (out.analysis_year < 1).any() or not out.calendar_year.between(1900, 2200).all():
        raise ValueError("Invalid D2 schedule year.")
    if out.duplicated(["schedule_id", "analysis_year"]).any():
        raise ValueError("Duplicate D2 schedule analysis year.")
    out.source_status = out.source_status.fillna("").astype(str).str.strip().str.upper()
    out.source_reference = out.source_reference.fillna("").astype(str).str.strip()
    if not out.source_status.isin(SOURCE_STATUSES).all() or out.source_reference.eq("").any():
        raise ValueError("D2 schedule requires supported source_status and nonempty source_reference.")
    out.retrieval_date = [_iso_date(v) for v in out.retrieval_date]
    out.notes = out.notes.fillna("").astype(str)
    for row in out.itertuples(index=False):
        factor = _exact_factor(environmental_factors, row.factor_set_id, "D2")
        if factor is None:
            raise ValueError("D2 schedule requires exactly one GWP_TOTAL D2 factor per factor_set_id.")
        if str(factor.declared_unit) != "kwh":
            raise ValueError("D2 exported-energy factor must use kwh declared unit.")
    return out


def load_end_of_life_assignments(path: Path, component_boq: pd.DataFrame, environmental_factors: pd.DataFrame) -> pd.DataFrame:
    return validate_end_of_life_assignments(pd.read_csv(path), component_boq, environmental_factors)


def load_d2_export_assignments(path: Path, operational_energy_flows: pd.DataFrame) -> pd.DataFrame:
    return validate_d2_export_assignments(pd.read_csv(path), operational_energy_flows)


def load_d2_factor_schedule(path: Path, environmental_factors: pd.DataFrame) -> pd.DataFrame:
    return validate_d2_factor_schedule(pd.read_csv(path), environmental_factors)


def build_eol_coverage(component_boq: pd.DataFrame, factors: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    boq = component_boq.set_index("boq_line_id", drop=False)
    for a in assignments.loc[assignments.active].itertuples(index=False):
        b = boq.loc[a.boq_line_id]
        mass = _mass_kg(b)
        statuses, reasons = {}, []
        if a.c1_factor_set_id:
            f = _exact_factor(factors, a.c1_factor_set_id, "C1")
            ok = f is not None and normalize_declared_unit(a.c1_activity_unit) == str(f.declared_unit)
            statuses["c1_status"] = "PASS_C1" if ok else "BLOCKED_C1_FACTOR_OR_UNIT"
            if not ok: reasons.append("C1 factor/unit")
        else:
            statuses["c1_status"] = "NOT_ASSESSED_C1_UNDECLARED"
        if a.c2_factor_set_id:
            f = _exact_factor(factors, a.c2_factor_set_id, "C2")
            ok = np.isfinite(mass) and f is not None and str(f.declared_unit) == "tkm"
            statuses["c2_status"] = "PASS_C2" if ok else "BLOCKED_C2_MASS_OR_FACTOR"
            if not ok: reasons.append("C2 mass/factor")
        else:
            statuses["c2_status"] = "NOT_ASSESSED_C2_UNDECLARED"
        for key, module, fraction, factor_set in (
            ("c3_status", "C3", a.c3_mass_fraction, a.c3_factor_set_id),
            ("c4_status", "C4", a.c4_mass_fraction, a.c4_factor_set_id),
            ("d1_status", "D1", a.d1_recovery_fraction, a.d1_factor_set_id),
        ):
            if fraction > 0:
                f = _exact_factor(factors, factor_set, module) if factor_set else None
                ok = np.isfinite(mass) and f is not None and str(f.declared_unit) in {"kg", "t"}
                statuses[key] = f"PASS_{module}" if ok else f"BLOCKED_{module}_MASS_OR_FACTOR"
                if not ok: reasons.append(f"{module} mass/factor")
            else:
                statuses[key] = f"NOT_APPLICABLE_{module}_ZERO_DECLARED_FRACTION"
        cstats = [statuses[k] for k in ("c1_status", "c2_status", "c3_status", "c4_status")]
        complete = all(s.startswith("PASS_") or s.startswith("NOT_APPLICABLE_") for s in cstats) and any(s.startswith("PASS_") for s in cstats)
        rows.append({
            "eol_assignment_id": a.eol_assignment_id, "boq_line_id": a.boq_line_id,
            "scenario_id": a.scenario_id, **statuses,
            "c_stage_status": "PASS_COMPLETE_C1_C4" if complete else "INCOMPLETE_C1_C4",
            "reason": "; ".join(reasons),
        })
    return pd.DataFrame(rows, columns=EOL_COVERAGE_COLUMNS)


def build_d2_coverage(flows: pd.DataFrame, assignments: pd.DataFrame, schedule: pd.DataFrame, analysis_years: int) -> pd.DataFrame:
    rows = []
    if assignments.empty:
        return pd.DataFrame(columns=D2_COVERAGE_COLUMNS)
    flow_index = flows.set_index("energy_flow_id", drop=False)
    schedule_years = schedule.groupby("schedule_id").analysis_year.apply(set).to_dict() if not schedule.empty else {}
    schedule_carriers = schedule.groupby("schedule_id").carrier_id.apply(lambda x: set(x.astype(str))).to_dict() if not schedule.empty else {}
    for a in assignments.itertuples(index=False):
        f = flow_index.loc[a.energy_flow_id]
        first, last = int(f.first_analysis_year), min(int(f.last_analysis_year), int(analysis_years))
        required = set(range(first, last + 1)) if first <= last else set()
        available = schedule_years.get(a.d2_factor_schedule_id, set())
        carriers = schedule_carriers.get(a.d2_factor_schedule_id, set())
        missing = sorted(required - available)
        if carriers and carriers != {str(f.carrier_id)}:
            status = "BLOCKED_D2_FACTOR_SCHEDULE_CARRIER_MISMATCH"
            reason = f"D2 schedule carrier(s) {sorted(carriers)} do not match exported flow carrier {f.carrier_id}."
        else:
            status = "PASS_COMPLETE_D2_FACTOR_SCHEDULE" if not missing else "BLOCKED_INCOMPLETE_D2_FACTOR_SCHEDULE"
            reason = "Explicit D2 factor schedule covers all in-RSP export years." if not missing else f"Missing D2 schedule years: {missing[:8]}"
        rows.append({
            "d2_assignment_id": a.d2_assignment_id, "energy_flow_id": a.energy_flow_id,
            "scenario_id": a.scenario_id, "carrier_id": f.carrier_id,
            "first_analysis_year": first, "last_analysis_year": last,
            "d2_factor_schedule_id": a.d2_factor_schedule_id,
            "d2_status": status, "reason": reason,
        })
    return pd.DataFrame(rows, columns=D2_COVERAGE_COLUMNS)


def _base_consequence(future_id, scenario_id, component_instance_id, lineage, generation, consequence_type,
                      event_time_years, boq_line_id, material_or_product_id, assignment_id, factor,
                      boq_quantity, boq_unit, activity_quantity, activity_unit, mapping_basis, conversion_method,
                      reported_module, source_event_type, factor_temporal_basis, provenance_status):
    return {
        "carbon_consequence_id": _stable_id("cc", reported_module, assignment_id, future_id, event_time_years, factor.factor_record_id),
        "future_id": int(future_id), "scenario_id": str(scenario_id),
        "component_instance_id": str(component_instance_id), "comparison_lineage_id": str(lineage),
        "component_generation": int(generation), "consequence_type": consequence_type,
        "lifecycle_event_id": np.nan, "source_event_type": source_event_type,
        "event_time_years": float(event_time_years), "boq_line_id": str(boq_line_id),
        "material_or_product_id": str(material_or_product_id), "assignment_id": str(assignment_id),
        "factor_set_id": str(factor.factor_set_id), "factor_record_id": str(factor.factor_record_id),
        "dataset_id": str(factor.dataset_id), "factor_product_or_process_id": str(factor.product_or_process_id),
        "factor_declared_unit": str(factor.declared_unit), "factor_reference_year": int(factor.reference_year),
        "indicator_id": "GWP_TOTAL", "source_factor_module_scope": str(factor.module_scope),
        "reported_module": reported_module, "boq_quantity": float(boq_quantity), "boq_unit": str(boq_unit),
        "resolved_activity_quantity": float(activity_quantity), "resolved_activity_unit": str(activity_unit),
        "indicator_value_per_declared_unit": float(factor.indicator_value), "indicator_unit": str(factor.indicator_unit),
        "gwp_kgco2e": float(activity_quantity) * float(factor.indicator_value),
        "mapping_basis": str(mapping_basis), "conversion_method": str(conversion_method),
        "source_type": str(factor.source_type), "source_citation": str(factor.source_citation),
        "verification_status": str(factor.verification_status), "data_quality_status": str(factor.data_quality_status),
        "license_status": str(factor.license_status), "redistribution_allowed": bool(factor.redistribution_allowed),
        "factor_uncertainty_mode": str(factor.uncertainty_mode), "factor_uncertainty_semantics": str(factor.uncertainty_semantics),
        "factor_uncertainty_applied": False, "factor_temporal_basis": str(factor_temporal_basis),
        "provenance_status": str(provenance_status),
    }


def build_eol_ledger(component_boq, factors, assignments, coverage, future_ids, analysis_years):
    if assignments.empty:
        return empty_carbon_consequence_ledger()
    boq = component_boq.set_index("boq_line_id", drop=False)
    cov = coverage.set_index("eol_assignment_id", drop=False)
    rows = []
    for a in assignments.loc[assignments.active].itertuples(index=False):
        b = boq.loc[a.boq_line_id]
        c = cov.loc[a.eol_assignment_id]
        mass = _mass_kg(b)
        flows = []
        if c.c1_status.startswith("PASS_"):
            f = _exact_factor(factors, a.c1_factor_set_id, "C1")
            flows.append(("C1", "C1_END_OF_LIFE_DECONSTRUCTION", f, float(a.c1_activity_quantity), normalize_declared_unit(a.c1_activity_unit), "EXPLICIT_ACTIVITY"))
        if c.c2_status.startswith("PASS_"):
            f = _exact_factor(factors, a.c2_factor_set_id, "C2")
            q = float(mass) / 1000.0 * float(a.c2_distance_km)
            flows.append(("C2", "C2_END_OF_LIFE_TRANSPORT", f, q, "tkm", "DOCUMENTED_MASS_X_DISTANCE"))
        if c.c3_status.startswith("PASS_") and a.c3_mass_fraction > 0:
            f = _exact_factor(factors, a.c3_factor_set_id, "C3")
            q, u = _mass_quantity_for_factor(float(mass) * float(a.c3_mass_fraction), f)
            flows.append(("C3", "C3_END_OF_LIFE_WASTE_PROCESSING", f, q, u, "DOCUMENTED_MASS_FRACTION"))
        if c.c4_status.startswith("PASS_") and a.c4_mass_fraction > 0:
            f = _exact_factor(factors, a.c4_factor_set_id, "C4")
            q, u = _mass_quantity_for_factor(float(mass) * float(a.c4_mass_fraction), f)
            flows.append(("C4", "C4_END_OF_LIFE_DISPOSAL", f, q, u, "DOCUMENTED_MASS_FRACTION"))
        if c.d1_status.startswith("PASS_") and a.d1_recovery_fraction > 0:
            f = _exact_factor(factors, a.d1_factor_set_id, "D1")
            q, u = _mass_quantity_for_factor(float(mass) * float(a.d1_recovery_fraction), f)
            flows.append(("D1", "D1_RECOVERY_BEYOND_BOUNDARY", f, q, u, "DOCUMENTED_RECOVERY_MASS_FRACTION"))
        for mod, ctype, f, q, u, method in flows:
            for fid in future_ids:
                rows.append(_base_consequence(
                    fid, a.scenario_id, b.component_instance_id, b.comparison_lineage_id, -1,
                    ctype, float(analysis_years), a.boq_line_id, b.material_or_product_id,
                    a.eol_assignment_id, f, b.quantity, b.quantity_unit, q, u,
                    a.mapping_basis, method, mod, "RSP_ACCOUNTING_END_OF_LIFE",
                    "STATIC_REFERENCE_FACTOR_AT_RSP_ACCOUNTING_BOUNDARY",
                    "EXPLICIT_TERMINAL_ACCOUNTING_SCENARIO",
                ))
    out = pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS)
    if not out.empty:
        if out.carbon_consequence_id.duplicated().any():
            raise ValueError("Duplicate terminal C/D consequence ID.")
        if out.loc[out.reported_module.eq("D1"), "lifecycle_event_id"].notna().any():
            raise ValueError("D1 terminal accounting must remain outside the lifecycle-event ledger.")
    return out if not out.empty else empty_carbon_consequence_ledger()


def build_d2_ledger(flows, assignments, schedule, factors, coverage, future_ids, analysis_years):
    if assignments.empty:
        return empty_carbon_consequence_ledger()
    flow_index = flows.set_index("energy_flow_id", drop=False)
    cov = coverage.set_index("d2_assignment_id", drop=False)
    sched = schedule.set_index(["schedule_id", "analysis_year"], drop=False)
    rows = []
    for a in assignments.itertuples(index=False):
        if not str(cov.loc[a.d2_assignment_id].d2_status).startswith("PASS_"):
            continue
        flow = flow_index.loc[a.energy_flow_id]
        for year in range(int(flow.first_analysis_year), min(int(flow.last_analysis_year), int(analysis_years)) + 1):
            sr = sched.loc[(a.d2_factor_schedule_id, year)]
            factor = _exact_factor(factors, sr.factor_set_id, "D2")
            for fid in future_ids:
                row = _base_consequence(
                    fid, a.scenario_id, "system_operational_energy", "system_operational_energy", 0,
                    "D2_EXPORTED_ENERGY_BEYOND_BOUNDARY", float(year) - 0.5, "", flow.carrier_id,
                    a.d2_assignment_id, factor, flow.annual_quantity_kwh, "kwh",
                    flow.annual_quantity_kwh, "kwh", "EXPLICIT_D2_EXPORT_FACTOR_SCHEDULE", "NONE",
                    "D2", "ANNUAL_EXPORTED_ENERGY", f"EXPLICIT_CALENDAR_YEAR_{int(sr.calendar_year)}",
                    "EXPLICIT_SEPARATE_BEYOND_BOUNDARY_D2",
                )
                rows.append(row)
    out = pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS)
    if not out.empty and out.carbon_consequence_id.duplicated().any():
        raise ValueError("Duplicate D2 consequence ID.")
    return out if not out.empty else empty_carbon_consequence_ledger()


def build_end_of_life_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame(columns=EOL_SUMMARY_COLUMNS)
    out = ledger.groupby(["future_id", "scenario_id", "reported_module"], as_index=False).agg(
        assessed_gwp_kgco2e=("gwp_kgco2e", "sum"), consequence_row_count=("carbon_consequence_id", "count")
    )
    out["assessment_scope"] = out.reported_module.map(lambda m: f"{m}_EXPLICIT_TERMINAL_OR_BEYOND_BOUNDARY_ONLY")
    out["assessment_label"] = out.reported_module.map(
        lambda m: "ASSESSED_SEPARATE_MODULE_D_NOT_NETTED_IN_A_C" if str(m).startswith("D") else f"ASSESSED_{m}_ONLY_NOT_WHOLE_LIFE_CARBON"
    )
    return out.loc[:, EOL_SUMMARY_COLUMNS]


def assess_end_of_life_and_d(component_boq, factors, eol_assignments, operational_energy_flows,
                             d2_assignments, d2_schedule, future_ids, analysis_years):
    eol_cov = build_eol_coverage(component_boq, factors, eol_assignments)
    d2_cov = build_d2_coverage(operational_energy_flows, d2_assignments, d2_schedule, analysis_years)
    eol_ledger = build_eol_ledger(component_boq, factors, eol_assignments, eol_cov, future_ids, analysis_years)
    d2_ledger = build_d2_ledger(operational_energy_flows, d2_assignments, d2_schedule, factors, d2_cov, future_ids, analysis_years)
    ledger = pd.concat([x for x in (eol_ledger, d2_ledger) if not x.empty], ignore_index=True) if (not eol_ledger.empty or not d2_ledger.empty) else empty_carbon_consequence_ledger()
    complete_c = int(eol_cov.c_stage_status.eq("PASS_COMPLETE_C1_C4").sum()) if not eol_cov.empty else 0
    status = "NO_END_OF_LIFE_OR_D_ASSIGNMENTS" if eol_assignments.empty and d2_assignments.empty else "EXPLICIT_C_D_MAPPING_AVAILABLE"
    meta = {
        "status": status,
        "eol_assignment_rows": len(eol_assignments), "complete_c_stage_rows": complete_c,
        "d2_assignment_rows": len(d2_assignments), "carbon_consequence_rows": len(ledger),
        "implemented_modules": ["C1", "C2", "C3", "C4", "D1", "D2"],
        "rsp_boundary_is_accounting_state_not_event": True,
        "b4_replacement_waste_duplicated_in_c": False,
        "a5_1_preconstruction_removal_duplicated_in_c": False,
        "module_d_netted_into_a_c": False,
        "factor_uncertainty_applied": False,
        "missing_data_treated_as_zero": False,
        "whole_life_carbon_generated": False,
        "claim": "Explicit terminal C1-C4 accounting with D1/D2 reported separately beyond the system boundary.",
    }
    return eol_cov, d2_cov, ledger, build_end_of_life_summary(ledger), meta


def append_end_of_life_and_d(combined: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return combined.copy()
    out = pd.concat([combined, ledger], ignore_index=True)
    if out.carbon_consequence_id.duplicated().any():
        raise ValueError("Carbon consequence ID collision after terminal C/D append.")
    return out
