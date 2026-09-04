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
SCORE_METRICS = ("probability_nonnegative", "worst_decile_mean_eur",
                 "median_net_benefit_eur", "p95_regret_eur")


def validate_weights(weights: dict) -> None:
    if set(weights) != set(SCORE_METRICS):
        raise ValueError("Score weights must specify exactly the four documented metrics.")
    values = np.asarray(list(weights.values()), dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or not np.isclose(values.sum(), 1):
        raise ValueError("Score weights must be finite, nonnegative and sum to one.")


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
    validate_weights(config["score_weights"])
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
    rng = np.random.default_rng(seed)
    columns = {}
    for name in PARAMETERS:
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


def simulate(scenarios: pd.DataFrame, futures: pd.DataFrame, config: dict) -> pd.DataFrame:
    validate_futures(futures)
    return pd.concat([evaluate_scenario(row, futures, config)
                      for _, row in scenarios.iterrows()], ignore_index=True)


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


def score_summary(summary: pd.DataFrame, weights: dict) -> pd.DataFrame:
    validate_weights(weights)
    summary = summary.copy()
    summary["composite_score"] = np.nan
    active = summary.loc[summary.decision_eligible].copy()
    score = pd.Series(0.0, index=active.index)
    for metric, weight in weights.items():
        values = active[metric]
        span = values.max() - values.min()
        # A constant criterion is neutral in either direction.
        normalized = pd.Series(0.5, index=active.index) if span == 0 else (values - values.min()) / span
        if metric == "p95_regret_eur":
            normalized = 1 - normalized
        score += weight * normalized
    summary.loc[active.index, "composite_score"] = score
    summary["composite_rank"] = summary.composite_score.rank(ascending=False, method="min").astype("Int64")
    return summary.sort_values(["composite_rank", "scenario"], na_position="last").reset_index(drop=True)


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
    return score_summary(pd.DataFrame(rows), config["score_weights"])


def all_summaries(results, config):
    return pd.concat([build_summary(results, p, config) for p in PERSPECTIVES], ignore_index=True)


def sensitivity_analysis(scenarios, futures, results, config):
    """Paired deterministic OAT diagnostics plus sampled Spearman associations."""
    medians = futures.median()
    central = simulate(scenarios, pd.DataFrame([medians]), config).set_index("scenario")
    rows = []
    correlations = []
    for parameter in PARAMETERS:
        low, high = futures[parameter].quantile([.1, .9])
        f = pd.DataFrame([medians, medians])
        f[parameter] = [low, high]
        simulated = simulate(scenarios, f, config)
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
                "equal": [.25, .25, .25, .25], "downside_emphasis": [.2, .5, .1, .2],
                "regret_emphasis": [.1, .2, .2, .5], "median_emphasis": [.1, .1, .6, .2]}
    rows = []
    for perspective, group in summary.groupby("perspective"):
        for name, vector in profiles.items():
            weights = dict(zip(SCORE_METRICS, vector))
            scored = score_summary(group, weights)
            for row in scored.itertuples():
                rows.append({"perspective": perspective, "weight_profile": name,
                             "scenario": row.scenario, "composite_score": row.composite_score,
                             "composite_rank": row.composite_rank,
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


def stress_tests(scenarios, futures, config):
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
        summary = all_summaries(simulate(s, f, config), config)
        summary.insert(0, "stress_case", name)
        rows.append(summary)
    return pd.concat(rows, ignore_index=True)


def write_report(output, summary, results, config, n, seed):
    lines = ["RENOVATION ECONOMIC DEMONSTRATOR - VERSION 2", "",
             f"Illustrative building: {config['dwellings']} dwellings; {config['analysis_years']} years.",
             f"Monte Carlo draws: {n:,}; seed: {seed}.",
             f"Owner receives {config['owner_energy_savings_share']:.0%} of avoided energy bills.",
             f"Reference eligible for selection: {config['include_reference_in_decisions']}.",
             "All amounts are incremental nominal-EUR cash flows discounted to time zero.",
             "The zero reference is not a cost-free building: its common cash flows are subtracted.",
             "Reference feasibility is assumed for this demonstration, not checked against regulations.", ""]
    for perspective in PERSPECTIVES:
        table = summary.loc[summary.perspective.eq(perspective)]
        leaders = table.loc[table.composite_rank.eq(1), "scenario"].tolist()
        renovation = results.loc[results.is_reference.eq(0)].pivot(
            index="future_id", columns="scenario", values=f"{perspective}_net_benefit_eur")
        count = int(renovation.max(axis=1).lt(0).sum())
        lines += [perspective.upper(), "Top composite rank (conditional): " + "; ".join(leaders),
                  f"All renovation alternatives negative: {count:,}/{n:,} ({count/n:.2%}).",
                  table[["scenario", "mean_net_benefit_eur", "probability_positive",
                         "probability_nonnegative", "worst_decile_mean_eur", "p95_regret_eur",
                         "best_option_share", "composite_score", "composite_rank"]].to_string(index=False), ""]
    lines += ["INTERPRETATION", "Composite score is relative to the eligible options and chosen weights; it is not a probability.",
              "Positive means NPV > 0; nonnegative means NPV >= 0. The zero reference is 0% positive and 100% nonnegative.",
              "Best-option share splits exact numerical ties; it is distinct from positive-outcome frequency.",
              "Owner plus tenant cash flows equal combined private cash flows; rent cancels in the combined view.",
              "Combined private is not a social-welfare calculation: public grants remain external benefits.",
              "OAT sensitivity holds other parameters at sampled medians; rank correlations describe associations, not causation.",
              "Weight and stress cases are diagnostics, not calibrated probabilities or exhaustive robustness proofs.", "",
              "LIMITATIONS", "Illustrative inputs; independent parameters; shared scenario shocks; constant growth within each future.",
              "No climate simulation, comfort thresholds, environmental LCA, component replacements or lifetime uncertainty.",
              "Terminal value is a hypothetical end-horizon premium, separate from in-horizon rent; valuation is not calibrated.",
              "Consult README.md and ASSUMPTIONS.md before interpreting or extending the model."]
    (output / "analysis_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(input_path=DEFAULT_INPUT, output_dir=PROJECT_DIR / "outputs", simulations=10000,
        seed=20260726, config_path=DEFAULT_CONFIG, charts=True):
    config = load_config(config_path)
    scenarios = load_scenarios(input_path)
    futures = sample_uncertain_futures(simulations, seed, config)
    results = simulate(scenarios, futures, config)
    summary = all_summaries(results, config)
    oat, correlations = sensitivity_analysis(scenarios, futures, results, config)
    weights = weight_sensitivity(summary, config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {"scenario_summary": summary, "simulation_results": results,
              "sampled_futures": futures.rename_axis("future_id").reset_index(),
              "uncertainty_summary": futures.describe(percentiles=[.1, .5, .9]).T.rename_axis("parameter").reset_index(),
              "sensitivity_oat": oat, "sensitivity_rank_correlations": correlations,
              "weight_sensitivity": weights, "allocation_sensitivity": allocation_sensitivity(results, config),
              "stress_test_summary": stress_tests(scenarios, futures, config)}
    for name, table in tables.items():
        table.to_csv(output_dir / f"{name}.csv", index=False)
    (output_dir / "resolved_config.json").write_text(json.dumps(config, indent=2) + "\n")
    scenarios.to_csv(output_dir / "resolved_scenarios.csv", index=False)
    write_report(output_dir, summary, results, config, simulations, seed)
    manifest = {"model_version": "2.0", "simulations": simulations, "seed": seed,
                "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                "charts_requested": charts,
                "input_sha256": hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
                "config_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
                "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (Path(__file__), PROJECT_DIR / "charts.py")}}
    if charts:
        from charts import create_charts
        manifest["matplotlib"] = create_charts(results, summary, oat, tables["allocation_sensitivity"], output_dir)
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "outputs")
    parser.add_argument("--simulations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260726)
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args()
    summary = run(args.input, args.output_dir, args.simulations, args.seed, args.config, not args.no_charts)
    print(summary[["perspective", "scenario", "mean_net_benefit_eur", "composite_rank"]].to_string(index=False))
    print(f"\nOutputs written to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
