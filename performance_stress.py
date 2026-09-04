"""Interface for externally specified performance stress assumptions.

Delivered multipliers are illustrative proxies, not climate simulation outputs.
Performance thresholds concern retained annual energy savings, not indoor comfort.
"""
import numpy as np
import pandas as pd
from random_streams import rng_for

FIELDS = ("energy_savings_factor_low","energy_savings_factor_high","equipment_performance_factor",
          "maintenance_factor","terminal_value_factor")


def load_stress_cases(path, scenarios, config):
    table = pd.read_csv(path)
    required = {"stress_case","scenario","basis",*FIELDS}
    if required-set(table): raise ValueError(f"Missing stress columns: {sorted(required-set(table))}")
    for name in ("stress_case","scenario","basis"):
        if table[name].isna().any() or table[name].astype(str).str.strip().eq("").any():
            raise ValueError(f"Empty stress metadata: {name}")
        table[name] = table[name].astype(str).str.strip()
    if table.duplicated(["stress_case","scenario"]).any(): raise ValueError("Duplicate case/option stress entries.")
    for name in FIELDS:
        table[name] = pd.to_numeric(table[name],errors="raise")
        if not np.isfinite(table[name]).all() or table[name].lt(0).any():
            raise ValueError(f"Stress multipliers must be finite and nonnegative: {name}")
    if table.energy_savings_factor_low.gt(table.energy_savings_factor_high).any():
        raise ValueError("Stress lower energy factor must not exceed its upper factor.")
    for case, group in table.groupby("stress_case"):
        for scenario in scenarios.scenario:
            if not group.scenario.isin(["*",scenario]).any():
                raise ValueError(f"Missing stress mapping for {case}/{scenario}.")
    if table.stress_case.nunique() < config["thresholds"]["minimum_acceptable_stress_cases"]:
        raise ValueError("Required acceptable case count exceeds the supplied stress cases.")
    return table


def performance_stress_analysis(scenarios, components, futures, config, seed, cases, evaluator, summarizer):
    from component_lifecycle import renewal_costs, apply_replacements
    thresholds = config["thresholds"]
    # Renewal paths/costs are paired across these cases; lifetime stress is not inferred from labels.
    component_totals, _ = renewal_costs(components,futures,config,seed)
    summaries = []
    for case in cases.stress_case.drop_duplicates():
        definitions = cases.loc[cases.stress_case.eq(case)]
        scenario_results, performance = [], {}
        common_u = rng_for(seed,f"performance_stress:{case}").random(len(futures))
        for _, scenario in scenarios.iterrows():
            matched = definitions.loc[definitions.scenario.eq(scenario.scenario)]
            spec = (matched if not matched.empty else definitions.loc[definitions.scenario.eq("*")]).iloc[0]
            multiplier = spec.energy_savings_factor_low + common_u*(spec.energy_savings_factor_high-spec.energy_savings_factor_low)
            retained = futures.performance_factor.to_numpy()*multiplier*spec.equipment_performance_factor
            changed_f, changed_s = futures.copy(), scenario.copy()
            changed_f["performance_factor"] = retained
            changed_f["value_uplift_factor"] *= spec.terminal_value_factor
            changed_s["annual_maintenance_eur"] *= spec.maintenance_factor
            scenario_results.append(evaluator(changed_s,changed_f,config))
            applicable = not bool(scenario.is_reference) and scenario.annual_energy_savings_kwh > 0
            performance[scenario.scenario] = (
                float((retained>=thresholds["retained_savings_fraction_min"]).mean()) if applicable else np.nan)
        results = apply_replacements(pd.concat(scenario_results,ignore_index=True),component_totals)
        summary = summarizer(results,config)
        summary.insert(0,"stress_case",case)
        summary["performance_basis"] = "Illustrative retained annual savings proxy; not indoor comfort"
        summary["performance_pass_probability"] = summary.scenario.map(performance)
        summary["performance_threshold_applicable"] = summary.performance_pass_probability.notna()
        summary["performance_threshold_pass"] = pd.Series(pd.NA,index=summary.index,dtype="boolean")
        mask = summary.performance_threshold_applicable
        summary.loc[mask,"performance_threshold_pass"] = summary.loc[mask,"performance_pass_probability"].ge(
            thresholds["performance_pass_probability_min"])
        summary["financial_threshold_pass"] = (
            summary.decision_eligible & summary.median_net_benefit_eur.ge(thresholds["median_npv_min_eur"])
            & summary.probability_positive.ge(thresholds["probability_positive_min"])
            & summary.p95_regret_eur.le(thresholds["p95_regret_max_eur"]))
        summary["acceptable_under_proxy_thresholds"] = summary.financial_threshold_pass & summary.performance_threshold_pass.fillna(False)
        summaries.append(summary)
    all_cases = pd.concat(summaries,ignore_index=True)
    rows = []
    for (perspective,scenario), group in all_cases.groupby(["perspective","scenario"]):
        applicable = bool(group.performance_threshold_applicable.all())
        count = int(group.acceptable_under_proxy_thresholds.sum())
        rows.append({"perspective":perspective,"scenario":scenario,"stress_case_count":len(group),
            "performance_threshold_applicable":applicable,"acceptable_case_count":count,
            "required_acceptable_cases":thresholds["minimum_acceptable_stress_cases"],
            "robust_across_stress_cases":applicable and count>=thresholds["minimum_acceptable_stress_cases"],
            "interpretation":"Conditional proxy screen; cases are unweighted, not event probabilities"})
    return all_cases,pd.DataFrame(rows)
