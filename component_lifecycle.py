"""Illustrative renewal-cost schedules for componentized incremental budgets.

Life is time to renewal; a sampled failure triggers immediate replacement.
There is no outage, damage-state or physical degradation model.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from random_streams import rng_for
from identity import (
    legacy_comparison_lineage_id,
    legacy_component_instance_id,
    legacy_component_type_id,
    legacy_scenario_id,
    validate_stable_id,
    validate_unique_ids,
)
from lifecycle_events import (
    canonical_replacement_events,
    empty_lifecycle_event_ledger,
    legacy_replacement_events_from_ledger,
)
from boundary_state import (
    canonical_rsp_boundary_states,
    empty_rsp_boundary_state,
)

COMPONENT_FIELDS = ("initial_cost_eur", "minimum_lifetime_years", "most_likely_lifetime_years",
                    "maximum_lifetime_years", "replacement_cost_factor", "maintenance_cost_eur")
EVENT_COLUMNS = ("future_id", "scenario", "component", "renewal_number", "renewal_time_years",
                 "preceding_service_life_years", "nominal_replacement_cost_eur", "pv_replacement_cost_eur")

INITIAL_COMPONENT_STATES = {"NEW_AT_T0", "RETAINED_EXISTING"}
M15_REMAINING_FIELDS = (
    "remaining_life_distribution",
    "remaining_life_min_years",
    "remaining_life_mode_years",
    "remaining_life_max_years",
    "remaining_life_fixed_years",
    "remaining_life_uncertainty_key",
)
M15_FULL_FIELDS = (
    "full_life_distribution",
    "full_life_min_years",
    "full_life_mode_years",
    "full_life_max_years",
    "full_life_fixed_years",
    "full_life_uncertainty_key",
)
M15_NUMERIC_FIELDS = (
    "remaining_life_min_years", "remaining_life_mode_years", "remaining_life_max_years",
    "remaining_life_fixed_years", "full_life_min_years", "full_life_mode_years",
    "full_life_max_years", "full_life_fixed_years", "age_at_t0_years",
)


def _is_blank(value) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def _optional_text(value, default=None):
    return default if _is_blank(value) else str(value).strip()


def _component_initial_state(component) -> str:
    state = _optional_text(getattr(component, "initial_component_state", None), "NEW_AT_T0")
    if state not in INITIAL_COMPONENT_STATES:
        raise ValueError(f"Unsupported initial_component_state: {state}")
    return state


def _explicit_life_spec(component, prefix: str):
    """Return an explicit M1.5 life model or None when no override is declared."""
    distribution = _optional_text(getattr(component, f"{prefix}_life_distribution", None))
    fields = M15_REMAINING_FIELDS if prefix == "remaining" else M15_FULL_FIELDS
    other_values = [getattr(component, field, None) for field in fields if field != f"{prefix}_life_distribution"]
    if distribution is None:
        if any(not _is_blank(v) for v in other_values):
            raise ValueError(f"{prefix}_life fields require {prefix}_life_distribution.")
        return None
    if distribution not in {"fixed", "triangular"}:
        raise ValueError(f"{prefix}_life_distribution must be 'fixed' or 'triangular'.")
    key = _optional_text(getattr(component, f"{prefix}_life_uncertainty_key", None))
    if not key:
        raise ValueError(f"{prefix}_life_uncertainty_key is required for an explicit {prefix} life model.")

    fixed = getattr(component, f"{prefix}_life_fixed_years", None)
    lo = getattr(component, f"{prefix}_life_min_years", None)
    mode = getattr(component, f"{prefix}_life_mode_years", None)
    hi = getattr(component, f"{prefix}_life_max_years", None)
    if distribution == "fixed":
        if _is_blank(fixed):
            raise ValueError(f"{prefix}_life_fixed_years is required for a fixed {prefix} life model.")
        fixed = float(fixed)
        if not np.isfinite(fixed) or fixed <= 0:
            raise ValueError(f"{prefix}_life_fixed_years must be finite and positive.")
        supplied = [v for v in (lo, mode, hi) if not _is_blank(v)]
        if supplied and not all(np.isclose(float(v), fixed, rtol=0, atol=0) for v in supplied):
            raise ValueError(f"Optional {prefix} min/mode/max must equal fixed years when supplied.")
        return {"distribution": "fixed", "min": fixed, "mode": fixed, "max": fixed, "key": key}

    if not _is_blank(fixed):
        raise ValueError(f"{prefix}_life_fixed_years must be blank for a triangular life model.")
    if any(_is_blank(v) for v in (lo, mode, hi)):
        raise ValueError(f"Triangular {prefix} life requires min, mode and max years.")
    lo, mode, hi = map(float, (lo, mode, hi))
    if not all(np.isfinite(v) for v in (lo, mode, hi)) or not (0 < lo <= mode <= hi) or lo == hi:
        raise ValueError(f"Triangular {prefix} life requires 0 < min <= mode <= max with min < max.")
    return {"distribution": "triangular", "min": lo, "mode": mode, "max": hi, "key": key}


def _full_life_spec(component):
    explicit = _explicit_life_spec(component, "full")
    if explicit is not None:
        return explicit
    return {
        "distribution": str(component.lifetime_distribution),
        "min": float(component.minimum_lifetime_years),
        "mode": float(component.most_likely_lifetime_years),
        "max": float(component.maximum_lifetime_years),
        "key": str(component.uncertainty_key),
    }


def _remaining_life_spec(component):
    if _component_initial_state(component) != "RETAINED_EXISTING":
        raise ValueError("Remaining life is only valid for RETAINED_EXISTING components.")
    explicit = _explicit_life_spec(component, "remaining")
    if explicit is None:
        raise ValueError("MISSING_REMAINING_LIFE_MODEL_FOR_RETAINED_COMPONENT")
    return explicit


def _validate_m15_life_models(table: pd.DataFrame) -> pd.DataFrame:
    """Validate optional M1.5 retained/full-life fields without altering legacy tables."""
    out = table.copy()
    if "initial_component_state" in out.columns:
        if out.initial_component_state.isna().any():
            raise ValueError("initial_component_state cannot be missing when the column is present.")
        out["initial_component_state"] = out.initial_component_state.astype(str).str.strip()
        if out.initial_component_state.eq("").any() or not out.initial_component_state.isin(INITIAL_COMPONENT_STATES).all():
            raise ValueError("initial_component_state must be NEW_AT_T0 or RETAINED_EXISTING.")

    for field in M15_NUMERIC_FIELDS:
        if field in out.columns:
            nonblank = ~out[field].isna() & out[field].astype(str).str.strip().ne("")
            converted = pd.to_numeric(out.loc[nonblank, field], errors="raise")
            if not np.isfinite(converted.to_numpy(dtype=float)).all():
                raise ValueError(f"Nonfinite M1.5 component field: {field}")
            out.loc[nonblank, field] = converted.astype(float)
    if "age_at_t0_years" in out.columns:
        nonblank = ~out.age_at_t0_years.isna() & out.age_at_t0_years.astype(str).str.strip().ne("")
        if (pd.to_numeric(out.loc[nonblank, "age_at_t0_years"], errors="raise") < 0).any():
            raise ValueError("age_at_t0_years is provenance metadata and must be nonnegative when supplied.")

    # Row-wise validation uses the same resolver as the simulation engine.
    for row in out.itertuples(index=False):
        state = _component_initial_state(row)
        _full_life_spec(row)
        age = getattr(row, "age_at_t0_years", None)
        if state == "RETAINED_EXISTING":
            _remaining_life_spec(row)
        else:
            if not _is_blank(age) and not np.isclose(float(age), 0.0, rtol=0, atol=0):
                raise ValueError("NEW_AT_T0 component age must be zero or blank.")
            for field in M15_REMAINING_FIELDS:
                if hasattr(row, field) and not _is_blank(getattr(row, field)):
                    raise ValueError("NEW_AT_T0 components must not declare remaining-life fields.")
    return out


def _draw_life(spec, n: int, seed: int, stream_key: str, central: bool):
    if central or spec["distribution"] == "fixed":
        return np.full(n, spec["mode"], dtype=float)
    rng = rng_for(seed, stream_key)
    return rng.triangular(spec["min"], spec["mode"], spec["max"], n)


def _ensure_component_identity_columns(table: pd.DataFrame, scenarios: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a copy with explicit identity/lineage columns.

    Migrated v3 files provide authoritative IDs.  Legacy files (and compact
    in-memory test fixtures) are still accepted and receive deterministic IDs
    prefixed ``legacy_``.  Explicit comparison lineage is independent of
    display labels and is therefore stable when names are edited.
    """
    out = table.copy()

    scenario_map = {}
    if scenarios is not None and {"scenario", "scenario_id"}.issubset(scenarios.columns):
        scenario_map = dict(zip(scenarios.scenario.astype(str), scenarios.scenario_id.astype(str)))

    if "scenario_id" in out:
        out["scenario_id"] = [validate_stable_id(v, "scenario_id") for v in out.scenario_id]
    else:
        out["scenario_id"] = [scenario_map.get(str(name), legacy_scenario_id(name)) for name in out.scenario]

    if scenario_map:
        expected = out.scenario.map(scenario_map)
        active_mask = expected.notna()
        if not expected.loc[active_mask].astype(str).eq(out.loc[active_mask, "scenario_id"].astype(str)).all():
            raise ValueError("Component scenario_id does not match the scenario table for its display scenario.")

    if "component_type_id" in out:
        out["component_type_id"] = [validate_stable_id(v, "component_type_id") for v in out.component_type_id]
    else:
        out["component_type_id"] = [
            legacy_component_type_id(k, n) for k, n in zip(out.uncertainty_key, out.component)
        ]

    if "component_instance_id" in out:
        out["component_instance_id"] = [validate_stable_id(v, "component_instance_id") for v in out.component_instance_id]
    else:
        out["component_instance_id"] = [
            legacy_component_instance_id(sid, name) for sid, name in zip(out.scenario_id, out.component)
        ]

    if "comparison_lineage_id" in out:
        out["comparison_lineage_id"] = [validate_stable_id(v, "comparison_lineage_id") for v in out.comparison_lineage_id]
    else:
        out["comparison_lineage_id"] = [legacy_comparison_lineage_id(k) for k in out.uncertainty_key]

    validate_unique_ids(out.component_instance_id, "component_instance_id")

    # One explicit lineage must describe one component family and one effective
    # full-life random stream. M1.5 separates the remaining-life stream used by
    # retained generation-0 components from the full-life stream used after
    # replacement. This preserves paired common-random-number semantics without
    # forcing remaining and full service lives to share a key.
    for lineage, group in out.groupby("comparison_lineage_id", sort=False):
        if group.component_type_id.nunique() != 1:
            raise ValueError(f"comparison_lineage_id maps to multiple component types: {lineage}")
        full_keys = []
        retained_remaining_keys = []
        for row in group.itertuples(index=False):
            full_keys.append(_full_life_spec(row)["key"])
            if _component_initial_state(row) == "RETAINED_EXISTING":
                retained_remaining_keys.append(_remaining_life_spec(row)["key"])
        if len(set(full_keys)) != 1:
            raise ValueError(f"comparison_lineage_id maps to multiple full-life uncertainty keys: {lineage}")
        if retained_remaining_keys and len(set(retained_remaining_keys)) != 1:
            raise ValueError(f"comparison_lineage_id maps to multiple retained remaining-life uncertainty keys: {lineage}")

    return out


