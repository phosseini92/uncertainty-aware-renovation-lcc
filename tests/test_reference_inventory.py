import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import renovation_lcc as m
from reference_inventory import (
    REFERENCE_INVENTORY_COLUMNS,
    empty_physical_reference_inventory,
    inventory_status,
    load_physical_reference_inventory,
    reference_inventory_to_lifecycle_components,
    validate_reference_lineage_compatibility,
)
from component_lifecycle import renewal_costs_with_ledger_and_boundary
from horizon import resolve_horizon


class PhysicalReferenceInventoryTests(unittest.TestCase):
    def setUp(self):
        scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        ref = scenarios.loc[scenarios.is_reference.eq(1)].iloc[0]
        self.reference_scenario_id = str(ref.scenario_id)
        self.reference_name = str(ref.scenario)
        self.base = m.load_config()
        self.futures = m.sample_uncertain_futures(2, 20260726, self.base)

    def _valid_row(self):
        return {
            "scenario_id": self.reference_scenario_id,
            "component_instance_id": "ci_reference_test_window",
            "comparison_lineage_id": "lineage_test_window",
            "component_type_id": "ctype_test_window",
            "component": "Synthetic reference window",
            "initial_component_state": "RETAINED_EXISTING",
            "physical_quantity": 10.0,
            "physical_unit": "m2",
            "remaining_life_distribution": "fixed",
            "remaining_life_min_years": "",
            "remaining_life_mode_years": "",
            "remaining_life_max_years": "",
            "remaining_life_fixed_years": 7.0,
            "remaining_life_uncertainty_key": "remaining_reference_test_window",
            "full_life_distribution": "fixed",
            "full_life_min_years": "",
            "full_life_mode_years": "",
            "full_life_max_years": "",
            "full_life_fixed_years": 20.0,
            "full_life_uncertainty_key": "full_reference_test_window",
            "age_at_t0_years": 13.0,
            "source_status": "TEST_ONLY_SYNTHETIC",
            "source_reference": "tests/test_reference_inventory.py",
            "notes": "Synthetic fixture; not research data.",
        }

    def test_empty_main_inventory_is_explicitly_unpopulated(self):
        inv = load_physical_reference_inventory(m.DEFAULT_REFERENCE_INVENTORY, self.reference_scenario_id)
        self.assertTrue(inv.empty)
        self.assertEqual(inventory_status(inv)["status"], "UNPOPULATED_SOURCE_DATA_ABSENT")

    def test_valid_synthetic_reference_uses_shared_lifecycle_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference.csv"
            pd.DataFrame([self._valid_row()], columns=REFERENCE_INVENTORY_COLUMNS).to_csv(path, index=False)
            inv = load_physical_reference_inventory(path, self.reference_scenario_id)
        components = reference_inventory_to_lifecycle_components(inv, self.reference_name)
        config, _ = resolve_horizon(self.base, "levels_50")
        totals, legacy, ledger, boundary = renewal_costs_with_ledger_and_boundary(
            components, self.futures.iloc[:1], config, 42, central=True
        )
        self.assertEqual(ledger.event_time_years.tolist(), [7.0, 27.0, 47.0])
        self.assertEqual(float(totals.pv_replacement_cost_eur.iloc[0]), 0.0)
        self.assertTrue((legacy.nominal_replacement_cost_eur == 0).all())
        self.assertEqual(int(boundary.component_generation_at_boundary.iloc[0]), 3)
        self.assertEqual(float(boundary.remaining_life_at_boundary_years.iloc[0]), 17.0)

    def test_retained_reference_requires_remaining_life(self):
        row = self._valid_row()
        row["remaining_life_distribution"] = ""
        row["remaining_life_fixed_years"] = ""
        row["remaining_life_uncertainty_key"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference.csv"
            pd.DataFrame([row], columns=REFERENCE_INVENTORY_COLUMNS).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "MISSING_REMAINING_LIFE_MODEL_FOR_RETAINED_COMPONENT"):
                load_physical_reference_inventory(path, self.reference_scenario_id)

    def test_reference_inventory_requires_physical_quantity_and_source(self):
        row = self._valid_row()
        row["physical_quantity"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference.csv"
            pd.DataFrame([row], columns=REFERENCE_INVENTORY_COLUMNS).to_csv(path, index=False)
            with self.assertRaises(ValueError):
                load_physical_reference_inventory(path, self.reference_scenario_id)

    def test_reference_inventory_cannot_use_nonreference_scenario(self):
        row = self._valid_row()
        row["scenario_id"] = "scn_envelope_retrofit"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference.csv"
            pd.DataFrame([row], columns=REFERENCE_INVENTORY_COLUMNS).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "declared reference scenario_id"):
                load_physical_reference_inventory(path, self.reference_scenario_id)

    def test_reference_lineage_must_match_intervention_type_and_full_life_stream(self):
        row = self._valid_row()
        row["comparison_lineage_id"] = "lineage_windows"
        row["component_type_id"] = "ctype_windows"
        row["full_life_uncertainty_key"] = "wrong_windows_stream"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference.csv"
            pd.DataFrame([row], columns=REFERENCE_INVENTORY_COLUMNS).to_csv(path, index=False)
            inv = load_physical_reference_inventory(path, self.reference_scenario_id)
        components = m.load_components(m.DEFAULT_COMPONENTS, m.load_scenarios(m.DEFAULT_INPUT))
        with self.assertRaisesRegex(ValueError, "full-life uncertainty stream"):
            validate_reference_lineage_compatibility(inv, components)

    def test_run_writes_boundary_and_reference_status_without_inventing_reference_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            m.run(output_dir=out, simulations=3, seed=123, charts=False, convergence_enabled=False,
                  horizon_mode="legacy_30")
            boundary = pd.read_csv(out / "rsp_boundary_state.csv")
            self.assertEqual(len(boundary), 3 * 13)
            self.assertTrue((out / "reference_inventory_status.json").exists())
            resolved_ref = pd.read_csv(out / "resolved_physical_reference_inventory.csv")
            self.assertTrue(resolved_ref.empty)
            ref_boundary = pd.read_csv(out / "reference_rsp_boundary_state.csv")
            self.assertTrue(ref_boundary.empty)

    def test_run_with_synthetic_reference_populates_reference_ledgers_without_changing_reference_npv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ref_path = tmp / "reference.csv"
            pd.DataFrame([self._valid_row()], columns=REFERENCE_INVENTORY_COLUMNS).to_csv(ref_path, index=False)
            out = tmp / "out"
            m.run(output_dir=out, simulations=2, seed=123, charts=False, convergence_enabled=False,
                  horizon_mode="legacy_30", reference_inventory_path=ref_path)
            ref_ledger = pd.read_csv(out / "reference_lifecycle_event_ledger.csv")
            ref_boundary = pd.read_csv(out / "reference_rsp_boundary_state.csv")
            summary = pd.read_csv(out / "scenario_summary.csv")
            self.assertFalse(ref_ledger.empty)
            self.assertEqual(len(ref_boundary), 2)
            ref_rows = summary.loc[summary.scenario.eq(self.reference_name)]
            self.assertTrue((ref_rows.median_net_benefit_eur == 0).all())


if __name__ == "__main__":
    unittest.main()
