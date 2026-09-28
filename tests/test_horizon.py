import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import renovation_lcc as m
from component_lifecycle import load_components, renewal_costs_with_ledger
from horizon import HORIZON_PROFILES, infer_horizon_mode, resolve_horizon


class HorizonArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.base = m.load_config()
        self.scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        self.components = load_components(m.DEFAULT_COMPONENTS, self.scenarios)
        self.futures = m.sample_uncertain_futures(100, 20260726, self.base)

    def test_named_profiles_are_exactly_30_50_60(self):
        self.assertEqual(dict(HORIZON_PROFILES), {
            "legacy_30": 30,
            "levels_50": 50,
            "rics_60": 60,
        })
        for mode, years in HORIZON_PROFILES.items():
            resolved, meta = resolve_horizon(self.base, mode)
            self.assertEqual(resolved["analysis_years"], years)
            self.assertEqual(meta.mode, mode)
            self.assertEqual(meta.years, years)
            self.assertEqual(meta.source, "profile_override")
            # Resolution must never mutate the caller's config.
            self.assertEqual(self.base["analysis_years"], 30)

    def test_default_resolution_preserves_config_and_infers_legacy_mode(self):
        resolved, meta = resolve_horizon(self.base)
        self.assertEqual(resolved, self.base)
        self.assertIsNot(resolved, self.base)
        self.assertEqual(meta.mode, "legacy_30")
        self.assertEqual(meta.years, 30)
        self.assertEqual(meta.source, "config")
        custom = copy.deepcopy(self.base)
        custom["analysis_years"] = 42
        resolved, meta = resolve_horizon(custom)
        self.assertEqual(meta.mode, "custom_config")
        self.assertEqual(infer_horizon_mode(42), "custom_config")
        self.assertEqual(resolved["analysis_years"], 42)

    def test_invalid_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_horizon(self.base, "unknown")

    def test_event_sets_are_nested_across_30_50_60_horizons(self):
        ledgers = {}
        for mode in HORIZON_PROFILES:
            config, _ = resolve_horizon(self.base, mode)
            _, _, ledger = renewal_costs_with_ledger(
                self.components, self.futures, config, 20260726
            )
            self.assertTrue((ledger.event_time_years < config["analysis_years"]).all())
            ledgers[mode] = ledger

        id30 = set(ledgers["legacy_30"].event_id)
        id50 = set(ledgers["levels_50"].event_id)
        id60 = set(ledgers["rics_60"].event_id)
        self.assertTrue(id30 < id50)
        self.assertTrue(id50 < id60)

        # Events already present at a shorter horizon retain byte-identical
        # physical timing/lifetime data at longer horizons.
        cols = [
            "event_id", "future_id", "scenario_id", "component_instance_id",
            "comparison_lineage_id", "component_generation", "event_type",
            "event_time_years", "random_stream_key", "sampled_service_life_years",
            "service_life_basis",
        ]
        thirty = ledgers["legacy_30"].loc[:, cols].sort_values("event_id").reset_index(drop=True)
        fifty_subset = ledgers["levels_50"].loc[
            ledgers["levels_50"].event_id.isin(id30), cols
        ].sort_values("event_id").reset_index(drop=True)
        pd.testing.assert_frame_equal(thirty, fifty_subset, check_exact=True)

    def test_exact_horizon_boundary_remains_excluded_for_each_profile(self):
        fixture = pd.DataFrame([dict(
            scenario="Test", component="Boundary component", uncertainty_key="boundary",
            initial_cost_eur=100, lifetime_distribution="fixed",
            minimum_lifetime_years=10, most_likely_lifetime_years=10,
            maximum_lifetime_years=10, replacement_cost_factor=1, maintenance_cost_eur=0,
        )])
        one_future = self.futures.iloc[:1].copy()
        expected = {"legacy_30": [10.0, 20.0], "levels_50": [10.0, 20.0, 30.0, 40.0],
                    "rics_60": [10.0, 20.0, 30.0, 40.0, 50.0]}
        for mode, event_times in expected.items():
            config, _ = resolve_horizon(self.base, mode)
            _, legacy, ledger = renewal_costs_with_ledger(fixture, one_future, config, 42, central=True)
            self.assertEqual(legacy.renewal_time_years.tolist(), event_times)
            self.assertEqual(ledger.event_time_years.tolist(), event_times)
            self.assertNotIn(float(config["analysis_years"]), event_times)

    def test_explicit_legacy_profile_matches_default_run_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            default = root / "default"
            explicit = root / "explicit"
            m.run(output_dir=default, simulations=120, seed=4242,
                  charts=False, convergence_enabled=False)
            m.run(output_dir=explicit, simulations=120, seed=4242,
                  charts=False, convergence_enabled=False, horizon_mode="legacy_30")
            csv_names = sorted(p.name for p in default.glob("*.csv"))
            self.assertEqual(csv_names, sorted(p.name for p in explicit.glob("*.csv")))
            for name in csv_names:
                self.assertEqual((default / name).read_bytes(), (explicit / name).read_bytes(), name)
            self.assertEqual((default / "resolved_config.json").read_bytes(),
                             (explicit / "resolved_config.json").read_bytes())
            self.assertEqual((default / "analysis_report.txt").read_bytes(),
                             (explicit / "analysis_report.txt").read_bytes())
            default_h = json.loads((default / "resolved_horizon.json").read_text())
            explicit_h = json.loads((explicit / "resolved_horizon.json").read_text())
            self.assertEqual(default_h["analysis_years"], 30)
            self.assertEqual(explicit_h["analysis_years"], 30)
            self.assertEqual(default_h["mode"], "legacy_30")
            self.assertEqual(explicit_h["mode"], "legacy_30")
            self.assertEqual(default_h["source"], "config")
            self.assertEqual(explicit_h["source"], "profile_override")

    def test_50_and_60_runs_write_resolved_horizon_and_recompute_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summaries = {}
            for mode, years in (("levels_50", 50), ("rics_60", 60)):
                out = root / mode
                summaries[mode] = m.run(
                    output_dir=out, simulations=80, seed=4242,
                    charts=False, convergence_enabled=False, horizon_mode=mode,
                )
                meta = json.loads((out / "resolved_horizon.json").read_text())
                cfg = json.loads((out / "resolved_config.json").read_text())
                self.assertEqual(meta["analysis_years"], years)
                self.assertEqual(meta["mode"], mode)
                self.assertEqual(cfg["analysis_years"], years)
                ledger = pd.read_csv(out / "lifecycle_event_ledger.csv")
                self.assertTrue((ledger.event_time_years < years).all())
            # A longer horizon must be a fresh calculation, not a scaled copy.
            fifty = summaries["levels_50"].set_index(["perspective", "scenario"])
            sixty = summaries["rics_60"].set_index(["perspective", "scenario"])
            common = fifty.index.intersection(sixty.index)
            delta = (fifty.loc[common, "median_net_benefit_eur"] -
                     sixty.loc[common, "median_net_benefit_eur"]).abs()
            self.assertTrue((delta > 0).any())


if __name__ == "__main__":
    unittest.main()
