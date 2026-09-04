"""Illustrative renewal-cost schedules for componentized incremental budgets.

Life is time to renewal; a sampled failure triggers immediate replacement.
There is no outage, damage-state or physical degradation model.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from random_streams import rng_for

COMPONENT_FIELDS = ("initial_cost_eur", "minimum_lifetime_years", "most_likely_lifetime_years",
                    "maximum_lifetime_years", "replacement_cost_factor", "maintenance_cost_eur")
EVENT_COLUMNS = ("future_id", "scenario", "component", "renewal_number", "renewal_time_years",
                 "preceding_service_life_years", "nominal_replacement_cost_eur", "pv_replacement_cost_eur")


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


def renewal_costs(components, futures, config, seed, central=False, retain_events=False):
    """Return per-future/per-component totals and optionally each renewal event.

    Replacement times are continuous years, strictly before the horizon. Each
    renewal receives a fresh lifetime. Shared uncertainty_key values couple the
    same component types across packages using common random quantiles.
    """
    n, horizon = len(futures), config["analysis_years"]
    discount = futures.discount_rate.to_numpy()
    cost_factor = futures.capex_factor.to_numpy()
    rows, events = [], []
    for component in components.itertuples():
        times, total = np.zeros(n), np.zeros(n)
        counts = np.zeros(n, dtype=int)
        first_life = None
        max_cycles = int(np.ceil(horizon / component.minimum_lifetime_years))
        if max_cycles > 1000:
            raise ValueError("At most 1000 possible renewals per component; review the lifetime/horizon units.")
        for cycle in range(1, max_cycles+1):
            if central or component.lifetime_distribution == "fixed":
                life = np.full(n, component.most_likely_lifetime_years)
            else:
                rng = rng_for(seed, f"lifetime:{component.uncertainty_key}:renewal:{cycle}")
                life = rng.triangular(component.minimum_lifetime_years,
                                      component.most_likely_lifetime_years,
                                      component.maximum_lifetime_years, n)
            if first_life is None: first_life = life.copy()
            times += life
            active = times < horizon
            if not active.any(): break
            ids = np.flatnonzero(active)
            nominal = (component.initial_cost_eur * component.replacement_cost_factor
                       * cost_factor[ids] * (1+config["replacement_cost_growth"])**times[ids])
            pv = nominal / (1+discount[ids])**times[ids]
            if not np.isfinite(pv).all(): raise ValueError("Nonfinite discounted replacement costs.")
            total[ids] += pv
            counts[ids] += 1
            if retain_events:
                events.append(pd.DataFrame({"future_id": ids, "scenario": component.scenario,
                    "component": component.component, "renewal_number": cycle,
                    "renewal_time_years": times[ids], "preceding_service_life_years": life[ids],
                    "nominal_replacement_cost_eur": nominal, "pv_replacement_cost_eur": pv}))
        rows.append(pd.DataFrame({"future_id": np.arange(n), "scenario": component.scenario,
            "component": component.component, "first_service_life_years": first_life,
            "replacement_count": counts, "pv_replacement_cost_eur": total}))
    columns = ["future_id", "scenario", "component", "first_service_life_years", "replacement_count", "pv_replacement_cost_eur"]
    totals = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=columns)
    ledger = pd.concat(events, ignore_index=True) if events else pd.DataFrame(columns=EVENT_COLUMNS)
    return totals, ledger


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
