# Renovation economics under uncertainty

**Parisa Hosseini | Research demonstrator | Version 2, September 2026**

A reproducible Python example comparing three illustrative multi-family housing
renovation packages against an explicit reference over 30 years. It separates
owner, tenant and combined private cash flows and examines how uncertain inputs,
benefit allocation and decision weights influence the comparison.

The scientific contribution of this sample is a transparent computational
workflow. Its numerical results are conditional on illustrative assumptions;
they are not findings from a measured building, a TU Delft project, or a
validated climate-resilience assessment.

## Start here

1. Read **ASSUMPTIONS.md**, especially the accounting boundary and reference.
2. Open **outputs/analysis_report.txt** for the numerical interpretation.
3. Inspect **outputs/allocation_tradeoff.png** and **outputs/sensitivity_tornado.png**.
4. Use the current root **README.md** and **ASSUMPTIONS.md** to interpret the work within its demonstrated scope.

The three intervention packages retain the original sample inputs: envelope
retrofit, envelope plus heat pump, and deep renovation plus PV. Their labels
do not imply that a heat pump, PV array or building envelope is simulated
physically; annual energy savings are input proxies.

## Run

Python 3.10 or newer is required. From this folder, create an isolated environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python renovation_lcc.py
python -m unittest discover -s tests -v
```

On Windows, activate with `.venv\Scripts\activate` instead. Exact package
versions used for the delivered run are recorded in
`requirements-reproduced.txt` and `outputs/run_manifest.json`.

Alternative run:

```sh
python renovation_lcc.py --input inputs/renovation_scenarios.csv \
  --config inputs/model_config.json --simulations 10000 \
  --seed 20260726 --output-dir outputs_alternative
