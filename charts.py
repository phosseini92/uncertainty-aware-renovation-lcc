"""Static, exportable research charts with full axes and arbitrary scenario names."""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter, MaxNLocator
import numpy as np

PERSPECTIVES = ("owner", "tenant", "combined_private")
TITLES = {"owner": "Owner", "tenant": "Tenant", "combined_private": "Combined private"}
LABELS = {"discount_rate": "Discount rate", "energy_price_eur_kwh": "Starting energy price",
          "energy_price_growth": "Energy-price growth", "rent_growth": "Rent growth",
          "grant_share": "Grant share", "capex_factor": "Capital-cost factor",
          "performance_factor": "Performance factor", "value_uplift_factor": "Terminal-value factor"}


def create_charts(results, summary, sensitivity, allocation, output_dir: Path):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.titlesize": 13, "axes.labelsize": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "savefig.facecolor": "white"})
    scenarios = results[["scenario", "is_reference"]].drop_duplicates()
    names = scenarios.scenario.tolist()
    palette = plt.get_cmap("tab10")
    colors = {row.scenario: "#64748b" if row.is_reference else palette(i % 10)
              for i, row in enumerate(scenarios.itertuples())}
    handles = [Line2D([0], [0], color=colors[name], lw=3,
                      label=textwrap.fill(name, 32)) for name in names]

    def finish(fig, title, filename, subtitle, legend=True):
        fig.suptitle(title, fontsize=19, fontweight="bold", color="#17365d", y=.98)
        fig.text(.5, .91, subtitle, ha="center", va="top", fontsize=10, color="#475569")
        if legend:
            fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, .055),
                       ncol=min(2, len(names)), frameon=False, fontsize=10)
        fig.text(.5, .015, "Illustrative assumptions | Incremental to reference | No climate or building calibration",
                 ha="center", fontsize=9, color="#64748b")
        fig.tight_layout(rect=(.01, .19 if legend else .09, .99, .87), w_pad=2.4)
        for extension in ("png", "svg"):
            fig.savefig(output_dir / f"{filename}.{extension}", dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 7))
    for ax, perspective in zip(axes, PERSPECTIVES):
        for name in names:
            values = np.sort(results.loc[results.scenario.eq(name), f"{perspective}_net_benefit_eur"].to_numpy()) / 1000
            if np.ptp(values) == 0:
                ax.vlines(values[0], 0, 1, color=colors[name], linestyle="--", linewidth=2)
            else:
                ax.step(np.r_[values[0], values], np.r_[0, np.arange(1, len(values)+1)/len(values)],
                        where="post", color=colors[name], linewidth=1.7)
        ax.set(title=TITLES[perspective], xlabel="Net benefit (EUR thousands)", ylim=(0, 1))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.xaxis.set_major_locator(MaxNLocator(5))
        ax.grid(alpha=.18)
    axes[0].set_ylabel("Share of draws at or below value")
    finish(fig, "Full distributions of discounted net benefit", "net_benefit_distributions",
           "Empirical cumulative distributions retain the tails; the reference has a point mass at zero.")

    fig, axes = plt.subplots(1, 3, figsize=(15, 7))
    for ax, perspective in zip(axes, PERSPECTIVES):
        table = summary.loc[summary.perspective.eq(perspective)]
        for name in names:
            row = table.loc[table.scenario.eq(name)].iloc[0]
            ax.scatter(row.probability_nonnegative * 100, row.worst_decile_mean_eur / 1000,
                       s=115, color=colors[name], edgecolor="white", linewidth=.9, zorder=3)
        ax.axhline(0, color="#94a3b8", linewidth=1)
        ax.set(title=TITLES[perspective], xlabel="Nonnegative outcomes (%)", xlim=(-5, 105))
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.grid(alpha=.18)
        ax.margins(y=.16)
    axes[0].set_ylabel("Mean of worst 10% (EUR thousands)")
    finish(fig, "Downside and break-even frequency", "robustness_map",
           "Upper-right indicates less financial downside. Equal marker sizes; no probability encoded as a score.")

    fig, axes = plt.subplots(1, 3, figsize=(15, 7), sharey=True)
    for ax, perspective in zip(axes, PERSPECTIVES):
        table = summary.loc[summary.perspective.eq(perspective)].set_index("scenario")
        for i, name in enumerate(names):
            value = table.loc[name, "p95_regret_eur"] / 1000
            if np.isfinite(value):
                ax.barh(i, value, color=colors[name], height=.6)
                ax.text(value, i, f"  {value:,.0f}", va="center", fontsize=9)
            else:
                ax.text(0, i, "Excluded from choice set", va="center", fontsize=9)
        ax.set(title=TITLES[perspective], xlabel="95th-percentile regret (EUR thousands)")
        ax.set_yticks(range(len(names)), [textwrap.fill(n, 24) for n in names])
        ax.margins(x=.22)
        ax.grid(axis="x", alpha=.18)
        ax.xaxis.set_major_locator(MaxNLocator(4))
    axes[0].invert_yaxis()
    finish(fig, "Loss relative to the best eligible option", "scenario_regret",
           "Regret compares the same sampled future across options, including the reference when eligible.", legend=False)

    alternatives = scenarios.loc[scenarios.is_reference.eq(0), "scenario"].tolist()
    fig, axes = plt.subplots(1, len(alternatives), figsize=(max(7, 5 * len(alternatives)), 7.5),
                             sharey=True, squeeze=False)
    parameters = list(LABELS)
    for ax, name in zip(axes.flat, alternatives):
        table = sensitivity.loc[sensitivity.perspective.eq("combined_private") & sensitivity.scenario.eq(name)].set_index("parameter")
        for i, parameter in enumerate(parameters):
            row = table.loc[parameter]
            low = (row.at_parameter_p10_eur - row.central_net_benefit_eur) / 1000
            high = (row.at_parameter_p90_eur - row.central_net_benefit_eur) / 1000
            ax.barh(i, abs(high-low), left=min(low, high), height=.45, color="#cbd5e1")
            ax.scatter(low, i, color="#2563eb", s=28, zorder=3)
            ax.scatter(high, i, color="#ea580c", s=28, zorder=3)
        ax.axvline(0, color="#94a3b8", linewidth=1)
        ax.set(title=textwrap.fill(name, 25), xlabel="NPV change (EUR thousands)")
        ax.set_yticks(range(len(parameters)), [LABELS[p] for p in parameters])
        ax.grid(axis="x", alpha=.18)
        ax.xaxis.set_major_locator(MaxNLocator(5))
        ax.use_sticky_edges = False
        ax.margins(x=.12)
    axes.flat[0].invert_yaxis()
    fig.legend(handles=[Line2D([0],[0],marker="o",linestyle="",color="#2563eb",label="Parameter at sampled P10"),
                        Line2D([0],[0],marker="o",linestyle="",color="#ea580c",label="Parameter at sampled P90")],
               loc="lower center", bbox_to_anchor=(.5,.04), ncol=2, frameon=False)
    finish(fig, "One-at-a-time sensitivity: combined private view", "sensitivity_tornado",
           "Median economic inputs and modal component lifetimes held fixed; interactions are not decomposed.", legend=False)

    fig, axes = plt.subplots(1, 3, figsize=(15, 7))
    for ax, perspective in zip(axes, PERSPECTIVES):
        for name in names:
            table = allocation.loc[allocation.perspective.eq(perspective) & allocation.scenario.eq(name)]
            ax.plot(table.owner_energy_savings_share * 100, table.mean_net_benefit_eur / 1000,
                    color=colors[name], marker="o", linewidth=2)
        ax.axhline(0, color="#94a3b8", linewidth=1)
        ax.set(title=TITLES[perspective], xlabel="Energy-bill savings assigned to owner (%)", xticks=[0,50,100])
        ax.grid(alpha=.18)
    axes[0].set_ylabel("Mean net benefit (EUR thousands)")
    finish(fig, "Who receives the energy savings?", "allocation_tradeoff",
           "Same physical savings, different private allocation. Combined totals stay unchanged.")
    return matplotlib.__version__


