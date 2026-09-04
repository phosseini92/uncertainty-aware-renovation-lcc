import sys
import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import renovation_lcc as m
from component_lifecycle import renewal_costs, load_components, apply_replacements


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.config=m.load_config()
        self.scenarios=m.load_scenarios(m.DEFAULT_INPUT)
        self.futures=m.sample_uncertain_futures(50,42,self.config)
        self.components=load_components(m.DEFAULT_COMPONENTS,self.scenarios)

    def test_multiple_replacements_discounting_and_horizon_boundary(self):
        c=self.config.copy();c['replacement_cost_growth']=.02
        f=self.futures.iloc[:1].copy();f['discount_rate']=.05;f['capex_factor']=1
        component=pd.DataFrame([dict(scenario='Test',component='Inverter',uncertainty_key='test',initial_cost_eur=100,
            lifetime_distribution='fixed',minimum_lifetime_years=10,most_likely_lifetime_years=10,
            maximum_lifetime_years=10,replacement_cost_factor=.8,maintenance_cost_eur=0)])
        totals,events=renewal_costs(component,f,c,42,retain_events=True)
        self.assertEqual(events.renewal_time_years.tolist(),[10.,20.])
        self.assertEqual(int(totals.replacement_count.iloc[0]),2)
        expected=80*(1.02/1.05)**10+80*(1.02/1.05)**20
        self.assertAlmostEqual(totals.pv_replacement_cost_eur.iloc[0],expected)
        self.assertAlmostEqual(events.pv_replacement_cost_eur.sum(),expected)

    def test_component_input_budget_and_lifetime_validation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'components.csv'
            for field,value in [('initial_cost_eur',-1),('minimum_lifetime_years',0),('maintenance_cost_eur',1000000)]:
                bad=self.components.copy();bad.loc[0,field]=value;bad.to_csv(path,index=False)
                with self.assertRaises(ValueError):load_components(path,self.scenarios)

    def test_lifetime_streams_are_nested_and_inventory_order_independent(self):
        full,events=renewal_costs(self.components,self.futures,self.config,42,retain_events=True)
        short,_=renewal_costs(self.components.iloc[::-1],self.futures.iloc[:10],self.config,42)
        keys=['scenario','component','future_id']
        pd.testing.assert_frame_equal(full.loc[full.future_id.lt(10)].sort_values(keys).reset_index(drop=True),
                                      short.sort_values(keys).reset_index(drop=True))
        by_component=full.groupby(['scenario','component']).first_service_life_years.apply(list)
        self.assertEqual(by_component.loc[('Envelope retrofit','Windows')],by_component.loc[('Envelope + heat pump','Windows')])

    def test_replacements_preserve_private_accounting_identity(self):
        raw=m.simulate(self.scenarios,self.futures,self.config)
        totals,events=renewal_costs(self.components,self.futures,self.config,42,retain_events=True)
        # Feed unadjusted component-free cash flows, without pre-existing cost columns.
        adjusted=apply_replacements(raw.drop(columns=['pv_replacement_cost_eur','replacement_count']),totals)
        np.testing.assert_allclose(adjusted.owner_net_benefit_eur+adjusted.tenant_net_benefit_eur,
                                   adjusted.combined_private_net_benefit_eur,atol=1e-8)
        np.testing.assert_allclose(adjusted.tenant_net_benefit_eur,raw.tenant_net_benefit_eur)
        np.testing.assert_allclose(raw.owner_net_benefit_eur-adjusted.owner_net_benefit_eur,
                                   adjusted.pv_replacement_cost_eur,atol=1e-8)
        self.assertAlmostEqual(events.pv_replacement_cost_eur.sum(),adjusted.pv_replacement_cost_eur.sum(),places=6)


if __name__=='__main__':unittest.main()
