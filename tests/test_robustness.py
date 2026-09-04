import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import renovation_lcc as m
from robustness import option_set_sensitivity


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.c=m.load_config();self.s=m.load_scenarios(m.DEFAULT_INPUT)
        self.f=m.sample_uncertain_futures(400,42,self.c)
        self.r=m.simulate(self.s,self.f,self.c)

    def test_fixed_scores_survive_all_diagnostic_option_sets(self):
        out=option_set_sensitivity(self.r,self.c,m.all_summaries)
        self.assertEqual(out.pairwise_preference_reversals_among_retained.max(),0)
        np.testing.assert_allclose(out.preference_score_change.dropna(),0,atol=1e-12)
        self.assertEqual(set(out.operation),{'full','remove','add_copy','add_dominated'})

    def test_reference_has_no_positive_probability_bonus(self):
        out=m.build_summary(self.r,'combined_private',self.c)
        reference=out.loc[out.is_reference].iloc[0]
        self.assertEqual(reference.preference_utility_probability_positive,0)
        self.assertAlmostEqual(reference.preference_based_score,.525)

    def test_regret_can_change_while_scores_do_not(self):
        full=m.build_summary(self.r,'combined_private',self.c).set_index('scenario')
        removed=m.build_summary(self.r.loc[self.r.scenario.ne('Deep renovation + PV')],'combined_private',self.c).set_index('scenario')
        common=removed.index
        np.testing.assert_allclose(full.loc[common].preference_based_score,removed.preference_based_score)
        self.assertTrue((full.loc[common].mean_regret_eur>=removed.mean_regret_eur-1e-8).all())


if __name__=='__main__':unittest.main()
