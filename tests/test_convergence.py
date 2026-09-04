import sys
import copy
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import renovation_lcc as m
from convergence import convergence_analysis


class ConvergenceTests(unittest.TestCase):
    def test_economic_draws_have_exact_prefixes(self):
        c=m.load_config()
        long=m.sample_uncertain_futures(400,42,c)
        short=m.sample_uncertain_futures(100,42,c)
        pd.testing.assert_frame_equal(long.iloc[:100],short,check_exact=True)

    def test_convergence_matches_direct_runs_and_has_bounded_intervals(self):
        c=m.load_config();c['convergence']['sample_sizes']=[20,40,80];c['convergence']['seeds']=[1,2]
        s=m.load_scenarios(m.DEFAULT_INPUT);components=m.load_components(m.DEFAULT_COMPONENTS,s)
        out,stability=convergence_analysis(s,components,c,m.sample_uncertain_futures,m.simulate,m.all_summaries)
        self.assertEqual(len(out),3*2*4*3)
        direct=m.all_summaries(m.simulate(s,m.sample_uncertain_futures(20,1,c),c,components,1),c)
        actual=out.loc[out.seed.eq(1)&out.sample_size.eq(20)].reset_index(drop=True)
        pd.testing.assert_frame_equal(direct,actual[direct.columns],check_exact=True)
        self.assertTrue(out.positive_frequency_wilson95_low.between(0,1).all())
        self.assertTrue(out.positive_frequency_wilson95_high.between(0,1).all())
        self.assertTrue(out.loc[out.is_largest_sample_reference].within_diagnostic_tolerances.isna().all())
        self.assertEqual(stability.independent_seeds.unique().tolist(),[2])


if __name__=='__main__':unittest.main()
