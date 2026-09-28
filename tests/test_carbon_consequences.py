import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import renovation_lcc as m
from carbon_consequences import (
    build_carbon_consequence_ledger,
    build_product_carbon_summary,
    build_product_carbon_coverage,
    carbon_engine_status,
)
from component_lifecycle import load_components
from environmental_factors import (
    ENVIRONMENTAL_FACTOR_COLUMNS,
    BOQ_FACTOR_ASSIGNMENT_COLUMNS,
    load_environmental_factors,
    load_boq_factor_assignments,
    build_boq_factor_compatibility,
    build_boq_factor_coverage,
)
from lifecycle_events import canonical_replacement_events
from physical_quantities import (
    COMPONENT_BOQ_COLUMNS,
    load_component_boq,
    expand_lifecycle_events_with_boq,
)
from reference_inventory import empty_physical_reference_inventory


class ProductCarbonConsequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        cls.components = load_components(m.DEFAULT_COMPONENTS, cls.scenarios)
        cls.empty_ref = empty_physical_reference_inventory()

    def _parent(self):
        return self.components.iloc[0].copy()

    def _write(self, rows, columns, tmp, name):
        path = Path(tmp) / name
        pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
        return path

    def _boq_row(self, parent=None, **overrides):
        p = self._parent() if parent is None else parent
        row = {
            "boq_line_id": "boq_test_product",
            "scenario_id": p.scenario_id,
            "component_instance_id": p.component_instance_id,
            "comparison_lineage_id": p.comparison_lineage_id,
            "component_type_id": p.component_type_id,
            "item_label": "Synthetic product quantity",
            "material_or_product_id": "prod_test_product",
            "assessment_role": "ASSESSMENT_INVENTORY",
            "quantity": 10.0,
            "quantity_unit": "m2",
            "mass_kg": np.nan,
            "source_status": "TEST_ONLY_SYNTHETIC",
            "source_reference": "synthetic fixture",
            "derivation_method": "",
            "notes": "",
        }
        row.update(overrides)
        return row

    def _factor_row(self, **overrides):
        row = {
            "factor_record_id": "fr_test_a1a3",
            "factor_set_id": "fs_test_product",
            "dataset_id": "dataset_test",
            "product_or_process_id": "prod_test_product",
            "indicator_id": "GWP_TOTAL",
            "indicator_value": 2.5,
            "indicator_unit": "kgco2e",
            "declared_unit": "m2",
            "module_scope": "A1-A3",
            "geography": "TEST",
            "reference_year": 2026,
            "source_type": "TEST_ONLY_SYNTHETIC",
            "source_citation": "synthetic fixture",
            "verification_status": "TEST_ONLY",
            "data_quality_status": "TEST_ONLY",
            "license_status": "TEST_ONLY",
            "redistribution_allowed": False,
            "uncertainty_mode": "DETERMINISTIC",
            "uncertainty_semantics": "NOT_APPLICABLE",
            "uncertainty_parameter_1": np.nan,
            "uncertainty_parameter_2": np.nan,
            "uncertainty_parameter_3": np.nan,
            "uncertainty_basis": "",
            "notes": "",
        }
        row.update(overrides)
        return row

    def _assignment(self, **overrides):
        row = {
            "assignment_id": "asg_test_product",
            "boq_line_id": "boq_test_product",
            "factor_set_id": "fs_test_product",
            "mapping_basis": "TEST_ONLY_SYNTHETIC",
            "mapping_reference": "synthetic fixture",
            "notes": "",
        }
        row.update(overrides)
        return row

    def _loaded_fixture(self, boq_row=None, factor_rows=None, assignment_rows=None):
        parent = self._parent()
        boq_row = self._boq_row(parent) if boq_row is None else boq_row
        factor_rows = [self._factor_row()] if factor_rows is None else factor_rows
        assignment_rows = [self._assignment()] if assignment_rows is None else assignment_rows
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        boq = load_component_boq(
            self._write([boq_row], COMPONENT_BOQ_COLUMNS, root, "boq.csv"),
            self.components,
            self.empty_ref,
        )
        factors = load_environmental_factors(
            self._write(factor_rows, ENVIRONMENTAL_FACTOR_COLUMNS, root, "factors.csv")
        )
        assignments = load_boq_factor_assignments(
            self._write(assignment_rows, BOQ_FACTOR_ASSIGNMENT_COLUMNS, root, "assignments.csv"),
            boq,
            factors,
        )
        compat = build_boq_factor_compatibility(boq, assignments, factors)
        coverage = build_boq_factor_coverage(boq, assignments, compat)
        return tmp, parent, boq, factors, assignments, compat, coverage

    def _one_b4_event_boq(self, parent, boq):
        ledger = canonical_replacement_events(
            future_ids=[0],
            scenario_id=parent.scenario_id,
            component_instance_id=parent.component_instance_id,
            comparison_lineage_id=parent.comparison_lineage_id,
            uncertainty_key=parent.uncertainty_key,
            generation=1,
            event_times_years=np.array([5.0]),
            sampled_service_life_years=np.array([5.0]),
        )
        return expand_lifecycle_events_with_boq(ledger, boq)

    def test_closed_form_initial_and_b4_quantity_times_factor(self):
        tmp, parent, boq, factors, assignments, compat, _ = self._loaded_fixture()
        self.addCleanup(tmp.cleanup)
        event_boq = self._one_b4_event_boq(parent, boq)
        ledger = build_carbon_consequence_ledger(
            components=self.components,
            component_boq=boq,
            lifecycle_event_ledger=event_boq.merge(pd.DataFrame(), how="left") if False else canonical_replacement_events(
                future_ids=[0], scenario_id=parent.scenario_id, component_instance_id=parent.component_instance_id,
                comparison_lineage_id=parent.comparison_lineage_id, uncertainty_key=parent.uncertainty_key, generation=1,
                event_times_years=np.array([5.0]), sampled_service_life_years=np.array([5.0])
            ),
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=event_boq,
            future_ids=[0],
        )
        self.assertEqual(len(ledger), 2)
        self.assertEqual(set(ledger.reported_module), {"A1-A3", "B4"})
        self.assertTrue(np.allclose(ledger.gwp_kgco2e, 25.0))
        summary = build_product_carbon_summary(ledger)
        self.assertEqual(len(summary), 2)
        self.assertAlmostEqual(summary.assessed_gwp_kgco2e.sum(), 50.0)

    def test_new_at_t0_initial_product_is_counted_once_per_future(self):
        tmp, _, boq, factors, assignments, compat, _ = self._loaded_fixture()
        self.addCleanup(tmp.cleanup)
        ledger = build_carbon_consequence_ledger(
            components=self.components,
            component_boq=boq,
            lifecycle_event_ledger=pd.DataFrame(),
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=pd.DataFrame(),
            future_ids=[0, 1, 2],
        )
        initial = ledger.loc[ledger.consequence_type.eq("INITIAL_PRODUCT_STAGE")]
        self.assertEqual(len(initial), 3)
        self.assertEqual(set(initial.future_id), {0, 1, 2})
        self.assertTrue(initial.lifecycle_event_id.isna().all())
        self.assertTrue(initial.event_time_years.eq(0.0).all())

    def test_retained_existing_receives_no_historical_a1_a3(self):
        retained = self.components.copy()
        retained["initial_component_state"] = "NEW_AT_T0"
        target_id = self._parent().component_instance_id
        retained.loc[retained.component_instance_id.eq(target_id), "initial_component_state"] = "RETAINED_EXISTING"
        tmp, parent, boq, factors, assignments, compat, _ = self._loaded_fixture()
        self.addCleanup(tmp.cleanup)
        event_boq = self._one_b4_event_boq(parent, boq)
        ledger = build_carbon_consequence_ledger(
            components=retained,
            component_boq=boq,
            lifecycle_event_ledger=canonical_replacement_events(
                future_ids=[0], scenario_id=parent.scenario_id, component_instance_id=parent.component_instance_id,
                comparison_lineage_id=parent.comparison_lineage_id, uncertainty_key=parent.uncertainty_key, generation=1,
                event_times_years=np.array([5.0]), sampled_service_life_years=np.array([5.0])
            ),
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=event_boq,
            future_ids=[0],
        )
        self.assertFalse(ledger.consequence_type.eq("INITIAL_PRODUCT_STAGE").any())
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger.consequence_type.iloc[0], "B4_REPLACEMENT_PRODUCT_STAGE")

    def test_b4_product_consequence_count_tracks_canonical_event_count(self):
        tmp, parent, boq, factors, assignments, compat, _ = self._loaded_fixture()
        self.addCleanup(tmp.cleanup)
        lifecycle = canonical_replacement_events(
            future_ids=[0, 1, 2],
            scenario_id=parent.scenario_id,
            component_instance_id=parent.component_instance_id,
            comparison_lineage_id=parent.comparison_lineage_id,
            uncertainty_key=parent.uncertainty_key,
            generation=1,
            event_times_years=np.array([5.0, 6.0, 7.0]),
            sampled_service_life_years=np.array([5.0, 6.0, 7.0]),
        )
        event_boq = expand_lifecycle_events_with_boq(lifecycle, boq)
        ledger = build_carbon_consequence_ledger(
            components=self.components,
            component_boq=boq,
            lifecycle_event_ledger=lifecycle,
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=event_boq,
            future_ids=[0, 1, 2],
        )
        b4 = ledger.loc[ledger.reported_module.eq("B4")]
        self.assertEqual(len(b4), len(lifecycle))
        self.assertEqual(set(b4.lifecycle_event_id), set(lifecycle.event_id))

    def test_disaggregated_a1_a2_a3_records_sum_without_double_counting(self):
        rows = [
            self._factor_row(factor_record_id="fr_test_a1", module_scope="A1", indicator_value=1.0),
            self._factor_row(factor_record_id="fr_test_a2", module_scope="A2", indicator_value=2.0),
            self._factor_row(factor_record_id="fr_test_a3", module_scope="A3", indicator_value=3.0),
        ]
        tmp, parent, boq, factors, assignments, compat, _ = self._loaded_fixture(factor_rows=rows)
        self.addCleanup(tmp.cleanup)
        event_boq = self._one_b4_event_boq(parent, boq)
        ledger = build_carbon_consequence_ledger(
            components=self.components,
            component_boq=boq,
            lifecycle_event_ledger=canonical_replacement_events(
                future_ids=[0], scenario_id=parent.scenario_id, component_instance_id=parent.component_instance_id,
                comparison_lineage_id=parent.comparison_lineage_id, uncertainty_key=parent.uncertainty_key, generation=1,
                event_times_years=np.array([5.0]), sampled_service_life_years=np.array([5.0])
            ),
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=event_boq,
            future_ids=[0],
        )
        initial = ledger.loc[ledger.reported_module.eq("A1-A3")]
        b4 = ledger.loc[ledger.reported_module.eq("B4")]
        self.assertEqual(len(initial), 3)
        self.assertEqual(len(b4), 3)
        self.assertAlmostEqual(initial.gwp_kgco2e.sum(), 60.0)
        self.assertAlmostEqual(b4.gwp_kgco2e.sum(), 60.0)

    def test_explicit_kg_to_tonne_conversion_is_used_in_impact(self):
        boq_row = self._boq_row(quantity=2000.0, quantity_unit="kg", mass_kg=2000.0)
        factor = self._factor_row(declared_unit="t", indicator_value=100.0)
        tmp, _, boq, factors, assignments, compat, _ = self._loaded_fixture(boq_row=boq_row, factor_rows=[factor])
        self.addCleanup(tmp.cleanup)
        ledger = build_carbon_consequence_ledger(
            components=self.components,
            component_boq=boq,
            lifecycle_event_ledger=pd.DataFrame(),
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=pd.DataFrame(),
            future_ids=[0],
        )
        self.assertEqual(ledger.conversion_method.iloc[0], "KG_TO_TONNE")
        self.assertAlmostEqual(ledger.resolved_activity_quantity.iloc[0], 2.0)
        self.assertAlmostEqual(ledger.gwp_kgco2e.iloc[0], 200.0)

    def test_blocked_missing_gwp_total_produces_no_carbon_rows(self):
        factor = self._factor_row(indicator_id="GWP_FOSSIL")
        tmp, _, boq, factors, assignments, compat, coverage = self._loaded_fixture(factor_rows=[factor])
        self.addCleanup(tmp.cleanup)
        self.assertEqual(compat.compatibility_gate_status.iloc[0], "BLOCKED_GWP_TOTAL_MISSING")
        ledger = build_carbon_consequence_ledger(
            components=self.components,
            component_boq=boq,
            lifecycle_event_ledger=pd.DataFrame(),
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=pd.DataFrame(),
            future_ids=[0],
        )
        self.assertTrue(ledger.empty)
        status = carbon_engine_status(
            component_boq=boq,
            boq_factor_coverage=coverage,
            consequence_ledger=ledger,
            product_summary=build_product_carbon_summary(ledger),
        )
        self.assertEqual(status["status"], "NO_EXECUTABLE_PRODUCT_CARBON_MAPPING")
        self.assertFalse(status["missing_data_treated_as_zero"])

    def test_duplicate_assignment_remains_hard_blocked_by_registry(self):
        assignments = [
            self._assignment(assignment_id="asg_test_one"),
            self._assignment(assignment_id="asg_test_two"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            boq = load_component_boq(
                self._write([self._boq_row()], COMPONENT_BOQ_COLUMNS, root, "boq.csv"),
                self.components, self.empty_ref,
            )
            factors = load_environmental_factors(
                self._write([self._factor_row()], ENVIRONMENTAL_FACTOR_COLUMNS, root, "factors.csv")
            )
            path = self._write(assignments, BOQ_FACTOR_ASSIGNMENT_COLUMNS, root, "assignments.csv")
            with self.assertRaisesRegex(ValueError, "at most one"):
                load_boq_factor_assignments(path, boq, factors)

    def test_horizon_nesting_of_b4_carbon_follows_event_nesting(self):
        tmp, parent, boq, factors, assignments, compat, _ = self._loaded_fixture()
        self.addCleanup(tmp.cleanup)
        ledgers = {}
        for horizon, times in ((30, [10.0, 20.0]), (50, [10.0, 20.0, 40.0]), (60, [10.0, 20.0, 40.0, 55.0])):
            # Create realistic successive generations with stable unique event identities.
            pieces = []
            for gen, t in enumerate(times, start=1):
                pieces.append(canonical_replacement_events(
                    future_ids=[0], scenario_id=parent.scenario_id,
                    component_instance_id=parent.component_instance_id,
                    comparison_lineage_id=parent.comparison_lineage_id,
                    uncertainty_key=parent.uncertainty_key, generation=gen,
                    event_times_years=np.array([t]), sampled_service_life_years=np.array([10.0]),
                ))
            lifecycle = pd.concat(pieces, ignore_index=True)
            event_boq = expand_lifecycle_events_with_boq(lifecycle, boq)
            carbon = build_carbon_consequence_ledger(
                components=self.components, component_boq=boq, lifecycle_event_ledger=lifecycle, factors=factors,
                assignments=assignments, compatibility=compat,
                event_boq_quantities=event_boq, future_ids=[0],
            )
            ledgers[horizon] = set(carbon.loc[carbon.reported_module.eq("B4"), "lifecycle_event_id"])
        self.assertTrue(ledgers[30] < ledgers[50] < ledgers[60])


    def test_initial_product_scope_does_not_leak_across_component_sets(self):
        tmp, _, boq, factors, assignments, compat, _ = self._loaded_fixture()
        self.addCleanup(tmp.cleanup)
        # Simulates calling the intervention engine while the BoQ table also
        # contains rows belonging to some other/reference component set.
        unrelated = self.components.loc[
            self.components.component_instance_id.ne(self._parent().component_instance_id)
        ].copy()
        ledger = build_carbon_consequence_ledger(
            components=unrelated,
            component_boq=boq,
            lifecycle_event_ledger=pd.DataFrame(),
            factors=factors,
            assignments=assignments,
            compatibility=compat,
            event_boq_quantities=pd.DataFrame(),
            future_ids=[0],
        )
        self.assertTrue(ledger.empty)

    def test_production_run_is_cleanly_non_assessed_not_zero_carbon(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            m.run(output_dir=out, simulations=2, seed=123, charts=False,
                  convergence_enabled=False, horizon_mode="legacy_30")
            ledger = pd.read_csv(out / "carbon_consequence_ledger.csv")
            summary = pd.read_csv(out / "assessed_product_carbon_by_module.csv")
            self.assertTrue(ledger.empty)
            self.assertTrue(summary.empty)
            import json
            status = json.loads((out / "carbon_engine_status.json").read_text())
            self.assertEqual(status["status"], "NO_ASSESSMENT_BOQ_LINES")
            self.assertFalse(status["whole_life_carbon_generated"])
            self.assertFalse(status["headline_carbon_generated"])
            self.assertFalse(status["missing_data_treated_as_zero"])
            manifest = json.loads((out / "run_manifest.json").read_text())
            self.assertEqual(manifest["migration_checkpoint"], "v3-M5-FINAL-LIFECYCLE-GATE")
            self.assertFalse(manifest["whole_life_carbon_generated"])


if __name__ == "__main__":
    unittest.main()
