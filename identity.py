"""Stable identity helpers for the staged v2.1 -> v3 migration.

M1.3 introduces explicit scenario/component IDs and comparison lineage while
preserving compatibility with legacy input files that contain only display
labels.  Explicit IDs are authoritative.  Legacy fallbacks are deterministic
but are intentionally prefixed ``legacy_`` because a display-label edit can
change them; they are not a substitute for migrated stable IDs.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

import pandas as pd

_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_stable_id(value: object, field: str) -> str:
    """Validate and return one explicit stable identifier."""
    if pd.isna(value):
        raise ValueError(f"Missing stable ID: {field}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Empty stable ID: {field}")
    if not _ID_RE.fullmatch(text):
        raise ValueError(
            f"Invalid stable ID in {field}: {text!r}. Use lowercase ASCII letters, digits and underscores; "
            "the first character must be a letter."
        )
    return text


def validate_unique_ids(values: Iterable[object], field: str) -> None:
    ids = [validate_stable_id(value, field) for value in values]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Stable IDs must be unique: {field}")


def _legacy_hash(prefix: str, *parts: object, length: int = 12) -> str:
    key = "|".join(str(part).strip() for part in parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:length]
    return f"legacy_{prefix}_{digest}"


def legacy_scenario_id(scenario_name: object) -> str:
    return _legacy_hash("scn", scenario_name)


def legacy_component_instance_id(scenario_id: object, component_name: object) -> str:
    return _legacy_hash("ci", scenario_id, component_name)


def legacy_component_type_id(uncertainty_key: object, component_name: object) -> str:
    return _legacy_hash("ctype", uncertainty_key, component_name)


def legacy_comparison_lineage_id(uncertainty_key: object) -> str:
    return _legacy_hash("lineage", uncertainty_key)
