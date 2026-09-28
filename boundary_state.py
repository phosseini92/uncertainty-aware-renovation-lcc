"""RSP-boundary component state for the staged v3 migration.

M1.6 deliberately keeps boundary *state* separate from the physical event
ledger.  Reaching the reference-study-period boundary is an observation point,
not necessarily a physical event.  This avoids creating fictitious events at
30/50/60 years while still providing the state needed later for residual value
and environmental consequence accounting.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
import pandas as pd

from identity import validate_stable_id

RSP_BOUNDARY_STATE_COLUMNS = (
    "boundary_state_id",
    "future_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "component_type_id",
    "component_generation_at_boundary",
    "initial_component_state",
    "rsp_years",
    "assessment_interval_start_years",
    "installation_time_years",
    "age_within_assessment_years",
    "age_at_boundary_years",
    "next_replacement_time_years",
    "remaining_life_at_boundary_years",
    "sampled_current_interval_life_years",
    "service_life_basis",
    "random_stream_key",
    "replacement_due_at_boundary",
    "state_status",
    "scenario",
    "component",
)


def empty_rsp_boundary_state() -> pd.DataFrame:
    return pd.DataFrame(columns=RSP_BOUNDARY_STATE_COLUMNS)


def _stable_boundary_state_id(
    future_id: int,
    scenario_id: str,
    component_instance_id: str,
    rsp_years: float,
) -> str:
    key = "|".join(
        [
            str(int(future_id)),
            str(scenario_id),
            str(component_instance_id),
            format(float(rsp_years), ".12g"),
        ]
    )
    return "bnd_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def canonical_rsp_boundary_states(
    *,
    future_ids: Iterable[int],
    scenario_id: str,
    component_instance_id: str,
    comparison_lineage_id: str,
    component_type_id: str,
    initial_component_state: str,
    component_generation_at_boundary: np.ndarray,
    rsp_years: float,
    assessment_interval_start_years: np.ndarray,
    installation_time_years: np.ndarray,
    age_within_assessment_years: np.ndarray,
    age_at_boundary_years: np.ndarray,
    next_replacement_time_years: np.ndarray,
    remaining_life_at_boundary_years: np.ndarray,
    sampled_current_interval_life_years: np.ndarray,
    service_life_basis: str,
    random_stream_key: str,
    replacement_due_at_boundary: np.ndarray,
    scenario: str,
    component: str,
) -> pd.DataFrame:
    ids = np.asarray(list(future_ids), dtype=int)
    generation = np.asarray(component_generation_at_boundary, dtype=int)
    interval_start = np.asarray(assessment_interval_start_years, dtype=float)
    installation = np.asarray(installation_time_years, dtype=float)
    age_within = np.asarray(age_within_assessment_years, dtype=float)
    age_boundary = np.asarray(age_at_boundary_years, dtype=float)
    next_repl = np.asarray(next_replacement_time_years, dtype=float)
    remaining = np.asarray(remaining_life_at_boundary_years, dtype=float)
    sampled = np.asarray(sampled_current_interval_life_years, dtype=float)
    due = np.asarray(replacement_due_at_boundary, dtype=bool)
    lengths = {len(x) for x in (ids, generation, interval_start, installation, age_within,
                                age_boundary, next_repl, remaining, sampled, due)}
    if len(lengths) != 1:
        raise ValueError("Boundary-state arrays must have equal length.")

    scenario_id = validate_stable_id(scenario_id, "scenario_id")
    component_instance_id = validate_stable_id(component_instance_id, "component_instance_id")
    comparison_lineage_id = validate_stable_id(comparison_lineage_id, "comparison_lineage_id")
    component_type_id = validate_stable_id(component_type_id, "component_type_id")
    if initial_component_state not in {"NEW_AT_T0", "RETAINED_EXISTING"}:
        raise ValueError(f"Unsupported initial_component_state: {initial_component_state}")
    if service_life_basis not in {"FULL_SERVICE_LIFE", "REMAINING_LIFE"}:
        raise ValueError(f"Unsupported service_life_basis: {service_life_basis}")
    if not np.isfinite(float(rsp_years)) or float(rsp_years) <= 0:
        raise ValueError("rsp_years must be finite and positive.")
    if not str(random_stream_key).strip():
        raise ValueError("Boundary state requires a nonempty random_stream_key.")

    rows = []
    for i in range(len(ids)):
        rows.append({
            "boundary_state_id": _stable_boundary_state_id(ids[i], scenario_id, component_instance_id, rsp_years),
            "future_id": int(ids[i]),
            "scenario_id": scenario_id,
            "component_instance_id": component_instance_id,
            "comparison_lineage_id": comparison_lineage_id,
            "component_type_id": component_type_id,
            "component_generation_at_boundary": int(generation[i]),
            "initial_component_state": initial_component_state,
            "rsp_years": float(rsp_years),
            "assessment_interval_start_years": float(interval_start[i]),
            "installation_time_years": float(installation[i]) if np.isfinite(installation[i]) else np.nan,
            "age_within_assessment_years": float(age_within[i]),
            "age_at_boundary_years": float(age_boundary[i]) if np.isfinite(age_boundary[i]) else np.nan,
            "next_replacement_time_years": float(next_repl[i]),
            "remaining_life_at_boundary_years": float(remaining[i]),
            "sampled_current_interval_life_years": float(sampled[i]),
            "service_life_basis": service_life_basis,
            "random_stream_key": str(random_stream_key),
            "replacement_due_at_boundary": bool(due[i]),
            "state_status": "IN_SERVICE_AT_RSP_BOUNDARY",
            "scenario": str(scenario),
            "component": str(component),
        })
    return validate_rsp_boundary_state(pd.DataFrame(rows, columns=RSP_BOUNDARY_STATE_COLUMNS))


def validate_rsp_boundary_state(table: pd.DataFrame) -> pd.DataFrame:
    missing = set(RSP_BOUNDARY_STATE_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(f"Missing RSP boundary-state columns: {sorted(missing)}")
    extra = set(table.columns) - set(RSP_BOUNDARY_STATE_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected RSP boundary-state columns: {sorted(extra)}")
    out = table.loc[:, RSP_BOUNDARY_STATE_COLUMNS].copy()
    if out.empty:
        return out

    for field in ("scenario_id", "component_instance_id", "comparison_lineage_id", "component_type_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    if out.boundary_state_id.isna().any() or out.boundary_state_id.astype(str).str.strip().eq("").any():
        raise ValueError("boundary_state_id must be nonempty.")
    if out.boundary_state_id.duplicated().any():
        raise ValueError("boundary_state_id must be unique.")

    numeric = (
        "future_id", "component_generation_at_boundary", "rsp_years",
        "assessment_interval_start_years", "installation_time_years",
        "age_within_assessment_years", "age_at_boundary_years",
        "next_replacement_time_years", "remaining_life_at_boundary_years",
        "sampled_current_interval_life_years",
    )
    for field in numeric:
        out[field] = pd.to_numeric(out[field], errors="coerce")
    required_finite = (
        "future_id", "component_generation_at_boundary", "rsp_years",
        "assessment_interval_start_years", "age_within_assessment_years",
        "next_replacement_time_years", "remaining_life_at_boundary_years",
        "sampled_current_interval_life_years",
    )
    if not np.isfinite(out.loc[:, required_finite].to_numpy(dtype=float)).all():
        raise ValueError("Required RSP boundary-state numeric fields must be finite.")
    if (out.future_id < 0).any() or (out.component_generation_at_boundary < 0).any():
        raise ValueError("Boundary future/generation identifiers must be nonnegative.")
    if (out.rsp_years <= 0).any():
        raise ValueError("RSP must be positive.")
    if (out.assessment_interval_start_years < 0).any():
        raise ValueError("Assessment interval start cannot precede t=0.")
    if (out.assessment_interval_start_years > out.rsp_years).any():
        raise ValueError("Assessment interval start cannot exceed the RSP boundary.")
    if (out.next_replacement_time_years + 1e-12 < out.rsp_years).any():
        raise ValueError("Boundary state must point to the first modeled replacement at or after the RSP.")
    if (out.remaining_life_at_boundary_years < -1e-10).any():
        raise ValueError("Remaining life at the RSP boundary cannot be negative.")
    expected_remaining = out.next_replacement_time_years - out.rsp_years
    if not np.allclose(out.remaining_life_at_boundary_years, expected_remaining, rtol=0, atol=1e-10):
        raise ValueError("Boundary remaining life must reconcile to next replacement time minus RSP.")
    expected_age_within = out.rsp_years - out.assessment_interval_start_years
    if not np.allclose(out.age_within_assessment_years, expected_age_within, rtol=0, atol=1e-10):
        raise ValueError("Boundary within-assessment age must reconcile to interval start.")
    if (out.sampled_current_interval_life_years <= 0).any():
        raise ValueError("Sampled current-interval life must be positive.")
    if not out.initial_component_state.isin({"NEW_AT_T0", "RETAINED_EXISTING"}).all():
        raise ValueError("Unsupported boundary initial_component_state.")
    if not out.service_life_basis.isin({"FULL_SERVICE_LIFE", "REMAINING_LIFE"}).all():
        raise ValueError("Unsupported boundary service_life_basis.")
    if out.loc[out.service_life_basis.eq("REMAINING_LIFE"), "component_generation_at_boundary"].ne(0).any():
        raise ValueError("REMAINING_LIFE at the RSP boundary is only valid for retained generation 0.")
    if out.loc[out.component_generation_at_boundary.gt(0), "service_life_basis"].ne("FULL_SERVICE_LIFE").any():
        raise ValueError("Installed replacement generations must use FULL_SERVICE_LIFE.")
    if not out.state_status.eq("IN_SERVICE_AT_RSP_BOUNDARY").all():
        raise ValueError("Unsupported boundary state_status.")

    due_expected = np.isclose(out.remaining_life_at_boundary_years.to_numpy(float), 0.0, rtol=0, atol=1e-10)
    if not np.array_equal(out.replacement_due_at_boundary.astype(bool).to_numpy(), due_expected):
        raise ValueError("replacement_due_at_boundary must match zero remaining life at the boundary.")

    identity_key = ["future_id", "scenario_id", "component_instance_id", "rsp_years"]
    if out.duplicated(identity_key).any():
        raise ValueError("Only one RSP boundary state is allowed per future/component/RSP.")
    return out.reset_index(drop=True)
