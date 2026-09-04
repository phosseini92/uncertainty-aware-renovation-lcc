import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import renovation_lcc as m
from performance_stress import load_stress_cases,performance_stress_analysis


class PerformanceStressTests(unittest.TestCase):
    def test_baseline_proxy_equals_unstressed_model_and_reference_is_not_comfort_pass(self):
        c=m.load_config();s=m.load_scenarios(m.DEFAULT_INPUT)
        components=m.load_components(m.DEFAULT_COMPONENTS,s)
        f=m.sample_uncertain_futures(100,42,c)
        cases=load_stress_cases(m.DEFAULT_STRESS,s,c)
        out,robust=performance_stress_analysis(s,components,f,c,42,cases,m.evaluate_scenario,m.all_summaries)
        base=m.all_summaries(m.simulate(s,f,c,components,42),c)
        actual=out.loc[out.stress_case.eq('Baseline proxy')].reset_index(drop=True)
        pd.testing.assert_frame_equal(base,actual[base.columns],check_exact=True)
        self.assertTrue(out.loc[out.is_reference].performance_threshold_pass.isna().all())
        self.assertFalse(robust.loc[~robust.performance_threshold_applicable].robust_across_stress_cases.any())
        self.assertTrue(robust.acceptable_case_count.le(robust.stress_case_count).all())

    def test_severe_savings_proxy_cannot_improve_performance_pass_rate(self):
        c=m.load_config();s=m.load_scenarios(m.DEFAULT_INPUT)
        components=m.load_components(m.DEFAULT_COMPONENTS,s);f=m.sample_uncertain_futures(200,42,c)
        cases=load_stress_cases(m.DEFAULT_STRESS,s,c)
        out,_=performance_stress_analysis(s,components,f,c,42,cases,m.evaluate_scenario,m.all_summaries)
        rates=out.loc[out.perspective.eq('combined_private')&~out.is_reference].pivot(
            index='scenario',columns='stress_case',values='performance_pass_probability')
        self.assertTrue(rates['Severe stress proxy'].le(rates['Baseline proxy']).all())


if __name__=='__main__':unittest.main()
