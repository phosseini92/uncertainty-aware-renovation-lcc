# Assumption register and equations

All numerical assumptions below are illustrative. Their source is the supplied
July 2026 demonstrator, except for the explicitly introduced accounting and
reference choices. No cost database, weather file, measured consumption record,
regulation or property valuation has been used to calibrate this revision.

## Cash-flow convention

- Time 0 is the investment decision. All comparisons are incremental.
- Annual energy, rent and maintenance amounts are nominal end-of-year cash flows.
  Input annual amounts correspond to year 1. A growth rate first increases them
  in year 2. The sampled discount rate is treated as nominal.
- EUR is the common unit; the example does not establish a market-price base date.
  A real application must align price dates and inflation consistently.
- Initial grants are received at time 0 on the full cost-adjusted investment.
  Eligibility caps, grant delays and grant taxation are omitted.
- The terminal reference value of EUR 6 million is interpreted as a hypothetical
  **nominal reference property value at the end of the analysis horizon**. It is
  not a current value that the model escalates. Changing the horizon requires
  reviewing this input.
- The terminal premium is assumed to represent asset value beyond the modelled
  horizon; it must not count the same in-horizon rent twice. This separation is an
  accounting assumption, not a calibrated property valuation method.
- Maintenance entries are incremental changes relative to reference maintenance.
  They do not cover a replacement schedule or loss of performance with age.

For first-year amount A, annual growth g, discount r and horizon T:

```text
PV(A,g,r,T) = sum for t=1..T of A * (1+g)^(t-1) / (1+r)^t
Gross investment = input CAPEX * capital-cost factor
Net investment   = gross investment * (1 - grant share)
PV energy        = PV(input kWh savings * performance factor * energy price,
                      energy-price growth, discount rate, T)
PV rent          = PV(monthly rent increment * dwellings * 12,
                      rent growth, discount rate, T)
PV maintenance   = PV(incremental annual maintenance, 0.02, discount rate, T)
PV terminal      = terminal reference value * premium fraction
                   * terminal-value factor / (1+discount rate)^T
```

The annual kWh saving is an avoided-energy-cost proxy. The model does not resolve
electricity versus fuel substitution, time-of-use tariffs, export revenues,
heat-pump COP, PV yield, storage or weather dependence. These are important
limits on interpreting technology labels.

## Fixed choices

| Assumption | Default | Meaning/source |
|---|---:|---|
| Horizon | 30 years | Retained example horizon |
| Dwellings | 24 | Retained illustrative building |
| End-horizon reference value | EUR 6,000,000 | Retained amount; nominal terminal interpretation made explicit |
| Maintenance growth | 2% annually | Retained illustrative escalation |
| Owner's energy-savings share | 0% | New illustrative tenant-billed default; configurable |
| Reference admissible | true | New explicit choice-set assumption; not a legal determination |
| Reference incremental flows | zero | Accounting normalization, not zero actual building costs |
| CAPEX/maintenance responsibility | owner | New explicit accounting boundary |
| Grant boundary | outside owner + tenants | Combined view includes external subsidy; not social welfare |

## Input distributions

The random generator is NumPy `default_rng`; the delivered sample uses seed
20260726 and 10,000 draws. Parameters are drawn in the order below, preserving
the original sampling design. Marginals are independent. Each draw is applied
to every option, including common cost and performance multipliers.

| Parameter | Distribution and parameters | Interpretation and limitation |
|---|---|---|
| Discount rate | Triangular: 2%, mode 3.5%, 6% | Fixed nominal rate per future |
| Starting energy price | Lognormal: median EUR 0.28/kWh, log sigma 0.18 | Effective avoided price; not a specific tariff |
| Energy-price growth | Triangular: -0.5%, mode 2%, 6% | Constant annual growth per future |
| Rent growth | Triangular: 0%, mode 1.5%, 3.5% | Escalation of incremental rent, not total building rent |
| Grant share | Normal: mean 20%, SD 8%, clipped to [0%,40%] | Clipping creates probability mass at the bounds |
| Capital-cost factor | Lognormal: median 1.05, log sigma 0.12 | Allows underruns as well as overruns; not overrun-only |
| Performance factor | Normal: mean 0.95, SD 0.10, clipped to [0.65,1.15] | Multiplies fixed annual savings; no building physics |
| Terminal-value factor | Normal: mean 1, SD 0.18, clipped to [0.55,1.35] | Multiplies an assumed terminal premium |

Lognormal values above are medians, not means. A clipped normal is not a
truncated-and-renormalized normal. Distribution families/ranges are retained
for reproducible comparison and must be justified afresh for real applications.
Sampling more futures does not make these assumed distributions empirically valid.

The input CSV retains the original intervention values (CAPEX EUR 400k/800k/1.8m;
annual energy savings 70k/145k/250k kWh; rent uplift EUR 15/35/55 per dwelling
per month; maintenance EUR 3.5k/7.5k/12.5k per year; terminal premium 3%/6%/9%).
These are illustrative differences from the reference, not measured outcomes.

## Decision interpretation

The choice set is shared across perspectives for diagnostic comparability.
No individual acceptance constraints, financing constraints or negotiations
between owner and tenant are enforced. Consequently, combined-private ranking
does not establish that all stakeholders accept the same intervention.

The model optimizes no continuous design variables. It ranks a finite set of
input alternatives. It evaluates probabilistic economic performance conditional
on chosen distributions, rather than guaranteeing robustness to unspecified
future states or quantifying climate resilience.
