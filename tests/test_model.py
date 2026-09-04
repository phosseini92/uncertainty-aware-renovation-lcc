import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renovation_lcc as model


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.config = model.load_config()
        self.scenarios = model.load_scenarios(model.DEFAULT_INPUT)
        self.futures = model.sample_uncertain_futures(200, 42, self.config)

    def test_annuity_matches_closed_form_and_boundary_cases(self):
        self.assertEqual(float(model.annuity_present_value(100, 0, 0, 30)), 3000)
        self.assertAlmostEqual(float(model.annuity_present_value(100, .03, .03, 30)), 3000/1.03)
        expected = 100/(.05-.02)*(1-(1.02/1.05)**30)
        self.assertAlmostEqual(float(model.annuity_present_value(100,.02,.05,30)), expected)
        self.assertEqual(float(model.annuity_present_value(100,.02,.05,0)), 0)

    def test_hand_calculated_accounting(self):
        c = copy.deepcopy(self.config)
        c.update(analysis_years=2, dwellings=1, owner_energy_savings_share=.25,
                 terminal_reference_building_value_eur=1000, maintenance_growth=0)
        f = pd.DataFrame([dict(discount_rate=0, energy_price_eur_kwh=2, energy_price_growth=0,
                               rent_growth=0, grant_share=.2, capex_factor=1,
                               performance_factor=1, value_uplift_factor=1)])
        s = pd.Series(dict(scenario="Test",is_reference=0,initial_capex_eur=100,
                           annual_energy_savings_kwh=10, monthly_income_uplift_eur_per_dwelling=1,
                           annual_maintenance_eur=3,terminal_value_uplift_pct=.01))
        row = model.evaluate_scenario(s,f,c).iloc[0]
        # Energy=40; rent=24; terminal=10; net investment=80; maintenance=6.
        self.assertEqual(row.owner_net_benefit_eur, -42)
        self.assertEqual(row.tenant_net_benefit_eur, 6)
        self.assertEqual(row.combined_private_net_benefit_eur, -36)

    def test_rent_cancels_and_energy_allocation_conserves_benefit(self):
        base = model.simulate(self.scenarios,self.futures,self.config)
        higher_rent = self.scenarios.copy()
        higher_rent.monthly_income_uplift_eur_per_dwelling *= 2
        changed = model.simulate(higher_rent,self.futures,self.config)
        np.testing.assert_allclose(base.combined_private_net_benefit_eur, changed.combined_private_net_benefit_eur)
        for share in [0,.5,1]:
            c = dict(self.config, owner_energy_savings_share=share)
            r = model.simulate(self.scenarios,self.futures,c)
            np.testing.assert_allclose(r.owner_net_benefit_eur+r.tenant_net_benefit_eur,
                                       r.combined_private_net_benefit_eur, atol=1e-8)
            np.testing.assert_allclose(r.combined_private_net_benefit_eur,base.combined_private_net_benefit_eur)

    def test_reference_is_zero_and_regret_includes_it(self):
        fixture = pd.DataFrame({"future_id":[0,1,0,1],"scenario":["Base","Base","Retrofit","Retrofit"],
                                "is_reference":[1,1,0,0], "owner_net_benefit_eur":[0.,0.,-10.,-20.]})
        summary = model.build_summary(fixture,"owner",self.config).set_index("scenario")
        self.assertEqual(summary.loc["Base","mean_regret_eur"],0)
        self.assertEqual(summary.loc["Retrofit","mean_regret_eur"],15)
        self.assertEqual(summary.loc["Base","probability_positive"],0)
        self.assertEqual(summary.loc["Base","probability_nonnegative"],1)
        self.assertEqual(summary.loc["Base","conditional_preference_rank"],1)
        actual = model.simulate(self.scenarios,self.futures,self.config)
        columns = [f"{p}_net_benefit_eur" for p in model.PERSPECTIVES]
        self.assertTrue(actual.loc[actual.is_reference.eq(1),columns].eq(0).all().all())

    def test_reference_exclusion_changes_choice_set_only(self):
        r = model.simulate(self.scenarios,self.futures,self.config)
        c = dict(self.config,include_reference_in_decisions=False)
        summary = model.build_summary(r,"owner",c)
        reference = summary.loc[summary.is_reference].iloc[0]
        self.assertFalse(reference.decision_eligible)
        self.assertTrue(pd.isna(reference.conditional_preference_rank))
        self.assertTrue(pd.isna(reference.p95_regret_eur))
        self.assertAlmostEqual(summary.best_option_share.sum(),1)

    def test_exact_tail_mass_and_ties(self):
        self.assertAlmostEqual(model.lower_tail_mean([0,10,20], .5),10/3)
        fixture = pd.DataFrame({"future_id":[0,0],"scenario":["Base","Same"],
                                "is_reference":[1,0],"owner_net_benefit_eur":[0.,0.]})
        summary = model.build_summary(fixture,"owner",self.config)
        np.testing.assert_allclose(summary.best_option_share,.5)
        np.testing.assert_allclose(summary.preference_based_score,.525)
        self.assertTrue(summary.conditional_preference_rank.eq(1).all())

    def test_input_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"bad.csv"
            for transform in [lambda x: x.assign(scenario="duplicate"),
                              lambda x: x.assign(initial_capex_eur=np.nan),
                              lambda x: x.assign(is_reference=0),
                              lambda x: x.assign(initial_capex_eur=-1)]:
                transform(self.scenarios.copy()).to_csv(path,index=False)
                with self.assertRaises(ValueError): model.load_scenarios(path)
        with self.assertRaises(ValueError): model.sample_uncertain_futures(0,42,self.config)
        with self.assertRaises(ValueError): model.annuity_present_value(100,0,-1,1)
        bad = copy.deepcopy(self.config)
        bad["owner_energy_savings_share"] = 1.1
        with self.assertRaises(ValueError): model.validate_config(bad)
        bad = copy.deepcopy(self.config)
        bad["score_weights"]["probability_positive"] = -1
        with self.assertRaises(ValueError): model.validate_config(bad)

    def test_sensitivity_exposes_energy_direction(self):
        r = model.simulate(self.scenarios,self.futures,self.config)
        oat, rho = model.sensitivity_analysis(self.scenarios,self.futures,r,self.config)
        owner_energy = oat.loc[oat.perspective.eq("owner") & oat.parameter.eq("energy_price_eur_kwh")]
        combined_energy = oat.loc[oat.perspective.eq("combined_private") & oat.parameter.eq("energy_price_eur_kwh")]
        np.testing.assert_allclose(owner_energy.signed_change_eur,0)
        self.assertTrue(combined_energy.signed_change_eur.gt(0).all())
        self.assertEqual(len(rho),3*3*8)

    def test_renamed_scenarios_generate_all_outputs_reproducibly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            s = self.scenarios.copy()
            s.loc[s.index[1],"scenario"] = "A newly named option"
            input_path = root/"input.csv"
            s.to_csv(input_path,index=False)
            components = pd.read_csv(model.DEFAULT_COMPONENTS)
            components.loc[components.scenario.eq("Envelope retrofit"),"scenario"] = "A newly named option"
            components_path = root/"components.csv"
            components.to_csv(components_path,index=False)
            a = model.run(input_path,root/"a",100,42,charts=True,components_path=components_path,convergence_enabled=False)
            b = model.run(input_path,root/"b",100,42,charts=False,components_path=components_path,convergence_enabled=False)
            pd.testing.assert_frame_equal(a,b,check_exact=True)
            self.assertEqual((root/"a/simulation_results.csv").read_bytes(),
                             (root/"b/simulation_results.csv").read_bytes())
            for name in ["net_benefit_distributions","robustness_map","scenario_regret",
                         "sensitivity_tornado","allocation_tradeoff"]:
                for ext in ["png","svg"]:
                    self.assertGreater((root/f"a/{name}.{ext}").stat().st_size,100)
            for name in ["sampled_futures","scenario_summary","sensitivity_oat",
                         "weight_sensitivity","allocation_sensitivity","stress_test_summary"]:
                self.assertTrue((root/f"a/{name}.csv").exists())
            manifest = json.loads((root/"a/run_manifest.json").read_text())
            self.assertIn("matplotlib",manifest)


if __name__ == "__main__":
    unittest.main()
