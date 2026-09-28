"""Environmental-factor registry and BoQ/declared-unit compatibility gate (v3 M1.8).

This module deliberately stops before carbon consequence calculation. It
validates environmental-factor provenance, indicator/module semantics, explicit
BoQ-to-factor assignments, and physical-unit compatibility. No kgCO2e result is
calculated here.

Research-integrity rules:
- no factor is inferred from product names, costs, or nearest matches;
- one executable BoQ line requires an explicit factor assignment;
- proxy mappings must be declared and evidenced;
- GWP_TOTAL is never reconstructed by summing disaggregated GWP indicators;
- physical-unit conversion is explicit and limited to exact units, kg<->tonne,
  or a documented total-mass bridge already carried by the BoQ row;
- missing data remain missing rather than becoming zero.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from identity import validate_stable_id, validate_unique_ids
from physical_quantities import normalize_physical_unit

ENVIRONMENTAL_FACTOR_COLUMNS = (
    "factor_record_id",
    "factor_set_id",
    "dataset_id",
    "product_or_process_id",
    "indicator_id",
    "indicator_value",
    "indicator_unit",
    "declared_unit",
    "module_scope",
    "geography",
    "reference_year",
    "source_type",
    "source_citation",
    "verification_status",
    "data_quality_status",
    "license_status",
    "redistribution_allowed",
    "uncertainty_mode",
    "uncertainty_semantics",
    "uncertainty_parameter_1",
    "uncertainty_parameter_2",
    "uncertainty_parameter_3",
    "uncertainty_basis",
    "notes",
)

BOQ_FACTOR_ASSIGNMENT_COLUMNS = (
    "assignment_id",
    "boq_line_id",
    "factor_set_id",
    "mapping_basis",
    "mapping_reference",
    "notes",
)

FACTOR_SET_SUMMARY_COLUMNS = (
    "factor_set_id",
    "dataset_id",
    "product_or_process_id",
    "declared_unit",
    "source_type",
    "geography",
    "reference_year",
    "indicator_ids",
    "module_scopes",
    "gwp_total_available",
    "gwp_disaggregated_count",
    "product_stage_gwp_total_available",
    "redistribution_allowed",
    "license_status",
    "record_count",
    "registry_status",
)

BOQ_FACTOR_COMPATIBILITY_COLUMNS = (
    "assignment_id",
    "boq_line_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "material_or_product_id",
    "factor_set_id",
    "factor_product_or_process_id",
    "mapping_basis",
    "boq_quantity",
    "boq_unit",
    "boq_mass_kg",
    "factor_declared_unit",
    "unit_compatibility_status",
    "conversion_method",
    "resolved_activity_quantity",
    "resolved_activity_unit",
    "gwp_total_available",
    "product_stage_gwp_total_available",
    "module_scopes",
    "compatibility_gate_status",
    "reason",
)

BOQ_FACTOR_COVERAGE_COLUMNS = (
    "boq_line_id",
    "scenario_id",
    "component_instance_id",
    "comparison_lineage_id",
    "material_or_product_id",
    "boq_quantity",
    "boq_unit",
    "boq_mass_kg",
    "assignment_status",
    "assignment_id",
    "factor_set_id",
    "mapping_basis",
    "factor_declared_unit",
    "unit_compatibility_status",
    "gwp_total_available",
    "product_stage_gwp_total_available",
    "compatibility_gate_status",
    "reason",
)

SUPPORTED_GWP_INDICATORS = {
    "GWP_TOTAL",
    "GWP_FOSSIL",
    "GWP_BIOGENIC",
    "GWP_LULUC",
}

ALLOWED_SOURCE_TYPES = {"EPD", "GENERIC_DATABASE", "LITERATURE", "TEST_ONLY_SYNTHETIC"}
ALLOWED_VERIFICATION_STATUS = {
    "THIRD_PARTY_VERIFIED",
    "DATABASE_VALIDATED",
    "PEER_REVIEWED_SOURCE",
    "UNVERIFIED",
    "TEST_ONLY",
}
ALLOWED_DATA_QUALITY_STATUS = {
    "DOCUMENTED_PRIMARY",
    "DOCUMENTED_SECONDARY",
    "PARTIAL_METADATA",
    "TEST_ONLY",
}
ALLOWED_LICENSE_STATUS = {
    "OPEN_REDISTRIBUTABLE",
    "OPEN_WITH_ATTRIBUTION",
    "RESTRICTED_NO_REDISTRIBUTION",
    "UNKNOWN",
    "TEST_ONLY",
}
ALLOWED_UNCERTAINTY_MODES = {
    "DETERMINISTIC",
    "TRIANGULAR",
    "NORMAL",
    "LOGNORMAL",
    "BOUNDED_NORMAL",
    "SCENARIO",
}
ALLOWED_UNCERTAINTY_SEMANTICS = {
    "NOT_APPLICABLE",
    "ALEATORY",
    "EPISTEMIC",
    "SCENARIO_NONPROBABILISTIC",
}
ALLOWED_MAPPING_BASIS = {"EXACT_PRODUCT_ID", "DOCUMENTED_PROXY", "TEST_ONLY_SYNTHETIC"}

# Environmental process factors need a somewhat wider declared-unit vocabulary
# than component BoQ rows. Product/material factor matching in M1.8 remains
# limited to units that can be reconciled explicitly with a BoQ line.
_DECLARED_UNIT_ALIASES = {
    "m²": "m2", "m^2": "m2", "sqm": "m2",
    "m³": "m3", "m^3": "m3", "cum": "m3",
    "tonne": "t", "tonnes": "t", "metric_ton": "t",
    "piece": "unit", "pieces": "unit", "pcs": "unit", "each": "unit",
    "kwp": "kwp", "kWp": "kwp",
    "kwh": "kwh", "kWh": "kwh",
    "mj": "mj", "MJ": "mj",
    "tkm": "tkm", "t-km": "tkm", "tonne-km": "tkm", "tonne_km": "tkm",
}
_ALLOWED_DECLARED_UNITS = {"kg", "t", "m", "m2", "m3", "unit", "kwp", "kwh", "mj", "tkm"}

_INDICATOR_UNIT_ALIASES = {
    "kgco2e": "kgco2e",
    "kg co2e": "kgco2e",
    "kg co2 eq": "kgco2e",
    "kg co2 eq.": "kgco2e",
    "kg co2-eq": "kgco2e",
    "kg co2-eq.": "kgco2e",
    "kgco2eq": "kgco2e",
    "kg co2 equivalent": "kgco2e",
}

ATOMIC_MODULES = {
    "A0", "A1", "A2", "A3", "A4", "A5.1", "A5.2", "A5.3",
    "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
    "C1", "C2", "C3", "C4", "D1", "D2",
}
_COMBINED_MODULE_EXPANSIONS = {
    "A1-A3": {"A1", "A2", "A3"},
    "A5": {"A5.1", "A5.2", "A5.3"},
    "A4-A5": {"A4", "A5.1", "A5.2", "A5.3"},
    "C3-C4": {"C3", "C4"},
    "C1-C4": {"C1", "C2", "C3", "C4"},
}
ALLOWED_MODULE_SCOPES = ATOMIC_MODULES | set(_COMBINED_MODULE_EXPANSIONS)


def empty_environmental_factors() -> pd.DataFrame:
    return pd.DataFrame(columns=ENVIRONMENTAL_FACTOR_COLUMNS)


def empty_boq_factor_assignments() -> pd.DataFrame:
    return pd.DataFrame(columns=BOQ_FACTOR_ASSIGNMENT_COLUMNS)


def normalize_declared_unit(value: object) -> str:
    if pd.isna(value):
        raise ValueError("Environmental factor declared_unit is required.")
    raw = str(value).strip()
    if not raw:
        raise ValueError("Environmental factor declared_unit is required.")
    normalized = _DECLARED_UNIT_ALIASES.get(raw, _DECLARED_UNIT_ALIASES.get(raw.lower(), raw.lower()))
    if normalized not in _ALLOWED_DECLARED_UNITS:
        raise ValueError(
            f"Unsupported environmental declared_unit: {raw!r}. "
            f"Supported units are {sorted(_ALLOWED_DECLARED_UNITS)}; no implicit conversion is performed."
        )
    return normalized


def normalize_indicator_unit(indicator_id: str, value: object) -> str:
    if pd.isna(value):
        raise ValueError("Environmental factor indicator_unit is required.")
    raw = str(value).strip()
    normalized = _INDICATOR_UNIT_ALIASES.get(raw, _INDICATOR_UNIT_ALIASES.get(raw.lower()))
    if indicator_id in SUPPORTED_GWP_INDICATORS:
        if normalized != "kgco2e":
            raise ValueError(
                f"GWP indicator {indicator_id} must use kgCO2e-compatible units; received {raw!r}."
            )
        return "kgco2e"
    raise ValueError(f"Unsupported environmental indicator_id: {indicator_id!r}")


def normalize_module_scope(value: object) -> str:
    if pd.isna(value):
        raise ValueError("Environmental factor module_scope is required.")
    scope = str(value).strip().upper().replace(" ", "")
    if scope not in ALLOWED_MODULE_SCOPES:
        raise ValueError(
            f"Unsupported module_scope: {value!r}. Allowed scopes are {sorted(ALLOWED_MODULE_SCOPES)}."
        )
    return scope


def _scope_atoms(scope: str) -> set[str]:
    return set(_COMBINED_MODULE_EXPANSIONS.get(scope, {scope}))


def _parse_bool(value: object, field: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        raise ValueError(f"{field} is required.")
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"{field} must be boolean-like true/false; received {value!r}.")


def _require_nonempty(table: pd.DataFrame, fields: Iterable[str]) -> None:
    for field in fields:
        values = table[field]
        if values.isna().any() or values.astype(str).str.strip().eq("").any():
            raise ValueError(f"Every environmental factor record requires nonempty {field}.")
        table[field] = values.astype(str).str.strip()


def _validate_uncertainty_row(row) -> None:
    mode = row.uncertainty_mode
    semantics = row.uncertainty_semantics
    params = [row.uncertainty_parameter_1, row.uncertainty_parameter_2, row.uncertainty_parameter_3]
    present = [not pd.isna(v) and str(v).strip() != "" for v in params]
    if mode == "DETERMINISTIC":
        if semantics != "NOT_APPLICABLE":
            raise ValueError("DETERMINISTIC factor records require uncertainty_semantics=NOT_APPLICABLE.")
        if any(present):
            raise ValueError("DETERMINISTIC factor records must not carry uncertainty parameters.")
        return
    if semantics == "NOT_APPLICABLE":
        raise ValueError(f"{mode} factor records require a nontrivial uncertainty_semantics value.")
    if mode == "TRIANGULAR" and sum(present) != 3:
        raise ValueError("TRIANGULAR factor uncertainty requires three parameters.")
    if mode in {"NORMAL", "LOGNORMAL", "BOUNDED_NORMAL"} and sum(present) < 2:
        raise ValueError(f"{mode} factor uncertainty requires at least two parameters.")
    if mode == "SCENARIO" and semantics != "SCENARIO_NONPROBABILISTIC":
        raise ValueError("SCENARIO factor uncertainty must use SCENARIO_NONPROBABILISTIC semantics.")
    if mode != "SCENARIO" and semantics == "SCENARIO_NONPROBABILISTIC":
        raise ValueError("SCENARIO_NONPROBABILISTIC semantics require uncertainty_mode=SCENARIO.")
    if str(row.uncertainty_basis).strip() == "" or pd.isna(row.uncertainty_basis):
        raise ValueError("Non-deterministic factor uncertainty requires uncertainty_basis.")


def load_environmental_factors(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return validate_environmental_factors(pd.read_csv(path))


def validate_environmental_factors(table: pd.DataFrame) -> pd.DataFrame:
    """Validate registry rows; shared by product and separate transport registries."""
    missing = set(ENVIRONMENTAL_FACTOR_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(f"Missing environmental factor columns: {sorted(missing)}")
    extra = set(table.columns) - set(ENVIRONMENTAL_FACTOR_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected environmental factor columns: {sorted(extra)}")
    table = table.loc[:, ENVIRONMENTAL_FACTOR_COLUMNS].copy()
    if table.empty:
        return table

    for field in ("factor_record_id", "factor_set_id", "product_or_process_id"):
        table[field] = [validate_stable_id(v, field) for v in table[field]]
    validate_unique_ids(table.factor_record_id, "factor_record_id")

    _require_nonempty(table, ("dataset_id", "geography", "source_citation"))

    table["indicator_id"] = table.indicator_id.astype(str).str.strip().str.upper()
    if not table.indicator_id.isin(SUPPORTED_GWP_INDICATORS).all():
        bad = sorted(set(table.loc[~table.indicator_id.isin(SUPPORTED_GWP_INDICATORS), "indicator_id"]))
        raise ValueError(f"Unsupported environmental indicator_id values: {bad}")
    table["indicator_value"] = pd.to_numeric(table.indicator_value, errors="raise")
    if not np.isfinite(table.indicator_value).all():
        raise ValueError("Environmental factor indicator_value must be finite; negative values remain allowed where sourced.")
    table["indicator_unit"] = [normalize_indicator_unit(i, u) for i, u in zip(table.indicator_id, table.indicator_unit)]
    table["declared_unit"] = [normalize_declared_unit(v) for v in table.declared_unit]
    table["module_scope"] = [normalize_module_scope(v) for v in table.module_scope]

    table["reference_year"] = pd.to_numeric(table.reference_year, errors="raise")
    if ((table.reference_year % 1) != 0).any() or not table.reference_year.between(1900, 2200).all():
        raise ValueError("reference_year must be an integer between 1900 and 2200.")
    table["reference_year"] = table.reference_year.astype(int)

    for field, allowed in (
        ("source_type", ALLOWED_SOURCE_TYPES),
        ("verification_status", ALLOWED_VERIFICATION_STATUS),
        ("data_quality_status", ALLOWED_DATA_QUALITY_STATUS),
        ("license_status", ALLOWED_LICENSE_STATUS),
        ("uncertainty_mode", ALLOWED_UNCERTAINTY_MODES),
        ("uncertainty_semantics", ALLOWED_UNCERTAINTY_SEMANTICS),
    ):
        table[field] = table[field].astype(str).str.strip().str.upper()
        if not table[field].isin(allowed).all():
            bad = sorted(set(table.loc[~table[field].isin(allowed), field]))
            raise ValueError(f"Invalid {field}: {bad}; allowed values are {sorted(allowed)}")

    table["redistribution_allowed"] = [
        _parse_bool(v, "redistribution_allowed") for v in table.redistribution_allowed
    ]
    inconsistent_license = table.redistribution_allowed & table.license_status.isin(
        ["RESTRICTED_NO_REDISTRIBUTION", "UNKNOWN"]
    )
    if inconsistent_license.any():
        raise ValueError("redistribution_allowed=true conflicts with restricted/unknown license_status.")

    test_rows = table.source_type.eq("TEST_ONLY_SYNTHETIC")
    if test_rows.any():
        required_test = (
            table.loc[test_rows, "verification_status"].eq("TEST_ONLY")
            & table.loc[test_rows, "data_quality_status"].eq("TEST_ONLY")
            & table.loc[test_rows, "license_status"].eq("TEST_ONLY")
        )
        if not required_test.all():
            raise ValueError(
                "TEST_ONLY_SYNTHETIC factor records must use TEST_ONLY verification, data-quality and license status."
            )

    # Uncertainty parameter columns are kept numeric when present but are not
    # interpreted as probability unless the semantics explicitly permit it.
    for field in ("uncertainty_parameter_1", "uncertainty_parameter_2", "uncertainty_parameter_3"):
        table[field] = pd.to_numeric(table[field], errors="coerce")
    table["uncertainty_basis"] = table.uncertainty_basis.fillna("").astype(str).str.strip()
    table["notes"] = table.notes.fillna("").astype(str)
    for row in table.itertuples(index=False):
        _validate_uncertainty_row(row)

    # One factor_set is one declared dataset/product/process basis. Module and
    # indicator rows may vary, but identity/provenance and declared unit may not.
    consistency_fields = (
        "dataset_id", "product_or_process_id", "declared_unit", "geography",
        "reference_year", "source_type", "source_citation", "verification_status",
        "data_quality_status", "license_status", "redistribution_allowed",
    )
    for factor_set_id, group in table.groupby("factor_set_id", sort=False):
        for field in consistency_fields:
            if group[field].nunique(dropna=False) != 1:
                raise ValueError(
                    f"factor_set_id {factor_set_id!r} is internally inconsistent for {field}; "
                    "split distinct datasets/bases into separate factor sets."
                )
        # Do not accept overlapping source module records for the same indicator.
        # Example: GWP_TOTAL A1-A3 plus separate GWP_TOTAL A1 is ambiguous/double-count prone.
        for indicator_id, indicator_group in group.groupby("indicator_id", sort=False):
            occupied: set[str] = set()
            for scope in indicator_group.module_scope:
                atoms = _scope_atoms(scope)
                overlap = occupied & atoms
                if overlap:
                    raise ValueError(
                        f"factor_set_id {factor_set_id!r}, indicator {indicator_id!r} has overlapping "
                        f"module scopes at {sorted(overlap)}; combined and disaggregated source modules "
                        "must not coexist without separate factor sets."
                    )
                occupied |= atoms

    # Exact duplicate semantic records are never useful even with different record IDs.
    semantic_keys = ["factor_set_id", "indicator_id", "module_scope"]
    if table.duplicated(semantic_keys).any():
        raise ValueError(f"Duplicate environmental factor semantics detected for {semantic_keys}.")

    return table


def _product_stage_gwp_total_available(group: pd.DataFrame) -> bool:
    total_scopes = set(group.loc[group.indicator_id.eq("GWP_TOTAL"), "module_scope"])
    if "A1-A3" in total_scopes:
        return True
    return {"A1", "A2", "A3"}.issubset(total_scopes)


def build_factor_set_summary(factors: pd.DataFrame) -> pd.DataFrame:
    if factors.empty:
        return pd.DataFrame(columns=FACTOR_SET_SUMMARY_COLUMNS)
    rows = []
    for factor_set_id, group in factors.groupby("factor_set_id", sort=True):
        indicators = sorted(set(group.indicator_id))
        scopes = sorted(set(group.module_scope))
        gwp_total_available = "GWP_TOTAL" in indicators
        disaggregated = len(set(indicators) & {"GWP_FOSSIL", "GWP_BIOGENIC", "GWP_LULUC"})
        product_stage = _product_stage_gwp_total_available(group)
        if not gwp_total_available:
            status = "GWP_TOTAL_MISSING"
        elif not product_stage:
            status = "PRODUCT_STAGE_GWP_TOTAL_MISSING"
        else:
            status = "READY_FOR_BOQ_MAPPING"
        first = group.iloc[0]
        rows.append({
            "factor_set_id": factor_set_id,
            "dataset_id": first.dataset_id,
            "product_or_process_id": first.product_or_process_id,
            "declared_unit": first.declared_unit,
            "source_type": first.source_type,
            "geography": first.geography,
            "reference_year": int(first.reference_year),
            "indicator_ids": "|".join(indicators),
            "module_scopes": "|".join(scopes),
            "gwp_total_available": bool(gwp_total_available),
            "gwp_disaggregated_count": int(disaggregated),
            "product_stage_gwp_total_available": bool(product_stage),
            "redistribution_allowed": bool(first.redistribution_allowed),
            "license_status": first.license_status,
            "record_count": int(len(group)),
            "registry_status": status,
        })
    return pd.DataFrame(rows, columns=FACTOR_SET_SUMMARY_COLUMNS)


def load_boq_factor_assignments(
    path: Path,
    component_boq: pd.DataFrame,
    factors: pd.DataFrame,
) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    table = pd.read_csv(path)
    missing = set(BOQ_FACTOR_ASSIGNMENT_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(f"Missing BoQ factor-assignment columns: {sorted(missing)}")
    extra = set(table.columns) - set(BOQ_FACTOR_ASSIGNMENT_COLUMNS)
    if extra:
        raise ValueError(f"Unexpected BoQ factor-assignment columns: {sorted(extra)}")
    table = table.loc[:, BOQ_FACTOR_ASSIGNMENT_COLUMNS].copy()
    if table.empty:
        return table

    for field in ("assignment_id", "boq_line_id", "factor_set_id"):
        table[field] = [validate_stable_id(v, field) for v in table[field]]
    validate_unique_ids(table.assignment_id, "assignment_id")
    if table.boq_line_id.duplicated().any():
        raise ValueError("Each executable BoQ line may have at most one product/material factor_set assignment in M1.8.")

    table["mapping_basis"] = table.mapping_basis.astype(str).str.strip().str.upper()
    if not table.mapping_basis.isin(ALLOWED_MAPPING_BASIS).all():
        bad = sorted(set(table.loc[~table.mapping_basis.isin(ALLOWED_MAPPING_BASIS), "mapping_basis"]))
        raise ValueError(f"Invalid mapping_basis: {bad}; allowed values are {sorted(ALLOWED_MAPPING_BASIS)}")
    table["mapping_reference"] = table.mapping_reference.fillna("").astype(str).str.strip()
    table["notes"] = table.notes.fillna("").astype(str)

    boq_lookup = component_boq.set_index("boq_line_id", drop=False) if not component_boq.empty else None
    factor_summary = build_factor_set_summary(factors)
    factor_lookup = factor_summary.set_index("factor_set_id", drop=False) if not factor_summary.empty else None

    unknown_boq = sorted(set(table.boq_line_id) - set(component_boq.boq_line_id))
    if unknown_boq:
        raise ValueError(f"Factor assignments reference unknown boq_line_id values: {unknown_boq}")
    unknown_sets = sorted(set(table.factor_set_id) - set(factors.factor_set_id))
    if unknown_sets:
        raise ValueError(f"Factor assignments reference unknown factor_set_id values: {unknown_sets}")

    for row in table.itertuples(index=False):
        boq_row = boq_lookup.loc[row.boq_line_id]
        if boq_row.assessment_role != "ASSESSMENT_INVENTORY":
            raise ValueError(
                f"boq_line_id {row.boq_line_id!r} is {boq_row.assessment_role}; only ASSESSMENT_INVENTORY lines "
                "may receive executable environmental factor assignments."
            )
        factor_row = factor_lookup.loc[row.factor_set_id]
        if row.mapping_basis == "EXACT_PRODUCT_ID":
            if str(boq_row.material_or_product_id) != str(factor_row.product_or_process_id):
                raise ValueError(
                    f"EXACT_PRODUCT_ID assignment {row.assignment_id!r} conflicts: BoQ product "
                    f"{boq_row.material_or_product_id!r} != factor product {factor_row.product_or_process_id!r}."
                )
        elif row.mapping_basis == "DOCUMENTED_PROXY":
            if not row.mapping_reference:
                raise ValueError("DOCUMENTED_PROXY assignments require a nonempty mapping_reference.")
        elif row.mapping_basis == "TEST_ONLY_SYNTHETIC":
            factor_group = factors.loc[factors.factor_set_id.eq(row.factor_set_id)]
            if not factor_group.source_type.eq("TEST_ONLY_SYNTHETIC").all():
                raise ValueError("TEST_ONLY_SYNTHETIC assignment basis may only target TEST_ONLY_SYNTHETIC factors.")
            if not row.mapping_reference:
                raise ValueError("TEST_ONLY_SYNTHETIC assignments require a mapping_reference identifying the fixture.")

    return table


def resolve_boq_declared_unit_compatibility(boq_row: pd.Series, factor_declared_unit: str) -> dict:
    """Resolve activity quantity for a factor without calculating impact."""
    boq_unit = normalize_physical_unit(boq_row.quantity_unit)
    factor_unit = normalize_declared_unit(factor_declared_unit)
    quantity = float(boq_row.quantity)
    mass_kg = None if pd.isna(boq_row.mass_kg) else float(boq_row.mass_kg)

    # If a mass-based BoQ line also carries the optional total-mass field, the
    # two representations must reconcile rather than silently disagree.
    if mass_kg is not None and boq_unit == "kg" and not np.isclose(mass_kg, quantity, rtol=1e-9, atol=1e-9):
        raise ValueError("BoQ quantity in kg conflicts with documented mass_kg for the same line.")
    if mass_kg is not None and boq_unit == "t" and not np.isclose(mass_kg, quantity * 1000.0, rtol=1e-9, atol=1e-9):
        raise ValueError("BoQ quantity in tonnes conflicts with documented mass_kg for the same line.")

    if boq_unit == factor_unit:
        return {
            "unit_compatibility_status": "COMPATIBLE_EXACT_UNIT",
            "conversion_method": "EXACT_UNIT",
            "resolved_activity_quantity": quantity,
            "resolved_activity_unit": factor_unit,
        }
    if boq_unit == "kg" and factor_unit == "t":
        return {
            "unit_compatibility_status": "COMPATIBLE_EXPLICIT_MASS_CONVERSION",
            "conversion_method": "KG_TO_TONNE",
            "resolved_activity_quantity": quantity / 1000.0,
            "resolved_activity_unit": "t",
        }
    if boq_unit == "t" and factor_unit == "kg":
        return {
            "unit_compatibility_status": "COMPATIBLE_EXPLICIT_MASS_CONVERSION",
            "conversion_method": "TONNE_TO_KG",
            "resolved_activity_quantity": quantity * 1000.0,
            "resolved_activity_unit": "kg",
        }
    # mass_kg in M1.7 is total documented mass for this BoQ line, not a density
    # or mass-per-unit inference. It can therefore provide an explicit bridge
    # to mass-declared environmental datasets.
    if mass_kg is not None and factor_unit == "kg":
        return {
            "unit_compatibility_status": "COMPATIBLE_DOCUMENTED_MASS_BRIDGE",
            "conversion_method": "TOTAL_MASS_KG",
            "resolved_activity_quantity": mass_kg,
            "resolved_activity_unit": "kg",
        }
    if mass_kg is not None and factor_unit == "t":
        return {
            "unit_compatibility_status": "COMPATIBLE_DOCUMENTED_MASS_BRIDGE",
            "conversion_method": "TOTAL_MASS_KG_TO_TONNE",
            "resolved_activity_quantity": mass_kg / 1000.0,
            "resolved_activity_unit": "t",
        }
    return {
        "unit_compatibility_status": "INCOMPATIBLE_UNIT",
        "conversion_method": "NONE",
        "resolved_activity_quantity": np.nan,
        "resolved_activity_unit": factor_unit,
    }


def build_boq_factor_compatibility(
    component_boq: pd.DataFrame,
    assignments: pd.DataFrame,
    factors: pd.DataFrame,
) -> pd.DataFrame:
    if assignments.empty:
        return pd.DataFrame(columns=BOQ_FACTOR_COMPATIBILITY_COLUMNS)

    summary = build_factor_set_summary(factors).set_index("factor_set_id", drop=False)
    boq_lookup = component_boq.set_index("boq_line_id", drop=False)
    rows = []
    for assignment in assignments.itertuples(index=False):
        boq_row = boq_lookup.loc[assignment.boq_line_id]
        fs = summary.loc[assignment.factor_set_id]
        unit = resolve_boq_declared_unit_compatibility(boq_row, fs.declared_unit)

        if unit["unit_compatibility_status"] == "INCOMPATIBLE_UNIT":
            gate = "BLOCKED_UNIT_INCOMPATIBLE"
            reason = (
                f"BoQ unit {normalize_physical_unit(boq_row.quantity_unit)} cannot be reconciled explicitly with "
                f"factor declared unit {fs.declared_unit}; no implicit density/geometry conversion is allowed."
            )
        elif not bool(fs.gwp_total_available):
            gate = "BLOCKED_GWP_TOTAL_MISSING"
            reason = "Assigned factor set has no GWP_TOTAL record; disaggregated GWP indicators are not summed implicitly."
        elif not bool(fs.product_stage_gwp_total_available):
            gate = "BLOCKED_PRODUCT_STAGE_SCOPE_MISSING"
            reason = "Assigned factor set lacks GWP_TOTAL coverage for A1-A3 (combined or complete A1/A2/A3 records)."
        elif assignment.mapping_basis == "DOCUMENTED_PROXY":
            gate = "PASS_DOCUMENTED_PROXY"
            reason = "Unit and product-stage GWP_TOTAL gates pass; factor mapping is an explicitly documented proxy."
        elif assignment.mapping_basis == "TEST_ONLY_SYNTHETIC":
            gate = "PASS_TEST_ONLY_SYNTHETIC"
            reason = "Synthetic test fixture passes structural/unit gates and is not empirical project evidence."
        else:
            gate = "PASS_EXACT_PRODUCT_MAPPING"
            reason = "Exact product identity, unit compatibility and product-stage GWP_TOTAL gates pass."

        rows.append({
            "assignment_id": assignment.assignment_id,
            "boq_line_id": assignment.boq_line_id,
            "scenario_id": boq_row.scenario_id,
            "component_instance_id": boq_row.component_instance_id,
            "comparison_lineage_id": boq_row.comparison_lineage_id,
            "material_or_product_id": boq_row.material_or_product_id,
            "factor_set_id": assignment.factor_set_id,
            "factor_product_or_process_id": fs.product_or_process_id,
            "mapping_basis": assignment.mapping_basis,
            "boq_quantity": float(boq_row.quantity),
            "boq_unit": normalize_physical_unit(boq_row.quantity_unit),
            "boq_mass_kg": np.nan if pd.isna(boq_row.mass_kg) else float(boq_row.mass_kg),
            "factor_declared_unit": fs.declared_unit,
            **unit,
            "gwp_total_available": bool(fs.gwp_total_available),
            "product_stage_gwp_total_available": bool(fs.product_stage_gwp_total_available),
            "module_scopes": fs.module_scopes,
            "compatibility_gate_status": gate,
            "reason": reason,
        })
    return pd.DataFrame(rows, columns=BOQ_FACTOR_COMPATIBILITY_COLUMNS)


def build_boq_factor_coverage(
    component_boq: pd.DataFrame,
    assignments: pd.DataFrame,
    compatibility: pd.DataFrame,
) -> pd.DataFrame:
    assessment = component_boq.loc[component_boq.assessment_role.eq("ASSESSMENT_INVENTORY")].copy()
    if assessment.empty:
        return pd.DataFrame(columns=BOQ_FACTOR_COVERAGE_COLUMNS)
    assignment_lookup = assignments.set_index("boq_line_id", drop=False) if not assignments.empty else None
    compat_lookup = compatibility.set_index("boq_line_id", drop=False) if not compatibility.empty else None
    rows = []
    for boq in assessment.itertuples(index=False):
        if assignment_lookup is None or boq.boq_line_id not in assignment_lookup.index:
            rows.append({
                "boq_line_id": boq.boq_line_id,
                "scenario_id": boq.scenario_id,
                "component_instance_id": boq.component_instance_id,
                "comparison_lineage_id": boq.comparison_lineage_id,
                "material_or_product_id": boq.material_or_product_id,
                "boq_quantity": float(boq.quantity),
                "boq_unit": normalize_physical_unit(boq.quantity_unit),
                "boq_mass_kg": np.nan if pd.isna(boq.mass_kg) else float(boq.mass_kg),
                "assignment_status": "ASSIGNMENT_MISSING",
                "assignment_id": pd.NA,
                "factor_set_id": pd.NA,
                "mapping_basis": pd.NA,
                "factor_declared_unit": pd.NA,
                "unit_compatibility_status": "NOT_EVALUATED",
                "gwp_total_available": False,
                "product_stage_gwp_total_available": False,
                "compatibility_gate_status": "BLOCKED_ASSIGNMENT_MISSING",
                "reason": "No explicit BoQ-to-factor assignment is present; factors are never inferred from names or IDs.",
            })
            continue
        assignment = assignment_lookup.loc[boq.boq_line_id]
        compat = compat_lookup.loc[boq.boq_line_id]
        rows.append({
            "boq_line_id": boq.boq_line_id,
            "scenario_id": boq.scenario_id,
            "component_instance_id": boq.component_instance_id,
            "comparison_lineage_id": boq.comparison_lineage_id,
            "material_or_product_id": boq.material_or_product_id,
            "boq_quantity": float(boq.quantity),
            "boq_unit": normalize_physical_unit(boq.quantity_unit),
            "boq_mass_kg": np.nan if pd.isna(boq.mass_kg) else float(boq.mass_kg),
            "assignment_status": "ASSIGNED_EXPLICITLY",
            "assignment_id": assignment.assignment_id,
            "factor_set_id": assignment.factor_set_id,
            "mapping_basis": assignment.mapping_basis,
            "factor_declared_unit": compat.factor_declared_unit,
            "unit_compatibility_status": compat.unit_compatibility_status,
            "gwp_total_available": bool(compat.gwp_total_available),
            "product_stage_gwp_total_available": bool(compat.product_stage_gwp_total_available),
            "compatibility_gate_status": compat.compatibility_gate_status,
            "reason": compat.reason,
        })
    return pd.DataFrame(rows, columns=BOQ_FACTOR_COVERAGE_COLUMNS)


def environmental_registry_status(
    factors: pd.DataFrame,
    factor_summary: pd.DataFrame,
    component_boq: pd.DataFrame,
    assignments: pd.DataFrame,
    coverage: pd.DataFrame,
) -> dict:
    assessment_lines = int(component_boq.assessment_role.eq("ASSESSMENT_INVENTORY").sum()) if not component_boq.empty else 0
    assigned = int(len(assignments))
    passing = int(coverage.compatibility_gate_status.astype(str).str.startswith("PASS_").sum()) if not coverage.empty else 0
    blocked = int(len(coverage) - passing) if not coverage.empty else 0
    unassigned = int(coverage.assignment_status.eq("ASSIGNMENT_MISSING").sum()) if not coverage.empty else 0

    if assessment_lines == 0:
        status = "NO_ASSESSMENT_BOQ_LINES"
    elif unassigned > 0:
        status = "BLOCKED_FACTOR_ASSIGNMENTS_MISSING"
    elif blocked > 0:
        status = "BLOCKED_FACTOR_COMPATIBILITY"
    elif passing == assessment_lines:
        status = "READY_FOR_CARBON_ENGINE_INPUT"
    else:
        status = "BLOCKED_INCOMPLETE_FACTOR_GATE"

    return {
        "status": status,
        "factor_records": int(len(factors)),
        "factor_sets": int(len(factor_summary)),
        "assessment_boq_lines": assessment_lines,
        "explicit_factor_assignments": assigned,
        "gate_pass_lines": passing,
        "gate_blocked_lines": blocked,
        "unassigned_boq_lines": unassigned,
        "headline_carbon_generated": False,
        "gwp_total_reconstruction_from_disaggregated_indicators": False,
        "implicit_unit_conversion_allowed": False,
        "cost_to_quantity_inference_allowed": False,
    }