def load_components(path: Path, scenarios: pd.DataFrame):
    table = pd.read_csv(path)
    required = {"scenario", "component", "uncertainty_key", "lifetime_distribution", *COMPONENT_FIELDS}
    if required - set(table):
        raise ValueError(f"Missing component columns: {sorted(required-set(table))}")
    for field in ("scenario", "component", "uncertainty_key", "lifetime_distribution"):
        if table[field].isna().any(): raise ValueError(f"Missing component field: {field}")
        table[field] = table[field].astype(str).str.strip()
        if table[field].eq("").any(): raise ValueError(f"Empty component field: {field}")
    if table.duplicated(["scenario", "component"]).any():
        raise ValueError("Component names must be unique within each scenario.")
    for field in COMPONENT_FIELDS:
        table[field] = pd.to_numeric(table[field], errors="raise")
        if not np.isfinite(table[field]).all(): raise ValueError(f"Nonfinite component field: {field}")
    if not table.lifetime_distribution.isin(["fixed", "triangular"]).all():
        raise ValueError("Lifetimes support 'fixed' or 'triangular'.")
    lo, mode, hi = (table[x] for x in COMPONENT_FIELDS[1:4])
    if ((lo <= 0) | (mode < lo) | (hi < mode)).any():
        raise ValueError("Lifetimes require 0 < minimum <= mode <= maximum.")
    if ((table.lifetime_distribution.eq("fixed")) & ((lo != mode) | (mode != hi))).any():
        raise ValueError("A fixed life must have equal minimum, mode and maximum.")
    if ((table.lifetime_distribution.eq("triangular")) & lo.eq(hi)).any():
        raise ValueError("Use 'fixed' for a degenerate lifetime.")
    if table[["initial_cost_eur", "replacement_cost_factor", "maintenance_cost_eur"]].lt(0).any().any():
        raise ValueError("Component budget, replacement factor and maintenance must be nonnegative.")

    table = _validate_m15_life_models(table)
    table = _ensure_component_identity_columns(table, scenarios)

    # Unused package rows are allowed so removing an alternative does not require a new inventory.
    active = table.loc[table.scenario.isin(scenarios.scenario)].copy()
    references = scenarios.loc[scenarios.is_reference.eq(1), "scenario"]
    if active.scenario.isin(references).any():
        raise ValueError("The zero incremental reference cannot have component costs.")
    for row in scenarios.loc[scenarios.is_reference.eq(0)].itertuples():
        components = active.loc[active.scenario.eq(row.scenario)]
        if components.empty: raise ValueError(f"No component inventory for {row.scenario}.")
        if not np.isclose(components.initial_cost_eur.sum(), row.initial_capex_eur, atol=.01, rtol=0):
            raise ValueError(f"Component investment does not reconcile to scenario CAPEX: {row.scenario}")
        if not np.isclose(components.maintenance_cost_eur.sum(), row.annual_maintenance_eur, atol=.01, rtol=0):
            raise ValueError(f"Component maintenance does not reconcile: {row.scenario}")
    return active.reset_index(drop=True)


