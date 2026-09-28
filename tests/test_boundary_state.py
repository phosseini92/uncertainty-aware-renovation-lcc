import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import renovation_lcc as m
from component_lifecycle import renewal_costs_with_ledger_and_boundary
from boundary_state import validate_rsp_boundary_state
from horizon import resolve_horizon


class BoundaryStateTests(unittest.TestCase):
    def setUp(self):
        self.base = m.load_config()
        self.futures = m.sample_uncertain_futures(4, 20260726, self.base)

    @staticmethod
    def _new_fixed(life=20.0, **overrides):
        row = dict(
            scenario_id="scn_test_new",
            component_instance_id="ci_test_new",
            comparison_lineage_id="lineage_test_new",
            component_type_id="ctype_test_new",
            scenario="Test new",
            component="Test new component",
            uncertainty_key="test_new",
            initial_cost_eur=1000.0,
            lifetime_distribution="fixed",
            minimum_lifetime_years=life,
            most_likely_lifetime_years=life,
            maximum_lifetime_years=life,
            replacement_cost_factor=1.0,
            maintenance_cost_eur=0.0,
            initial_component_state="NEW_AT_T0",
            full_life_distribution="fixed",
            full_life_fixed_years=life,
            full_life_uncertainty_key="full_test_new",
        )
        row.update(overrides)
        return pd.DataFrame([row])

    @staticmethod
    def _retained_fixed(remaining=7.0, full=20.0, age=13.0, **overrides):
        row = dict(
            scenario_id="scn_test_retained",
            component_instance_id="ci_test_retained",
            comparison_lineage_id="lineage_test_retained",
            component_type_id="ctype_test_retained",
            scenario="Test retained",
            component="Test retained component",
            uncertainty_key="test_retained",
            initial_cost_eur=1000.0,
            lifetime_distribution="fixed",
            minimum_lifetime_years=full,
            most_likely_lifetime_years=full,
            maximum_lifetime_years=full,
            replacement_cost_factor=1.0,
            maintenance_cost_eur=0.0,
            initial_component_state="RETAINED_EXISTING",
            age_at_t0_years=age,
            remaining_life_distribution="fixed",
            remaining_life_fixed_years=remaining,
            remaining_life_uncertainty_key="remaining_test_retained",
            full_life_distribution="fixed",
            full_life_fixed_years=full,
            full_life_uncertainty_key="full_test_retained",
        )
        row.update(overrides)
        return pd.DataFrame([row])

    def test_new_component_boundary_state_at_50(self):
        config, _ = resolve_horizon(self.base, "levels_50")
        _, _, ledger, boundary = renewal_costs_with_ledger_and_boundary(
            self._new_fixed(20.0), self.futures.iloc[:1], config, 42, central=True
        )
        self.assertEqual(ledger.event_time_years.tolist(), [20.0, 40.0])
        row = boundary.iloc[0]
        self.assertEqual(int(row.component_generation_at_boundary), 2)
        self.assertEqual(float(row.assessment_interval_start_years), 40.0)
        self.assertEqual(float(row.installation_time_years), 40.0)
        self.assertEqual(float(row.age_within_assessment_years), 10.0)
        self.assertEqual(float(row.age_at_boundary_years), 10.0)
        self.assertEqual(float(row.next_replacement_time_years), 60.0)
        self.assertEqual(float(row.remaining_life_at_boundary_years), 10.0)
        self.assertEqual(row.service_life_basis, "FULL_SERVICE_LIFE")
        self.assertFalse(bool(row.replacement_due_at_boundary))

    def test_retained_component_boundary_state_at_50(self):
        config, _ = resolve_horizon(self.base, "levels_50")
        _, _, ledger, boundary = renewal_costs_with_ledger_and_boundary(
            self._retained_fixed(7.0, 20.0, 13.0), self.futures.iloc[:1], config, 42, central=True
        )
        self.assertEqual(ledger.event_time_years.tolist(), [7.0, 27.0, 47.0])
        row = boundary.iloc[0]
        self.assertEqual(int(row.component_generation_at_boundary), 3)
        self.assertEqual(float(row.installation_time_years), 47.0)
        self.assertEqual(float(row.age_at_boundary_years), 3.0)
        self.assertEqual(float(row.next_replacement_time_years), 67.0)
        self.assertEqual(float(row.remaining_life_at_boundary_years), 17.0)
        self.assertEqual(row.service_life_basis, "FULL_SERVICE_LIFE")

    def test_retained_generation_zero_preserves_age_provenance(self):
        config, _ = resolve_horizon(self.base, "legacy_30")
        _, _, ledger, boundary = renewal_costs_with_ledger_and_boundary(
            self._retained_fixed(40.0, 20.0, 13.0), self.futures.iloc[:1], config, 42, central=True
        )
        self.assertTrue(ledger.empty)
        row = boundary.iloc[0]
        self.assertEqual(int(row.component_generation_at_boundary), 0)
        self.assertEqual(float(row.installation_time_years), -13.0)
        self.assertEqual(float(row.age_at_boundary_years), 43.0)
        self.assertEqual(float(row.remaining_life_at_boundary_years), 10.0)
        self.assertEqual(row.service_life_basis, "REMAINING_LIFE")

    def test_retained_unknown_age_remains_unknown(self):
        config, _ = resolve_horizon(self.base, "legacy_30")
        comp = self._retained_fixed(40.0, 20.0, np.nan)
        _, _, _, boundary = renewal_costs_with_ledger_and_boundary(
            comp, self.futures.iloc[:1], config, 42, central=True
        )
        self.assertTrue(pd.isna(boundary.installation_time_years.iloc[0]))
        self.assertTrue(pd.isna(boundary.age_at_boundary_years.iloc[0]))
        self.assertEqual(float(boundary.age_within_assessment_years.iloc[0]), 30.0)

    def test_event_exactly_at_boundary_is_excluded_but_due(self):
        config, _ = resolve_horizon(self.base, "levels_50")
        _, _, ledger, boundary = renewal_costs_with_ledger_and_boundary(
            self._new_fixed(25.0), self.futures.iloc[:1], config, 42, central=True
        )
        self.assertEqual(ledger.event_time_years.tolist(), [25.0])
        row = boundary.iloc[0]
        self.assertEqual(int(row.component_generation_at_boundary), 1)
        self.assertEqual(float(row.next_replacement_time_years), 50.0)
        self.assertEqual(float(row.remaining_life_at_boundary_years), 0.0)
        self.assertTrue(bool(row.replacement_due_at_boundary))

    def test_one_boundary_state_per_future_component(self):
        config, _ = resolve_horizon(self.base, "rics_60")
        _, _, _, boundary = renewal_costs_with_ledger_and_boundary(
            self._new_fixed(20.0), self.futures, config, 42, central=True
        )
        self.assertEqual(len(boundary), len(self.futures))
        self.assertEqual(boundary.boundary_state_id.nunique(), len(self.futures))
        validate_rsp_boundary_state(boundary)

    def test_boundary_id_is_label_invariant_when_stable_ids_are_fixed(self):
        config, _ = resolve_horizon(self.base, "levels_50")
        a = self._new_fixed()
        b = self._new_fixed(scenario="Renamed scenario", component="Renamed component")
        _, _, _, ba = renewal_costs_with_ledger_and_boundary(a, self.futures.iloc[:2], config, 42, central=True)
        _, _, _, bb = renewal_costs_with_ledger_and_boundary(b, self.futures.iloc[:2], config, 42, central=True)
        self.assertEqual(ba.boundary_state_id.tolist(), bb.boundary_state_id.tolist())
        comparable = [c for c in ba.columns if c not in {"scenario", "component"}]
        pd.testing.assert_frame_equal(ba[comparable], bb[comparable], check_exact=True)


if __name__ == "__main__":
    unittest.main()
