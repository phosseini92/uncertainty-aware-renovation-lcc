import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import renovation_lcc as m
from environmental_factors import (
    ENVIRONMENTAL_FACTOR_COLUMNS,
    BOQ_FACTOR_ASSIGNMENT_COLUMNS,
    build_boq_factor_compatibility,
    build_boq_factor_coverage,
    build_factor_set_summary,
    environmental_registry_status,
    load_boq_factor_assignments,
    load_environmental_factors,
    normalize_declared_unit,
    normalize_indicator_unit,
    resolve_boq_declared_unit_compatibility,
)
from physical_quantities import COMPONENT_BOQ_COLUMNS


class EnvironmentalFactorRegistryTests(unittest.TestCase):
    def _write(self, rows, columns, tmp, name):
        path = Path(tmp) / name
        pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
        return path

    def _factor(self, **updates):
        row = {
            "factor_record_id": "fr_test_window_total_a1a3",
            "factor_set_id": "fs_test_window",
            "dataset_id": "dataset_test_window_2026",
            "product_or_process_id": "prod_test_window",
            "indicator_id": "GWP_TOTAL",
            "indicator_value": 12.5,
            "indicator_unit": "kg CO2 eq.",
            "declared_unit": "m2",
            "module_scope": "A1-A3",
            "geography": "TEST",
            "reference_year": 2026,
            "source_type": "TEST_ONLY_SYNTHETIC",
            "source_citation": "Synthetic unit-test factor; not empirical project evidence.",
            "verification_status": "TEST_ONLY",
            "data_quality_status": "TEST_ONLY",
            "license_status": "TEST_ONLY",
            "redistribution_allowed": False,
            "uncertainty_mode": "DETERMINISTIC",
            "uncertainty_semantics": "NOT_APPLICABLE",
            "uncertainty_parameter_1": "",
            "uncertainty_parameter_2": "",
            "uncertainty_parameter_3": "",
            "uncertainty_basis": "",
            "notes": "test fixture",
        }
        row.update(updates)
        return row

    def _boq(self, **updates):
        row = {
            "boq_line_id": "boq_test_window",
            "scenario_id": "scn_test_option",
            "component_instance_id": "ci_test_window",
            "comparison_lineage_id": "lineage_windows",
            "component_type_id": "ctype_windows",
            "item_label": "Synthetic test window",
            "material_or_product_id": "prod_test_window",
            "assessment_role": "ASSESSMENT_INVENTORY",
            "quantity": 100.0,
            "quantity_unit": "m2",
            "mass_kg": np.nan,
            "source_status": "TEST_ONLY_SYNTHETIC",
            "source_reference": "synthetic fixture",
            "derivation_method": "",
            "notes": "test",
        }
        row.update(updates)
        return pd.Series(row)

    def _assignment(self, **updates):
        row = {
            "assignment_id": "fa_test_window",
            "boq_line_id": "boq_test_window",
            "factor_set_id": "fs_test_window",
            "mapping_basis": "EXACT_PRODUCT_ID",
            "mapping_reference": "",
            "notes": "",
        }
        row.update(updates)
        return row

    def _load_factor_rows(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = self._write(rows, ENVIRONMENTAL_FACTOR_COLUMNS, tmp.name, "factors.csv")
        return load_environmental_factors(path)

    def _load_assignment_rows(self, rows, boq, factors):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = self._write(rows, BOQ_FACTOR_ASSIGNMENT_COLUMNS, tmp.name, "assignments.csv")
        return load_boq_factor_assignments(path, boq, factors)

    def test_production_registry_and_assignments_are_empty(self):
        factors = load_environmental_factors(m.DEFAULT_ENVIRONMENTAL_FACTORS)
        assignments = load_boq_factor_assignments(
            m.DEFAULT_BOQ_FACTOR_ASSIGNMENTS,
            pd.read_csv(m.DEFAULT_COMPONENT_BOQ),
            factors,
        )
        self.assertTrue(factors.empty)
        self.assertTrue(assignments.empty)

    def test_gwp_and_declared_unit_normalization(self):
        self.assertEqual(normalize_indicator_unit("GWP_TOTAL", "kg CO2 eq."), "kgco2e")
        self.assertEqual(normalize_declared_unit("m²"), "m2")
        self.assertEqual(normalize_declared_unit("tonne-km"), "tkm")
        with self.assertRaisesRegex(ValueError, "kgCO2e-compatible"):
            normalize_indicator_unit("GWP_TOTAL", "g CO2e")

    def test_factor_registry_validates_provenance_and_normalizes_fields(self):
        factors = self._load_factor_rows([self._factor()])
        row = factors.iloc[0]
        self.assertEqual(row.indicator_unit, "kgco2e")
        self.assertEqual(row.declared_unit, "m2")
        self.assertEqual(row.module_scope, "A1-A3")
        self.assertEqual(row.source_type, "TEST_ONLY_SYNTHETIC")

    def test_duplicate_factor_record_id_is_rejected(self):
        rows = [self._factor(), self._factor(indicator_id="GWP_FOSSIL")]
        with self.assertRaisesRegex(ValueError, "Stable IDs must be unique"):
            self._load_factor_rows(rows)

    def test_license_redistribution_conflict_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "redistribution_allowed=true"):
            self._load_factor_rows([
                self._factor(
                    source_type="LITERATURE",
                    verification_status="PEER_REVIEWED_SOURCE",
                    data_quality_status="DOCUMENTED_SECONDARY",
                    license_status="RESTRICTED_NO_REDISTRIBUTION",
                    redistribution_allowed=True,
                )
            ])

    def test_scenario_uncertainty_requires_nonprobabilistic_semantics(self):
        bad = self._factor(
            uncertainty_mode="SCENARIO",
            uncertainty_semantics="EPISTEMIC",
            uncertainty_parameter_1="",
            uncertainty_parameter_2="",
            uncertainty_parameter_3="",
            uncertainty_basis="Named future pathway; not a probability distribution",
        )
        with self.assertRaisesRegex(ValueError, "SCENARIO_NONPROBABILISTIC"):
            self._load_factor_rows([bad])
        good = dict(bad)
        good["uncertainty_semantics"] = "SCENARIO_NONPROBABILISTIC"
        factors = self._load_factor_rows([good])
        self.assertEqual(factors.iloc[0].uncertainty_semantics, "SCENARIO_NONPROBABILISTIC")

    def test_factor_set_cannot_mix_declared_units_or_products(self):
        rows = [
            self._factor(),
            self._factor(
                factor_record_id="fr_test_window_fossil_a1a3",
                indicator_id="GWP_FOSSIL",
                declared_unit="kg",
            ),
        ]
        with self.assertRaisesRegex(ValueError, "internally inconsistent for declared_unit"):
            self._load_factor_rows(rows)

    def test_overlapping_module_scopes_are_rejected_per_indicator(self):
        rows = [
            self._factor(),
            self._factor(
                factor_record_id="fr_test_window_total_a1",
                module_scope="A1",
                indicator_value=4.0,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            self._load_factor_rows(rows)

    def test_total_and_disaggregated_gwp_can_coexist_without_implicit_sum(self):
        rows = [
            self._factor(),
            self._factor(
                factor_record_id="fr_test_window_fossil_a1a3",
                indicator_id="GWP_FOSSIL",
                indicator_value=10.0,
            ),
            self._factor(
                factor_record_id="fr_test_window_biogenic_a1a3",
                indicator_id="GWP_BIOGENIC",
                indicator_value=-0.5,
            ),
        ]
        factors = self._load_factor_rows(rows)
        summary = build_factor_set_summary(factors).iloc[0]
        self.assertTrue(bool(summary.gwp_total_available))
        self.assertEqual(int(summary.gwp_disaggregated_count), 2)
        self.assertTrue(bool(summary.product_stage_gwp_total_available))
        # Registry preserves source indicators; no derived/summed GWP_TOTAL row is created.
        self.assertEqual(int(factors.indicator_id.eq("GWP_TOTAL").sum()), 1)

    def test_exact_assignment_requires_exact_product_identity(self):
        factors = self._load_factor_rows([self._factor(product_or_process_id="prod_other")])
        boq = pd.DataFrame([self._boq().to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        with self.assertRaisesRegex(ValueError, "EXACT_PRODUCT_ID"):
            self._load_assignment_rows([self._assignment()], boq, factors)

    def test_documented_proxy_requires_reference_but_allows_identity_mismatch(self):
        factors = self._load_factor_rows([self._factor(product_or_process_id="prod_proxy")])
        boq = pd.DataFrame([self._boq().to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        with self.assertRaisesRegex(ValueError, "mapping_reference"):
            self._load_assignment_rows([
                self._assignment(mapping_basis="DOCUMENTED_PROXY")
            ], boq, factors)
        assignments = self._load_assignment_rows([
            self._assignment(mapping_basis="DOCUMENTED_PROXY", mapping_reference="Documented proxy rationale")
        ], boq, factors)
        self.assertEqual(assignments.iloc[0].mapping_basis, "DOCUMENTED_PROXY")

    def test_information_only_boq_line_cannot_receive_executable_factor(self):
        factors = self._load_factor_rows([self._factor()])
        boq = pd.DataFrame([self._boq(assessment_role="INFORMATION_ONLY").to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        with self.assertRaisesRegex(ValueError, "ASSESSMENT_INVENTORY"):
            self._load_assignment_rows([self._assignment()], boq, factors)

    def test_exact_unit_gate_passes_without_impact_calculation(self):
        factors = self._load_factor_rows([self._factor()])
        boq = pd.DataFrame([self._boq().to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        assignments = self._load_assignment_rows([self._assignment()], boq, factors)
        compat = build_boq_factor_compatibility(boq, assignments, factors).iloc[0]
        self.assertEqual(compat.unit_compatibility_status, "COMPATIBLE_EXACT_UNIT")
        self.assertEqual(compat.conversion_method, "EXACT_UNIT")
        self.assertEqual(float(compat.resolved_activity_quantity), 100.0)
        self.assertEqual(compat.compatibility_gate_status, "PASS_EXACT_PRODUCT_MAPPING")
        self.assertNotIn("impact", compat.index)

    def test_explicit_kg_tonne_conversion_is_supported(self):
        factors = self._load_factor_rows([self._factor(declared_unit="t")])
        boq_row = self._boq(quantity=2500.0, quantity_unit="kg")
        resolved = resolve_boq_declared_unit_compatibility(boq_row, "t")
        self.assertEqual(resolved["conversion_method"], "KG_TO_TONNE")
        self.assertAlmostEqual(resolved["resolved_activity_quantity"], 2.5)

    def test_mass_based_boq_cannot_carry_conflicting_total_mass(self):
        boq_row = self._boq(quantity=1000.0, quantity_unit="kg", mass_kg=999.0)
        with self.assertRaisesRegex(ValueError, "conflicts with documented mass_kg"):
            resolve_boq_declared_unit_compatibility(boq_row, "kg")

    def test_documented_total_mass_bridge_is_supported_without_density_inference(self):
        factors = self._load_factor_rows([self._factor(declared_unit="kg")])
        boq = pd.DataFrame([self._boq(quantity=100.0, quantity_unit="m2", mass_kg=1800.0).to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        assignments = self._load_assignment_rows([self._assignment()], boq, factors)
        compat = build_boq_factor_compatibility(boq, assignments, factors).iloc[0]
        self.assertEqual(compat.unit_compatibility_status, "COMPATIBLE_DOCUMENTED_MASS_BRIDGE")
        self.assertEqual(compat.conversion_method, "TOTAL_MASS_KG")
        self.assertEqual(float(compat.resolved_activity_quantity), 1800.0)

    def test_incompatible_units_are_blocked_not_converted_implicitly(self):
        factors = self._load_factor_rows([self._factor(declared_unit="m3")])
        boq = pd.DataFrame([self._boq(quantity_unit="m2", mass_kg=np.nan).to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        assignments = self._load_assignment_rows([self._assignment()], boq, factors)
        compat = build_boq_factor_compatibility(boq, assignments, factors).iloc[0]
        self.assertEqual(compat.unit_compatibility_status, "INCOMPATIBLE_UNIT")
        self.assertEqual(compat.compatibility_gate_status, "BLOCKED_UNIT_INCOMPATIBLE")
        self.assertTrue(pd.isna(compat.resolved_activity_quantity))

    def test_missing_gwp_total_is_blocked_and_not_reconstructed(self):
        factors = self._load_factor_rows([
            self._factor(
                factor_record_id="fr_test_window_fossil_a1a3",
                indicator_id="GWP_FOSSIL",
                indicator_value=10.0,
            )
        ])
        boq = pd.DataFrame([self._boq().to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        assignments = self._load_assignment_rows([self._assignment()], boq, factors)
        compat = build_boq_factor_compatibility(boq, assignments, factors).iloc[0]
        self.assertEqual(compat.compatibility_gate_status, "BLOCKED_GWP_TOTAL_MISSING")
        self.assertFalse(bool(compat.gwp_total_available))

    def test_missing_product_stage_scope_is_blocked(self):
        factors = self._load_factor_rows([self._factor(module_scope="C4")])
        boq = pd.DataFrame([self._boq().to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        assignments = self._load_assignment_rows([self._assignment()], boq, factors)
        compat = build_boq_factor_compatibility(boq, assignments, factors).iloc[0]
        self.assertEqual(compat.compatibility_gate_status, "BLOCKED_PRODUCT_STAGE_SCOPE_MISSING")

    def test_unassigned_assessment_boq_line_stays_blocked(self):
        boq = pd.DataFrame([self._boq().to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        coverage = build_boq_factor_coverage(
            boq,
            pd.DataFrame(columns=BOQ_FACTOR_ASSIGNMENT_COLUMNS),
            pd.DataFrame(),
        )
        row = coverage.iloc[0]
        self.assertEqual(row.assignment_status, "ASSIGNMENT_MISSING")
        self.assertEqual(row.compatibility_gate_status, "BLOCKED_ASSIGNMENT_MISSING")

    def test_registry_status_never_claims_carbon_result(self):
        factors = self._load_factor_rows([self._factor()])
        summary = build_factor_set_summary(factors)
        boq = pd.DataFrame([self._boq().to_dict()], columns=COMPONENT_BOQ_COLUMNS)
        assignments = self._load_assignment_rows([self._assignment()], boq, factors)
        compat = build_boq_factor_compatibility(boq, assignments, factors)
        coverage = build_boq_factor_coverage(boq, assignments, compat)
        status = environmental_registry_status(factors, summary, boq, assignments, coverage)
        self.assertEqual(status["status"], "READY_FOR_CARBON_ENGINE_INPUT")
        self.assertFalse(status["headline_carbon_generated"])
        self.assertFalse(status["gwp_total_reconstruction_from_disaggregated_indicators"])
        self.assertFalse(status["implicit_unit_conversion_allowed"])

    def test_run_writes_m18_registry_outputs_without_carbon_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            m.run(
                output_dir=out,
                simulations=2,
                seed=123,
                charts=False,
                convergence_enabled=False,
                horizon_mode="legacy_30",
            )
            required = [
                "resolved_environmental_factors.csv",
                "resolved_boq_environmental_factor_assignments.csv",
                "environmental_factor_set_summary.csv",
                "boq_factor_compatibility.csv",
                "boq_factor_coverage.csv",
                "environmental_registry_status.json",
            ]
            for name in required:
                self.assertTrue((out / name).exists(), name)
            factors = pd.read_csv(out / "resolved_environmental_factors.csv")
            assignments = pd.read_csv(out / "resolved_boq_environmental_factor_assignments.csv")
            self.assertTrue(factors.empty)
            self.assertTrue(assignments.empty)
            status = json.loads((out / "environmental_registry_status.json").read_text())
            self.assertEqual(status["status"], "NO_ASSESSMENT_BOQ_LINES")
            self.assertFalse(status["headline_carbon_generated"])
            self.assertTrue((out / "carbon_consequence_ledger.csv").exists())
            self.assertTrue(pd.read_csv(out / "carbon_consequence_ledger.csv").empty)
            manifest = json.loads((out / "run_manifest.json").read_text())
            self.assertEqual(manifest["migration_checkpoint"], "v3-M5-FINAL-LIFECYCLE-GATE")
            self.assertFalse(manifest["headline_carbon_generated"])


if __name__ == "__main__":
    unittest.main()
