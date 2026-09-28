"""Declared reference-study-period profiles for the staged v3 migration.

M1.4 scope
----------
This module separates the assessment horizon from the historical 30-year
hard-coded default without changing any economic or lifecycle equations.

The three named profiles are methodological run modes, not claims of formal
standards compliance:

- ``legacy_30``: exact v2.1 continuity horizon (30 years)
- ``levels_50``: 50-year research horizon used for Level(s)-aligned analysis
- ``rics_60``: 60-year comparison horizon used for RICS-WLCA-aligned analysis

The runtime configuration remains a normal model config with the existing
``analysis_years`` field.  Profile resolution only replaces that one value in
an isolated copy, so legacy callers and the 30-year default remain intact.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Mapping


HORIZON_PROFILES: Mapping[str, int] = {
    "legacy_30": 30,
    "levels_50": 50,
    "rics_60": 60,
}


@dataclass(frozen=True)
class HorizonResolution:
    """Resolved horizon metadata for one model run."""

    mode: str
    years: int
    source: str


def validate_horizon_mode(mode: str) -> str:
    text = str(mode).strip()
    if text not in HORIZON_PROFILES:
        allowed = ", ".join(HORIZON_PROFILES)
        raise ValueError(f"Unsupported horizon mode: {text!r}. Choose one of: {allowed}.")
    return text


def infer_horizon_mode(years: int) -> str:
    """Return the named profile matching ``years`` or ``custom_config``."""
    for mode, profile_years in HORIZON_PROFILES.items():
        if years == profile_years:
            return mode
    return "custom_config"


def resolve_horizon(config: dict, horizon_mode: str | None = None) -> tuple[dict, HorizonResolution]:
    """Return an isolated runtime config and explicit horizon metadata.

    When ``horizon_mode`` is ``None`` the input configuration is preserved
    exactly (apart from the defensive deep copy).  This is the legacy-default
    path and is essential to 30-year numerical parity.

    When a named profile is supplied, only ``analysis_years`` is overridden.
    No linear scaling or post-processing of results is permitted; all model
    equations are re-evaluated for the resolved horizon.
    """
    if type(config.get("analysis_years")) is not int or config["analysis_years"] < 1:
        raise ValueError("analysis_years must be a positive integer before horizon resolution.")

    runtime = deepcopy(config)
    if horizon_mode is None:
        years = int(runtime["analysis_years"])
        return runtime, HorizonResolution(
            mode=infer_horizon_mode(years),
            years=years,
            source="config",
        )

    mode = validate_horizon_mode(horizon_mode)
    years = HORIZON_PROFILES[mode]
    runtime["analysis_years"] = years
    return runtime, HorizonResolution(mode=mode, years=years, source="profile_override")