```

`--no-charts` runs the numerical analysis without importing Matplotlib.
Use a new output directory for each experiment to keep its files together.
The command prints the summary and writes all raw draws and cash-flow components.

## Accounting boundary

Every cash flow is incremental to **Reference: no additional intervention**.
The reference is represented by zero differences, not by zero actual operating
costs. Input savings and maintenance changes must already be measured against
that reference. Common costs therefore cancel.

Let E be discounted energy-bill savings, R the discounted rent increase paid by
tenants to the owner, V the terminal value premium, C net initial investment
after grants, M incremental maintenance, and a the owner's share of E:

```text
Owner net benefit            = a E + R + V - C - M
Tenant net benefit           = (1 - a) E - R
Combined private net benefit = E + V - C - M
Owner + tenant               = combined private
```

The default is **a = 0**, representing tenants paying energy bills directly.
This is an illustrative tenure assumption, not a claim about a specific building.
Change `owner_energy_savings_share` in `inputs/model_config.json` to investigate
other allocations. Rent is a transfer and cancels in the combined view.
Grants originate outside this private boundary and remain included. Consequently,
the combined private view must not be described as a societal cost-benefit analysis.

The owner pays all net capital and maintenance costs and receives all terminal
asset appreciation. Moving costs, taxes, vacancy, finance structure and unequal
effects across the 24 households are not modelled. A tenant-favoured option need
not be financeable for the owner; the three rankings are diagnostic perspectives,
not an agreed collective recommendation.

## Reference eligibility

The reference is included in the choice set by default. This makes it possible
to observe when every renovation performs worse than the reference financially.
Its legal and physical feasibility is assumed, not established.

If intervention is mandatory, set `include_reference_in_decisions` to `false`:
the reference remains visible as an accounting comparator but receives no
decision rank, regret or best-option share. If the appropriate benchmark is a
minimum mandatory intervention, first redefine every input as a difference
against that benchmark. Renaming a reference without rebasing the inputs is
not sufficient. Baseline inputs must be zero and exactly one row must carry
`is_reference=1`.

## Uncertainty and time

Eight economic/performance parameters are independently drawn with a fixed seed.
The same sampled future is applied to every alternative. This avoids comparing
different economic environments when calculating regret. It also imposes common
cost and performance factors across technologies; technology-specific uncertainty
and cross-parameter dependence are not modelled.

Cash flows change annually through fixed growth rates within each sampled future.
There are no year-by-year stochastic shocks, adaptive renovation timings, climate
trajectories, component replacements or uncertain service lives.

## Decision metrics

- Mean, median, P10 and P90 of discounted net benefit.
- `probability_positive`: empirical share of draws with NPV strictly greater than zero.
- `probability_nonnegative`: share with NPV greater than or equal to zero; used in the score.
- `worst_decile_mean_eur`: exact empirical mean of the lowest 10% probability mass,
  allowing a fractional boundary observation for small sample sizes.
- Mean and 95th-percentile regret: the benefit of the best eligible option in each
  common future minus the option's benefit.
- `best_option_share`: fraction of best outcomes, splitting numerical ties equally.
- `composite_score`: weighted min-max normalized criteria, followed by a rank.

The default weights are 0.30 for nonnegative frequency, 0.25 for lower-tail mean,
0.25 for median benefit, and 0.20 for lower P95 regret. They are illustrative
preferences, not estimated stakeholder weights. Constant criteria receive 0.5.
Only decision-eligible options set the normalization ranges. A score of 1 is a
relative score, not certainty, a success probability, or proof of optimality.
Scores can change when options, accounting perspective or weights change.

For the zero reference, positive frequency is 0% and nonnegative frequency is
100%. This is intentional. It avoids treating break-even as a positive gain while
allowing no-loss performance to enter the decision criteria.

## Sensitivity and diagnostic stress tests

1. **One-at-a-time (OAT):** move one parameter from its sampled P10 to P90 while
   holding all others at sampled medians. Results are deterministic conditional
   evaluations, not the P10/P90 of the output distribution. Interactions are not
   decomposed. Medians and bounds depend on the chosen sample and seed.
2. **Spearman rank associations:** correlate ranked sampled inputs and ranked
   net benefits. These are not causal effects or variance-based sensitivity indices.
3. **Decision weights:** compare the configured weights with equal, downside-,
   regret-, and median-emphasizing profiles. Five profiles are not an exhaustive
   sensitivity proof.
4. **Benefit allocation:** evaluate owner energy-savings shares of 0%, 50% and 100%.
   Combined private outcomes remain unchanged by construction.
5. **Stress cases:** remove grants, terminal appreciation or rent increases, and
   apply energy prices x0.75 with capital costs x1.25. These are transparent
   accounting/input perturbations, not calibrated hazard scenarios. No probability
   is assigned to a stress case. The same draws are used for paired comparisons.

## Output map

| File in outputs/ | Content |
|---|---|
| analysis_report.txt | Accounting assumptions, rankings and interpretation |
| scenario_summary.csv | All three perspectives and all alternatives |
| simulation_results.csv | Every future/option and its cash-flow components |
| sampled_futures.csv | Full eight-parameter draws keyed by future_id |
| uncertainty_summary.csv | Distribution summary statistics |
| sensitivity_oat.csv | Conditional P10/P90 parameter perturbations |
| sensitivity_rank_correlations.csv | Rank associations with net benefit |
| weight_sensitivity.csv | Scores/ranks under five preference profiles |
| allocation_sensitivity.csv | Energy savings allocation comparisons |
| stress_test_summary.csv | Paired diagnostic stress results |
| resolved_config.json / resolved_scenarios.csv | Inputs actually used |
| run_manifest.json | Versions, seed and input/source SHA-256 checksums |
| net_benefit_distributions.png / .svg | Full empirical cumulative distributions |
| robustness_map.png / .svg | Lower-tail outcome versus nonnegative frequency |
| scenario_regret.png / .svg | P95 regret by accounting perspective |
| sensitivity_tornado.png / .svg | OAT results for the combined private view |
| allocation_tradeoff.png / .svg | Distribution of energy benefits across parties |

All plots contain explicit axes and units. Reference distributions are point
masses at zero. PNGs provide previews; SVGs preserve scalable export quality.

## Validation and next research steps

Tests cover analytical discounting identities, a hand-calculated accounting case,
transfer cancellation, benefit allocation, reference inclusion/exclusion,
regret, ties, exact lower-tail mass, input checks, sensitivity direction and a
complete renamed-scenario run. Passing these checks establishes implementation
properties, not empirical validity of the parameter distributions.

Before extending this to a building case, specify the tenure and regulatory
baseline, obtain defensible cost and valuation inputs, distinguish energy
carriers, and add maintenance/replacement schedules. Climate/comfort modelling
would require a documented interface to building-performance outputs. Environmental
LCA would require its own inventory, boundaries and impact factors.

The supplied earlier model and inputs are retained in `provenance/` for traceability.
See **CHANGELOG.md** for the material changes in version 2.