def _renewal_cost_engine(components, futures, config, seed, central=False, retain_events=False, retain_boundary=False):
    """Internal renewal engine returning totals plus canonical physical events.

    Economic equations remain the v2.1 equations. M1.5 adds one new physical
    lifecycle semantic: a RETAINED_EXISTING component may use an explicit
    remaining-life model for its first renewal only; every installed replacement
    uses the full service-life model. NEW_AT_T0 legacy components follow the
    exact v2.1 lifetime streams and therefore preserve 30-year parity.
    """
    components = _validate_m15_life_models(components)
    components = _ensure_component_identity_columns(components)
    n, horizon = len(futures), config["analysis_years"]
    discount = futures.discount_rate.to_numpy()
    cost_factor = futures.capex_factor.to_numpy()
    rows, canonical_chunks, replacement_cost_chunks, boundary_chunks = [], [], [], []
    for component in components.itertuples():
        times, total = np.zeros(n), np.zeros(n)
        counts = np.zeros(n, dtype=int)
        boundary_recorded = np.zeros(n, dtype=bool) if retain_boundary else None
        first_life = None
        state = _component_initial_state(component)
        full_spec = _full_life_spec(component)
        remaining_spec = _remaining_life_spec(component) if state == "RETAINED_EXISTING" else None

        # Upper-bound the number of generations without using the retained
        # component's possibly short remaining life as if it recurred forever.
        if state == "RETAINED_EXISTING":
            max_cycles = 1 + int(np.ceil(max(0.0, horizon - remaining_spec["min"]) / full_spec["min"]))
        else:
            max_cycles = int(np.ceil(horizon / full_spec["min"]))
        max_cycles = max(1, max_cycles)
        if max_cycles > 1000:
            raise ValueError("At most 1000 possible renewals per component; review the lifetime/horizon units.")

        for cycle in range(1, max_cycles + 1):
            if cycle == 1 and state == "RETAINED_EXISTING":
                spec = remaining_spec
                service_life_basis = "REMAINING_LIFE"
                stream_key = f"remaining_life:{spec['key']}:initial"
            else:
                spec = full_spec
                service_life_basis = "FULL_SERVICE_LIFE"
                # This exact key preserves the v2.1 random stream for every
                # NEW_AT_T0 default component and for later full-life renewals.
                stream_key = f"lifetime:{spec['key']}:renewal:{cycle}"

            life = _draw_life(spec, n, seed, stream_key, central)
            if first_life is None:
                first_life = life.copy()
            interval_start = times.copy()
            times += life

            # M1.6: capture exactly one state per future/component at the RSP
            # boundary. The boundary is an observation state, not a physical
            # lifecycle event, so it is emitted to a separate state ledger.
            if retain_boundary:
                crossing = (~boundary_recorded) & (times >= horizon)
                if crossing.any():
                    b_ids = np.flatnonzero(crossing)
                    generation_at_boundary = np.full(len(b_ids), cycle - 1, dtype=int)
                    assessment_start = interval_start[b_ids]
                    age_within = horizon - assessment_start
                    installation = assessment_start.copy()
                    age_at_boundary = age_within.copy()
                    if cycle == 1 and state == "RETAINED_EXISTING":
                        age0 = getattr(component, "age_at_t0_years", None)
                        if _is_blank(age0):
                            installation[:] = np.nan
                            age_at_boundary[:] = np.nan
                        else:
                            age0 = float(age0)
                            installation[:] = -age0
                            age_at_boundary[:] = age0 + horizon
                    remaining_at_boundary = times[b_ids] - horizon
                    due = np.isclose(remaining_at_boundary, 0.0, rtol=0, atol=1e-10)
                    boundary_chunks.append(canonical_rsp_boundary_states(
                        future_ids=b_ids,
                        scenario_id=component.scenario_id,
                        component_instance_id=component.component_instance_id,
                        comparison_lineage_id=component.comparison_lineage_id,
                        component_type_id=component.component_type_id,
                        initial_component_state=state,
                        component_generation_at_boundary=generation_at_boundary,
                        rsp_years=horizon,
                        assessment_interval_start_years=assessment_start,
                        installation_time_years=installation,
                        age_within_assessment_years=age_within,
                        age_at_boundary_years=age_at_boundary,
                        next_replacement_time_years=times[b_ids],
                        remaining_life_at_boundary_years=remaining_at_boundary,
                        sampled_current_interval_life_years=life[b_ids],
                        service_life_basis=service_life_basis,
                        random_stream_key=stream_key,
                        replacement_due_at_boundary=due,
                        scenario=component.scenario,
                        component=component.component,
                    ))
                    boundary_recorded[b_ids] = True

            active = times < horizon
            if not active.any():
                break
            ids = np.flatnonzero(active)
            nominal = (component.initial_cost_eur * component.replacement_cost_factor
                       * cost_factor[ids] * (1+config["replacement_cost_growth"])**times[ids])
            pv = nominal / (1+discount[ids])**times[ids]
            if not np.isfinite(pv).all():
                raise ValueError("Nonfinite discounted replacement costs.")
            total[ids] += pv
            counts[ids] += 1
            if retain_events:
                canonical = canonical_replacement_events(
                    future_ids=ids,
                    scenario_id=component.scenario_id,
                    component_instance_id=component.component_instance_id,
                    comparison_lineage_id=component.comparison_lineage_id,
                    uncertainty_key=spec["key"],
                    generation=cycle,
                    event_times_years=times[ids],
                    sampled_service_life_years=life[ids],
                    random_stream_key=stream_key,
                    service_life_basis=service_life_basis,
                )
                canonical_chunks.append(canonical)
                replacement_cost_chunks.append(pd.DataFrame({
                    "future_id": ids,
                    "scenario_id": component.scenario_id,
                    "component_instance_id": component.component_instance_id,
                    "component_generation": cycle,
                    "scenario": component.scenario,
                    "component": component.component,
                    "nominal_replacement_cost_eur": nominal,
                    "pv_replacement_cost_eur": pv,
                }))
        if retain_boundary and not boundary_recorded.all():
            raise ValueError("Failed to resolve an RSP boundary state for every future/component stream.")
        rows.append(pd.DataFrame({"future_id": np.arange(n), "scenario": component.scenario,
            "component": component.component, "first_service_life_years": first_life,
            "replacement_count": counts, "pv_replacement_cost_eur": total}))
    columns = ["future_id", "scenario", "component", "first_service_life_years", "replacement_count", "pv_replacement_cost_eur"]
    totals = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=columns)
    canonical_ledger = (pd.concat(canonical_chunks, ignore_index=True)
                        if canonical_chunks else empty_lifecycle_event_ledger())
    replacement_costs = (pd.concat(replacement_cost_chunks, ignore_index=True)
                         if replacement_cost_chunks else pd.DataFrame(columns=[
                             "future_id", "scenario_id", "component_instance_id", "component_generation",
                             "scenario", "component", "nominal_replacement_cost_eur", "pv_replacement_cost_eur"]))
    boundary_state = (pd.concat(boundary_chunks, ignore_index=True)
                      if boundary_chunks else empty_rsp_boundary_state())
    return totals, canonical_ledger, replacement_costs, boundary_state


