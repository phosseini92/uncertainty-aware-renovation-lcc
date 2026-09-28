import unittest
import numpy as np
import pandas as pd

import renovation_lcc as m
import lifecycle_aggregation as agg
from carbon_consequences import CARBON_CONSEQUENCE_COLUMNS


def row(cid,module,gwp=1.0,sid='scn_envelope_retrofit',fid=0):
    r={c:np.nan for c in CARBON_CONSEQUENCE_COLUMNS}
    r.update({'carbon_consequence_id':cid,'future_id':fid,'scenario_id':sid,'reported_module':module,'gwp_kgco2e':gwp})
    return r


class LifecycleAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.scenarios=m.load_scenarios(m.DEFAULT_INPUT)

    def applicability(self):
        return agg.load_module_applicability(m.DEFAULT_MODULE_APPLICABILITY,self.scenarios)

    def test_production_scope_file_is_complete_for_every_scenario(self):
        a=self.applicability()
        self.assertEqual(len(a),len(self.scenarios)*len(agg.ALL_MODULES))
        self.assertFalse(a.duplicated(['scenario_id','module_id']).any())

    def test_deferred_modules_are_not_zero_or_not_applicable(self):
        cov=agg.build_module_coverage(self.scenarios,self.applicability(),pd.DataFrame(columns=CARBON_CONSEQUENCE_COLUMNS))
        b2=cov.loc[(cov.scenario_id.eq('scn_envelope_retrofit'))&cov.module_id.eq('B2')].iloc[0]
        self.assertEqual(b2.coverage_status,'NOT_ASSESSED_SCOPE')

    def test_required_missing_module_is_not_assessed_not_zero(self):
        cov=agg.build_module_coverage(self.scenarios,self.applicability(),pd.DataFrame(columns=CARBON_CONSEQUENCE_COLUMNS))
        c1=cov.loc[(cov.scenario_id.eq('scn_envelope_retrofit'))&cov.module_id.eq('C1')].iloc[0]
        self.assertEqual(c1.coverage_status,'NOT_ASSESSED_MISSING_DATA')

    def test_reference_current_intervention_a_stage_is_not_applicable(self):
        cov=agg.build_module_coverage(self.scenarios,self.applicability(),pd.DataFrame(columns=CARBON_CONSEQUENCE_COLUMNS))
        x=cov.loc[(cov.scenario_id.eq('scn_reference_minimum_intervention'))&cov.module_id.eq('A4')].iloc[0]
        self.assertEqual(x.coverage_status,'NOT_APPLICABLE')

    def test_partial_a_c_total_is_never_labeled_whole_life(self):
        ledger=pd.DataFrame([row('c1','A1-A3',10),row('c2','B6',20),row('c3','C1',5)],columns=CARBON_CONSEQUENCE_COLUMNS)
        cov=agg.build_module_coverage(self.scenarios,self.applicability(),ledger)
        out=agg.build_lifecycle_aggregation(self.scenarios,cov,ledger,[0])
        r=out.loc[out.scenario_id.eq('scn_envelope_retrofit')].iloc[0]
        self.assertAlmostEqual(r.assessed_a_c_gwp_kgco2e,35.0)
        self.assertFalse(r.whole_life_carbon_label_allowed)
        self.assertIn('PARTIAL',r.reporting_label)

    def test_module_d_summary_is_separate_and_not_in_a_c_total(self):
        ledger=pd.DataFrame([row('a','A1-A3',10),row('d1','D1',-5),row('d2','D2',-2)],columns=CARBON_CONSEQUENCE_COLUMNS)
        cov=agg.build_module_coverage(self.scenarios,self.applicability(),ledger)
        out=agg.build_lifecycle_aggregation(self.scenarios,cov,ledger,[0])
        d=agg.build_separate_d_summary(ledger)
        r=out.loc[out.scenario_id.eq('scn_envelope_retrofit')].iloc[0]
        self.assertAlmostEqual(r.assessed_a_c_gwp_kgco2e,10.0)
        self.assertAlmostEqual(d.separate_d_gwp_kgco2e.sum(),-7.0)

    def test_aggregation_meta_never_generates_headline_for_current_bounded_scope(self):
        cov,out,d,meta=agg.assess_lifecycle_aggregation(self.scenarios,self.applicability(),pd.DataFrame(columns=CARBON_CONSEQUENCE_COLUMNS),[0])
        self.assertFalse(meta['whole_life_carbon_generated'])
        self.assertFalse(meta['headline_carbon_generated'])
        self.assertFalse(meta['module_d_netted_into_a_c'])

    def test_run_manifest_uses_dynamic_coverage_gate_flags_once(self):
        from pathlib import Path
        source=Path(m.__file__).read_text()
        self.assertEqual(source.count('"whole_life_carbon_generated":'),1)
        self.assertEqual(source.count('"headline_carbon_generated":'),1)
        self.assertIn('"whole_life_carbon_generated":lifecycle_aggregation_meta["whole_life_carbon_generated"]',source)
        self.assertIn('"headline_carbon_generated":lifecycle_aggregation_meta["headline_carbon_generated"]',source)

if __name__=='__main__': unittest.main()
