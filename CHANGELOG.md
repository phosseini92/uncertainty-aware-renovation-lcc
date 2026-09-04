# V2.1 - four bounded methodological upgrades

The version was implemented through an iterative technical review of the
demonstrator, including AI-assisted debugging, testing and documentation support.
V2 and the original July folder were preserved. The author remains responsible
for the model, assumptions and interpretation.

1. Added reconciled component budgets, sampled service lives, repeated renewals,
   continuous event times, nominal escalation, discounting and event-level output.
2. Removed within-set min-max normalization. Individual metrics/Pareto trade-offs
   lead the report. An optional fixed-anchor score uses three independent metrics;
   regret remains a separate live-choice-set diagnostic. Added removal, duplicate
   and dominated-addition tests and output.
3. Added nested sample-size streams and five-seed convergence diagnostics, Wilson
   frequency intervals, cross-seed ranges and predeclared numerical tolerances.
4. Added a configurable external performance-stress interface and separate financial
   and retained-savings screens, with an explicitly conditional case-count flag.

## Why results differ from V2

V2.1 includes costs that V2 omitted. The random-stream scheme also changed to
make sample-size prefixes invariant, so a same-number seed no longer reproduces
the V2 draws. The version and sampling scheme are recorded in the manifest.
Preference criteria, normalization and naming changed. No claim of unchanged
rankings or economic conclusions is appropriate.

The reported V2 rank reversal was independently reproduced before revision:
with all options the combined-private score led with Envelope + heat pump;
removing Deep renovation + PV led with Reference. This arose from within-set
scaling and was not fixed merely by renaming the score.

V2.1 keeps regret outside the score because its benchmark changes with the option
set. Fixed anchors alone would not make a regret-based score set-independent.
The new diagnostic tests retained-option score values and pairwise order, rather
than requiring ordinal ranks or live-set regret to remain unchanged.

## Deferred work

Measured building calibration, physical failure/downtime, component residuals,
reference replacement schedules, temperature/comfort simulation, multiple energy
carriers, environmental LCA, empirical correlations and a dashboard are outside
this revision.
