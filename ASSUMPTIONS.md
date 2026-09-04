# V2.1 assumption register

## Evidence status

The original 24-dwelling scenario budgets and economic distributions were supplied
with the July 2026 demonstrator. Component allocations and lifetimes were added
as illustrative assumptions during the September revision. The stress multipliers
follow the proposed numerical examples, with labels explicitly changed to proxies.
No authoritative lifetime database, measured building dataset or climate projection
was used to establish these values. They must not be cited as empirical evidence.

## Core accounting

- Horizon 30 years; all values are incremental to the reference.
- Owner energy-bill savings share defaults to zero; tenants receive those savings.
- Owner pays initial net investment, routine maintenance and subsequent renewals.
- Rent increments are transfers and cancel in the combined private account.
- Initial grants apply to cost-adjusted investment; no grants are assumed on renewals.
- Nominal first-year annual amounts occur at year 1 end. Growth starts affecting
  them in year 2. The nominal discount rate is fixed within each future.
- The EUR 6 million terminal reference value is a hypothetical end-horizon nominal
  property value, not a current property value that is escalated by the model.
- Terminal premium represents post-horizon asset value, separate from rent within
  the horizon. This assumption needs real valuation evidence before an application.
- No taxes, debt, vacancy, moving costs, subsidies' public financing or household
  heterogeneity are modelled. Combined private is not social welfare.

```text
PV of annual amount A = sum t=1..T [A*(1+g)^(t-1)/(1+r)^t]
Renewal time k        = sum of sampled service lives 1..k
Nominal renewal cost  = component initial-cost allocation * replacement factor
                        * sampled capital-cost factor * (1+replacement growth)^time
PV renewal cost       = nominal renewal cost / (1+discount rate)^time
```

Only times strictly less than T incur renewals. Continuous timing is intentional;
there is no annual rounding. A failure is represented as the end of service life
followed by immediate renewal. Failure probabilities, repair states, outages and
physical degradation are not independently modelled.

## Component budgets and lifetimes

| Package | Component | Initial allocation, EUR | Life min/mode/max, years | Replacement fraction | Annual maintenance allocation, EUR |
|---|---|---:|---|---:|---:|
| Envelope | Insulation | 200,000 | 30 / 40 / 50 | 0.70 | 1,200 |
| Envelope | Windows | 140,000 | 20 / 30 / 40 | 0.85 | 1,600 |
| Envelope | Facade finish | 60,000 | 15 / 22 / 30 | 1.00 | 700 |
| Envelope + heat pump | Insulation | 200,000 | 30 / 40 / 50 | 0.70 | 1,000 |
| Envelope + heat pump | Windows | 140,000 | 20 / 30 / 40 | 0.85 | 1,500 |
| Envelope + heat pump | Facade finish | 60,000 | 15 / 22 / 30 | 1.00 | 500 |
| Envelope + heat pump | Heat pump | 400,000 | 12 / 18 / 25 | 0.80 | 4,500 |
| Deep + PV | Insulation | 500,000 | 30 / 40 / 50 | 0.70 | 1,500 |
| Deep + PV | Windows | 300,000 | 20 / 30 / 40 | 0.85 | 2,200 |
| Deep + PV | Facade finish | 200,000 | 15 / 22 / 30 | 1.00 | 800 |
| Deep + PV | Heat pump | 450,000 | 12 / 18 / 25 | 0.80 | 4,500 |
| Deep + PV | PV modules | 280,000 | 20 / 25 / 35 | 0.70 | 2,500 |
| Deep + PV | Inverter | 70,000 | 10 / 12 / 15 | 0.90 | 1,000 |

All default lives are triangular. These allocations are not equipment quotations;
they reconcile to illustrative incremental package CAPEX of EUR 400k / 800k / 1.8m
and maintenance of EUR 3.5k / 7.5k / 12.5k per year. The program checks both totals.
Maintenance is already charged by the scenario model and is not added again by
the component model. Initial allocations likewise are not added to CAPEX again.

Renewal growth is 2% nominal annually. Replacements use the same capital-cost
factor as the initial investment, giving perfect within-future cost-factor
dependence. Fresh lifetimes are sampled after each renewal. Equal uncertainty
keys couple component types across alternatives, but successive renewals and
distinct keys are independent. Technology-specific failure dependence remains
outside scope.

These are assumed incremental renewal obligations. In a real case, common
reference replacements and avoided maintenance must be modelled or subtracted;
using gross retrofit replacements as incremental costs can overstate costs.
Near-horizon renewals receive no remaining-life credit, potentially penalizing
such options. The separate property premium does not resolve component-level
residual value automatically. Both limits are disclosed rather than calibrated away.

## Economic uncertainty

| Parameter | Distribution |
|---|---|
| Discount rate | Triangular 0.02 / 0.035 / 0.06 |
| Effective energy price | Lognormal median 0.28 EUR/kWh, log sigma 0.18 |
| Energy-price growth | Triangular -0.005 / 0.02 / 0.06 |
| Rent growth | Triangular 0 / 0.015 / 0.035 |
| Initial grant share | Normal mean 0.20, SD 0.08, clipped to [0,0.40] |
| Capital-cost factor | Lognormal median 1.05, log sigma 0.12 |
| Savings performance factor | Normal mean 0.95, SD 0.10, clipped to [0.65,1.15] |
| Terminal-value factor | Normal mean 1, SD 0.18, clipped to [0.55,1.35] |

Clipping creates probability mass at bounds; it is not a renormalized truncated
normal. Lognormal parameters are medians. The capital-cost factor allows both
underruns and overruns. Economic marginals are independent; the same future is
applied across all packages. Growth rates do not fluctuate year by year.

Annual kWh savings remain proxies. Electricity/fuel substitution, COP, PV yield,
export prices, storage and weather dependence are not resolved. The lifetime
extension does not add any of these physical mechanisms.

## Preference and numerical tolerances

Fixed utility bounds and weights are in `model_config.json`. Bounds are budget-scale
illustrations declared before inspecting V2.1 outputs; there is no claim that a
stakeholder chose them. A changed criterion or value boundary should be reported
as a preference change. Saturating utilities can create ties; raw metrics remain
available and take precedence in scientific interpretation.

Convergence tolerances (EUR 10k mean; 1 percentage point positive frequency;
EUR 20k P10; EUR 30k lower tail/P95 regret) are declared numerical targets.
They must not be adjusted after the run to force all cases to pass. The five
independent seed ranges describe finite sampling variation, not input-model validity.

## Stress inputs and thresholds

| Proxy case | Retained savings multiplier | Equipment factor | Routine maintenance | Terminal premium |
|---|---|---:|---:|---:|
| Baseline | 1.00 | 1.00 | 1.00 | 1.00 |
| Moderate | 0.95 | 0.95 | 1.10 | 0.98 |
| Severe | 0.85 | 0.85 | 1.25 | 0.90 |
| Energy disruption | Uniform [0.80,1.10] | 0.90 | 1.15 | 0.95 |

These are hypothetical input perturbations, not historical/warming predictions.
The savings and equipment factors multiply the sampled savings-performance factor.
The joint product is a normalized energy-savings proxy, not equipment reliability
or thermal comfort. Renewal timing and costs are held paired across these cases.

Financial screen: median >= 0; positive frequency >= 0.70; P95 regret <= EUR 500k.
Performance proxy screen: at least 90% of draws retain 75% of the assumed annual
savings target. Count-based robustness: both screens pass in at least 3 of 4 cases.
These thresholds are illustrative and were declared before inspecting results.
Case counts are not probabilities. Zero-savings references have no applicable
performance target and do not automatically pass.
