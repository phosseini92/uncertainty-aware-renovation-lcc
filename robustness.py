"""Independent outcome metrics first; fixed-anchor preferences are optional diagnostics."""
import numpy as np
import pandas as pd

METRICS = ("probability_positive", "worst_decile_mean_eur", "median_net_benefit_eur")


def validate_preferences(config):
    if set(config["score_weights"]) != set(METRICS) or set(config["preference_anchors"]) != set(METRICS):
        raise ValueError("Preference weights/anchors must define the three documented independent metrics.")
    weights = np.asarray(list(config["score_weights"].values()), float)
    if not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError("Preference weights must be finite, nonnegative and sum to one.")
    for metric, bounds in config["preference_anchors"].items():
        if len(bounds) != 2 or not np.isfinite(bounds).all() or bounds[0] >= bounds[1]:
            raise ValueError(f"Invalid fixed preference anchors: {metric}")


def score_summary(summary, config):
    validate_preferences(config)
    result = summary.copy()
    score = pd.Series(0., index=result.index)
    for metric, weight in config["score_weights"].items():
        low, high = config["preference_anchors"][metric]
        scaled = ((result[metric]-low)/(high-low)).clip(0, 1)
        result[f"preference_utility_{metric}"] = scaled
        score += weight * scaled
    result["preference_based_score"] = score.where(result.decision_eligible)
    result["conditional_preference_rank"] = result.preference_based_score.round(12).rank(
        ascending=False, method="min").astype("Int64")
    active = result.loc[result.decision_eligible, list(METRICS)].to_numpy()
    flags = []
    for point in active:
        dominates = (active >= point).all(axis=1) & (active > point).any(axis=1)
        flags.append(not dominates.any())
    result["pareto_on_core_metrics"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    result.loc[result.decision_eligible, "pareto_on_core_metrics"] = flags
    # Tables do not lead with a synthetic winner. Keep the physical alternatives in alphabetical order.
    return result.sort_values("scenario").reset_index(drop=True)


def option_set_sensitivity(results, config, summarizer):
    names = results.scenario.drop_duplicates().tolist()
    base = summarizer(results, config)
    cases = [("full", "none", results)]
    for name in names:
        subset = results.loc[results.scenario.ne(name)]
        eligible = subset.loc[subset.is_reference.eq(0)] if not config["include_reference_in_decisions"] else subset
        if not eligible.empty: cases.append(("remove", name, subset))
        clone = results.loc[results.scenario.eq(name)].copy()
        clone["scenario"] = f"Diagnostic copy of {name}"
        clone["is_reference"] = 0
        cases.append(("add_copy", name, pd.concat([results, clone], ignore_index=True)))
    dominated = results.loc[results.scenario.eq(names[0])].copy()
    dominated["scenario"] = "Diagnostic dominated alternative"
    dominated["is_reference"] = 0
    for perspective in base.perspective.unique():
        col = f"{perspective}_net_benefit_eur"
        dominated[col] = results.groupby("future_id")[col].min().to_numpy()-100000
    cases.append(("add_dominated", "synthetic EUR 100k below every outcome", pd.concat([results, dominated], ignore_index=True)))
    rows = []
    for operation, changed, data in cases:
        summary = summarizer(data, config)
        for perspective, group in summary.groupby("perspective"):
            original = base.loc[base.perspective.eq(perspective)].set_index("scenario")
            updated = group.set_index("scenario")
            common = [n for n in names if n in updated.index and bool(original.loc[n,"decision_eligible"])
                      and bool(updated.loc[n,"decision_eligible"])]
            reversals = 0
            for i, a in enumerate(common):
                for b in common[i+1:]:
                    before = round(original.loc[a,"preference_based_score"]-original.loc[b,"preference_based_score"],12)
                    after = round(updated.loc[a,"preference_based_score"]-updated.loc[b,"preference_based_score"],12)
                    reversals += int(before*after < 0)
            for row in group.to_dict("records"):
                old_score = original.loc[row["scenario"],"preference_based_score"] if row["scenario"] in original.index else np.nan
                old_rank = original.loc[row["scenario"],"conditional_preference_rank"] if row["scenario"] in original.index else pd.NA
                rows.append({"operation":operation,"changed_option":changed,**row,
                    "full_set_preference_rank":old_rank,"preference_score_change":row["preference_based_score"]-old_score,
                    "pairwise_preference_reversals_among_retained":reversals})
    return pd.DataFrame(rows)