def renewal_costs(components, futures, config, seed, central=False, retain_events=False):
    """Return v2.1-compatible totals and, optionally, each renewal event.

    Replacement times are continuous years, strictly before the resolved horizon.
    NEW_AT_T0 components and all post-replacement generations use full service
    life. RETAINED_EXISTING components use a separately declared remaining-life
    model for the first renewal only. Shared effective full-life uncertainty keys
    couple the same component families across packages using common random quantiles.

    M1 migration note: when events are retained, their timing is now first
    represented in the canonical lifecycle ledger and then adapted back to the
    exact v2.1 event schema.  The public return shape remains unchanged.
    """
    totals, lifecycle_ledger, replacement_costs, _boundary_state = _renewal_cost_engine(
        components, futures, config, seed, central=central, retain_events=retain_events)
    if retain_events:
        legacy_events = legacy_replacement_events_from_ledger(lifecycle_ledger, replacement_costs)
    else:
        legacy_events = pd.DataFrame(columns=EVENT_COLUMNS)
    return totals, legacy_events


def renewal_costs_with_ledger(components, futures, config, seed, central=False):
    """Return v2.1 totals/events plus the new canonical lifecycle event ledger."""
    totals, lifecycle_ledger, replacement_costs, _boundary_state = _renewal_cost_engine(
        components, futures, config, seed, central=central, retain_events=True)
    legacy_events = legacy_replacement_events_from_ledger(lifecycle_ledger, replacement_costs)
    return totals, legacy_events, lifecycle_ledger


