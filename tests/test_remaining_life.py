import copy
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import renovation_lcc as m
from component_lifecycle import renewal_costs_with_ledger
from horizon import resolve_horizon
from lifecycle_events import validate_lifecycle_event_ledger


class RemainingLifeArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.base = m.load_config()
        self.futures = m.sample_uncertain_futures(80, 20260726, self.base)

    @staticmethod
    def _retained_fixture(**overrides):
        row = dict(
            scenario="Test retained option",
            component="Test window",
            uncertainty_key="legacy_full_window",
            initial_cost_eur=1000.0,
            lifetime_distribution="fixed",
            minimum_lifetime_years=20.0,
            most_likely_lifetime_years=20.0,
            maximum_lifetime_years=20.0,
            replacement_cost_factor=1.0,
            maintenance_cost_eur=0.0,
            initial_component_state="RETAINED_EXISTING",
            age_at_t0_years=13.0,
            remaining_life_distribution="fixed",
            remaining_life_min_years=np.nan,
            remaining_life_mode_years=np.nan,
            remaining_life_max_years=np.nan,
            remaining_life_fixed_years=7.0,
            remaining_life_uncertainty_key="remaining_window",
            full_life_distribution="fixed",
            full_life_min_years=np.nan,
            full_life_mode_years=np.nan,
            full_life_max_years=np.nan,
            full_life_fixed_years=20.0,
            full_life_uncertainty_key="full_window",
        )
        row.update(overrides)
        return pd.DataFrame([row])

    @staticmethod
    def _new_fixture(**overrides):
        row = dict(
            scenario="Test new option",
            component="Test component",
            uncertainty_key="legacy_component",
            initial_cost_eur=1000.0,
            lifetime_distribution="fixed",
            minimum_lifetime_years=10.0,
            most_likely_lifetime_years=10.0,
            maximum_lifetime_years=10.0,
            replacement_cost_factor=1.0,
            maintenance_cost_eur=0.0,
            initial_component_state="NEW_AT_T0",
        )
        row.update(overrides)
        return pd.DataFrame([row])

    def test_fixed_retained_golden_schedule_across_30_50_60(self):
        component = self._retained_fixture()
        one_future = self.futures.iloc[:1]
        expected = {
            "legacy_30": [7.0, 27.0],
            "levels_50": [7.0, 27.0, 47.0],
            "rics_60": [7.0, 27.0, 47.0],
        }
        for mode, times in expected.items():
            config, _ = resolve_horizon(self.base, mode)
            totals, legacy, ledger = renewal_costs_with_ledger(
                component, one_future, config, 4242, central=True
            )
            self.assertEqual(legacy.renewal_time_years.tolist(), times)
            self.assertEqual(ledger.event_time_years.tolist(), times)
            self.assertEqual(totals.first_service_life_years.tolist(), [7.0])
            self.assertEqual(ledger.service_life_basis.tolist()[0], "REMAINING_LIFE")
            self.assertTrue(ledger.service_life_basis.iloc[1:].eq("FULL_SERVICE_LIFE").all())
            self.assertEqual(ledger.sampled_service_life_years.tolist()[0], 7.0)
            self.assertEqual(ledger.sampled_service_life_years.tolist()[1:], [20.0] * (len(times) - 1))
            self.assertEqual(ledger.random_stream_key.tolist()[0], "remaining_life:remaining_window:initial")
            for generation, key in enumerate(ledger.random_stream_key.tolist()[1:], start=2):
                self.assertEqual(key, f"lifetime:full_window:renewal:{generation}")

    def test_retained_component_requires_explicit_remaining_life(self):
        component = self._retained_fixture().drop(columns=[
            "remaining_life_distribution", "remaining_life_min_years",
            "remaining_life_mode_years", "remaining_life_max_years",
            "remaining_life_fixed_years", "remaining_life_uncertainty_key",
        ])
        with self.assertRaisesRegex(ValueError, "MISSING_REMAINING_LIFE_MODEL_FOR_RETAINED_COMPONENT"):
            renewal_costs_with_ledger(component, self.futures.iloc[:2], self.base, 42)

    def test_new_component_must_not_declare_remaining_life(self):
        component = self._new_fixture(
            remaining_life_distribution="fixed",
            remaining_life_fixed_years=4.0,
            remaining_life_uncertainty_key="not_allowed",
        )
        with self.assertRaisesRegex(ValueError, "NEW_AT_T0 components must not declare remaining-life fields"):
            renewal_costs_with_ledger(component, self.futures.iloc[:2], self.base, 42)

    def test_new_at_t0_age_must_be_zero_or_blank(self):
        bad = self._new_fixture(age_at_t0_years=3.0)
        with self.assertRaisesRegex(ValueError, "age must be zero or blank"):
            renewal_costs_with_ledger(bad, self.futures.iloc[:1], self.base, 42)
        good = self._new_fixture(age_at_t0_years=0.0)
        _, _, ledger = renewal_costs_with_ledger(good, self.futures.iloc[:1], self.base, 42, central=True)
        self.assertFalse(ledger.empty)

    def test_age_at_t0_is_metadata_not_a_remaining_life_formula(self):
        a = self._retained_fixture(age_at_t0_years=1.0)
        b = self._retained_fixture(age_at_t0_years=49.0)
        _, _, ledger_a = renewal_costs_with_ledger(a, self.futures.iloc[:20], self.base, 42)
        _, _, ledger_b = renewal_costs_with_ledger(b, self.futures.iloc[:20], self.base, 42)
        pd.testing.assert_frame_equal(ledger_a, ledger_b, check_exact=True)

    def test_explicit_full_life_model_controls_new_and_post_replacement_generations(self):
        component = self._new_fixture(
            full_life_distribution="fixed",
            full_life_fixed_years=20.0,
            full_life_uncertainty_key="explicit_full",
        )
        config, _ = resolve_horizon(self.base, "levels_50")
        _, legacy, ledger = renewal_costs_with_ledger(
            component, self.futures.iloc[:1], config, 42, central=True
        )
        self.assertEqual(legacy.renewal_time_years.tolist(), [20.0, 40.0])
        self.assertTrue(ledger.service_life_basis.eq("FULL_SERVICE_LIFE").all())
        self.assertEqual(ledger.random_stream_key.tolist(), [
            "lifetime:explicit_full:renewal:1",
            "lifetime:explicit_full:renewal:2",
        ])

    def test_remaining_and_full_life_random_streams_are_independent(self):
        a = self._retained_fixture(
            remaining_life_distribution="triangular",
            remaining_life_fixed_years=np.nan,
            remaining_life_min_years=4.0,
            remaining_life_mode_years=7.0,
            remaining_life_max_years=10.0,
            full_life_distribution="triangular",
            full_life_fixed_years=np.nan,
            full_life_min_years=15.0,
            full_life_mode_years=20.0,
            full_life_max_years=25.0,
            full_life_uncertainty_key="full_a",
        )
        b = a.copy()
        b["full_life_uncertainty_key"] = "full_b"
        config, _ = resolve_horizon(self.base, "rics_60")
        _, _, la = renewal_costs_with_ledger(a, self.futures, config, 4242)
        _, _, lb = renewal_costs_with_ledger(b, self.futures, config, 4242)
        first_a = la.loc[la.component_generation.eq(1)].sort_values("future_id")
        first_b = lb.loc[lb.component_generation.eq(1)].sort_values("future_id")
        np.testing.assert_array_equal(first_a.event_time_years.to_numpy(), first_b.event_time_years.to_numpy())
        np.testing.assert_array_equal(first_a.sampled_service_life_years.to_numpy(),
                                      first_b.sampled_service_life_years.to_numpy())
        second_a = la.loc[la.component_generation.eq(2)].sort_values("future_id")
        second_b = lb.loc[lb.component_generation.eq(2)].sort_values("future_id")
        self.assertEqual(len(second_a), len(second_b))
        self.assertFalse(np.array_equal(second_a.sampled_service_life_years.to_numpy(),
                                        second_b.sampled_service_life_years.to_numpy()))

    def test_ledger_rejects_remaining_life_basis_after_generation_one(self):
        component = self._retained_fixture()
        config, _ = resolve_horizon(self.base, "levels_50")
        _, _, ledger = renewal_costs_with_ledger(component, self.futures.iloc[:1], config, 42, central=True)
        bad = ledger.copy()
        bad.loc[bad.component_generation.eq(2), "service_life_basis"] = "REMAINING_LIFE"
        with self.assertRaisesRegex(ValueError, "first replacement generation"):
            validate_lifecycle_event_ledger(bad)


    def test_csv_loader_accepts_explicit_mixed_new_and_retained_states(self):
        import tempfile
        from component_lifecycle import load_components

        scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        raw = pd.read_csv(m.DEFAULT_COMPONENTS)
        raw["initial_component_state"] = "NEW_AT_T0"
        text_fields = {"remaining_life_distribution", "remaining_life_uncertainty_key"}
        for field in [
            "remaining_life_distribution", "remaining_life_min_years",
            "remaining_life_mode_years", "remaining_life_max_years",
            "remaining_life_fixed_years", "remaining_life_uncertainty_key",
        ]:
            raw[field] = pd.Series([pd.NA if field in text_fields else np.nan] * len(raw),
                                   dtype="object" if field in text_fields else "float64")
        idx = raw.index[0]
        raw.loc[idx, "initial_component_state"] = "RETAINED_EXISTING"
        raw.loc[idx, "remaining_life_distribution"] = "fixed"
        raw.loc[idx, "remaining_life_fixed_years"] = 5.0
        raw.loc[idx, "remaining_life_uncertainty_key"] = "retained_loader_test"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "components.csv"
            raw.to_csv(path, index=False)
            loaded = load_components(path, scenarios)
        self.assertEqual(loaded.loc[idx, "initial_component_state"], "RETAINED_EXISTING")
        _, _, ledger = renewal_costs_with_ledger(loaded.iloc[[idx]], self.futures.iloc[:1], self.base, 42, central=True)
        self.assertEqual(ledger.event_time_years.iloc[0], 5.0)
        self.assertEqual(ledger.service_life_basis.iloc[0], "REMAINING_LIFE")

    def test_same_lineage_cannot_silently_use_different_full_life_streams(self):
        a = self._retained_fixture(
            scenario="A", component="Window A", full_life_uncertainty_key="full_a",
            remaining_life_uncertainty_key="remaining_shared",
        )
        b = self._retained_fixture(
            scenario="B", component="Window B", full_life_uncertainty_key="full_b",
            remaining_life_uncertainty_key="remaining_shared",
        )
        combined = pd.concat([a, b], ignore_index=True)
        # Force the two rows into one explicit comparison lineage.
        combined["comparison_lineage_id"] = "lineage_test_windows"
        combined["component_type_id"] = "ctype_test_windows"
        combined["component_instance_id"] = ["ci_test_a", "ci_test_b"]
        combined["scenario_id"] = ["scn_test_a", "scn_test_b"]
        with self.assertRaisesRegex(ValueError, "multiple full-life uncertainty keys"):
            renewal_costs_with_ledger(combined, self.futures.iloc[:2], self.base, 42)


if __name__ == "__main__":
    unittest.main()
