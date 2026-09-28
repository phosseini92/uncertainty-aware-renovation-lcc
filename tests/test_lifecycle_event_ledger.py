import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import renovation_lcc as m
from component_lifecycle import (
    load_components,
    renewal_costs,
    renewal_costs_with_ledger,
)
from lifecycle_events import (
    LIFECYCLE_EVENT_COLUMNS,
    validate_lifecycle_event_ledger,
)


class LifecycleEventLedgerTests(unittest.TestCase):
    def setUp(self):
        self.config = m.load_config()
        self.scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        self.components = load_components(m.DEFAULT_COMPONENTS, self.scenarios)
        self.futures = m.sample_uncertain_futures(80, 4242, self.config)

    def test_canonical_ledger_reconciles_exactly_to_legacy_events(self):
        totals_old_api, legacy_old_api = renewal_costs(
            self.components, self.futures, self.config, 4242, retain_events=True
        )
        totals, legacy, ledger = renewal_costs_with_ledger(
            self.components, self.futures, self.config, 4242
        )
        pd.testing.assert_frame_equal(totals_old_api, totals)
        pd.testing.assert_frame_equal(legacy_old_api, legacy)
        self.assertEqual(tuple(ledger.columns), LIFECYCLE_EVENT_COLUMNS)
        self.assertTrue(ledger.event_type.eq("B4_REPLACEMENT").all())
        self.assertEqual(len(ledger), len(legacy))

        keys = ["scenario", "component", "future_id", "renewal_number"]
        legacy_sorted = legacy.sort_values(keys).reset_index(drop=True)
        scenario_names = self.scenarios.set_index("scenario_id").scenario.to_dict()
        component_names = self.components.set_index("component_instance_id").component.to_dict()
        ledger_check = ledger.assign(
            scenario=ledger.scenario_id.map(scenario_names),
            component=ledger.component_instance_id.map(component_names),
            renewal_number=ledger.component_generation,
            renewal_time_years=ledger.event_time_years,
            preceding_service_life_years=ledger.sampled_service_life_years,
        ).sort_values(keys).reset_index(drop=True)
        np.testing.assert_allclose(
            ledger_check.renewal_time_years,
            legacy_sorted.renewal_time_years,
            rtol=0,
            atol=0,
        )
        np.testing.assert_allclose(
            ledger_check.preceding_service_life_years,
            legacy_sorted.preceding_service_life_years,
            rtol=0,
            atol=0,
        )
        self.assertEqual(
            ledger_check[["scenario", "component", "future_id", "renewal_number"]].to_dict("records"),
            legacy_sorted[["scenario", "component", "future_id", "renewal_number"]].to_dict("records"),
        )

    def test_ledger_validation_rejects_duplicate_identity_and_invalid_time(self):
        _, _, ledger = renewal_costs_with_ledger(
            self.components, self.futures.iloc[:10], self.config, 4242
        )
        self.assertFalse(ledger.empty)
        duplicate = pd.concat([ledger, ledger.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            validate_lifecycle_event_ledger(duplicate)
        invalid = ledger.copy()
        invalid.loc[invalid.index[0], "event_time_years"] = 0
        with self.assertRaises(ValueError):
            validate_lifecycle_event_ledger(invalid)

    def test_m1_does_not_invent_unavailable_physical_or_calendar_data(self):
        _, _, ledger = renewal_costs_with_ledger(
            self.components, self.futures.iloc[:20], self.config, 4242
        )
        # v2.1 has no documented physical quantities/units or assessment base year.
        self.assertTrue(ledger.calendar_year.isna().all())
        self.assertTrue(ledger.event_quantity.isna().all())
        self.assertTrue(ledger.event_unit.isna().all())
        self.assertTrue(ledger.physical_state_before.isna().all())
        self.assertTrue(ledger.physical_state_after.isna().all())
        self.assertFalse(ledger.scenario_id.str.startswith("legacy_").any())
        self.assertFalse(ledger.component_instance_id.str.startswith("legacy_").any())
        self.assertFalse(ledger.comparison_lineage_id.str.startswith("legacy_").any())
        self.assertTrue(ledger.service_life_basis.eq("FULL_SERVICE_LIFE").all())


    def test_stable_ids_survive_display_label_changes(self):
        base_components = self.components.copy()
        _, _, base_ledger = renewal_costs_with_ledger(
            base_components, self.futures.iloc[:25], self.config, 4242
        )

        renamed = base_components.copy()
        renamed["scenario"] = renamed["scenario"].replace({
            "Envelope retrofit": "Envelope package renamed for display",
            "Envelope + heat pump": "Heat-pump package renamed for display",
            "Deep renovation + PV": "Deep package renamed for display",
        })
        renamed["component"] = renamed["component"] + " display"
        _, _, renamed_ledger = renewal_costs_with_ledger(
            renamed, self.futures.iloc[:25], self.config, 4242
        )
        pd.testing.assert_frame_equal(base_ledger, renamed_ledger, check_exact=True)

    def test_explicit_lineage_pairs_same_component_family_across_options(self):
        by_lineage = self.components.groupby("comparison_lineage_id")
        for _, group in by_lineage:
            self.assertEqual(group.component_type_id.nunique(), 1)
            self.assertEqual(group.uncertainty_key.nunique(), 1)
        windows = self.components.loc[self.components.component.eq("Windows")]
        self.assertEqual(windows.comparison_lineage_id.nunique(), 1)
        self.assertEqual(len(windows), 3)

    def test_legacy_component_fixture_without_ids_remains_supported(self):
        legacy = self.components.drop(
            columns=["scenario_id", "component_instance_id", "comparison_lineage_id", "component_type_id"]
        )
        _, _, ledger = renewal_costs_with_ledger(
            legacy, self.futures.iloc[:12], self.config, 4242
        )
        self.assertTrue(ledger.scenario_id.str.startswith("legacy_").all())
        self.assertTrue(ledger.component_instance_id.str.startswith("legacy_").all())
        self.assertTrue(ledger.comparison_lineage_id.str.startswith("legacy_").all())

    def test_run_writes_canonical_ledger_without_changing_summary_path(self):
        with tempfile.TemporaryDirectory() as d:
            summary = m.run(
                output_dir=Path(d), simulations=120, seed=4242,
                charts=False, convergence_enabled=False,
            )
            path = Path(d) / "lifecycle_event_ledger.csv"
            self.assertTrue(path.exists())
            ledger = pd.read_csv(path)
            self.assertEqual(tuple(ledger.columns), LIFECYCLE_EVENT_COLUMNS)
            self.assertFalse(ledger.empty)
            # Existing scenario summary remains populated and structurally valid.
            self.assertFalse(summary.empty)
            self.assertIn("median_net_benefit_eur", summary.columns)


if __name__ == "__main__":
    unittest.main()
