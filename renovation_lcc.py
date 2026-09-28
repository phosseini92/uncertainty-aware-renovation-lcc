"""Illustrative incremental renovation cash flows under uncertainty.

Three private accounting perspectives; an explicit reference; diagnostic
sensitivity analysis. This is not a calibrated building-performance model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
from random_streams import rng_for
from robustness import score_summary, validate_preferences, option_set_sensitivity
from component_lifecycle import (
    load_components,
    renewal_costs,
    renewal_costs_with_ledger,
    renewal_costs_with_ledger_and_boundary,
    apply_replacements,
)
from convergence import validate_convergence, convergence_analysis
from performance_stress import load_stress_cases, performance_stress_analysis
from identity import legacy_scenario_id, validate_stable_id, validate_unique_ids
from horizon import HORIZON_PROFILES, resolve_horizon
from boundary_state import empty_rsp_boundary_state
from lifecycle_events import empty_lifecycle_event_ledger
from reference_inventory import (
    load_physical_reference_inventory,
    reference_inventory_to_lifecycle_components,
    inventory_status as physical_reference_inventory_status,
    validate_reference_lineage_compatibility,
)
from physical_quantities import (
    load_component_boq,
    load_reference_component_presence,
    validate_reference_presence_consistency,
    build_physical_quantity_coverage,
    build_reference_coverage_skeleton,
    expand_lifecycle_events_with_boq,
    expand_boundary_states_with_boq,
    boq_status as physical_boq_status,
)
from environmental_factors import (
    load_environmental_factors,
    load_boq_factor_assignments,
    build_factor_set_summary,
    build_boq_factor_compatibility,
    build_boq_factor_coverage,
    environmental_registry_status,
)
from a4_transport import (
    load_transport_scenarios, load_transport_factors, load_boq_transport_assignments,
    assess_initial_transport, append_a4_to_product_ledger,
)
from b4_transport import (
    load_boq_replacement_transport_assignments, assess_b4_replacement_transport,
    append_b4_transport_to_combined_ledger,
)
from a5_construction import (
    load_construction_process_scenarios, load_boq_construction_process_assignments,
    assess_initial_a5, append_a5_to_combined_ledger,
)
from a5_1_removal import (
    load_removal_transport_scenarios, load_preconstruction_waste_routes,
    load_preconstruction_removal_scenarios, assess_a5_1, append_a5_1_to_combined_ledger,
)
from b4_event_processes import (
    load_b4_event_process_assignments, assess_b4_event_processes, append_b4_event_processes,
)
from b6_operational import (
    load_operational_energy_flows, load_operational_factor_schedule,
    assess_operational_energy, append_operational_consequences,
)
from end_of_life import (
    load_end_of_life_assignments, load_d2_export_assignments, load_d2_factor_schedule,
    assess_end_of_life_and_d, append_end_of_life_and_d,
)
from lifecycle_aggregation import (
    load_module_applicability, assess_lifecycle_aggregation,
)
from carbon_consequences import (
    build_carbon_consequence_ledger,
    build_product_carbon_summary,
    build_product_carbon_coverage,
    carbon_engine_status,
    empty_carbon_consequence_ledger,
)

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_DIR / "inputs/renovation_scenarios.csv"
DEFAULT_CONFIG = PROJECT_DIR / "inputs/model_config.json"
PERSPECTIVES = ("owner", "tenant", "combined_private")
PARAMETERS = ("discount_rate", "energy_price_eur_kwh", "energy_price_growth",
              "rent_growth", "grant_share", "capex_factor", "performance_factor",
              "value_uplift_factor")
NUMERIC_INPUTS = ("initial_capex_eur", "annual_energy_savings_kwh",
                  "monthly_income_uplift_eur_per_dwelling", "annual_maintenance_eur",
                  "terminal_value_uplift_pct")
SCORE_METRICS = ("probability_positive", "worst_decile_mean_eur", "median_net_benefit_eur")
DEFAULT_COMPONENTS = PROJECT_DIR / "inputs/components.csv"
DEFAULT_STRESS = PROJECT_DIR / "inputs/climate_stress_scenarios.csv"
DEFAULT_REFERENCE_INVENTORY = PROJECT_DIR / "inputs/physical_reference_inventory.csv"
DEFAULT_COMPONENT_BOQ = PROJECT_DIR / "inputs/component_boq.csv"
DEFAULT_REFERENCE_PRESENCE = PROJECT_DIR / "inputs/reference_component_presence.csv"
DEFAULT_ENVIRONMENTAL_FACTORS = PROJECT_DIR / "inputs/environmental_factors.csv"
DEFAULT_BOQ_FACTOR_ASSIGNMENTS = PROJECT_DIR / "inputs/boq_environmental_factor_assignments.csv"
DEFAULT_TRANSPORT_SCENARIOS = PROJECT_DIR / "inputs/transport_scenarios.csv"
DEFAULT_TRANSPORT_FACTORS = PROJECT_DIR / "inputs/transport_factors.csv"
DEFAULT_BOQ_TRANSPORT_ASSIGNMENTS = PROJECT_DIR / "inputs/boq_transport_assignments.csv"
DEFAULT_BOQ_REPLACEMENT_TRANSPORT_ASSIGNMENTS = PROJECT_DIR / "inputs/boq_replacement_transport_assignments.csv"
DEFAULT_CONSTRUCTION_PROCESS_SCENARIOS = PROJECT_DIR / "inputs/construction_process_scenarios.csv"
DEFAULT_BOQ_CONSTRUCTION_PROCESS_ASSIGNMENTS = PROJECT_DIR / "inputs/boq_construction_process_assignments.csv"
DEFAULT_REMOVAL_TRANSPORT_SCENARIOS = PROJECT_DIR / "inputs/removal_transport_scenarios.csv"
DEFAULT_PRECONSTRUCTION_WASTE_ROUTES = PROJECT_DIR / "inputs/preconstruction_waste_routes.csv"
DEFAULT_PRECONSTRUCTION_REMOVAL_SCENARIOS = PROJECT_DIR / "inputs/preconstruction_removal_scenarios.csv"
DEFAULT_B4_EVENT_PROCESS_ASSIGNMENTS = PROJECT_DIR / "inputs/b4_event_process_assignments.csv"
DEFAULT_OPERATIONAL_ENERGY_FLOWS = PROJECT_DIR / "inputs/operational_energy_flows.csv"
DEFAULT_OPERATIONAL_ENERGY_FACTOR_SCHEDULE = PROJECT_DIR / "inputs/operational_energy_factor_schedule.csv"
DEFAULT_END_OF_LIFE_ASSIGNMENTS = PROJECT_DIR / "inputs/end_of_life_assignments.csv"
DEFAULT_D2_EXPORT_ASSIGNMENTS = PROJECT_DIR / "inputs/d2_export_assignments.csv"
DEFAULT_D2_EXPORT_FACTOR_SCHEDULE = PROJECT_DIR / "inputs/d2_export_factor_schedule.csv"
DEFAULT_MODULE_APPLICABILITY = PROJECT_DIR / "inputs/module_applicability.csv"


def validate_config(config: dict) -> None:
    allowed_conventions = {"EN15978_2026_INFORMED", "LEVELS_1_2", "RICS_WLCA_2E", "CUSTOM_RESEARCH"}
    if config.get("assessment_convention") not in allowed_conventions:
        raise ValueError(f"assessment_convention must be one of {sorted(allowed_conventions)}.")
    if config.get("generated_energy_reporting_approach") != "PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED":
        raise ValueError(
            "M3.1.1 supports generated_energy_reporting_approach="
            "PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED only; D2 remains deferred."
        )
    if config.get("factor_extrapolation_policy") != "ERROR_IF_MISSING":
        raise ValueError(
            "M3.1.1 supports factor_extrapolation_policy=ERROR_IF_MISSING only; "
            "no interpolation, extrapolation or carry-forward is implemented."
        )
    for field in ("analysis_years", "dwellings"):
        if type(config[field]) is not int or config[field] < 1:
            raise ValueError(f"{field} must be a positive integer.")
    for field in ("terminal_reference_building_value_eur", "maintenance_growth",
                  "owner_energy_savings_share"):
        if not np.isfinite(config[field]):
            raise ValueError(f"{field} must be finite.")
    if config["terminal_reference_building_value_eur"] < 0:
        raise ValueError("Terminal reference value must be nonnegative.")
    if config["maintenance_growth"] <= -1:
        raise ValueError("Maintenance growth must exceed -1.")
    if not 0 <= config["owner_energy_savings_share"] <= 1:
        raise ValueError("Owner energy savings share must be between zero and one.")
    if type(config["include_reference_in_decisions"]) is not bool:
        raise ValueError("include_reference_in_decisions must be a boolean.")
    validate_preferences(config)
    validate_convergence(config["convergence"])
    if not np.isfinite(config["replacement_cost_growth"]) or config["replacement_cost_growth"] <= -1:
        raise ValueError("Replacement cost growth must be finite and exceed -1.")
    thresholds = config["thresholds"]
    for field in ("probability_positive_min", "performance_pass_probability_min"):
        if not 0 <= thresholds[field] <= 1: raise ValueError(f"Invalid probability threshold: {field}")
    for field in ("median_npv_min_eur", "p95_regret_max_eur", "retained_savings_fraction_min"):
        if not np.isfinite(thresholds[field]): raise ValueError(f"Nonfinite threshold: {field}")
    if thresholds["p95_regret_max_eur"] < 0 or thresholds["retained_savings_fraction_min"] < 0:
        raise ValueError("Regret and performance thresholds must be nonnegative.")
    if type(thresholds["minimum_acceptable_stress_cases"]) is not int or thresholds["minimum_acceptable_stress_cases"] < 1:
        raise ValueError("Minimum acceptable case count must be a positive integer.")
    if set(config["uncertainties"]) != set(PARAMETERS):
        raise ValueError("Configuration must define all eight uncertainty parameters.")
    for name, spec in config["uncertainties"].items():
        kind = spec["distribution"]
        numbers = np.asarray([v for k, v in spec.items() if k != "distribution"], dtype=float)
        if not np.isfinite(numbers).all():
            raise ValueError(f"Nonfinite distribution parameter: {name}")
        if kind == "triangular":
            if not spec["low"] <= spec["mode"] <= spec["high"] or spec["low"] == spec["high"]:
                raise ValueError(f"Invalid triangular distribution: {name}")
        elif kind == "lognormal":
            if spec["median"] <= 0 or spec["log_sigma"] < 0:
                raise ValueError(f"Invalid lognormal distribution: {name}")
        elif kind == "clipped_normal":
            if spec["sd"] < 0 or spec["low"] > spec["high"]:
                raise ValueError(f"Invalid clipped normal distribution: {name}")
        else:
            raise ValueError(f"Unsupported distribution: {kind}")


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_config(config)
    return config


def load_scenarios(path: Path) -> pd.DataFrame:
    """Load scenarios with explicit v3 IDs or deterministic legacy fallbacks.

    ``scenario`` remains the v2.1 display/economic key so all public numerical
    outputs stay compatible.  ``scenario_id`` is the stable v3 identity used
    by the lifecycle ledger and future cross-table joins.  Migrated files must
    provide explicit IDs; legacy files without the column receive clearly
    prefixed deterministic fallback IDs.
    """
    scenarios = pd.read_csv(path)
    required = {"scenario", "is_reference", *NUMERIC_INPUTS}
    if required - set(scenarios):
        raise ValueError(f"Missing input columns: {sorted(required - set(scenarios))}")
    if len(scenarios) < 2:
        raise ValueError("Include one reference and at least one renovation.")
    if scenarios.scenario.isna().any():
        raise ValueError("Scenario names must not be missing.")
    scenarios["scenario"] = scenarios.scenario.astype(str).str.strip()
    if scenarios.scenario.eq("").any() or scenarios.scenario.duplicated().any():
        raise ValueError("Scenario names must be nonempty and unique.")

    if "scenario_id" in scenarios:
        scenarios["scenario_id"] = [validate_stable_id(v, "scenario_id") for v in scenarios.scenario_id]
        validate_unique_ids(scenarios.scenario_id, "scenario_id")
    else:
        scenarios.insert(0, "scenario_id", [legacy_scenario_id(v) for v in scenarios.scenario])

    for field in (*NUMERIC_INPUTS, "is_reference"):
        scenarios[field] = pd.to_numeric(scenarios[field], errors="raise")
        if not np.isfinite(scenarios[field]).all():
            raise ValueError(f"Nonfinite input: {field}")
    if not scenarios.is_reference.isin([0, 1]).all() or scenarios.is_reference.sum() != 1:
        raise ValueError("Exactly one reference row must have is_reference=1.")
    if (scenarios.initial_capex_eur < 0).any():
        raise ValueError("Initial renovation investment must be nonnegative.")
    reference = scenarios.loc[scenarios.is_reference.eq(1), list(NUMERIC_INPUTS)]
    if reference.ne(0).any().any():
        raise ValueError("Reference inputs must be zero: all entries are incremental to it.")
    return scenarios


def validate_futures(futures: pd.DataFrame) -> None:
    if futures.empty or set(PARAMETERS) - set(futures):
        raise ValueError("Nonempty futures with all eight parameters are required.")
    if not np.isfinite(futures[list(PARAMETERS)].to_numpy()).all():
        raise ValueError("Futures must be finite.")
    for field in ("discount_rate", "energy_price_growth", "rent_growth"):
        if (futures[field] <= -1).any():
            raise ValueError(f"{field} must exceed -1.")
    if not futures.grant_share.between(0, 1).all():
        raise ValueError("Grant shares must lie between zero and one.")
    for field in ("energy_price_eur_kwh", "capex_factor", "performance_factor", "value_uplift_factor"):
        if (futures[field] < 0).any():
            raise ValueError(f"{field} must be nonnegative.")


def sample_uncertain_futures(n: int, seed: int, config: dict) -> pd.DataFrame:
    if type(n) is not int or n < 1 or type(seed) is not int or seed < 0:
        raise ValueError("Simulations must be a positive integer; seed must be a nonnegative integer.")
    columns = {}
    for name in PARAMETERS:
        rng = rng_for(seed, f"economic:{name}")
        p = config["uncertainties"][name]
        if p["distribution"] == "triangular":
            values = rng.triangular(p["low"], p["mode"], p["high"], n)
        elif p["distribution"] == "lognormal":
            values = rng.lognormal(np.log(p["median"]), p["log_sigma"], n)
        else:
            values = np.clip(rng.normal(p["mean"], p["sd"], n), p["low"], p["high"])
        columns[name] = values
    futures = pd.DataFrame(columns)
    validate_futures(futures)
    return futures


def annuity_present_value(first_year_value, growth_rate, discount_rate, years):
    """End-of-year nominal cash flows; first-year amount is not pre-escalated."""
    value, growth, discount = np.broadcast_arrays(
        np.asarray(first_year_value, float), np.asarray(growth_rate, float),
        np.asarray(discount_rate, float))
    if type(years) is not int or years < 0:
        raise ValueError("Years must be a nonnegative integer.")
    if not all(np.isfinite(x).all() for x in (value, growth, discount)):
        raise ValueError("Cash-flow inputs must be finite.")
    if (growth <= -1).any() or (discount <= -1).any():
        raise ValueError("Growth and discount rates must exceed -1.")
    pv = np.zeros_like(value)
    with np.errstate(over="raise", invalid="raise"):
        for year in range(1, years + 1):
            pv += value * (1 + growth) ** (year - 1) / (1 + discount) ** year
    return pv


def evaluate_scenario(scenario: pd.Series, futures: pd.DataFrame, config: dict) -> pd.DataFrame:
    """All costs, savings and value changes are incremental to the reference."""
    discount = futures.discount_rate.to_numpy()
    years = config["analysis_years"]
    capex_gross = scenario.initial_capex_eur * futures.capex_factor.to_numpy()
    grant = capex_gross * futures.grant_share.to_numpy()
    capex_net = capex_gross - grant
    energy = annuity_present_value(
        scenario.annual_energy_savings_kwh * futures.performance_factor.to_numpy()
        * futures.energy_price_eur_kwh.to_numpy(),
        futures.energy_price_growth.to_numpy(), discount, years)
    rent = annuity_present_value(
        np.full(len(futures), scenario.monthly_income_uplift_eur_per_dwelling
                * config["dwellings"] * 12), futures.rent_growth.to_numpy(), discount, years)
    maintenance = annuity_present_value(np.full(len(futures), scenario.annual_maintenance_eur),
                                       config["maintenance_growth"], discount, years)
    terminal = (config["terminal_reference_building_value_eur"] * scenario.terminal_value_uplift_pct
                * futures.value_uplift_factor.to_numpy() / (1 + discount) ** years)
    owner_share = config["owner_energy_savings_share"]
    owner = owner_share * energy + rent + terminal - capex_net - maintenance
    tenant = (1 - owner_share) * energy - rent
    combined = energy + terminal - capex_net - maintenance
    result = pd.DataFrame({
        "future_id": np.arange(len(futures)), "scenario": scenario.scenario,
        "is_reference": int(scenario.is_reference),
        "gross_capex_eur": capex_gross, "grant_eur": grant, "effective_capex_eur": capex_net,
        "pv_energy_savings_eur": energy, "pv_rent_transfer_eur": rent,
        "pv_maintenance_eur": maintenance, "pv_terminal_value_uplift_eur": terminal,
        "owner_net_benefit_eur": owner, "tenant_net_benefit_eur": tenant,
        "combined_private_net_benefit_eur": combined})
    if not np.isfinite(result.select_dtypes(include="number")).all().all():
        raise ValueError("Nonfinite model output; check input magnitudes and horizon.")
    return result


def simulate(scenarios, futures, config, components=None, seed=0, central_lifetimes=False):
    validate_futures(futures)
    results = pd.concat([evaluate_scenario(row, futures, config)
                         for _, row in scenarios.iterrows()], ignore_index=True)
    if components is not None:
        totals, _ = renewal_costs(components, futures, config, seed, central=central_lifetimes)
        return apply_replacements(results, totals)
    return apply_replacements(results, pd.DataFrame())


def lower_tail_mean(values, fraction=0.1):
    """Exact empirical lower-tail mass, including a fractional boundary observation."""
    ordered = np.sort(np.asarray(values, dtype=float))
    mass = len(ordered) * fraction
    full = int(np.floor(mass))
    remainder = mass - full
    total = ordered[:full].sum()
    if remainder > 0:
        total += remainder * ordered[full]
    return total / mass


def build_summary(results: pd.DataFrame, perspective: str, config: dict) -> pd.DataFrame:
    pivot = results.pivot(index="future_id", columns="scenario", values=f"{perspective}_net_benefit_eur")
    references = results.groupby("scenario").is_reference.first()
    eligible = [name for name in pivot if config["include_reference_in_decisions"] or not references[name]]
    best = pivot[eligible].max(axis=1)
    winners = np.isclose(pivot[eligible].to_numpy(), best.to_numpy()[:, None], rtol=0, atol=1e-8)
    winning_share = (winners / winners.sum(axis=1, keepdims=True)).mean(axis=0)
    shares = dict(zip(eligible, winning_share))
    rows = []
    for name in pivot:
        values = pivot[name]
        in_choice_set = name in eligible
        regret = best - values
        rows.append({"perspective": perspective, "scenario": name,
                     "is_reference": bool(references[name]), "decision_eligible": in_choice_set,
                     "mean_net_benefit_eur": values.mean(), "median_net_benefit_eur": values.median(),
                     "p10_net_benefit_eur": values.quantile(.1), "p90_net_benefit_eur": values.quantile(.9),
                     "probability_positive": (values > 0).mean(),
                     "probability_nonnegative": (values >= 0).mean(),
                     "worst_decile_mean_eur": lower_tail_mean(values),
                     "mean_regret_eur": regret.mean() if in_choice_set else np.nan,
                     "p95_regret_eur": regret.quantile(.95) if in_choice_set else np.nan,
                     "best_option_share": shares.get(name, np.nan)})
    summary = pd.DataFrame(rows)
    if "pv_replacement_cost_eur" in results:
        replacements = results.groupby("scenario").agg(
            mean_pv_replacement_cost_eur=("pv_replacement_cost_eur","mean"),
            mean_replacement_count=("replacement_count","mean")).reset_index()
        summary = summary.merge(replacements,on="scenario",validate="one_to_one")
    return score_summary(summary, config)


def all_summaries(results, config):
    return pd.concat([build_summary(results, p, config) for p in PERSPECTIVES], ignore_index=True)


def sensitivity_analysis(scenarios, futures, results, config, components=None, seed=0):
    """Paired deterministic OAT diagnostics plus sampled Spearman associations."""
    medians = futures.median()
    central = simulate(scenarios, pd.DataFrame([medians]), config, components, seed, central_lifetimes=True).set_index("scenario")
    rows = []
    correlations = []
    for parameter in PARAMETERS:
        low, high = futures[parameter].quantile([.1, .9])
        f = pd.DataFrame([medians, medians])
        f[parameter] = [low, high]
        simulated = simulate(scenarios, f, config, components, seed, central_lifetimes=True)
        for name, group in simulated.groupby("scenario"):
            if group.is_reference.iloc[0]:
                continue
            for perspective in PERSPECTIVES:
                values = group[f"{perspective}_net_benefit_eur"].to_numpy()
                rows.append({"perspective": perspective, "scenario": name, "parameter": parameter,
                             "parameter_p10": low, "parameter_p90": high,
                             "central_net_benefit_eur": central.loc[name, f"{perspective}_net_benefit_eur"],
                             "at_parameter_p10_eur": values[0], "at_parameter_p90_eur": values[1],
                             "signed_change_eur": values[1] - values[0],
                             "absolute_span_eur": abs(values[1] - values[0])})
    for name, group in results.groupby("scenario"):
        if group.is_reference.iloc[0]:
            continue
        x = futures.loc[group.future_id].reset_index(drop=True).rank()
        for perspective in PERSPECTIVES:
            y = group[f"{perspective}_net_benefit_eur"].reset_index(drop=True).rank()
            for parameter in PARAMETERS:
                rho = x[parameter].corr(y) if x[parameter].nunique() > 1 and y.nunique() > 1 else np.nan
                correlations.append({"perspective": perspective, "scenario": name,
                                     "parameter": parameter, "spearman_rho": rho})
    return pd.DataFrame(rows), pd.DataFrame(correlations)


def weight_sensitivity(summary, config):
    profiles = {"configured": list(config["score_weights"][x] for x in SCORE_METRICS),
                "equal": [1/3, 1/3, 1/3], "downside_emphasis": [.2, .6, .2],
                "positive_frequency_emphasis": [.6, .2, .2], "median_emphasis": [.2, .2, .6]}
    rows = []
    for perspective, group in summary.groupby("perspective"):
        for name, vector in profiles.items():
            weights = dict(zip(SCORE_METRICS, vector))
            scored = score_summary(group, dict(config, score_weights=weights))
            for row in scored.itertuples():
                rows.append({"perspective": perspective, "weight_profile": name,
                             "scenario": row.scenario, "preference_based_score": row.preference_based_score,
                             "conditional_preference_rank": row.conditional_preference_rank,
                             **{f"weight_{k}": v for k, v in weights.items()}})
    return pd.DataFrame(rows)


def allocation_sensitivity(results, config):
    """Reallocate a fixed energy benefit; combined private totals must not change."""
    rows = []
    original = config["owner_energy_savings_share"]
    for share in (0., .5, 1.):
        changed = results.copy()
        delta = (share - original) * changed.pv_energy_savings_eur
        changed["owner_net_benefit_eur"] += delta
        changed["tenant_net_benefit_eur"] -= delta
        summary = all_summaries(changed, config)
        summary.insert(0, "owner_energy_savings_share", share)
        rows.append(summary)
    return pd.concat(rows, ignore_index=True)


def stress_tests(scenarios, futures, config, components=None, seed=0):
    """Illustrative accounting/input changes; no event probabilities assigned."""
    rows = []
    for name in ("configured", "no_grants", "no_terminal_uplift", "no_rent_uplift",
                 "energy_price_x0.75_capex_x1.25"):
        f, s = futures.copy(), scenarios.copy()
        if name == "no_grants": f["grant_share"] = 0.
        if name == "no_terminal_uplift": f["value_uplift_factor"] = 0.
        if name == "no_rent_uplift": s["monthly_income_uplift_eur_per_dwelling"] = 0.
        if name == "energy_price_x0.75_capex_x1.25":
            f["energy_price_eur_kwh"] *= .75
            f["capex_factor"] *= 1.25
        summary = all_summaries(simulate(s, f, config, components, seed), config)
        summary.insert(0, "stress_case", name)
        rows.append(summary)
    return pd.concat(rows, ignore_index=True)


def write_report(output, tables, config, n, seed):
    summary = tables["scenario_summary"]
    lines = ["RENOVATION ECONOMICS UNDER UNCERTAINTY - VERSION 2.1", "",
        f"Illustrative {config['dwellings']}-dwelling building, {config['analysis_years']}-year horizon.",
        f"Sample size: {n:,}; seed: {seed}; keyed streams with nested sample-size prefixes.",
        f"Owner share of energy-bill savings: {config['owner_energy_savings_share']:.0%}.",
        "All costs are incremental. Component renewal costs are charged to the owner and combined private account.",
        "The renewal-cost summary column describes the package in every perspective; it is not a tenant expense.",
        "Primary evidence consists of individual financial metrics and their trade-offs, not a composite winner.", ""]
    columns = ["scenario","median_net_benefit_eur","probability_positive","worst_decile_mean_eur",
               "p95_regret_eur","best_option_share","mean_pv_replacement_cost_eur","pareto_on_core_metrics"]
    for perspective in PERSPECTIVES:
        table = summary.loc[summary.perspective.eq(perspective)]
        lines += [perspective.upper(),table[columns].to_string(index=False,float_format=lambda x:f"{x:,.4f}"), ""]
    option = tables["option_set_sensitivity"]
    delta = option.preference_score_change.dropna().abs().max()
    reversals = option.pairwise_preference_reversals_among_retained.max()
    lines += ["FIXED-ANCHOR PREFERENCE DIAGNOSTIC",
        "Weights and EUR anchors are explicit illustrative preferences, not calibrated stakeholder utilities.",
        "Only positive-frequency, median and lower-tail mean enter this optional score.",
        "Regret and best-option share are separate choice-set-relative metrics.",
        f"Largest retained-option score change across diagnostic option sets: {delta:.12g}.",
        f"Maximum pairwise preference-order reversals among retained options: {reversals}.",
        "Ordinal ranks can shift when an option is removed or a better option is added; unchanged pairwise order is the check.", ""]
    if "monte_carlo_convergence" in tables:
        convergence = tables["monte_carlo_convergence"]
        lines += ["MONTE CARLO DIAGNOSTICS",f"Sample sizes: {config['convergence']['sample_sizes']}; seeds: {config['convergence']['seeds']}.",
            "The largest sample is a finite comparison sample, not ground truth. Nested differences and cross-seed ranges are diagnostics."]
        selected = convergence.loc[convergence.sample_size.eq(n) & ~convergence.is_largest_sample_reference]
        if not selected.empty:
            count = int(selected.within_diagnostic_tolerances.fillna(False).sum())
            lines += [f"At N={n:,}, {count}/{len(selected)} perspective/option/seed rows meet ALL declared numerical tolerances versus the largest N."]
            for metric in config["convergence"]["tolerances"]:
                error = selected[f"abs_difference_vs_largest_{metric}"].max()
                lines += [f"  Maximum absolute {metric} difference: {error:,.6f}; tolerance: {config['convergence']['tolerances'][metric]}."]
        lines += ["Positive-outcome Wilson intervals quantify Monte Carlo frequency uncertainty conditional on the assumed distributions.", ""]
    else:
        lines += ["Monte Carlo convergence diagnostics skipped for this run.", ""]
    robustness = tables["robust_across_stress_cases"]
    lines += ["PERFORMANCE STRESS INTERFACE",
        "Delivered stress multipliers and thresholds are hypothetical. No historical climate data, temperature pathway or comfort simulation is used.",
        "Performance means retention of an assumed energy-savings target, not health, safety or indoor comfort.",
        robustness[["perspective","scenario","acceptable_case_count","required_acceptable_cases","robust_across_stress_cases"]].to_string(index=False),
        "No option needs to pass the screen: thresholds are not tuned to force a successful result.", "",
        "LIMITS", "Component lifetimes/costs are illustrative budget allocations; failure triggers immediate renewal with no downtime.",
        "No replacement at or beyond the horizon; no component-specific residual credit; terminal property premium remains separate and hypothetical.",
        "Routine maintenance reconciles to the scenario budget and is not charged again by the lifecycle module.",
        "No calibrated climate risk, building physics, environmental LCA or real-world validation is claimed.",
        "See ASSUMPTIONS.md and README.md for interpretation."]
    (output/"analysis_report.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")


def run(input_path=DEFAULT_INPUT, output_dir=PROJECT_DIR/"outputs", simulations=10000,
        seed=20260726, config_path=DEFAULT_CONFIG, charts=True, components_path=DEFAULT_COMPONENTS,
        stress_path=DEFAULT_STRESS, convergence_enabled=True, horizon_mode=None,
        reference_inventory_path=DEFAULT_REFERENCE_INVENTORY,
        component_boq_path=DEFAULT_COMPONENT_BOQ,
        reference_presence_path=DEFAULT_REFERENCE_PRESENCE,
        environmental_factors_path=DEFAULT_ENVIRONMENTAL_FACTORS,
        boq_factor_assignments_path=DEFAULT_BOQ_FACTOR_ASSIGNMENTS,
        transport_scenarios_path=DEFAULT_TRANSPORT_SCENARIOS,
        transport_factors_path=DEFAULT_TRANSPORT_FACTORS,
        boq_transport_assignments_path=DEFAULT_BOQ_TRANSPORT_ASSIGNMENTS,
        boq_replacement_transport_assignments_path=DEFAULT_BOQ_REPLACEMENT_TRANSPORT_ASSIGNMENTS,
        construction_process_scenarios_path=DEFAULT_CONSTRUCTION_PROCESS_SCENARIOS,
        boq_construction_process_assignments_path=DEFAULT_BOQ_CONSTRUCTION_PROCESS_ASSIGNMENTS,
        removal_transport_scenarios_path=DEFAULT_REMOVAL_TRANSPORT_SCENARIOS,
        preconstruction_waste_routes_path=DEFAULT_PRECONSTRUCTION_WASTE_ROUTES,
        preconstruction_removal_scenarios_path=DEFAULT_PRECONSTRUCTION_REMOVAL_SCENARIOS,
        b4_event_process_assignments_path=DEFAULT_B4_EVENT_PROCESS_ASSIGNMENTS,
        operational_energy_flows_path=DEFAULT_OPERATIONAL_ENERGY_FLOWS,
        operational_energy_factor_schedule_path=DEFAULT_OPERATIONAL_ENERGY_FACTOR_SCHEDULE,
        end_of_life_assignments_path=DEFAULT_END_OF_LIFE_ASSIGNMENTS,
        d2_export_assignments_path=DEFAULT_D2_EXPORT_ASSIGNMENTS,
        d2_export_factor_schedule_path=DEFAULT_D2_EXPORT_FACTOR_SCHEDULE,
        module_applicability_path=DEFAULT_MODULE_APPLICABILITY):
    base_config = load_config(config_path)
    config, horizon = resolve_horizon(base_config, horizon_mode)
    # Validate the resolved copy as well as the source config.  Named horizon
    # profiles change only analysis_years, but this keeps the run boundary
    # explicit and protects future profile extensions.
    validate_config(config)
    scenarios = load_scenarios(input_path)
    components = load_components(components_path,scenarios)
    stress_cases = load_stress_cases(stress_path,scenarios,config)
    futures = sample_uncertain_futures(simulations,seed,config)
    life_totals, events, lifecycle_event_ledger, rsp_boundary_state = renewal_costs_with_ledger_and_boundary(
        components,futures,config,seed)

    reference_row = scenarios.loc[scenarios.is_reference.eq(1)].iloc[0]
    physical_reference_inventory = load_physical_reference_inventory(
        reference_inventory_path, str(reference_row.scenario_id))
    validate_reference_lineage_compatibility(physical_reference_inventory, components)
    reference_inventory_meta = physical_reference_inventory_status(physical_reference_inventory)
    if physical_reference_inventory.empty:
        reference_lifecycle_event_ledger = empty_lifecycle_event_ledger()
        reference_rsp_boundary_state = empty_rsp_boundary_state()
    else:
        reference_components = reference_inventory_to_lifecycle_components(
            physical_reference_inventory, str(reference_row.scenario))
        _ref_totals, _ref_events, reference_lifecycle_event_ledger, reference_rsp_boundary_state = (
            renewal_costs_with_ledger_and_boundary(reference_components, futures, config, seed)
        )

    # M1.7: documented physical quantity / BoQ bridge. The production BoQ may
    # remain empty; absence is reported explicitly and no quantity is inferred
    # from cost, component labels, or service-life data.
    component_boq = load_component_boq(component_boq_path, components, physical_reference_inventory)
    reference_presence = load_reference_component_presence(reference_presence_path, components)
    validate_reference_presence_consistency(reference_presence, physical_reference_inventory)
    physical_quantity_coverage = build_physical_quantity_coverage(
        components, physical_reference_inventory, component_boq
    )
    reference_coverage_skeleton = build_reference_coverage_skeleton(
        reference_presence, physical_reference_inventory, component_boq
    )
    physical_boq_meta = physical_boq_status(component_boq, physical_quantity_coverage)
    lifecycle_event_boq_quantities = expand_lifecycle_events_with_boq(
        lifecycle_event_ledger, component_boq
    )
    rsp_boundary_boq_state = expand_boundary_states_with_boq(
        rsp_boundary_state, component_boq
    )
    reference_lifecycle_event_boq_quantities = expand_lifecycle_events_with_boq(
        reference_lifecycle_event_ledger, component_boq
    )
    reference_rsp_boundary_boq_state = expand_boundary_states_with_boq(
        reference_rsp_boundary_state, component_boq
    )

    # M1.8: environmental-factor registry and explicit BoQ/declared-unit gate.
    # This stage does not calculate kgCO2e. It only resolves factor provenance,
    # module/indicator availability, explicit product mappings and physical-unit
    # compatibility for later carbon consequence calculation.
    environmental_factors = load_environmental_factors(environmental_factors_path)
    factor_set_summary = build_factor_set_summary(environmental_factors)
    boq_factor_assignments = load_boq_factor_assignments(
        boq_factor_assignments_path, component_boq, environmental_factors
    )
    boq_factor_compatibility = build_boq_factor_compatibility(
        component_boq, boq_factor_assignments, environmental_factors
    )
    boq_factor_coverage = build_boq_factor_coverage(
        component_boq, boq_factor_assignments, boq_factor_compatibility
    )
    environmental_registry_meta = environmental_registry_status(
        environmental_factors, factor_set_summary, component_boq,
        boq_factor_assignments, boq_factor_coverage
    )

    # M2.1: narrow product-stage carbon consequence engine.  The same canonical
    # lifecycle events generated by the renewal engine drive B4 product-stage
    # consequences; no service-life resampling occurs here.  Initial A1-A3 is
    # calculated only for NEW_AT_T0 components. Retained existing components do
    # not receive historical A1-A3. This product subengine remains unchanged;
    # M2.2 initial A4 is appended below after product summary/status calculation.
    future_ids = [int(v) for v in futures.index]
    intervention_carbon_ledger = build_carbon_consequence_ledger(
        components=components,
        component_boq=component_boq,
        lifecycle_event_ledger=lifecycle_event_ledger,
        factors=environmental_factors,
        assignments=boq_factor_assignments,
        compatibility=boq_factor_compatibility,
        event_boq_quantities=lifecycle_event_boq_quantities,
        future_ids=future_ids,
    )
    if physical_reference_inventory.empty:
        reference_carbon_ledger = empty_carbon_consequence_ledger()
    else:
        reference_carbon_ledger = build_carbon_consequence_ledger(
            components=physical_reference_inventory,
            component_boq=component_boq,
            lifecycle_event_ledger=reference_lifecycle_event_ledger,
            factors=environmental_factors,
            assignments=boq_factor_assignments,
            compatibility=boq_factor_compatibility,
            event_boq_quantities=reference_lifecycle_event_boq_quantities,
            future_ids=future_ids,
        )
    carbon_consequence_ledger = pd.concat(
        [t for t in (intervention_carbon_ledger, reference_carbon_ledger) if not t.empty], ignore_index=True
    ) if (not intervention_carbon_ledger.empty or not reference_carbon_ledger.empty) else empty_carbon_consequence_ledger()
    product_carbon_summary = build_product_carbon_summary(carbon_consequence_ledger)
    carbon_component_basis = pd.concat(
        [components, physical_reference_inventory], ignore_index=True, sort=False
    ) if not physical_reference_inventory.empty else components
    product_carbon_coverage = build_product_carbon_coverage(
        components=carbon_component_basis,
        boq_factor_coverage=boq_factor_coverage,
    )
    carbon_engine_meta = carbon_engine_status(
        component_boq=component_boq,
        boq_factor_coverage=boq_factor_coverage,
        consequence_ledger=carbon_consequence_ledger,
        product_summary=product_carbon_summary,
    )
    # M2.2: independent initial-transport registry and mass/distance gate.
    # Product summary/status above remain the frozen M2.1 subengine outputs.
    transport_scenarios = load_transport_scenarios(transport_scenarios_path)
    transport_factors = load_transport_factors(transport_factors_path)
    transport_assignments = load_boq_transport_assignments(
        boq_transport_assignments_path, component_boq, transport_scenarios, transport_factors)
    for field in ("factor_record_id", "factor_set_id"):
        if set(environmental_factors[field]) & set(transport_factors[field]):
            raise ValueError(f"Product and transport registry {field} values must be disjoint for traceability.")
    if set(boq_factor_assignments.assignment_id) & set(transport_assignments.assignment_id):
        raise ValueError("Product and transport assignment IDs must be disjoint for traceability.")
    (a4_compatibility, a4_coverage, a4_ledger, a4_summary, a4_meta) = assess_initial_transport(
        carbon_component_basis, component_boq, transport_scenarios, transport_factors,
        transport_assignments, future_ids)
    carbon_consequence_ledger = append_a4_to_product_ledger(carbon_consequence_ledger, a4_ledger)

    # M2.3: replacement transport is attached to the canonical B4 replacement
    # event and reported inside B4. It reuses the documented transport registry
    # but has a separate assignment table so M2.2 initial A4 semantics and
    # outputs remain frozen. No service-life resampling occurs.
    replacement_transport_assignments = load_boq_replacement_transport_assignments(
        boq_replacement_transport_assignments_path, component_boq, transport_scenarios, transport_factors)
    construction_process_scenarios = load_construction_process_scenarios(
        construction_process_scenarios_path, environmental_factors)
    construction_process_assignments = load_boq_construction_process_assignments(
        boq_construction_process_assignments_path, component_boq, construction_process_scenarios, environmental_factors)
    if set(boq_factor_assignments.assignment_id) & set(replacement_transport_assignments.assignment_id):
        raise ValueError("Product and replacement transport assignment IDs must be disjoint for traceability.")
    if set(transport_assignments.assignment_id) & set(replacement_transport_assignments.assignment_id):
        raise ValueError("Initial and replacement transport assignment IDs must be disjoint for traceability.")
    (b4_transport_compatibility, b4_transport_coverage, intervention_b4_transport_ledger,
     intervention_b4_transport_summary, intervention_b4_transport_meta) = assess_b4_replacement_transport(
        components, component_boq, lifecycle_event_ledger, lifecycle_event_boq_quantities,
        transport_scenarios, transport_factors, replacement_transport_assignments)
    if physical_reference_inventory.empty:
        reference_b4_transport_compatibility = b4_transport_compatibility.iloc[:0].copy()
        reference_b4_transport_coverage = b4_transport_coverage.iloc[:0].copy()
        reference_b4_transport_ledger = empty_carbon_consequence_ledger()
        reference_b4_transport_summary = intervention_b4_transport_summary.iloc[:0].copy()
    else:
        (reference_b4_transport_compatibility, reference_b4_transport_coverage, reference_b4_transport_ledger,
         reference_b4_transport_summary, _reference_b4_transport_meta) = assess_b4_replacement_transport(
            physical_reference_inventory, component_boq, reference_lifecycle_event_ledger,
            reference_lifecycle_event_boq_quantities, transport_scenarios, transport_factors,
            replacement_transport_assignments)
    b4_transport_ledger = pd.concat(
        [t for t in (intervention_b4_transport_ledger, reference_b4_transport_ledger) if not t.empty],
        ignore_index=True
    ) if (not intervention_b4_transport_ledger.empty or not reference_b4_transport_ledger.empty) else empty_carbon_consequence_ledger()
    b4_transport_summary = pd.concat(
        [t for t in (intervention_b4_transport_summary, reference_b4_transport_summary) if not t.empty],
        ignore_index=True
    ) if (not intervention_b4_transport_summary.empty or not reference_b4_transport_summary.empty) else intervention_b4_transport_summary.iloc[:0].copy()
    b4_transport_coverage_combined = pd.concat(
        [t for t in (b4_transport_coverage, reference_b4_transport_coverage) if not t.empty], ignore_index=True
    ) if (not b4_transport_coverage.empty or not reference_b4_transport_coverage.empty) else b4_transport_coverage.iloc[:0].copy()
    b4_transport_meta = intervention_b4_transport_meta.copy()
    b4_transport_meta["reference_carbon_consequence_rows"] = len(reference_b4_transport_ledger)
    b4_transport_meta["carbon_consequence_rows"] = len(b4_transport_ledger)
    carbon_consequence_ledger = append_b4_transport_to_combined_ledger(carbon_consequence_ledger, b4_transport_ledger)
    (a5_compatibility, a5_coverage, a5_ledger, a5_summary, a5_meta) = assess_initial_a5(
        component_boq, construction_process_scenarios, environmental_factors,
        construction_process_assignments, futures.index
    )
    carbon_consequence_ledger = append_a5_to_combined_ledger(carbon_consequence_ledger, a5_ledger)
    # M2.5: A5.1 pre-construction removal of existing works. Removed-at-t0
    # inventory is structurally separate from current-construction BoQ/A5.3.
    # Removal activity, outbound removed-material transport, and waste
    # processing/disposal are independently gated but all report to A5.1.
    removal_transport_scenarios = load_removal_transport_scenarios(
        removal_transport_scenarios_path, transport_factors)
    preconstruction_waste_routes = load_preconstruction_waste_routes(
        preconstruction_waste_routes_path, environmental_factors)
    preconstruction_removal_scenarios = load_preconstruction_removal_scenarios(
        preconstruction_removal_scenarios_path, scenarios, component_boq, environmental_factors,
        removal_transport_scenarios, preconstruction_waste_routes)
    (a5_1_compatibility, a5_1_coverage, a5_1_ledger, a5_1_summary, a5_1_meta) = assess_a5_1(
        preconstruction_removal_scenarios, environmental_factors, removal_transport_scenarios,
        transport_factors, preconstruction_waste_routes, futures.index
    )
    carbon_consequence_ledger = append_a5_1_to_combined_ledger(carbon_consequence_ledger, a5_1_ledger)

    # M2.6: complete the process family attributable to canonical B4 replacement
    # events. Source process factors retain their native A5.1/A5.2/A4/C3/C4
    # scopes in provenance, but all replacement-event consequences report in B4.
    # This preserves event ownership and prevents reclassification/double counting.
    b4_event_process_assignments = load_b4_event_process_assignments(
        b4_event_process_assignments_path, component_boq, environmental_factors, transport_factors)
    (b4_event_process_compatibility, b4_event_process_coverage, b4_event_process_ledger,
     b4_event_process_summary, b4_event_process_meta) = assess_b4_event_processes(
        component_boq, lifecycle_event_ledger, lifecycle_event_boq_quantities,
        environmental_factors, transport_factors, b4_event_process_assignments)
    carbon_consequence_ledger = append_b4_event_processes(
        carbon_consequence_ledger, b4_event_process_ledger)

    # M3.1: B6 operational-energy GWP.  This engine consumes only explicit
    # operational physical flows and an explicit annual factor schedule.  It
    # never derives energy use from the legacy annual_energy_savings_kwh
    # economic proxy.  Generated/self-consumed/exported flows are retained for
    # physical bookkeeping, but export receives no credit here and is not
    # netted into A-C; D2 remains a later separate-beyond-boundary milestone.
    operational_energy_flows = load_operational_energy_flows(
        operational_energy_flows_path, scenarios)
    operational_energy_factor_schedule = load_operational_factor_schedule(
        operational_energy_factor_schedule_path, environmental_factors)
    (operational_energy_coverage, operational_energy_ledger,
     operational_energy_summary, operational_energy_meta) = assess_operational_energy(
        operational_energy_flows, operational_energy_factor_schedule,
        environmental_factors, future_ids, config["analysis_years"],
        factor_extrapolation_policy=config["factor_extrapolation_policy"],
        generated_energy_reporting_approach=config["generated_energy_reporting_approach"],
    )
    carbon_consequence_ledger = append_operational_consequences(
        carbon_consequence_ledger, operational_energy_ledger)

    # M4: explicit terminal C1-C4 accounting plus separate D1/D2. The RSP
    # boundary remains an accounting state, not a lifecycle event. Production
    # mappings may remain empty; missing data are never converted to zero.
    end_of_life_assignments = load_end_of_life_assignments(
        end_of_life_assignments_path, component_boq, environmental_factors)
    d2_export_assignments = load_d2_export_assignments(
        d2_export_assignments_path, operational_energy_flows)
    d2_export_factor_schedule = load_d2_factor_schedule(
        d2_export_factor_schedule_path, environmental_factors)
    (end_of_life_coverage, d2_export_coverage, end_of_life_d_ledger,
     end_of_life_d_summary, end_of_life_d_meta) = assess_end_of_life_and_d(
        component_boq, environmental_factors, end_of_life_assignments,
        operational_energy_flows, d2_export_assignments, d2_export_factor_schedule,
        future_ids, horizon.years)
    carbon_consequence_ledger = append_end_of_life_and_d(
        carbon_consequence_ledger, end_of_life_d_ledger)

    # M5: applicability/coverage gate and lifecycle aggregation. Partial numeric
    # results remain explicitly labelled partial; Module D is always separate.
    module_applicability = load_module_applicability(module_applicability_path, scenarios)
    (lifecycle_module_coverage, lifecycle_carbon_aggregation, separate_module_d_summary,
     lifecycle_aggregation_meta) = assess_lifecycle_aggregation(
        scenarios, module_applicability, carbon_consequence_ledger, future_ids)

    raw = pd.concat([evaluate_scenario(row,futures,config) for _,row in scenarios.iterrows()],ignore_index=True)
    results = apply_replacements(raw,life_totals)
    summary = all_summaries(results,config)
    oat, correlations = sensitivity_analysis(scenarios,futures,results,config,components,seed)
    climate, robustness = performance_stress_analysis(scenarios,components,futures,config,seed,stress_cases,
                                                      evaluate_scenario,all_summaries)
    component_summary = life_totals.groupby(["scenario","component"],as_index=False).agg(
        mean_first_service_life_years=("first_service_life_years","mean"),
        mean_replacement_count=("replacement_count","mean"),
        probability_at_least_one_replacement=("replacement_count",lambda x:(x>0).mean()),
        mean_pv_replacement_cost_eur=("pv_replacement_cost_eur","mean"))
    tables = {"scenario_summary":summary,"simulation_results":results,
        "sampled_futures":futures.rename_axis("future_id").reset_index(),
        "uncertainty_summary":futures.describe(percentiles=[.1,.5,.9]).T.rename_axis("parameter").reset_index(),
        "component_lifecycle_draws":life_totals,"lifecycle_replacements":events,
        "lifecycle_event_ledger":lifecycle_event_ledger,"rsp_boundary_state":rsp_boundary_state,
        "reference_lifecycle_event_ledger":reference_lifecycle_event_ledger,
        "reference_rsp_boundary_state":reference_rsp_boundary_state,
        "lifecycle_event_boq_quantities":lifecycle_event_boq_quantities,
        "rsp_boundary_boq_state":rsp_boundary_boq_state,
        "reference_lifecycle_event_boq_quantities":reference_lifecycle_event_boq_quantities,
        "reference_rsp_boundary_boq_state":reference_rsp_boundary_boq_state,
        "physical_quantity_coverage":physical_quantity_coverage,
        "reference_coverage_skeleton":reference_coverage_skeleton,
        "environmental_factor_set_summary":factor_set_summary,
        "boq_factor_compatibility":boq_factor_compatibility,
        "boq_factor_coverage":boq_factor_coverage,
        "product_carbon_coverage":product_carbon_coverage,
        "carbon_consequence_ledger":carbon_consequence_ledger,
        "assessed_product_carbon_by_module":product_carbon_summary,
        "a4_transport_compatibility":a4_compatibility,
        "a4_transport_coverage":a4_coverage,
        "assessed_a4_transport_carbon_by_module":a4_summary,
        "b4_replacement_transport_compatibility":b4_transport_compatibility,
        "b4_replacement_transport_coverage":b4_transport_coverage_combined,
        "assessed_b4_replacement_transport_carbon_by_module":b4_transport_summary,
        "a5_construction_compatibility":a5_compatibility,
        "a5_construction_coverage":a5_coverage,
        "assessed_a5_construction_carbon_by_module":a5_summary,
        "a5_1_preconstruction_removal_compatibility":a5_1_compatibility,
        "a5_1_preconstruction_removal_coverage":a5_1_coverage,
        "assessed_a5_1_preconstruction_removal_carbon_by_module":a5_1_summary,
        "b4_event_process_compatibility":b4_event_process_compatibility,
        "b4_event_process_coverage":b4_event_process_coverage,
        "assessed_b4_event_process_carbon_by_module":b4_event_process_summary,
        "operational_energy_coverage":operational_energy_coverage,
        "assessed_operational_carbon_by_module":operational_energy_summary,
        "end_of_life_coverage":end_of_life_coverage,
        "d2_export_coverage":d2_export_coverage,
        "assessed_end_of_life_and_module_d_carbon_by_module":end_of_life_d_summary,
        "lifecycle_module_coverage":lifecycle_module_coverage,
        "lifecycle_carbon_aggregation":lifecycle_carbon_aggregation,
        "separate_module_d_summary":separate_module_d_summary,
        "component_summary":component_summary,
        "sensitivity_oat":oat,"sensitivity_rank_correlations":correlations,
        "weight_sensitivity":weight_sensitivity(summary,config),
        "allocation_sensitivity":allocation_sensitivity(results,config),
        "stress_test_summary":stress_tests(scenarios,futures,config,components,seed),
        "option_set_sensitivity":option_set_sensitivity(results,config,all_summaries),
        "climate_stress_summary":climate,"robust_across_stress_cases":robustness}
    if convergence_enabled:
        convergence, stability = convergence_analysis(scenarios,components,config,
                                                      sample_uncertain_futures,simulate,all_summaries)
        tables.update(monte_carlo_convergence=convergence,seed_stability=stability)
    output = Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    for name,table in tables.items(): table.to_csv(output/f"{name}.csv",index=False)
    for name,table in [("resolved_scenarios",scenarios),("resolved_components",components),("resolved_stress_cases",stress_cases)]:
        table.to_csv(output/f"{name}.csv",index=False)
    physical_reference_inventory.to_csv(output/"resolved_physical_reference_inventory.csv",index=False)
    (output/"reference_inventory_status.json").write_text(
        json.dumps(reference_inventory_meta, indent=2)+"\n")
    component_boq.to_csv(output/"resolved_component_boq.csv",index=False)
    reference_presence.to_csv(output/"resolved_reference_component_presence.csv",index=False)
    (output/"physical_boq_status.json").write_text(
        json.dumps(physical_boq_meta, indent=2)+"\n")
    environmental_factors.to_csv(output/"resolved_environmental_factors.csv",index=False)
    boq_factor_assignments.to_csv(output/"resolved_boq_environmental_factor_assignments.csv",index=False)
    (output/"environmental_registry_status.json").write_text(
        json.dumps(environmental_registry_meta, indent=2)+"\n")
    (output/"carbon_engine_status.json").write_text(
        json.dumps(carbon_engine_meta, indent=2)+"\n")
    transport_scenarios.to_csv(output/"resolved_transport_scenarios.csv",index=False)
    transport_factors.to_csv(output/"resolved_transport_factors.csv",index=False)
    transport_assignments.to_csv(output/"resolved_boq_transport_assignments.csv",index=False)
    replacement_transport_assignments.to_csv(output/"resolved_boq_replacement_transport_assignments.csv",index=False)
    construction_process_scenarios.to_csv(output/"resolved_construction_process_scenarios.csv",index=False)
    construction_process_assignments.to_csv(output/"resolved_boq_construction_process_assignments.csv",index=False)
    removal_transport_scenarios.to_csv(output/"resolved_removal_transport_scenarios.csv",index=False)
    preconstruction_waste_routes.to_csv(output/"resolved_preconstruction_waste_routes.csv",index=False)
    preconstruction_removal_scenarios.to_csv(output/"resolved_preconstruction_removal_scenarios.csv",index=False)
    b4_event_process_assignments.to_csv(output/"resolved_b4_event_process_assignments.csv",index=False)
    operational_energy_flows.to_csv(output/"resolved_operational_energy_flows.csv",index=False)
    operational_energy_factor_schedule.to_csv(output/"resolved_operational_energy_factor_schedule.csv",index=False)
    end_of_life_assignments.to_csv(output/"resolved_end_of_life_assignments.csv",index=False)
    d2_export_assignments.to_csv(output/"resolved_d2_export_assignments.csv",index=False)
    d2_export_factor_schedule.to_csv(output/"resolved_d2_export_factor_schedule.csv",index=False)
    module_applicability.to_csv(output/"resolved_module_applicability.csv",index=False)
    (output/"a4_transport_engine_status.json").write_text(json.dumps(a4_meta, indent=2)+"\n")
    (output/"b4_replacement_transport_engine_status.json").write_text(json.dumps(b4_transport_meta, indent=2)+"\n")
    (output/"a5_construction_engine_status.json").write_text(json.dumps(a5_meta, indent=2)+"\n")
    (output/"a5_1_preconstruction_removal_engine_status.json").write_text(json.dumps(a5_1_meta, indent=2)+"\n")
    (output/"b4_event_process_engine_status.json").write_text(json.dumps(b4_event_process_meta, indent=2)+"\n")
    (output/"b6_operational_energy_engine_status.json").write_text(json.dumps(operational_energy_meta, indent=2)+"\n")
    (output/"end_of_life_module_d_engine_status.json").write_text(json.dumps(end_of_life_d_meta, indent=2)+"\n")
    (output/"lifecycle_aggregation_status.json").write_text(json.dumps(lifecycle_aggregation_meta, indent=2)+"\n")
    resolved_config_bytes = (json.dumps(config,indent=2)+"\n").encode("utf-8")
    (output/"resolved_config.json").write_bytes(resolved_config_bytes)
    (output/"resolved_horizon.json").write_text(json.dumps({
        "mode": horizon.mode,
        "analysis_years": horizon.years,
        "source": horizon.source,
        "named_profiles": dict(HORIZON_PROFILES),
        "boundary_rule": "events exactly at or beyond the horizon are excluded",
        "resimulation_rule": "results are re-evaluated for each horizon; no linear scaling",
    },indent=2)+"\n")
    write_report(output,tables,config,simulations,seed)
    manifest = {"model_version":"3.2.0-research","economic_core_version":"2.1","migration_checkpoint":"v3-M5-FINAL-LIFECYCLE-GATE",
        "simulations":simulations,"seed":seed,
        "horizon_mode":horizon.mode,"analysis_years":horizon.years,"horizon_source":horizon.source,
        "resolved_config_sha256":hashlib.sha256(resolved_config_bytes).hexdigest(),
        "sampling_scheme":"keyed economic and lifetime streams; stable nested prefixes",
        "physical_reference_inventory_status":reference_inventory_meta["status"],
        "physical_reference_component_rows":reference_inventory_meta["component_rows"],
        "physical_boq_status":physical_boq_meta["status"],
        "physical_boq_rows":physical_boq_meta["boq_rows"],
        "environmental_registry_status":environmental_registry_meta["status"],
        "environmental_factor_records":environmental_registry_meta["factor_records"],
        "environmental_factor_sets":environmental_registry_meta["factor_sets"],
        "environmental_gate_pass_lines":environmental_registry_meta["gate_pass_lines"],
        "carbon_engine_status":carbon_engine_meta["status"],
        "carbon_consequence_rows":len(carbon_consequence_ledger),
        "product_carbon_consequence_rows":carbon_engine_meta["carbon_consequence_rows"],
        "a4_transport_consequence_rows":len(a4_ledger),
        "a4_transport_engine_status":a4_meta["status"],
        "b4_replacement_transport_consequence_rows":len(b4_transport_ledger),
        "b4_replacement_transport_engine_status":b4_transport_meta["status"],
        "a5_construction_consequence_rows":len(a5_ledger),
        "a5_construction_engine_status":a5_meta["status"],
        "a5_1_preconstruction_removal_consequence_rows":len(a5_1_ledger),
        "a5_1_preconstruction_removal_engine_status":a5_1_meta["status"],
        "b4_event_process_consequence_rows":len(b4_event_process_ledger),
        "b4_event_process_engine_status":b4_event_process_meta["status"],
        "b6_operational_consequence_rows":len(operational_energy_ledger),
        "b6_operational_engine_status":operational_energy_meta["status"],
        "terminal_c_d_consequence_rows":len(end_of_life_d_ledger),
        "terminal_c_d_engine_status":end_of_life_d_meta["status"],
        "lifecycle_aggregation_status":lifecycle_aggregation_meta["status"],
        "whole_life_carbon_generated":lifecycle_aggregation_meta["whole_life_carbon_generated"],
        "headline_carbon_generated":lifecycle_aggregation_meta["headline_carbon_generated"],
        "b6_legacy_energy_savings_proxy_used_for_carbon":False,
        "b6_export_credit_netted_into_a_c":False,
        "assessment_convention":config["assessment_convention"],
        "generated_energy_reporting_approach":config["generated_energy_reporting_approach"],
        "factor_extrapolation_policy":config["factor_extrapolation_policy"],
        "b6_future_factor_policy":operational_energy_meta["future_factor_policy"],
        "environmental_factor_reference_year_semantics":"DATASET_OR_SOURCE_REFERENCE_VINTAGE_NOT_APPLICATION_YEAR",
        "implemented_carbon_modules":carbon_engine_meta["implemented_modules"] + a4_meta["implemented_modules"] + b4_transport_meta["implemented_modules"] + a5_meta["implemented_modules"] + a5_1_meta["implemented_modules"] + b4_event_process_meta["implemented_modules"] + operational_energy_meta["implemented_modules"] + end_of_life_d_meta["implemented_modules"],
        "reference_presence_unknown_lineages":int(reference_presence.reference_presence_status.eq("UNKNOWN").sum()),
        "reference_coverage_denominator_scope":"KNOWN_INTERVENTION_LINEAGES_ONLY",
        "python":platform.python_version(),"numpy":np.__version__,"pandas":pd.__version__,
        "convergence_enabled":convergence_enabled,"charts_requested":charts,
        "input_sha256":{label:hashlib.sha256(Path(path).read_bytes()).hexdigest() for label,path in
            [("scenarios",input_path),("config",config_path),("components",components_path),("stress_cases",stress_path),
             ("physical_reference_inventory",reference_inventory_path),("component_boq",component_boq_path),
             ("reference_component_presence",reference_presence_path),("environmental_factors",environmental_factors_path),
             ("boq_environmental_factor_assignments",boq_factor_assignments_path),
             ("transport_scenarios",transport_scenarios_path),("transport_factors",transport_factors_path),
             ("boq_transport_assignments",boq_transport_assignments_path),
             ("boq_replacement_transport_assignments",boq_replacement_transport_assignments_path),
             ("construction_process_scenarios",construction_process_scenarios_path),
             ("boq_construction_process_assignments",boq_construction_process_assignments_path),
             ("removal_transport_scenarios",removal_transport_scenarios_path),
             ("preconstruction_waste_routes",preconstruction_waste_routes_path),
             ("preconstruction_removal_scenarios",preconstruction_removal_scenarios_path),
             ("b4_event_process_assignments",b4_event_process_assignments_path),
             ("operational_energy_flows",operational_energy_flows_path),
             ("operational_energy_factor_schedule",operational_energy_factor_schedule_path),
             ("end_of_life_assignments",end_of_life_assignments_path),
             ("d2_export_assignments",d2_export_assignments_path),
             ("d2_export_factor_schedule",d2_export_factor_schedule_path),
             ("module_applicability",module_applicability_path)]},
        "source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in PROJECT_DIR.glob("*.py")}}
    if charts:
        from charts import create_charts, create_v21_charts
        manifest["matplotlib"] = create_charts(results,summary,oat,tables["allocation_sensitivity"],output)
        create_v21_charts(tables,config,output)
    (output/"run_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=DEFAULT_INPUT)
    parser.add_argument("--config",type=Path,default=DEFAULT_CONFIG)
    parser.add_argument("--components",type=Path,default=DEFAULT_COMPONENTS)
    parser.add_argument("--stress-cases",type=Path,default=DEFAULT_STRESS)
    parser.add_argument("--reference-inventory",type=Path,default=DEFAULT_REFERENCE_INVENTORY)
    parser.add_argument("--component-boq",type=Path,default=DEFAULT_COMPONENT_BOQ)
    parser.add_argument("--reference-presence",type=Path,default=DEFAULT_REFERENCE_PRESENCE)
    parser.add_argument("--environmental-factors",type=Path,default=DEFAULT_ENVIRONMENTAL_FACTORS)
    parser.add_argument("--boq-factor-assignments",type=Path,default=DEFAULT_BOQ_FACTOR_ASSIGNMENTS)
    parser.add_argument("--transport-scenarios",type=Path,default=DEFAULT_TRANSPORT_SCENARIOS)
    parser.add_argument("--transport-factors",type=Path,default=DEFAULT_TRANSPORT_FACTORS)
    parser.add_argument("--boq-transport-assignments",type=Path,default=DEFAULT_BOQ_TRANSPORT_ASSIGNMENTS)
    parser.add_argument("--boq-replacement-transport-assignments",type=Path,default=DEFAULT_BOQ_REPLACEMENT_TRANSPORT_ASSIGNMENTS)
    parser.add_argument("--construction-process-scenarios",type=Path,default=DEFAULT_CONSTRUCTION_PROCESS_SCENARIOS)
    parser.add_argument("--boq-construction-process-assignments",type=Path,default=DEFAULT_BOQ_CONSTRUCTION_PROCESS_ASSIGNMENTS)
    parser.add_argument("--removal-transport-scenarios",type=Path,default=DEFAULT_REMOVAL_TRANSPORT_SCENARIOS)
    parser.add_argument("--preconstruction-waste-routes",type=Path,default=DEFAULT_PRECONSTRUCTION_WASTE_ROUTES)
    parser.add_argument("--preconstruction-removal-scenarios",type=Path,default=DEFAULT_PRECONSTRUCTION_REMOVAL_SCENARIOS)
    parser.add_argument("--b4-event-process-assignments",type=Path,default=DEFAULT_B4_EVENT_PROCESS_ASSIGNMENTS)
    parser.add_argument("--operational-energy-flows",type=Path,default=DEFAULT_OPERATIONAL_ENERGY_FLOWS)
    parser.add_argument("--operational-energy-factor-schedule",type=Path,default=DEFAULT_OPERATIONAL_ENERGY_FACTOR_SCHEDULE)
    parser.add_argument("--end-of-life-assignments",type=Path,default=DEFAULT_END_OF_LIFE_ASSIGNMENTS)
    parser.add_argument("--d2-export-assignments",type=Path,default=DEFAULT_D2_EXPORT_ASSIGNMENTS)
    parser.add_argument("--d2-export-factor-schedule",type=Path,default=DEFAULT_D2_EXPORT_FACTOR_SCHEDULE)
    parser.add_argument("--module-applicability",type=Path,default=DEFAULT_MODULE_APPLICABILITY)
    parser.add_argument("--output-dir",type=Path,default=PROJECT_DIR/"outputs")
    parser.add_argument("--simulations",type=int,default=10000)
    parser.add_argument("--seed",type=int,default=20260726)
    parser.add_argument("--no-charts",action="store_true")
    parser.add_argument("--skip-convergence",action="store_true")
    parser.add_argument("--horizon-mode",choices=list(HORIZON_PROFILES),default=None,
                        help="Named v3 reference-study-period profile; default preserves config analysis_years.")
    args = parser.parse_args()
    summary = run(args.input,args.output_dir,args.simulations,args.seed,args.config,not args.no_charts,
                  args.components,args.stress_cases,not args.skip_convergence,args.horizon_mode,
                  args.reference_inventory,args.component_boq,args.reference_presence,
                  args.environmental_factors,args.boq_factor_assignments,
                  args.transport_scenarios,args.transport_factors,args.boq_transport_assignments,
                  args.boq_replacement_transport_assignments,args.construction_process_scenarios,
                  args.boq_construction_process_assignments,args.removal_transport_scenarios,
                  args.preconstruction_waste_routes,args.preconstruction_removal_scenarios,
                  args.b4_event_process_assignments,args.operational_energy_flows,
                  args.operational_energy_factor_schedule,args.end_of_life_assignments,
                  args.d2_export_assignments,args.d2_export_factor_schedule,args.module_applicability)
    print(summary[["perspective","scenario","median_net_benefit_eur","probability_positive",
                   "worst_decile_mean_eur","pareto_on_core_metrics"]].to_string(index=False))
    print(f"\nOutputs written to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