def renewal_costs_with_ledger_and_boundary(components, futures, config, seed, central=False):
    """Return v2.1 totals/events plus canonical event and RSP-boundary state ledgers."""
    totals, lifecycle_ledger, replacement_costs, boundary_state = _renewal_cost_engine(
        components, futures, config, seed, central=central, retain_events=True, retain_boundary=True)
    legacy_events = legacy_replacement_events_from_ledger(lifecycle_ledger, replacement_costs)
    return totals, legacy_events, lifecycle_ledger, boundary_state


def apply_replacements(results, component_totals):
    result = results.copy()
    if component_totals.empty:
        result["pv_replacement_cost_eur"] = 0.
        result["replacement_count"] = 0
    else:
        grouped = component_totals.groupby(["future_id", "scenario"], as_index=False)[
            ["pv_replacement_cost_eur", "replacement_count"]].sum()
        result = result.merge(grouped, on=["future_id", "scenario"], how="left", validate="one_to_one")
        result["pv_replacement_cost_eur"] = result.pv_replacement_cost_eur.fillna(0)
        result["replacement_count"] = result.replacement_count.fillna(0).astype(int)
    # Costs paid by the owner; no second charge for initial investment or routine maintenance.
    for perspective in ("owner", "combined_private"):
        result[f"{perspective}_net_benefit_eur"] -= result.pv_replacement_cost_eur
    return result
