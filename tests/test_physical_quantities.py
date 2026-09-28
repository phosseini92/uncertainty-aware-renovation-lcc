import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import renovation_lcc as m
from horizon import resolve_horizon
from component_lifecycle import renewal_costs_with_ledger_and_boundary
from reference_inventory import REFERENCE_INVENTORY_COLUMNS, load_physical_reference_inventory, reference_inventory_to_lifecycle_components
from physical_quantities import (
    COMPONENT_BOQ_COLUMNS,
    REFERENCE_PRESENCE_COLUMNS,
    build_physical_quantity_coverage,
    build_reference_coverage_skeleton,
    expand_boundary_states_with_boq,
    expand_lifecycle_events_with_boq,
    load_component_boq,
    load_reference_component_presence,
    normalize_physical_unit,
    validate_reference_presence_consistency,
)


class PhysicalQuantityAndCoverageTests(unittest.TestCase):
    def setUp(self):
        self.scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        self.components = m.load_components(m.DEFAULT_COMPONENTS, self.scenarios)
        self.reference_row = self.scenarios.loc[self.scenarios.is_reference.eq(1)].iloc[0]
        self.reference_id = str(self.reference_row.scenario_id)
        self.reference_name = str(self.reference_row.scenario)
        self.empty_ref = load_physical_reference_inventory(m.DEFAULT_REFERENCE_INVENTORY, self.reference_id)
        self.base = m.load_config()
        self.futures = m.sample_uncertain_futures(1, 20260726, self.base)

    def _option_parent(self):
        return self.components.iloc[0]

    def _boq_row(self, parent=None, **overrides):
        parent = self._option_parent() if parent is None else parent
        row = {
            "boq_line_id": "boq_test_insulation_01",
            "scenario_id": str(parent.scenario_id),
            "component_instance_id": str(parent.component_instance_id),
            "comparison_lineage_id": str(parent.comparison_lineage_id),
            "component_type_id": str(parent.component_type_id),
            "item_label": "Synthetic insulation quantity",
            "material_or_product_id": "prod_test_insulation",
            "assessment_role": "ASSESSMENT_INVENTORY",
            "quantity": 100.0,
            "quantity_unit": "m2",
            "mass_kg": "",
            "source_status": "TEST_ONLY_SYNTHETIC",
            "source_reference": "tests/test_physical_quantities.py",
            "derivation_method": "",
            "notes": "Synthetic fixture only.",
        }
        row.update(overrides)
        return row

    def _reference_row(self, lineage="lineage_windows", ctype="ctype_windows"):
        return {
            "scenario_id": self.reference_id,
            "component_instance_id": "ci_reference_test_window",
            "comparison_lineage_id": lineage,
            "component_type_id": ctype,
            "component": "Synthetic existing window",
            "initial_component_state": "RETAINED_EXISTING",
            "physical_quantity": 80.0,
            "physical_unit": "m²",
            "remaining_life_distribution": "fixed",
            "remaining_life_min_years": "",
            "remaining_life_mode_years": "",
            "remaining_life_max_years": "",
            "remaining_life_fixed_years": 7.0,
            "remaining_life_uncertainty_key": "remaining_windows",
            "full_life_distribution": "fixed",
            "full_life_min_years": "",
            "full_life_mode_years": "",
            "full_life_max_years": "",
            "full_life_fixed_years": 20.0,
            "full_life_uncertainty_key": "windows",
            "age_at_t0_years": 13.0,
            "source_status": "TEST_ONLY_SYNTHETIC",
            "source_reference": "tests/test_physical_quantities.py",
            "notes": "Synthetic fixture only.",
        }

    def _presence(self, status_overrides=None):
        table = pd.read_csv(m.DEFAULT_REFERENCE_PRESENCE)
        if status_overrides:
            for lineage, status in status_overrides.items():
                table.loc[table.comparison_lineage_id.eq(lineage), "reference_presence_status"] = status
                table.loc[table.comparison_lineage_id.eq(lineage), "evidence_status"] = "TEST_ONLY_SYNTHETIC"
                table.loc[table.comparison_lineage_id.eq(lineage), "evidence_source"] = "tests/test_physical_quantities.py"
        return table

    @staticmethod
    def _write_csv(table, columns, directory, name):
        path = Path(directory) / name
        pd.DataFrame(table, columns=columns).to_csv(path, index=False)
        return path

    def test_production_boq_is_empty_and_cost_is_not_used_as_quantity_proxy(self):
        boq = load_component_boq(m.DEFAULT_COMPONENT_BOQ, self.components, self.empty_ref)
        self.assertTrue(boq.empty)
        coverage = build_physical_quantity_coverage(self.components, self.empty_ref, boq)
        self.assertEqual(len(coverage), len(self.components))
        self.assertTrue(coverage.quantity_mapping_status.eq("BOQ_MISSING").all())
        self.assertTrue((self.components.initial_cost_eur > 0).all())

    def test_valid_boq_maps_to_exact_parent_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_csv([self._boq_row()], COMPONENT_BOQ_COLUMNS, tmp, "boq.csv")
            boq = load_component_boq(path, self.components, self.empty_ref)
        self.assertEqual(len(boq), 1)
        self.assertEqual(boq.quantity_unit.iloc[0], "m2")
        coverage = build_physical_quantity_coverage(self.components, self.empty_ref, boq)
        row = coverage.loc[coverage.component_instance_id.eq(self._option_parent().component_instance_id)].iloc[0]
        self.assertEqual(row.quantity_mapping_status, "BOQ_MAPPED")
        self.assertEqual(int(row.assessment_inventory_line_count), 1)

    def test_unknown_parent_is_rejected(self):
        row = self._boq_row(component_instance_id="ci_unknown_component")
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_csv([row], COMPONENT_BOQ_COLUMNS, tmp, "boq.csv")
            with self.assertRaisesRegex(ValueError, "unknown component_instance_id"):
                load_component_boq(path, self.components, self.empty_ref)

    def test_parent_lineage_mismatch_is_rejected(self):
        row = self._boq_row(comparison_lineage_id="lineage_windows")
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_csv([row], COMPONENT_BOQ_COLUMNS, tmp, "boq.csv")
            with self.assertRaisesRegex(ValueError, "conflicts with parent component"):
                load_component_boq(path, self.components, self.empty_ref)

    def test_quantity_must_be_positive_and_source_backed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_csv([self._boq_row(quantity=0)], COMPONENT_BOQ_COLUMNS, tmp, "bad_qty.csv")
            with self.assertRaisesRegex(ValueError, "strictly positive"):
                load_component_boq(path, self.components, self.empty_ref)
            path = self._write_csv([self._boq_row(source_reference="")], COMPONENT_BOQ_COLUMNS, tmp, "bad_source.csv")
            with self.assertRaisesRegex(ValueError, "source_reference"):
                load_component_boq(path, self.components, self.empty_ref)

    def test_derived_quantity_requires_derivation_method(self):
        row = self._boq_row(source_status="DERIVED_FROM_DOCUMENTED_GEOMETRY", derivation_method="")
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_csv([row], COMPONENT_BOQ_COLUMNS, tmp, "boq.csv")
            with self.assertRaisesRegex(ValueError, "derivation_method"):
                load_component_boq(path, self.components, self.empty_ref)

    def test_unit_normalization_is_explicit_and_unsupported_unit_fails(self):
        self.assertEqual(normalize_physical_unit("m²"), "m2")
        self.assertEqual(normalize_physical_unit("kWp"), "kwp")
        with self.assertRaisesRegex(ValueError, "Unsupported physical quantity unit"):
            normalize_physical_unit("EUR")

    def test_one_event_can_expand_to_multiple_boq_lines_without_mutating_event_scalar(self):
        parent = self._option_parent()
        rows = [
            self._boq_row(parent, boq_line_id="boq_test_a", material_or_product_id="prod_test_a", quantity=100, quantity_unit="m2"),
            self._boq_row(parent, boq_line_id="boq_test_b", material_or_product_id="prod_test_b", quantity=500, quantity_unit="kg"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_csv(rows, COMPONENT_BOQ_COLUMNS, tmp, "boq.csv")
            boq = load_component_boq(path, self.components, self.empty_ref)
        comp = self.components.loc[self.components.component_instance_id.eq(parent.component_instance_id)]
        config, _ = resolve_horizon(self.base, "rics_60")
        _, _, ledger, boundary = renewal_costs_with_ledger_and_boundary(comp, self.futures, config, 42, central=True)
        self.assertTrue(ledger.event_quantity.isna().all())
        expanded = expand_lifecycle_events_with_boq(ledger, boq)
        self.assertEqual(len(expanded), 2 * len(ledger))
        self.assertEqual(expanded.event_boq_id.nunique(), len(expanded))
        self.assertEqual(set(expanded.quantity_unit), {"m2", "kg"})
        expanded_boundary = expand_boundary_states_with_boq(boundary, boq)
        self.assertEqual(len(expanded_boundary), 2)
        self.assertEqual(expanded_boundary.boundary_boq_state_id.nunique(), 2)

    def test_reference_presence_skeleton_explicitly_covers_all_known_lineages(self):
        presence = load_reference_component_presence(m.DEFAULT_REFERENCE_PRESENCE, self.components)
        self.assertEqual(len(presence), self.components.comparison_lineage_id.nunique())
        self.assertTrue(presence.reference_presence_status.eq("UNKNOWN").all())
        validate_reference_presence_consistency(presence, self.empty_ref)
        boq = load_component_boq(m.DEFAULT_COMPONENT_BOQ, self.components, self.empty_ref)
        skeleton = build_reference_coverage_skeleton(presence, self.empty_ref, boq)
        self.assertTrue(skeleton.comparison_coverage_status.eq("REFERENCE_PRESENCE_UNRESOLVED").all())
        self.assertTrue(skeleton.coverage_denominator_scope.eq("KNOWN_INTERVENTION_LINEAGES_ONLY").all())
        self.assertNotIn("coverage_percent", skeleton.columns)

    def test_documented_absence_is_distinct_from_missing_reference_data(self):
        presence = self._presence({"lineage_pv_modules": "ABSENT_DOCUMENTED"})
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_csv(presence.to_dict("records"), REFERENCE_PRESENCE_COLUMNS, tmp, "presence.csv")
            loaded = load_reference_component_presence(path, self.components)
        validate_reference_presence_consistency(loaded, self.empty_ref)
        skeleton = build_reference_coverage_skeleton(loaded, self.empty_ref, load_component_boq(m.DEFAULT_COMPONENT_BOQ, self.components, self.empty_ref))
        row = skeleton.loc[skeleton.comparison_lineage_id.eq("lineage_pv_modules")].iloc[0]
        self.assertEqual(row.comparison_coverage_status, "REFERENCE_ABSENCE_DOCUMENTED")
        self.assertEqual(row.reference_quantity_mapping_status, "NOT_APPLICABLE_DOCUMENTED_ABSENCE")

    def test_present_declaration_requires_executable_reference_inventory(self):
        presence = self._presence({"lineage_windows": "PRESENT_DOCUMENTED"})
        with self.assertRaisesRegex(ValueError, "PRESENT_DOCUMENTED"):
            validate_reference_presence_consistency(presence, self.empty_ref)

    def test_unknown_declaration_cannot_coexist_with_reference_inventory_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = self._write_csv([self._reference_row()], REFERENCE_INVENTORY_COLUMNS, tmp, "ref.csv")
            ref = load_physical_reference_inventory(ref_path, self.reference_id)
        presence = self._presence()
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            validate_reference_presence_consistency(presence, ref)

    def test_present_reference_with_boq_is_quantity_mapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ref_path = self._write_csv([self._reference_row()], REFERENCE_INVENTORY_COLUMNS, tmp, "ref.csv")
            ref = load_physical_reference_inventory(ref_path, self.reference_id)
            presence = self._presence({"lineage_windows": "PRESENT_DOCUMENTED"})
            presence_path = self._write_csv(presence.to_dict("records"), REFERENCE_PRESENCE_COLUMNS, tmp, "presence.csv")
            presence = load_reference_component_presence(presence_path, self.components)
            ref_parent = ref.iloc[0]
            boq_row = self._boq_row(
                ref_parent,
                boq_line_id="boq_reference_window",
                material_or_product_id="prod_reference_window",
                item_label="Synthetic reference-window product quantity",
                quantity=80.0,
                quantity_unit="m2",
            )
            boq_path = self._write_csv([boq_row], COMPONENT_BOQ_COLUMNS, tmp, "boq.csv")
            boq = load_component_boq(boq_path, self.components, ref)
        validate_reference_presence_consistency(presence, ref)
        skeleton = build_reference_coverage_skeleton(presence, ref, boq)
        row = skeleton.loc[skeleton.comparison_lineage_id.eq("lineage_windows")].iloc[0]
        self.assertEqual(row.comparison_coverage_status, "REFERENCE_QUANTITY_MAPPED")
        self.assertEqual(int(row.reference_assessment_inventory_line_count), 1)
        coverage = build_physical_quantity_coverage(self.components, ref, boq)
        ref_cov = coverage.loc[coverage.component_instance_id.eq("ci_reference_test_window")].iloc[0]
        self.assertTrue(bool(ref_cov.primary_component_quantity_available))
        self.assertEqual(ref_cov.primary_component_unit, "m2")
        self.assertEqual(ref_cov.quantity_mapping_status, "BOQ_MAPPED")

    def test_run_writes_m17_outputs_without_fabricating_quantities(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            m.run(output_dir=out, simulations=2, seed=123, charts=False, convergence_enabled=False,
                  horizon_mode="legacy_30")
            required = [
                "resolved_component_boq.csv",
                "resolved_reference_component_presence.csv",
                "physical_quantity_coverage.csv",
                "reference_coverage_skeleton.csv",
                "lifecycle_event_boq_quantities.csv",
                "rsp_boundary_boq_state.csv",
                "reference_lifecycle_event_boq_quantities.csv",
                "reference_rsp_boundary_boq_state.csv",
                "physical_boq_status.json",
            ]
            for name in required:
                self.assertTrue((out / name).exists(), name)
            boq = pd.read_csv(out / "resolved_component_boq.csv")
            self.assertTrue(boq.empty)
            qcov = pd.read_csv(out / "physical_quantity_coverage.csv")
            self.assertEqual(len(qcov), 13)
            self.assertTrue(qcov.quantity_mapping_status.eq("BOQ_MISSING").all())
            event_map = pd.read_csv(out / "lifecycle_event_boq_quantities.csv")
            self.assertTrue(event_map.empty)


if __name__ == "__main__":
    unittest.main()
