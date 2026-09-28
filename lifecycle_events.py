"""Canonical physical lifecycle-event ledger for the v3 migration.

Milestone M1.1-M1.6 scope
-------------------------
This module introduces a validated, carbon-neutral physical event ledger and
an adapter back to the exact v2.1 replacement-event schema.  It deliberately
contains no carbon factors, environmental calculations or stakeholder
allocation. M1.5 adds explicit service-life provenance so the first renewal of
a retained existing component can use a documented remaining-life model while
subsequent renewals use the full service-life model. M1.6 keeps RSP-boundary
observations in a separate state ledger because reaching the analysis boundary
is not itself a physical event.

The current v2.1 component inventory is cost-centric and has no physical
quantity/unit or calendar base year.  Those fields therefore remain nullable
in the legacy adapter until later v3 migration milestones provide documented
physical inputs.  No values are invented to fill those gaps.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
import pandas as pd

from identity import validate_stable_id

# `future_id` is required even though it was omitted from the first design
# draft: a Monte-Carlo event ledger cannot be uniquely queried or reconciled
# across futures without it.
LIFECYCLE_EVENT_COLUMNS = (
    "event_id",
    "future_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "component_generation",
    "event_type",
    "event_time_years",
    "calendar_year",
    "event_quantity",
    "event_unit",
    "physical_state_before",
    "physical_state_after",
    "source_event_id",
    "random_stream_key",
    "sampled_service_life_years",
    "service_life_basis",
)

SUPPORTED_EVENT_TYPES = {
    "T0_RETAINED_STATE",
    "T0_REMOVAL",
    "T0_INSTALL",
    "MAINTENANCE",
    "REPAIR",
    "B4_REPLACEMENT",
    "B5_REFURBISHMENT",
}

# Exact public v2.1 schema.  The adapter must reproduce this without changes.
LEGACY_REPLACEMENT_EVENT_COLUMNS = (
    "future_id",
    "scenario",
    "component",
    "renewal_number",
    "renewal_time_years",
    "preceding_service_life_years",
    "nominal_replacement_cost_eur",
    "pv_replacement_cost_eur",
)


def empty_lifecycle_event_ledger() -> pd.DataFrame:
    """Return an empty canonical ledger with stable column order."""
    return pd.DataFrame(columns=LIFECYCLE_EVENT_COLUMNS)


def _stable_event_id(
    future_id: int,
    scenario_id: str,
    component_instance_id: str,
    event_type: str,
    component_generation: int,
) -> str:
    """Create a compact deterministic identifier from physical event identity.

    Time and cost are intentionally excluded.  If an assumption changes the
    event timing, it is still the same logical generation event in the same
    future/scenario/component stream; the changed time remains visible in the
    event record.  M1.3 supplies explicit stable scenario/component IDs, so
    display-label edits do not alter event identity.
    """
    key = "|".join(
        [
            str(int(future_id)),
            str(scenario_id),
            str(component_instance_id),
            str(event_type),
            str(int(component_generation)),
        ]
    )
    return "evt_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def canonical_replacement_events(
    *,
    future_ids: Iterable[int],
    scenario_id: str,
    component_instance_id: str,
    comparison_lineage_id: str,
    uncertainty_key: str,
    generation: int,
    event_times_years: np.ndarray,
    sampled_service_life_years: np.ndarray,
    random_stream_key: str | None = None,
    service_life_basis: str = "FULL_SERVICE_LIFE",
) -> pd.DataFrame:
    """Build canonical B4 replacement events from the existing v2.1 engine.

    Stable identity is independent of display labels. M1.5 also records whether
    the interval preceding a replacement came from an explicit remaining-life
    model (retained component, first renewal only) or from the full service-life
    model. Physical quantity, calendar year and state remain nullable until
    later v3 milestones provide documented inputs.
    """
    ids = np.asarray(list(future_ids), dtype=int)
    times = np.asarray(event_times_years, dtype=float)
    lives = np.asarray(sampled_service_life_years, dtype=float)
    if not (len(ids) == len(times) == len(lives)):
        raise ValueError("Replacement event arrays must have equal length.")

    scenario_id = str(scenario_id).strip()
    component_instance_id = str(component_instance_id).strip()
    lineage_id = str(comparison_lineage_id).strip()
    if not scenario_id or not component_instance_id or not lineage_id:
        raise ValueError("Stable scenario/component/lineage IDs must be nonempty.")
    stream_key = (str(random_stream_key).strip() if random_stream_key is not None
                  else f"lifetime:{uncertainty_key}:renewal:{int(generation)}")
    if not stream_key:
        raise ValueError("Replacement events require a nonempty random_stream_key.")
    service_life_basis = str(service_life_basis).strip()
    if service_life_basis not in {"FULL_SERVICE_LIFE", "REMAINING_LIFE"}:
        raise ValueError(f"Unsupported service_life_basis: {service_life_basis}")

    rows = []
    for future_id, event_time, service_life in zip(ids, times, lives):
        rows.append(
            {
                "event_id": _stable_event_id(
                    future_id,
                    scenario_id,
                    component_instance_id,
                    "B4_REPLACEMENT",
                    generation,
                ),
                "future_id": int(future_id),
                "scenario_id": scenario_id,
                "component_instance_id": component_instance_id,
                "comparison_lineage_id": lineage_id,
                "component_generation": int(generation),
                "event_type": "B4_REPLACEMENT",
                "event_time_years": float(event_time),
                # No assessment base year exists in v2.1.  Leave nullable.
                "calendar_year": pd.NA,
                # v2.1 components are cost allocations, not physical BoQ rows.
                "event_quantity": np.nan,
                "event_unit": pd.NA,
                "physical_state_before": pd.NA,
                "physical_state_after": pd.NA,
                "source_event_id": pd.NA,
                "random_stream_key": stream_key,
                "sampled_service_life_years": float(service_life),
                "service_life_basis": service_life_basis,
            }
        )
    ledger = pd.DataFrame(rows, columns=LIFECYCLE_EVENT_COLUMNS)
    return validate_lifecycle_event_ledger(ledger)


def validate_lifecycle_event_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    """Validate the canonical event ledger and return a normalized copy.

    M1 validation intentionally checks only facts that the legacy model can
    support.  Physical quantities, calendar year, and state become stricter in
    later milestones once documented v3 inputs exist.
    """
    missing = set(LIFECYCLE_EVENT_COLUMNS) - set(ledger.columns)
    if missing:
        raise ValueError(f"Missing lifecycle event columns: {sorted(missing)}")
    extra = set(ledger.columns) - set(LIFECYCLE_EVENT_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected lifecycle event columns: {sorted(extra)}")

    out = ledger.loc[:, LIFECYCLE_EVENT_COLUMNS].copy()
    if out.empty:
        return out

    required_text = [
        "event_id",
        "scenario_id",
        "component_instance_id",
        "comparison_lineage_id",
        "event_type",
        "random_stream_key",
        "service_life_basis",
    ]
    for field in required_text:
        if out[field].isna().any():
            raise ValueError(f"Missing lifecycle event field: {field}")
        out[field] = out[field].astype(str).str.strip()
        if out[field].eq("").any():
            raise ValueError(f"Empty lifecycle event field: {field}")

    for field in ("scenario_id", "component_instance_id", "comparison_lineage_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]

    if out.event_id.duplicated().any():
        raise ValueError("Lifecycle event IDs must be unique.")
    if not out.event_type.isin(SUPPORTED_EVENT_TYPES).all():
        bad = sorted(set(out.loc[~out.event_type.isin(SUPPORTED_EVENT_TYPES), "event_type"]))
        raise ValueError(f"Unsupported lifecycle event type(s): {bad}")

    for field in ("future_id", "component_generation"):
        numeric = pd.to_numeric(out[field], errors="raise")
        if not np.isfinite(numeric.to_numpy(dtype=float)).all():
            raise ValueError(f"Nonfinite lifecycle event field: {field}")
        if (numeric < 0).any() or not np.allclose(numeric, np.floor(numeric)):
            raise ValueError(f"Lifecycle event field must be a non-negative integer: {field}")
        out[field] = numeric.astype(int)

    for field in ("event_time_years", "sampled_service_life_years"):
        out[field] = pd.to_numeric(out[field], errors="raise")
        if not np.isfinite(out[field]).all():
            raise ValueError(f"Nonfinite lifecycle event field: {field}")
        if (out[field] <= 0).any():
            raise ValueError(f"Lifecycle event field must be positive: {field}")

    allowed_life_basis = {"FULL_SERVICE_LIFE", "REMAINING_LIFE"}
    if not out.service_life_basis.isin(allowed_life_basis).all():
        bad = sorted(set(out.loc[~out.service_life_basis.isin(allowed_life_basis), "service_life_basis"]))
        raise ValueError(f"Unsupported service_life_basis value(s): {bad}")
    if out.loc[out.service_life_basis.eq("REMAINING_LIFE"), "component_generation"].ne(1).any():
        raise ValueError("REMAINING_LIFE may only precede the first replacement generation.")

    if out.loc[out.event_type.eq("B4_REPLACEMENT"), "component_generation"].lt(1).any():
        raise ValueError("B4 replacement generations start at 1.")

    # A generation in one future/component stream can occur only once.
    key = ["future_id", "scenario_id", "component_instance_id", "event_type", "component_generation"]
    if out.duplicated(key).any():
        raise ValueError("Duplicate lifecycle event identity within a future/component stream.")

    return out


def legacy_replacement_events_from_ledger(
    lifecycle_ledger: pd.DataFrame,
    replacement_costs: pd.DataFrame,
) -> pd.DataFrame:
    """Recreate the exact v2.1 replacement-event table from canonical events.

    Economic amounts remain calculated by the unchanged v2.1 equations.  They
    are joined to the physical ledger by future/scenario/component/generation;
    lifecycle timing itself comes from the canonical ledger.
    """
    ledger = validate_lifecycle_event_ledger(lifecycle_ledger)
    repl = ledger.loc[ledger.event_type.eq("B4_REPLACEMENT")].copy()
    if repl.empty:
        return pd.DataFrame(columns=LEGACY_REPLACEMENT_EVENT_COLUMNS)

    needed_costs = {
        "future_id",
        "scenario_id",
        "component_instance_id",
        "component_generation",
        "nominal_replacement_cost_eur",
        "pv_replacement_cost_eur",
    }
    missing = needed_costs - set(replacement_costs.columns)
    if missing:
        raise ValueError(f"Missing replacement-cost adapter columns: {sorted(missing)}")

    keys = ["future_id", "scenario_id", "component_instance_id", "component_generation"]
    merged = repl.merge(
        replacement_costs.loc[:, [*keys, "nominal_replacement_cost_eur", "pv_replacement_cost_eur"]],
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if merged[["nominal_replacement_cost_eur", "pv_replacement_cost_eur"]].isna().any().any():
        raise ValueError("Every canonical replacement event must reconcile to one economic consequence.")

    # Recover display names without parsing arbitrary user labels from IDs.
    # The migration-cost table carries the exact original strings.
    names = replacement_costs.loc[:, [*keys, "scenario", "component"]]
    merged = merged.drop(columns=["scenario_id"], errors="ignore").merge(
        names,
        on=["future_id", "component_instance_id", "component_generation"],
        how="left",
        validate="one_to_one",
    )

    out = pd.DataFrame(
        {
            "future_id": merged.future_id.astype(int),
            "scenario": merged.scenario,
            "component": merged.component,
            "renewal_number": merged.component_generation.astype(int),
            "renewal_time_years": merged.event_time_years.astype(float),
            "preceding_service_life_years": merged.sampled_service_life_years.astype(float),
            "nominal_replacement_cost_eur": merged.nominal_replacement_cost_eur.astype(float),
            "pv_replacement_cost_eur": merged.pv_replacement_cost_eur.astype(float),
        },
        columns=LEGACY_REPLACEMENT_EVENT_COLUMNS,
    )
    # Preserve the canonical ledger's construction order so the public v2.1
    # CSV is byte-order compatible with the pre-migration event stream.
    return out.reset_index(drop=True)
