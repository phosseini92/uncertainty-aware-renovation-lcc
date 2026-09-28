"""Explicit module-applicability, coverage and lifecycle-carbon aggregation gate.

The gate distinguishes assessed results from missing/not-assessed modules and
prevents partial numeric results from being mislabeled as complete Whole-Life
Carbon. Module D is always summarized separately and never netted into A-C.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import pandas as pd
from identity import validate_stable_id, validate_unique_ids

MODULE_APPLICABILITY_COLUMNS = (
    "declaration_id", "scenario_id", "module_id", "applicability_status",
    "rationale", "source_status", "source_reference", "retrieval_date", "notes",
)
MODULE_COVERAGE_COLUMNS = (
    "scenario_id", "module_id", "applicability_status", "consequence_row_count",
    "coverage_status", "reason",
)
LIFECYCLE_AGGREGATION_COLUMNS = (
    "future_id", "scenario_id", "assessed_a_c_gwp_kgco2e", "assessed_a_c_module_count",
    "required_scope_complete", "whole_life_carbon_label_allowed", "reporting_label",
)
D_SUMMARY_COLUMNS = (
    "future_id", "scenario_id", "reported_module", "separate_d_gwp_kgco2e",
    "consequence_row_count", "reporting_label",
)
A_C_MODULES = (
    "A1-A3", "A4", "A5.1", "A5.2", "A5.3",
    "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
    "C1", "C2", "C3", "C4",
)
D_MODULES = ("D1", "D2")
ALL_MODULES = set(A_C_MODULES + D_MODULES)
APPLICABILITY = {"REQUIRED", "NOT_APPLICABLE", "DEFERRED_NOT_ASSESSED", "OPTIONAL_SEPARATE"}
SOURCE_STATUSES = {"ASSESSMENT_SCOPE_DECLARATION", "DOCUMENTED_PROJECT_DATA", "TEST_ONLY_SYNTHETIC"}


def _schema(table, columns, label):
    missing, extra = set(columns) - set(table.columns), set(table.columns) - set(columns)
    if missing or extra:
        raise ValueError(f"{label} schema: missing={sorted(missing)}, extra={sorted(extra)}")
    return table.loc[:, columns].copy()


def validate_module_applicability(table: pd.DataFrame, scenarios: pd.DataFrame) -> pd.DataFrame:
    out = _schema(table, MODULE_APPLICABILITY_COLUMNS, "Module applicability")
    if out.empty:
        return out
    for field in ("declaration_id", "scenario_id"):
        out[field] = [validate_stable_id(v, field) for v in out[field]]
    validate_unique_ids(out.declaration_id, "declaration_id")
    out.module_id = out.module_id.astype(str).str.strip().str.upper()
    out.applicability_status = out.applicability_status.astype(str).str.strip().str.upper()
    if not out.module_id.isin(ALL_MODULES).all():
        raise ValueError("Unsupported module_id in applicability declaration.")
    if not out.applicability_status.isin(APPLICABILITY).all():
        raise ValueError("Unsupported applicability_status.")
    if out.duplicated(["scenario_id", "module_id"]).any():
        raise ValueError("Duplicate scenario/module applicability declaration.")
    for field in ("rationale", "source_status", "source_reference"):
        out[field] = out[field].fillna("").astype(str).str.strip()
        if out[field].eq("").any():
            raise ValueError(f"Module applicability requires {field}.")
    out.source_status = out.source_status.str.upper()
    if not out.source_status.isin(SOURCE_STATUSES).all():
        raise ValueError("Unsupported applicability source_status.")
    for value in out.retrieval_date:
        text = str(value).strip()
        if date.fromisoformat(text).isoformat() != text:
            raise ValueError("retrieval_date must be ISO YYYY-MM-DD.")
    out.retrieval_date = out.retrieval_date.astype(str)
    out.notes = out.notes.fillna("").astype(str)
    if not set(out.scenario_id).issubset(set(scenarios.scenario_id.astype(str))):
        raise ValueError("Applicability declaration references unknown scenario_id.")
    return out


def load_module_applicability(path: Path, scenarios: pd.DataFrame) -> pd.DataFrame:
    return validate_module_applicability(pd.read_csv(path), scenarios)


def build_module_coverage(scenarios: pd.DataFrame, applicability: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    rows = []
    decl = {(r.scenario_id, r.module_id): r for r in applicability.itertuples(index=False)}
    counts = ledger.groupby(["scenario_id", "reported_module"]).size().to_dict() if not ledger.empty else {}
    for sid in scenarios.scenario_id.astype(str):
        for module in A_C_MODULES + D_MODULES:
            d = decl.get((sid, module))
            n = int(counts.get((sid, module), 0))
            if d is None:
                app, status, reason = "UNDECLARED", "MISSING_DATA_UNDECLARED_APPLICABILITY", "No explicit module applicability declaration."
            else:
                app = d.applicability_status
                if app == "REQUIRED":
                    status = "ASSESSED" if n > 0 else "NOT_ASSESSED_MISSING_DATA"
                    reason = "Required module has assessed consequence rows." if n > 0 else "Required module has no assessed consequence rows; missing is not zero."
                elif app == "NOT_APPLICABLE":
                    status = "NOT_APPLICABLE" if n == 0 else "CONFLICT_NOT_APPLICABLE_HAS_RESULTS"
                    reason = "Explicitly documented as not applicable." if n == 0 else "Not-applicable declaration conflicts with assessed results."
                elif app == "DEFERRED_NOT_ASSESSED":
                    status = "NOT_ASSESSED_SCOPE" if n == 0 else "CONFLICT_DEFERRED_HAS_RESULTS"
                    reason = "Explicitly deferred outside the bounded research-release scope." if n == 0 else "Deferred declaration conflicts with assessed results."
                else:
                    status = "ASSESSED" if n > 0 else "NOT_ASSESSED_OPTIONAL"
                    reason = "Separate optional Module-D result is available." if n > 0 else "Optional separate Module-D result not supplied."
            rows.append({"scenario_id": sid, "module_id": module, "applicability_status": app,
                         "consequence_row_count": n, "coverage_status": status, "reason": reason})
    return pd.DataFrame(rows, columns=MODULE_COVERAGE_COLUMNS)


def build_lifecycle_aggregation(scenarios, coverage, ledger, future_ids):
    rows = []
    a_c = ledger.loc[ledger.reported_module.isin(A_C_MODULES)] if not ledger.empty else ledger
    for sid in scenarios.scenario_id.astype(str):
        cov = coverage.loc[(coverage.scenario_id.eq(sid)) & coverage.module_id.isin(A_C_MODULES)]
        required = cov.loc[cov.applicability_status.eq("REQUIRED")]
        required_complete = (not required.empty) and required.coverage_status.eq("ASSESSED").all()
        any_deferred = cov.applicability_status.eq("DEFERRED_NOT_ASSESSED").any()
        conflicts = cov.coverage_status.str.startswith("CONFLICT_").any() or cov.coverage_status.str.startswith("MISSING_DATA_").any()
        whole_life_allowed = bool(required_complete and not any_deferred and not conflicts and cov.coverage_status.isin({"ASSESSED", "NOT_APPLICABLE"}).all())
        sub = a_c.loc[a_c.scenario_id.eq(sid)] if not a_c.empty else a_c
        module_count = int(sub.reported_module.nunique()) if not sub.empty else 0
        for fid in future_ids:
            total = float(sub.loc[sub.future_id.eq(int(fid)), "gwp_kgco2e"].sum()) if not sub.empty else 0.0
            label = "WHOLE_LIFE_CARBON_A_C_COMPLETE_EXPLICIT_COVERAGE" if whole_life_allowed else "PARTIAL_ASSESSED_A_C_CARBON_WITH_EXPLICIT_COVERAGE_NOT_WHOLE_LIFE"
            rows.append({"future_id": int(fid), "scenario_id": sid, "assessed_a_c_gwp_kgco2e": total,
                         "assessed_a_c_module_count": module_count, "required_scope_complete": bool(required_complete),
                         "whole_life_carbon_label_allowed": whole_life_allowed, "reporting_label": label})
    return pd.DataFrame(rows, columns=LIFECYCLE_AGGREGATION_COLUMNS)


def build_separate_d_summary(ledger):
    if ledger.empty:
        return pd.DataFrame(columns=D_SUMMARY_COLUMNS)
    sub = ledger.loc[ledger.reported_module.isin(D_MODULES)]
    if sub.empty:
        return pd.DataFrame(columns=D_SUMMARY_COLUMNS)
    out = sub.groupby(["future_id", "scenario_id", "reported_module"], as_index=False).agg(
        separate_d_gwp_kgco2e=("gwp_kgco2e", "sum"), consequence_row_count=("carbon_consequence_id", "count"))
    out["reporting_label"] = "SEPARATE_BEYOND_BOUNDARY_RESULT_NOT_NETTED_IN_A_C"
    return out.loc[:, D_SUMMARY_COLUMNS]


def assess_lifecycle_aggregation(scenarios, applicability, ledger, future_ids):
    coverage = build_module_coverage(scenarios, applicability, ledger)
    aggregation = build_lifecycle_aggregation(scenarios, coverage, ledger, future_ids)
    d_summary = build_separate_d_summary(ledger)
    allowed = int(aggregation.loc[aggregation.whole_life_carbon_label_allowed, "scenario_id"].nunique()) if not aggregation.empty else 0
    meta = {
        "status": "EXPLICIT_COVERAGE_GATE_ACTIVE" if not applicability.empty else "NO_MODULE_APPLICABILITY_DECLARATIONS",
        "declared_module_rows": len(applicability), "whole_life_label_allowed_scenarios": allowed,
        "whole_life_carbon_generated": bool(allowed > 0), "headline_carbon_generated": bool(allowed > 0),
        "module_d_netted_into_a_c": False, "missing_data_treated_as_zero": False,
        "deferred_use_stage_modules": ["B1", "B2", "B3", "B5", "B7", "B8"],
        "claim": "Numeric A-C results are reported with explicit module coverage; incomplete scope is never labeled Whole-Life Carbon and Module D remains separate.",
    }
    return coverage, aggregation, d_summary, meta