def create_v21_charts(tables, config, output):
    scenarios = tables["simulation_results"][["scenario","is_reference"]].drop_duplicates()
    names = scenarios.scenario.tolist()
    palette = plt.get_cmap("tab10")
    colors = {r.scenario:"#64748b" if r.is_reference else palette(i%10)
              for i,r in enumerate(scenarios.itertuples())}

    def save(fig, name, title, subtitle):
        fig.suptitle(title,fontsize=18,fontweight="bold",color="#17365d",y=.99)
        fig.text(.5,.935,subtitle,ha="center",fontsize=10,color="#475569")
        fig.text(.5,.013,"Illustrative model | No empirical building or climate validation",ha="center",fontsize=9,color="#64748b")
        for ext in ("png","svg"): fig.savefig(output/f"{name}.{ext}",dpi=180)
        plt.close(fig)

    component_summary = tables["component_summary"]
    packages = component_summary.scenario.drop_duplicates().tolist()
    components = component_summary.component.drop_duplicates().tolist()
    fig,ax = plt.subplots(figsize=(13,6.5))
    left = np.zeros(len(packages))
    for j,component in enumerate(components):
        means = component_summary.loc[component_summary.component.eq(component)].set_index("scenario").mean_pv_replacement_cost_eur
        width = np.array([means.get(p,0)/1000 for p in packages])
        ax.barh(range(len(packages)),width,left=left,label=component,color=palette(j%10),height=.55)
        left += width
    for i,value in enumerate(left): ax.text(value,i,f"  {value:,.0f}",va="center")
    ax.set_yticks(range(len(packages)),[textwrap.fill(p,25) for p in packages])
    ax.set_xlabel("Mean discounted replacement costs (EUR thousands)")
    ax.invert_yaxis();ax.margins(x=.15);ax.grid(axis="x",alpha=.18)
    fig.legend(loc="lower center",bbox_to_anchor=(.5,.065),ncol=3,frameon=False)
    fig.tight_layout(rect=(.01,.20,.98,.86))
    save(fig,"lifecycle_replacement_costs","Component renewals within the analysis horizon",
         "Fresh lifetimes after each replacement; events at or after the horizon excluded; no residual credit.")

    climate = tables["climate_stress_summary"]
    combined = climate.loc[climate.perspective.eq("combined_private")]
    case_names = combined.stress_case.drop_duplicates().tolist()
    values = np.full((len(names),len(case_names)),np.nan)
    labels = {}
    for i,name in enumerate(names):
        for j,case in enumerate(case_names):
            row = combined.loc[combined.scenario.eq(name)&combined.stress_case.eq(case)].iloc[0]
            if row.performance_threshold_applicable:
                values[i,j] = int(row.acceptable_under_proxy_thresholds)
                labels[i,j] = f"Financial: {'pass' if row.financial_threshold_pass else 'fail'}\nPerformance proxy: {'pass' if row.performance_threshold_pass else 'fail'}"
            else: labels[i,j] = "Reference comparator\nPerformance: N/A"
    fig,ax = plt.subplots(figsize=(14,7))
    from matplotlib.colors import ListedColormap
    cmap=ListedColormap(["#fee2e2","#dcfce7"]).with_extremes(bad="#e2e8f0")
    ax.imshow(np.ma.masked_invalid(values),vmin=0,vmax=1,cmap=cmap,aspect="auto")
    for (i,j),label in labels.items():ax.text(j,i,label,ha="center",va="center",fontsize=10,color="#334155")
    ax.set_xticks(range(len(case_names)),[textwrap.fill(x,19) for x in case_names])
    ax.set_yticks(range(len(names)),[textwrap.fill(x,24) for x in names])
    ax.tick_params(length=0)
    fig.tight_layout(rect=(.01,.09,.99,.84))
    save(fig,"climate_stress_thresholds","Conditional stress screening: combined private view",
         "Hypothetical performance multipliers; retained energy savings are not an indoor-comfort metric.")

    if "seed_stability" not in tables:return
    stability = tables["seed_stability"]
    selected = stability.loc[stability.perspective.eq("combined_private")]
    fig,axes = plt.subplots(2,2,figsize=(14,10))
    metrics = [("mean_net_benefit_eur","Mean NPV (EUR thousands)",1000),
               ("probability_positive","Positive outcomes (%)",.01),
               ("worst_decile_mean_eur","Worst-decile mean (EUR thousands)",1000),
               ("p95_regret_eur","P95 regret (EUR thousands)",1000)]
    for ax,(metric,label,unit) in zip(axes.flat,metrics):
        for name in names:
            group = selected.loc[selected.scenario.eq(name)].sort_values("sample_size")
            x=group.sample_size.to_numpy()
            ax.plot(x,group[f"{metric}_mean"]/unit,color=colors[name],marker="o",label=textwrap.fill(name,32))
            ax.fill_between(x,group[f"{metric}_min"]/unit,group[f"{metric}_max"]/unit,color=colors[name],alpha=.12)
        ax.set_xscale("log")
        ax.set_xticks(sorted(selected.sample_size.unique()),[f"{n:,}" for n in sorted(selected.sample_size.unique())])
        ax.set(xlabel="Monte Carlo draws",ylabel=label)
        ax.grid(alpha=.18)
    handles,labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="lower center",bbox_to_anchor=(.5,.042),ncol=2,frameon=False)
    fig.tight_layout(rect=(.01,.14,.99,.89),h_pad=2)
    save(fig,"convergence_plot","Monte Carlo sample-size and seed diagnostics",
         "Lines: mean across independent seeds. Bands: observed seed ranges, not confidence intervals.")
