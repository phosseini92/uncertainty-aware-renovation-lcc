"""Finite-sample diagnostics across nested sample sizes and independent seeds."""
import numpy as np
import pandas as pd

CONVERGENCE_METRICS = ("mean_net_benefit_eur", "probability_positive", "p10_net_benefit_eur",
                       "worst_decile_mean_eur", "p95_regret_eur")


def validate_convergence(settings):
    sizes, seeds = settings["sample_sizes"], settings["seeds"]
    if len(sizes) < 2 or len(set(sizes)) != len(sizes) or any(type(x) is not int or x < 10 for x in sizes):
        raise ValueError("Convergence needs at least two unique sample sizes >= 10.")
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or any(type(x) is not int or x < 0 for x in seeds):
        raise ValueError("Convergence needs at least two unique nonnegative integer seeds.")
    if set(settings["tolerances"]) != set(CONVERGENCE_METRICS):
        raise ValueError("Convergence tolerances must specify the five documented metrics.")
    if any(not np.isfinite(x) or x <= 0 for x in settings["tolerances"].values()):
        raise ValueError("Convergence tolerances must be positive and finite.")


def convergence_analysis(scenarios, components, config, sampler, simulator, summarizer):
    settings = config["convergence"]
    validate_convergence(settings)
    sizes, seeds = sorted(settings["sample_sizes"]), settings["seeds"]
    rows = []
    for seed in seeds:
        futures = sampler(sizes[-1], seed, config)
        full = simulator(scenarios, futures, config, components, seed)
        largest = summarizer(full, config).set_index(["perspective", "scenario"])
        for n in sizes:
            summary = summarizer(full.loc[full.future_id.lt(n)], config)
            for row in summary.to_dict("records"):
                reference = largest.loc[(row["perspective"],row["scenario"])]
                p = row["probability_positive"]
                z, den = 1.959963984540054, 1+1.959963984540054**2/n
                centre = (p+z*z/(2*n))/den
                half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
                entry = {"sample_size":n,"seed":seed,**row,
                    "positive_frequency_wilson95_low":max(0,centre-half),
                    "positive_frequency_wilson95_high":min(1,centre+half),
                    "comparison_sample_size":sizes[-1],"is_largest_sample_reference":n==sizes[-1]}
                evaluated, passed = [], []
                for metric in CONVERGENCE_METRICS:
                    error = abs(row[metric]-reference[metric])
                    entry[f"abs_difference_vs_largest_{metric}"] = error
                    if np.isfinite(error):
                        evaluated.append(metric)
                        passed.append(error <= settings["tolerances"][metric])
                entry["within_diagnostic_tolerances"] = all(passed) if n != sizes[-1] and evaluated else pd.NA
                entry["metrics_evaluated"] = len(evaluated)
                rows.append(entry)
    result = pd.DataFrame(rows)
    result["conditional_preference_rank"] = result.conditional_preference_rank.astype("Int64")
    result["pareto_on_core_metrics"] = result.pareto_on_core_metrics.astype("boolean")
    result["within_diagnostic_tolerances"] = result.within_diagnostic_tolerances.astype("boolean")
    stability = []
    for (n,perspective,scenario), group in result.groupby(["sample_size","perspective","scenario"]):
        entry = {"sample_size":n,"perspective":perspective,"scenario":scenario,
                 "independent_seeds":len(group),
                 "first_preference_rank_count":int(group.conditional_preference_rank.eq(1).sum()),
                 "preference_rank_min":group.conditional_preference_rank.min(),
                 "preference_rank_max":group.conditional_preference_rank.max()}
        for metric in CONVERGENCE_METRICS:
            for stat in ("mean","min","max","std"):
                entry[f"{metric}_{stat}"] = getattr(group[metric],stat)()
        stability.append(entry)
    return result, pd.DataFrame(stability)
