import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import renovation_lcc as m
import a4_transport as a4
from component_lifecycle import load_components
from physical_quantities import COMPONENT_BOQ_COLUMNS, load_component_boq
from reference_inventory import empty_physical_reference_inventory


class A4TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        all_components = load_components(m.DEFAULT_COMPONENTS, m.load_scenarios(m.DEFAULT_INPUT))
        # A <30-year life ensures real B4 events in every audited horizon.
        cls.components = pd.concat([all_components.iloc[[6]], all_components.drop(all_components.index[6])]).reset_index(drop=True)

    def fixture(self):
        p = self.components.iloc[0]
        boq = pd.DataFrame([dict(zip(COMPONENT_BOQ_COLUMNS, (
            "boq_a4_test", p.scenario_id, p.component_instance_id, p.comparison_lineage_id,
            p.component_type_id, "Synthetic transport item", "product_a4_test", "ASSESSMENT_INVENTORY",
            1000.0, "kg", 1000.0, "TEST_ONLY_SYNTHETIC", "Synthetic mass fixture", "", "",
        )))])
        scenarios = pd.DataFrame([dict(zip(a4.TRANSPORT_SCENARIO_COLUMNS, (
            "route_test", "FACTORY_GATE", "PROJECT_SITE", 100.0, "ROAD", "test_truck",
            "SOURCE_FACTOR_INCLUDES_LOAD_AND_RETURN", "TEST_ONLY_SYNTHETIC", "Synthetic distance fixture",
            "2026-09-27", "",
        )))])
        factors = pd.DataFrame([{
            "factor_record_id": "tf_test_gwp", "factor_set_id": "tfs_test", "dataset_id": "test_dataset",
            "product_or_process_id": "transport_test", "indicator_id": "GWP_TOTAL", "indicator_value": 0.1,
            "indicator_unit": "kgco2e", "declared_unit": "tkm", "module_scope": "A4", "geography": "TEST",
            "reference_year": 2026, "source_type": "TEST_ONLY_SYNTHETIC", "source_citation": "Synthetic factor fixture",
            "verification_status": "TEST_ONLY", "data_quality_status": "TEST_ONLY", "license_status": "TEST_ONLY",
            "redistribution_allowed": False, "uncertainty_mode": "DETERMINISTIC", "uncertainty_semantics": "NOT_APPLICABLE",
            "uncertainty_parameter_1": np.nan, "uncertainty_parameter_2": np.nan, "uncertainty_parameter_3": np.nan,
            "uncertainty_basis": "", "notes": "", "transport_mode": "ROAD", "vehicle_class": "test_truck",
            "load_factor_basis": "SOURCE_FACTOR_INCLUDES_LOAD_AND_RETURN", "factor_system_boundary": "TEST_WELL_TO_WHEEL",
            "retrieval_date": "2026-09-27",
        }], columns=a4.TRANSPORT_FACTOR_COLUMNS)
        assignments = pd.DataFrame([dict(zip(a4.BOQ_TRANSPORT_ASSIGNMENT_COLUMNS, (
            "ta_test", "boq_a4_test", p.scenario_id, "route_test", "flow_test", "tfs_test", True,
            "NEW_INSTALLATION", "TEST_ONLY_SYNTHETIC", "Synthetic explicit mapping", "",
        )))])
        return [self.components.copy(), boq, scenarios, factors, assignments, [0, 1, 2]]

    def assert_block(self, fixture, expected):
        gates, coverage, ledger, summary, status = a4.assess_initial_transport(*fixture)
        self.assertEqual(gates.compatibility_gate_status.iloc[0], expected)
        self.assertEqual(coverage.compatibility_gate_status.iloc[0], expected)
        self.assertTrue(ledger.empty)
        self.assertTrue(summary.empty)
        self.assertFalse(status["missing_data_treated_as_zero"])

    def test_golden_1000kg_100km_point1_equals_10(self):
        gates, coverage, ledger, summary, status = a4.assess_initial_transport(*self.fixture())
        self.assertEqual(gates.resolved_activity_quantity.tolist(), [100.0])
        self.assertEqual(ledger.gwp_kgco2e.tolist(), [10.0] * 3)
        self.assertEqual(summary.assessed_gwp_kgco2e.tolist(), [10.0] * 3)
        self.assertEqual(status["gate_pass_lines"], 1)

    def test_tonnes_and_documented_mass_bridge_agree(self):
        for unit, qty, mass in [("t", 1.0, np.nan), ("kg", 1000.0, np.nan), ("m2", 7.0, 1000.0)]:
            with self.subTest(unit=unit):
                f = self.fixture()
                f[1].loc[0, ["quantity_unit", "quantity", "mass_kg"]] = [unit, qty, mass]
                self.assertEqual(a4.assess_initial_transport(*f)[2].gwp_kgco2e.tolist(), [10.0] * 3)

    def test_m2_without_mass_is_blocked(self):
        f = self.fixture(); f[1].loc[0, ["quantity_unit", "mass_kg"]] = ["m2", np.nan]
        self.assert_block(f, "BLOCKED_MASS_MISSING")

    def test_missing_distance_is_not_zero(self):
        f = self.fixture(); f[2].loc[0, "distance_km"] = np.nan
        self.assert_block(f, "BLOCKED_DISTANCE_MISSING")

    def test_documented_zero_distance_is_valid_zero(self):
        f = self.fixture(); f[2].loc[0, "distance_km"] = 0.0
        result = a4.assess_initial_transport(*f)
        self.assertTrue(result[2].gwp_kgco2e.eq(0.0).all())
        self.assertEqual(result[4]["gate_pass_lines"], 1)

    def test_negative_nonfinite_and_invalid_distances_fail(self):
        for v in [-1.0, np.inf, -np.inf, "unknown"]:
            f = self.fixture(); f[2]["distance_km"] = v
            with self.subTest(v=v), self.assertRaises(ValueError):
                a4.assess_initial_transport(*f)

    def test_missing_gwp_total_never_sums_subindicators(self):
        f = self.fixture()
        f[3] = pd.concat([f[3].assign(indicator_id=i, factor_record_id="tf_"+str(n))
                          for n, i in enumerate(["GWP_FOSSIL", "GWP_BIOGENIC", "GWP_LULUC"])], ignore_index=True)
        self.assert_block(f, "BLOCKED_GWP_TOTAL_MISSING")

    def test_wrong_declared_unit_is_blocked(self):
        f = self.fixture(); f[3].loc[0, "declared_unit"] = "kg"
        self.assert_block(f, "BLOCKED_TRANSPORT_FACTOR_UNIT")

    def test_tonne_km_alias_is_normalized(self):
        f = self.fixture(); f[3].loc[0, "declared_unit"] = "tonne-km"
        self.assertTrue(a4.assess_initial_transport(*f)[2].factor_declared_unit.eq("tkm").all())

    def test_wrong_source_module_is_blocked(self):
        f = self.fixture(); f[3].loc[0, "module_scope"] = "A1-A3"
        self.assert_block(f, "BLOCKED_A4_FACTOR_SCOPE")

    def test_duplicate_active_assignment_is_hard_failure(self):
        f = self.fixture(); f[4] = pd.concat([f[4], f[4].assign(assignment_id="ta_other", transport_flow_id="flow_other")])
        with self.assertRaisesRegex(ValueError, "at most one"):
            a4.assess_initial_transport(*f)

    def test_same_flow_cannot_be_assigned_to_two_boq_lines(self):
        f = self.fixture()
        f[1] = pd.concat([f[1], f[1].assign(boq_line_id="boq_other")])
        f[4] = pd.concat([f[4], f[4].assign(assignment_id="ta_other", boq_line_id="boq_other")])
        with self.assertRaisesRegex(ValueError, "Duplicate active transport flow"):
            a4.assess_initial_transport(*f)

    def test_inactive_alternative_is_not_counted(self):
        f = self.fixture(); f[4] = pd.concat([f[4], f[4].assign(assignment_id="ta_other", active=False)])
        self.assertEqual(len(a4.assess_initial_transport(*f)[2]), 3)

    def test_all_inactive_is_missing_assignment(self):
        f = self.fixture(); f[4].loc[0, "active"] = False
        gates, cov, ledger, summary, status = a4.assess_initial_transport(*f)
        self.assertTrue(gates.empty)
        self.assertEqual(cov.compatibility_gate_status.iloc[0], "BLOCKED_TRANSPORT_ASSIGNMENT_MISSING")
        self.assertTrue(ledger.empty)

    def test_retained_components_do_not_inherit_historical_a4(self):
        f = self.fixture(); f[0].loc[f[0].index[0], "initial_component_state"] = "RETAINED_EXISTING"
        self.assert_block(f, "BLOCKED_RETAINED_NO_DOCUMENTED_T0_TRANSPORT")

    def test_explicit_documented_retained_movement_can_be_assessed(self):
        f = self.fixture(); f[0].loc[f[0].index[0], "initial_component_state"] = "RETAINED_EXISTING"
        f[4].loc[0, "initial_transport_basis"] = "DOCUMENTED_RETAINED_T0_TRANSPORT"
        self.assertTrue(a4.assess_initial_transport(*f)[2].gwp_kgco2e.eq(10.0).all())

    def test_retained_without_assignment_is_not_applicable(self):
        f = self.fixture(); f[0].loc[f[0].index[0], "initial_component_state"] = "RETAINED_EXISTING"
        f[4] = f[4].iloc[:0]
        self.assertEqual(a4.assess_initial_transport(*f)[4]["status"], "NOT_APPLICABLE_NO_INITIAL_TRANSPORT")

    def test_assignment_scenario_cannot_leak_into_reference(self):
        f = self.fixture(); f[4].loc[0, "scenario_id"] = "unrelated_reference"
        with self.assertRaisesRegex(ValueError, "scope leakage"):
            a4.assess_initial_transport(*f)

    def test_scoped_components_do_not_import_other_inventory(self):
        f = self.fixture(); f[0] = f[0].iloc[1:]
        self.assertTrue(a4.assess_initial_transport(*f)[2].empty)

    def test_boq_parent_scenario_mismatch_is_hard_failure(self):
        f = self.fixture()
        f[1].loc[0, "scenario_id"] = "foreign_scope"
        f[4].loc[0, "scenario_id"] = "foreign_scope"
        with self.assertRaisesRegex(ValueError, "component parent"):
            a4.assess_initial_transport(*f)

    def test_mass_mismatch_is_hard_failure(self):
        f = self.fixture(); f[1].loc[0, "mass_kg"] = 999.0
        with self.assertRaisesRegex(ValueError, "conflicts"):
            a4.assess_initial_transport(*f)

    def test_mode_vehicle_and_load_basis_must_match(self):
        for field in ("transport_mode", "vehicle_class", "load_factor_basis"):
            f = self.fixture(); f[3].loc[0, field] = "different"
            with self.subTest(field=field):
                self.assert_block(f, "BLOCKED_TRANSPORT_FACTOR_BASIS")

    def test_information_only_cannot_be_counted(self):
        f = self.fixture(); f[1].loc[0, "assessment_role"] = "INFORMATION_ONLY"
        with self.assertRaisesRegex(ValueError, "INFORMATION_ONLY"):
            a4.assess_initial_transport(*f)

    def test_missing_sources_dates_and_mapping_evidence_fail(self):
        for table, field in [(2, "source_reference"), (3, "source_citation"), (4, "mapping_reference"), (3, "retrieval_date")]:
            f = self.fixture(); f[table].loc[0, field] = ""
            with self.subTest(field=field), self.assertRaises(ValueError):
                a4.assess_initial_transport(*f)

    def test_invalid_date_and_unknown_ids_fail(self):
        for table, field, value in [(2, "retrieval_date", "2026-02-30"), (4, "factor_set_id", "missing"),
                                    (4, "transport_scenario_id", "missing"), (4, "boq_line_id", "missing")]:
            f = self.fixture(); f[table].loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                a4.assess_initial_transport(*f)

    def test_duplicate_factor_semantics_are_blocked(self):
        f = self.fixture(); f[3] = pd.concat([f[3], f[3].assign(factor_record_id="tf_duplicate")], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            a4.assess_initial_transport(*f)

    def test_nonfinite_or_negative_transport_factor_is_blocked(self):
        for v in [-0.1, np.inf, np.nan]:
            f = self.fixture(); f[3].loc[0, "indicator_value"] = v
            with self.subTest(v=v), self.assertRaises(ValueError):
                a4.assess_initial_transport(*f)

    def test_synthetic_source_cannot_be_mislabeled_documented(self):
        f = self.fixture(); f[4].loc[0, "mapping_basis"] = "DOCUMENTED_TRANSPORT_PROCESS"
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            a4.assess_initial_transport(*f)

    def test_duplicate_future_ids_are_blocked(self):
        f = self.fixture(); f[5] = [0, 0]
        with self.assertRaisesRegex(ValueError, "Duplicate future"):
            a4.assess_initial_transport(*f)

    def test_only_once_at_zero_and_never_replacement_event(self):
        ledger = a4.assess_initial_transport(*self.fixture())[2]
        self.assertEqual(len(ledger), 3)
        self.assertEqual(ledger.carbon_consequence_id.nunique(), 3)
        self.assertTrue(ledger.event_time_years.eq(0.0).all())
        self.assertTrue(ledger.component_generation.eq(0).all())
        self.assertTrue(ledger.lifecycle_event_id.isna().all())
        for field, value in [("event_time_years", 7.0), ("lifecycle_event_id", "replacement_event"), ("component_generation", 1)]:
            bad = ledger.copy(); bad.loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                a4.validate_a4_transport_ledger(bad)

    def test_labels_do_not_change_consequence_identity(self):
        f = self.fixture(); first = a4.assess_initial_transport(*f)[2]
        f[0]["component"] = "Renamed"; f[1]["item_label"] = "Renamed"; f[2]["notes"] = "Different display text"
        pd.testing.assert_frame_equal(first, a4.assess_initial_transport(*f)[2])

    def test_full_run_empty_production_reports_unassessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            m.run(output_dir=out, simulations=2, charts=False, convergence_enabled=False)
            status = json.loads((out / "a4_transport_engine_status.json").read_text())
            self.assertEqual(status["status"], "NO_ASSESSMENT_BOQ_LINES")
            self.assertFalse(status["missing_data_treated_as_zero"])
            self.assertTrue(pd.read_csv(out / "carbon_consequence_ledger.csv").empty)
            self.assertIn("A4_INITIAL_TRANSPORT", json.loads((out / "run_manifest.json").read_text())["implemented_carbon_modules"])

    def test_full_run_populated_transport_horizon_invariance_and_product_isolation(self):
        # Closed-form product + actual canonical renewal model, not mocked events.
        f = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {}
            for key, table in [("component_boq_path", f[1]), ("transport_scenarios_path", f[2]),
                               ("transport_factors_path", f[3]), ("boq_transport_assignments_path", f[4])]:
                paths[key] = root / (key + ".csv"); table.to_csv(paths[key], index=False)
            product = f[3].loc[:, a4.ENVIRONMENTAL_FACTOR_COLUMNS].copy()
            product.loc[0, ["factor_record_id", "factor_set_id", "product_or_process_id", "declared_unit", "module_scope", "indicator_value"]] = [
                "pf_test", "pfs_test", "product_a4_test", "kg", "A1-A3", 2.5]
            paths["environmental_factors_path"] = root / "product.csv"; product.to_csv(paths["environmental_factors_path"], index=False)
            paths["boq_factor_assignments_path"] = root / "product_mapping.csv"
            pd.DataFrame([{"assignment_id": "pa_test", "boq_line_id": "boq_a4_test", "factor_set_id": "pfs_test",
                           "mapping_basis": "TEST_ONLY_SYNTHETIC", "mapping_reference": "fixture", "notes": ""}]).to_csv(paths["boq_factor_assignments_path"], index=False)
            a4_reference = None
            for horizon in ("legacy_30", "levels_50", "rics_60"):
                out = root / horizon
                m.run(output_dir=out, simulations=2, charts=False, convergence_enabled=False, horizon_mode=horizon, **paths)
                ledger = pd.read_csv(out / "carbon_consequence_ledger.csv")
                transport = ledger.loc[ledger.reported_module.eq("A4")].reset_index(drop=True)
                self.assertEqual(len(transport), 2)
                self.assertTrue(transport.gwp_kgco2e.eq(10.0).all())
                self.assertEqual(set(ledger.reported_module), {"A1-A3", "B4", "A4"})
                self.assertNotIn("A4", set(pd.read_csv(out / "assessed_product_carbon_by_module.csv").reported_module))
                if a4_reference is not None:
                    pd.testing.assert_frame_equal(transport, a4_reference)
                a4_reference = transport
            # Perturb transport only: product rows and product summary stay exact.
            old = pd.read_csv(root / "legacy_30" / "carbon_consequence_ledger.csv")
            f[2]["distance_km"] = 200.0; f[2].to_csv(paths["transport_scenarios_path"], index=False)
            out = root / "changed"
            m.run(output_dir=out, simulations=2, charts=False, convergence_enabled=False, horizon_mode="legacy_30", **paths)
            new = pd.read_csv(out / "carbon_consequence_ledger.csv")
            pd.testing.assert_frame_equal(old.loc[old.reported_module.ne("A4")], new.loc[new.reported_module.ne("A4")])
            self.assertTrue(new.loc[new.reported_module.eq("A4"), "gwp_kgco2e"].eq(20.0).all())
            for name in ("assessed_product_carbon_by_module.csv", "product_carbon_coverage.csv", "carbon_engine_status.json", "lifecycle_event_ledger.csv", "simulation_results.csv"):
                self.assertEqual((out/name).read_bytes(), (root/"legacy_30"/name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
