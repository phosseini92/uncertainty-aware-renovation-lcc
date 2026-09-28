"""B6 operational-energy carbon consequence engine (v3 M3.1).

Scope is deliberately narrow and auditable:
- explicit annual operational energy flows by scenario and carrier;
- explicit analysis-year -> calendar-year GWP_TOTAL factor schedules;
- B6 consequences for imported operational energy only;
- onsite GENERATED / SELF_CONSUMED / EXPORTED electricity is tracked for
  physical balance and provenance, but export is NOT credited or netted here;
- no inference from the legacy ``annual_energy_savings_kwh`` economic proxy;
- no interpolation/extrapolation of missing future factors;
- environmental-factor uncertainty metadata is retained but not sampled.

This module does not implement D2. Exported energy is carried forward as an
explicit physical flow for a later separate-beyond-boundary D2 milestone.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from carbon_consequences import CARBON_CONSEQUENCE_COLUMNS, _stable_id, empty_carbon_consequence_ledger
from identity import validate_stable_id, validate_unique_ids


OPERATIONAL_ENERGY_FLOW_COLUMNS = (
    "energy_flow_id",
    "scenario_id",
    "carrier_id",
    "flow_type",
    "annual_quantity_kwh",
    "first_analysis_year",
    "last_analysis_year",
    "b6_factor_schedule_id",
    "source_status",
    "source_reference",
    "retrieval_date",
    "notes",
)

OPERATIONAL_FACTOR_SCHEDULE_COLUMNS = (
    "schedule_id",
    "carrier_id",
    "analysis_year",
    "calendar_year",
    "factor_set_id",
    "source_status",
    "source_reference",
    "retrieval_date",
    "notes",
)

OPERATIONAL_COVERAGE_COLUMNS = (
    "energy_flow_id",
    "scenario_id",
    "carrier_id",
    "flow_type",
    "annual_quantity_kwh",
    "first_analysis_year",
    "last_analysis_year",
    "in_rsp_first_analysis_year",
    "in_rsp_last_analysis_year",
    "b6_factor_schedule_id",
    "b6_status",
    "b6_reason",
    "balance_status",
    "export_treatment",
)

OPERATIONAL_SUMMARY_COLUMNS = (
    "future_id",
    "scenario_id",
    "assessment_scope",
    "reported_module",
    "assessed_gwp_kgco2e",
    "consequence_row_count",
    "assessment_label",
)

FLOW_TYPES = {"IMPORTED", "GENERATED", "SELF_CONSUMED", "EXPORTED"}
SOURCE_STATUSES = {"DOCUMENTED_PROJECT_DATA", "PUBLIC_DOCUMENTED_DATA", "TEST_ONLY_SYNTHETIC"}
INFORMATIONAL_FLOW_TYPES = {"GENERATED", "SELF_CONSUMED", "EXPORTED"}


def _schema(table: pd.DataFrame, columns: tuple[str, ...], label: str) -> pd.DataFrame:
    missing = set(columns) - set(table.columns)
    extra = set(table.columns) - set(columns)
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


def empty_operational_energy_flows() -> pd.DataFrame:
    return pd.DataFrame(columns=OPERATIONAL_ENERGY_FLOW_COLUMNS)


def empty_operational_factor_schedule() -> pd.DataFrame:
    return pd.DataFrame(columns=OPERATIONAL_FACTOR_SCHEDULE_COLUMNS)


def _validate_no_overlapping_flow_intervals(out: pd.DataFrame) -> None:
    for key, group in out.groupby(["scenario_id", "carrier_id", "flow_type"], sort=False):
        active: set[int] = set()
        for row in group.itertuples(index=False):
            years = set(range(int(row.first_analysis_year), int(row.last_analysis_year) + 1))
            overlap = active & years
            if overlap:
                raise ValueError(
                    "Overlapping operational flow intervals are ambiguous for "
                    f"scenario/carrier/flow_type={key}; overlapping years={sorted(overlap)[:8]}."
                )
            active |= years


def _validate_declared_flow_balance(out: pd.DataFrame) -> None:
    """Check PV/electricity bookkeeping year by year on explicitly declared flows.

    Generated energy is allowed to exceed self-consumed + exported energy because
    curtailment or other documented losses may exist.  What is forbidden is
    self-consumption or export exceeding the generated quantity for the same
    scenario, carrier and analysis year.
    """
    if out.empty:
        return
    for (scenario_id, carrier_id), group in out.groupby(["scenario_id", "carrier_id"], sort=False):
        first = int(group.first_analysis_year.min())
        last = int(group.last_analysis_year.max())
        for year in range(first, last + 1):
            active = group[(group.first_analysis_year <= year) & (group.last_analysis_year >= year)]
            quantities = {
                flow: float(active.loc[active.flow_type.eq(flow), "annual_quantity_kwh"].sum())
                for flow in FLOW_TYPES
            }
            generated = quantities["GENERATED"]
            self_consumed = quantities["SELF_CONSUMED"]
            exported = quantities["EXPORTED"]
            if self_consumed > generated + 1e-12:
                raise ValueError(
                    f"SELF_CONSUMED exceeds GENERATED for {scenario_id}/{carrier_id} in analysis year {year}."
                )
            if self_consumed + exported > generated + 1e-12:
                raise ValueError(
                    f"SELF_CONSUMED + EXPORTED exceeds GENERATED for {scenario_id}/{carrier_id} "
                    f"in analysis year {year}."
                )


def validate_operational_energy_flows(table: pd.DataFrame, scenarios: pd.DataFrame) -> pd.DataFrame:
    out = _schema(table, OPERATIONAL_ENERGY_FLOW_COLUMNS, "Operational energy flow")
    if out.empty:
        return out

    for field in ("energy_flow_id", "scenario_id", "carrier_id"):
        out[field] = [validate_stable_id(value, field) for value in out[field]]
    validate_unique_ids(out.energy_flow_id, "energy_flow_id")

    out.flow_type = out.flow_type.astype(str).str.strip().str.upper()
    if not out.flow_type.isin(FLOW_TYPES).all():
        raise ValueError(f"Unsupported operational flow_type; allowed={sorted(FLOW_TYPES)}")

    out.annual_quantity_kwh = pd.to_numeric(out.annual_quantity_kwh, errors="raise")
    values = out.annual_quantity_kwh.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("annual_quantity_kwh must be finite and nonnegative.")

    for field in ("first_analysis_year", "last_analysis_year"):
        out[field] = pd.to_numeric(out[field], errors="raise")
        values = out[field].to_numpy(dtype=float)
        if not np.isfinite(values).all() or ((values % 1) != 0).any() or (values < 1).any():
            raise ValueError(f"{field} must be a positive integer.")
        out[field] = out[field].astype(int)
    if (out.first_analysis_year > out.last_analysis_year).any():
        raise ValueError("Operational flow first_analysis_year exceeds last_analysis_year.")

    out.b6_factor_schedule_id = out.b6_factor_schedule_id.fillna("").astype(str).str.strip()
    out.b6_factor_schedule_id = [
        validate_stable_id(value, "b6_factor_schedule_id") if value else ""
        for value in out.b6_factor_schedule_id
    ]

    out.source_status = out.source_status.astype(str).str.strip().str.upper()
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError(f"Unsupported operational source_status; allowed={sorted(SOURCE_STATUSES)}")
    out.source_reference = out.source_reference.fillna("").astype(str).str.strip()
    if out.source_reference.eq("").any():
        raise ValueError("Operational flow source_reference is required; missing data must not be encoded as zero.")
    out.retrieval_date = [_iso_date(value) for value in out.retrieval_date]
    out.notes = out.notes.fillna("").astype(str)

    known_scenarios = set(scenarios.scenario_id.astype(str))
    if not set(out.scenario_id).issubset(known_scenarios):
        unknown = sorted(set(out.scenario_id) - known_scenarios)
        raise ValueError(f"Operational flow references unknown scenario_id: {unknown}")

    for row in out.itertuples(index=False):
        if row.flow_type == "IMPORTED" and not row.b6_factor_schedule_id:
            raise ValueError("IMPORTED operational flow requires an explicit b6_factor_schedule_id.")
        if row.flow_type != "IMPORTED" and row.b6_factor_schedule_id:
            raise ValueError("Only IMPORTED operational flow may carry a B6 factor schedule in M3.1.")

    _validate_no_overlapping_flow_intervals(out)
    _validate_declared_flow_balance(out)
    return out


def validate_operational_factor_schedule(table: pd.DataFrame, environmental_factors: pd.DataFrame) -> pd.DataFrame:
    out = _schema(table, OPERATIONAL_FACTOR_SCHEDULE_COLUMNS, "Operational factor schedule")
    if out.empty:
        return out

    for field in ("schedule_id", "carrier_id", "factor_set_id"):
        out[field] = [validate_stable_id(value, field) for value in out[field]]

    for field in ("analysis_year", "calendar_year"):
        out[field] = pd.to_numeric(out[field], errors="raise")
        values = out[field].to_numpy(dtype=float)
        if not np.isfinite(values).all() or ((values % 1) != 0).any():
            raise ValueError(f"{field} must be an integer.")
        out[field] = out[field].astype(int)
    if (out.analysis_year < 1).any():
        raise ValueError("analysis_year must be >= 1.")
    if not out.calendar_year.between(1900, 2200).all():
        raise ValueError("calendar_year must be between 1900 and 2200.")
    if out.duplicated(["schedule_id", "analysis_year"]).any():
        raise ValueError("Duplicate operational factor schedule year.")

    out.source_status = out.source_status.astype(str).str.strip().str.upper()
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError(f"Unsupported operational schedule source_status; allowed={sorted(SOURCE_STATUSES)}")
    out.source_reference = out.source_reference.fillna("").astype(str).str.strip()
    if out.source_reference.eq("").any():
        raise ValueError("Operational factor schedule source_reference is required.")
    out.retrieval_date = [_iso_date(value) for value in out.retrieval_date]
    out.notes = out.notes.fillna("").astype(str)

    factor_set_ids = set(environmental_factors.factor_set_id.astype(str))
    if not set(out.factor_set_id).issubset(factor_set_ids):
        unknown = sorted(set(out.factor_set_id) - factor_set_ids)
        raise ValueError(f"Operational factor schedule references unknown factor_set_id: {unknown}")

    for schedule_id, group in out.groupby("schedule_id", sort=False):
        if group.carrier_id.nunique() != 1:
            raise ValueError(f"Operational schedule {schedule_id} mixes carrier_id values.")
        offsets = group.calendar_year - group.analysis_year
        if offsets.nunique() != 1:
            raise ValueError(
                f"Operational schedule {schedule_id} has inconsistent analysis-year/calendar-year mapping."
            )
        years = sorted(group.analysis_year.tolist())
        if len(years) > 1 and any(b <= a for a, b in zip(years, years[1:])):
            raise ValueError(f"Operational schedule {schedule_id} analysis years must be strictly increasing.")

    for row in out.itertuples(index=False):
        candidates = environmental_factors.loc[
            environmental_factors.factor_set_id.eq(row.factor_set_id)
            & environmental_factors.indicator_id.eq("GWP_TOTAL")
            & environmental_factors.module_scope.eq("B6")
        ]
        if len(candidates) != 1:
            raise ValueError(
                "Operational factor schedule requires exactly one GWP_TOTAL environmental factor with exact B6 scope."
            )
        factor = candidates.iloc[0]
        if str(factor.declared_unit).strip().lower() != "kwh":
            raise ValueError("B6 operational energy GWP factor must use kwh declared unit.")
        value = float(factor.indicator_value)
        if not np.isfinite(value) or value < 0:
            raise ValueError("B6 GWP_TOTAL factor must be finite and nonnegative; negative credits are not allowed in B6.")
    return out


def load_operational_energy_flows(path: Path, scenarios: pd.DataFrame) -> pd.DataFrame:
    return validate_operational_energy_flows(pd.read_csv(path), scenarios)


def load_operational_factor_schedule(path: Path, environmental_factors: pd.DataFrame) -> pd.DataFrame:
    return validate_operational_factor_schedule(pd.read_csv(path), environmental_factors)


def _schedule_lookup(schedule: pd.DataFrame) -> dict[tuple[str, int], object]:
    if schedule.empty:
        return {}
    return {
        (str(row.schedule_id), int(row.analysis_year)): row
        for row in schedule.itertuples(index=False)
    }


def build_operational_coverage(
    flows: pd.DataFrame,
    schedule: pd.DataFrame,
    analysis_years: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    schedule_lookup = _schedule_lookup(schedule)

    for row in flows.itertuples(index=False):
        in_first = max(1, int(row.first_analysis_year))
        in_last = min(int(row.last_analysis_year), int(analysis_years))
        active_years = list(range(in_first, in_last + 1)) if in_first <= in_last else []

        if row.flow_type == "IMPORTED":
            if not active_years:
                b6_status = "NOT_APPLICABLE_OUTSIDE_RSP"
                b6_reason = "Declared imported-energy interval does not overlap the selected reference study period."
            elif float(row.annual_quantity_kwh) == 0.0:
                b6_status = "PASS_EXPLICIT_ZERO_IMPORTED_ENERGY"
                b6_reason = "Explicit documented zero imported-energy flow; no zero-impact consequence row is emitted."
            else:
                missing = [
                    year for year in active_years
                    if (str(row.b6_factor_schedule_id), year) not in schedule_lookup
                ]
                carrier_mismatch = [
                    year for year in active_years
                    if (str(row.b6_factor_schedule_id), year) in schedule_lookup
                    and str(schedule_lookup[(str(row.b6_factor_schedule_id), year)].carrier_id) != str(row.carrier_id)
                ]
                if carrier_mismatch:
                    b6_status = "BLOCKED_FACTOR_SCHEDULE_CARRIER_MISMATCH"
                    b6_reason = f"B6 schedule carrier differs from flow carrier in years: {carrier_mismatch[:8]}"
                elif missing:
                    b6_status = "BLOCKED_INCOMPLETE_B6_FACTOR_SCHEDULE"
                    b6_reason = f"Missing explicit B6 factor schedule years: {missing[:8]}"
                else:
                    b6_status = "PASS_COMPLETE_B6_FACTOR_SCHEDULE"
                    b6_reason = "Explicit B6 factor schedule covers every in-RSP analysis year; no interpolation/extrapolation."
        else:
            b6_status = "NOT_APPLICABLE_INFORMATIONAL_FLOW"
            if row.flow_type == "EXPORTED":
                b6_reason = "Exported energy is tracked physically but is not a B6 credit and is not netted into A-C."
            else:
                b6_reason = f"{row.flow_type} is tracked for operational-energy balance but does not itself create B6 GWP."

        rows.append({
            "energy_flow_id": row.energy_flow_id,
            "scenario_id": row.scenario_id,
            "carrier_id": row.carrier_id,
            "flow_type": row.flow_type,
            "annual_quantity_kwh": float(row.annual_quantity_kwh),
            "first_analysis_year": int(row.first_analysis_year),
            "last_analysis_year": int(row.last_analysis_year),
            "in_rsp_first_analysis_year": in_first if active_years else np.nan,
            "in_rsp_last_analysis_year": in_last if active_years else np.nan,
            "b6_factor_schedule_id": row.b6_factor_schedule_id,
            "b6_status": b6_status,
            "b6_reason": b6_reason,
            "balance_status": "PASS_DECLARED_ANNUAL_FLOW_BALANCE",
            "export_treatment": "TRACKED_ONLY_D2_DEFERRED_NOT_NETTED_IN_A_C" if row.flow_type == "EXPORTED" else "NOT_APPLICABLE",
        })
    return pd.DataFrame(rows, columns=OPERATIONAL_COVERAGE_COLUMNS)


def build_operational_ledger(
    flows: pd.DataFrame,
    schedule: pd.DataFrame,
    environmental_factors: pd.DataFrame,
    coverage: pd.DataFrame,
    future_ids,
    analysis_years: int,
) -> pd.DataFrame:
    if flows.empty:
        return empty_carbon_consequence_ledger()

    coverage_lookup = coverage.set_index("energy_flow_id", drop=False)
    schedule_lookup = _schedule_lookup(schedule)
    rows: list[dict[str, object]] = []

    for flow in flows.itertuples(index=False):
        cov = coverage_lookup.loc[flow.energy_flow_id]
        if cov.b6_status != "PASS_COMPLETE_B6_FACTOR_SCHEDULE":
            continue
        first = max(1, int(flow.first_analysis_year))
        last = min(int(flow.last_analysis_year), int(analysis_years))
        quantity = float(flow.annual_quantity_kwh)
        if quantity <= 0:
            continue

        for analysis_year in range(first, last + 1):
            schedule_row = schedule_lookup[(str(flow.b6_factor_schedule_id), analysis_year)]
            factors = environmental_factors.loc[
                environmental_factors.factor_set_id.eq(schedule_row.factor_set_id)
                & environmental_factors.indicator_id.eq("GWP_TOTAL")
                & environmental_factors.module_scope.eq("B6")
            ]
            if len(factors) != 1:
                raise ValueError("Executable B6 schedule lost its unique GWP_TOTAL/B6 factor during ledger build.")
            factor = factors.iloc[0]
            factor_value = float(factor.indicator_value)
            impact = quantity * factor_value
            event_time = float(analysis_year) - 0.5  # midpoint of annual period, safely inside [0, RSP)

            for future_id in future_ids:
                rows.append({
                    "carbon_consequence_id": _stable_id(
                        "cc", "b6_operational_energy_import", flow.energy_flow_id,
                        analysis_year, factor.factor_record_id, int(future_id)
                    ),
                    "future_id": int(future_id),
                    "scenario_id": flow.scenario_id,
                    "component_instance_id": "system_operational_energy",
                    "comparison_lineage_id": "system_operational_energy",
                    "component_generation": 0,
                    "consequence_type": "B6_OPERATIONAL_ENERGY_IMPORT",
                    "lifecycle_event_id": np.nan,
                    "source_event_type": "ANNUAL_OPERATIONAL_ENERGY",
                    "event_time_years": event_time,
                    "boq_line_id": "",
                    "material_or_product_id": flow.carrier_id,
                    "assignment_id": flow.energy_flow_id,
                    "factor_set_id": factor.factor_set_id,
                    "factor_record_id": factor.factor_record_id,
                    "dataset_id": factor.dataset_id,
                    "factor_product_or_process_id": factor.product_or_process_id,
                    "factor_declared_unit": factor.declared_unit,
                    "factor_reference_year": int(factor.reference_year),
                    "indicator_id": "GWP_TOTAL",
                    "source_factor_module_scope": "B6",
                    "reported_module": "B6",
                    "boq_quantity": quantity,
                    "boq_unit": "kwh",
                    "resolved_activity_quantity": quantity,
                    "resolved_activity_unit": "kwh",
                    "indicator_value_per_declared_unit": factor_value,
                    "indicator_unit": factor.indicator_unit,
                    "gwp_kgco2e": impact,
                    "mapping_basis": "EXPLICIT_ANNUAL_FACTOR_SCHEDULE",
                    "conversion_method": "NONE",
                    "source_type": factor.source_type,
                    "source_citation": factor.source_citation,
                    "verification_status": factor.verification_status,
                    "data_quality_status": factor.data_quality_status,
                    "license_status": factor.license_status,
                    "redistribution_allowed": bool(factor.redistribution_allowed),
                    "factor_uncertainty_mode": factor.uncertainty_mode,
                    "factor_uncertainty_semantics": factor.uncertainty_semantics,
                    "factor_uncertainty_applied": False,
                    "factor_temporal_basis": f"EXPLICIT_ANALYSIS_YEAR_{analysis_year}_CALENDAR_YEAR_{int(schedule_row.calendar_year)}",
                    "provenance_status": "EXPLICIT_B6_FLOW_AND_TIME_SERIES_FACTOR",
                })

    if not rows:
        return empty_carbon_consequence_ledger()
    out = pd.DataFrame(rows, columns=CARBON_CONSEQUENCE_COLUMNS)
    if out.carbon_consequence_id.duplicated().any():
        raise ValueError("Duplicate B6 operational carbon consequence ID.")
    if not out.reported_module.eq("B6").all():
        raise ValueError("Operational consequences generated by M3.1 must report to B6.")
    if not out.source_factor_module_scope.eq("B6").all():
        raise ValueError("M3.1 B6 consequences require exact B6 source factor scope.")
    if not out.indicator_id.eq("GWP_TOTAL").all():
        raise ValueError("M3.1 executes GWP_TOTAL only.")
    if out.lifecycle_event_id.notna().any():
        raise ValueError("Annual B6 operational consequences are not canonical component lifecycle events.")
    expected = out.resolved_activity_quantity.astype(float) * out.indicator_value_per_declared_unit.astype(float)
    if not np.allclose(expected, out.gwp_kgco2e.astype(float), rtol=1e-12, atol=1e-12):
        raise ValueError("B6 GWP does not reconcile to kWh × factor.")
    return out


def build_operational_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame(columns=OPERATIONAL_SUMMARY_COLUMNS)
    out = ledger.groupby(["future_id", "scenario_id", "reported_module"], as_index=False).agg(
        assessed_gwp_kgco2e=("gwp_kgco2e", "sum"),
        consequence_row_count=("carbon_consequence_id", "count"),
    )
    out["assessment_scope"] = "B6_OPERATIONAL_ENERGY_IMPORTS_ONLY"
    out["assessment_label"] = "ASSESSED_B6_OPERATIONAL_ENERGY_ONLY_NOT_WHOLE_LIFE_CARBON"
    return out.loc[:, OPERATIONAL_SUMMARY_COLUMNS]


def assess_operational_energy(
    flows: pd.DataFrame,
    schedule: pd.DataFrame,
    environmental_factors: pd.DataFrame,
    future_ids,
    analysis_years: int,
    factor_extrapolation_policy: str = "ERROR_IF_MISSING",
    generated_energy_reporting_approach: str = "PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED",
):
    if factor_extrapolation_policy != "ERROR_IF_MISSING":
        raise ValueError(
            "M3.1.1 B6 supports ERROR_IF_MISSING only; no interpolation, extrapolation or carry-forward is implemented."
        )
    if generated_energy_reporting_approach != "PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED":
        raise ValueError(
            "M3.1.1 B6 supports PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED only."
        )
    coverage = build_operational_coverage(flows, schedule, analysis_years)
    ledger = build_operational_ledger(
        flows, schedule, environmental_factors, coverage, future_ids, analysis_years
    )
    summary = build_operational_summary(ledger)

    executable = int(coverage.b6_status.eq("PASS_COMPLETE_B6_FACTOR_SCHEDULE").sum()) if not coverage.empty else 0
    explicit_zero = int(coverage.b6_status.eq("PASS_EXPLICIT_ZERO_IMPORTED_ENERGY").sum()) if not coverage.empty else 0
    blocked = int(coverage.b6_status.str.startswith("BLOCKED_").sum()) if not coverage.empty else 0
    exported = int(coverage.flow_type.eq("EXPORTED").sum()) if not coverage.empty else 0

    if flows.empty:
        status = "NO_OPERATIONAL_ENERGY_FLOWS"
    elif blocked:
        status = "B6_BLOCKED_INCOMPLETE_OR_INCOMPATIBLE_FACTOR_MAPPING"
    elif executable or explicit_zero:
        status = "B6_OPERATIONAL_ENERGY_MAPPING_AVAILABLE"
    else:
        status = "NO_EXECUTABLE_B6_OPERATIONAL_CARBON_MAPPING"

    meta = {
        "status": status,
        "flow_rows": len(flows),
        "b6_executable_import_flow_rows": executable,
        "b6_explicit_zero_import_flow_rows": explicit_zero,
        "blocked_import_flow_rows": blocked,
        "exported_flow_rows_tracked": exported,
        "carbon_consequence_rows": len(ledger),
        "implemented_modules": ["B6"],
        "legacy_annual_energy_savings_proxy_used_for_carbon": False,
        "negative_operational_energy_flows_allowed": False,
        "generated_self_consumed_exported_flows_used_as_negative_b6": False,
        "export_credit_calculated": False,
        "export_credit_netted_into_a_c": False,
        "d2_status": "DEFERRED_SEPARATE_BEYOND_BOUNDARY_MILESTONE",
        "factor_extrapolation_policy": factor_extrapolation_policy,
        "generated_energy_reporting_approach": generated_energy_reporting_approach,
        "future_factor_policy": "EXPLICIT_ANNUAL_SCHEDULE_ERROR_IF_MISSING_NO_INTERPOLATION_NO_EXTRAPOLATION",
        "factor_reference_year_semantics": "DATASET_OR_SOURCE_REFERENCE_VINTAGE_NOT_APPLICATION_YEAR",
        "application_year_semantics": "operational_energy_factor_schedule.calendar_year",
        "factor_uncertainty_applied": False,
        "missing_data_treated_as_zero": False,
        "whole_life_carbon_generated": False,
        "claim": (
            "B6 operational GWP is calculated only from explicit imported-energy flows and an explicit "
            "analysis-year/calendar-year factor schedule. Generated, self-consumed and exported flows are "
            "tracked for physical bookkeeping; export is not credited or netted in this milestone."
        ),
    }
    return coverage, ledger, summary, meta


def append_operational_consequences(combined: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return combined.copy()
    if combined.empty:
        return ledger.copy()
    out = pd.concat([combined, ledger], ignore_index=True)
    if out.carbon_consequence_id.duplicated().any():
        raise ValueError("Carbon consequence ID collision after B6 operational append.")
    return out
