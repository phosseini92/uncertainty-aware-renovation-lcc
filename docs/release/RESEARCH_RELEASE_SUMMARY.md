# v3.2.0 research release summary

This release intentionally ends feature development for the PhD-application demonstrator. It closes the lifecycle-carbon architecture through terminal C1–C4, separately reported D1/D2 and an explicit module-coverage gate, while preserving the hard-frozen economic/lifecycle behavior of M3.1.1.

The release is designed as a reproducible decision-support demonstrator rather than a calibrated case-study LCA. Its central research contribution is the traceable architecture: a physical lifecycle event is represented once, can produce economic and carbon consequences without service-life resampling, and remains auditable through BoQ, factor, provenance, applicability and missing-data gates.

Default case data remain illustrative. Where source-backed environmental inputs are unavailable, the software reports not assessed rather than fabricating a value. This is why the current default run does not emit a Whole-Life Carbon headline even though the C/D and aggregation architecture is implemented.
