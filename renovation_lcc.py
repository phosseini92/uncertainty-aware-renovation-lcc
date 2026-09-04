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
from component_lifecycle import load_components, renewal_costs, apply_replacements
from convergence import validate_convergence, convergence_analysis
from performance_stress import load_stress_cases, performance_stress_analysis

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


def validate_config(config: dict) -> None:
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
        stress_path=DEFAULT_STRESS, convergence_enabled=True):
    config = load_config(config_path)
    scenarios = load_scenarios(input_path)
    components = load_components(components_path,scenarios)
    stress_cases = load_stress_cases(stress_path,scenarios,config)
    futures = sample_uncertain_futures(simulations,seed,config)
    life_totals, events = renewal_costs(components,futures,config,seed,retain_events=True)
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
        "component_lifecycle_draws":life_totals,"lifecycle_replacements":events,"component_summary":component_summary,
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
    (output/"resolved_config.json").write_text(json.dumps(config,indent=2)+"\n")
    write_report(output,tables,config,simulations,seed)
    manifest = {"model_version":"2.1","simulations":simulations,"seed":seed,
        "sampling_scheme":"keyed economic and lifetime streams; stable nested prefixes",
        "python":platform.python_version(),"numpy":np.__version__,"pandas":pd.__version__,
        "convergence_enabled":convergence_enabled,"charts_requested":charts,
        "input_sha256":{label:hashlib.sha256(Path(path).read_bytes()).hexdigest() for label,path in
            [("scenarios",input_path),("config",config_path),("components",components_path),("stress_cases",stress_path)]},
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
    parser.add_argument("--output-dir",type=Path,default=PROJECT_DIR/"outputs")
    parser.add_argument("--simulations",type=int,default=10000)
    parser.add_argument("--seed",type=int,default=20260726)
    parser.add_argument("--no-charts",action="store_true")
    parser.add_argument("--skip-convergence",action="store_true")
    args = parser.parse_args()
    summary = run(args.input,args.output_dir,args.simulations,args.seed,args.config,not args.no_charts,
                  args.components,args.stress_cases,not args.skip_convergence)
    print(summary[["perspective","scenario","median_net_benefit_eur","probability_positive",
                   "worst_decile_mean_eur","pareto_on_core_metrics"]].to_string(index=False))
    print(f"\nOutputs written to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
