import unittest
import numpy as np
import pandas as pd

import renovation_lcc as m
import end_of_life as eol
import b6_operational as b6
from environmental_factors import ENVIRONMENTAL_FACTOR_COLUMNS, validate_environmental_factors
from physical_quantities import COMPONENT_BOQ_COLUMNS


def factor(record,setid,module,value,unit='kg',process=None):
    return {
        'factor_record_id':record,'factor_set_id':setid,'dataset_id':'test_dataset','product_or_process_id':process or setid,
        'indicator_id':'GWP_TOTAL','indicator_value':value,'indicator_unit':'kgco2e','declared_unit':unit,'module_scope':module,
        'geography':'TEST','reference_year':2026,'source_type':'TEST_ONLY_SYNTHETIC','source_citation':'Synthetic fixture',
        'verification_status':'TEST_ONLY','data_quality_status':'TEST_ONLY','license_status':'TEST_ONLY','redistribution_allowed':False,
        'uncertainty_mode':'DETERMINISTIC','uncertainty_semantics':'NOT_APPLICABLE','uncertainty_parameter_1':np.nan,
        'uncertainty_parameter_2':np.nan,'uncertainty_parameter_3':np.nan,'uncertainty_basis':'','notes':''
    }


def factors():
    return validate_environmental_factors(pd.DataFrame([
        factor('f_c1','fs_c1','C1',0.5,'kwh'), factor('f_c2','fs_c2','C2',0.1,'tkm'),
        factor('f_c3','fs_c3','C3',0.2,'kg'), factor('f_c4','fs_c4','C4',0.05,'kg'),
        factor('f_d1','fs_d1','D1',-0.1,'kg'), factor('f_d2_y1','fs_d2_y1','D2',-0.05,'kwh'),
        factor('f_d2_y2','fs_d2_y2','D2',-0.04,'kwh'),
    ],columns=ENVIRONMENTAL_FACTOR_COLUMNS))


def boq():
    row={c:'' for c in COMPONENT_BOQ_COLUMNS}
    row.update({'boq_line_id':'boq_eol','scenario_id':'scn_envelope_retrofit','component_instance_id':'cmp_eol',
                'comparison_lineage_id':'lin_eol','component_type_id':'wall','item_label':'Wall','material_or_product_id':'mat_eol',
                'assessment_role':'ASSESSMENT_INVENTORY','quantity':1000.0,'quantity_unit':'kg','mass_kg':1000.0,
                'source_status':'TEST_ONLY_SYNTHETIC','source_reference':'fixture','derivation_method':'TEST_ONLY_SYNTHETIC','notes':''})
    return pd.DataFrame([row],columns=COMPONENT_BOQ_COLUMNS)


def assignment():
    return pd.DataFrame([[
        'eol_a','boq_eol','scn_envelope_retrofit','eol_flow','fs_c1',20.0,'kwh','fs_c2',100.0,
        'fs_c3',0.7,'fs_c4',0.3,'fs_d1',0.5,True,'TEST_ONLY_SYNTHETIC','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''
    ]],columns=eol.EOL_ASSIGNMENT_COLUMNS)


def flows(scenarios):
    raw=pd.DataFrame([
        ['flow_gen','scn_envelope_retrofit','electricity','GENERATED',150.0,1,2,'','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''],
        ['flow_self','scn_envelope_retrofit','electricity','SELF_CONSUMED',50.0,1,2,'','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''],
        ['flow_export','scn_envelope_retrofit','electricity','EXPORTED',100.0,1,2,'','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''],
    ],columns=b6.OPERATIONAL_ENERGY_FLOW_COLUMNS)
    return b6.validate_operational_energy_flows(raw,scenarios)


class EndOfLifeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios=m.load_scenarios(m.DEFAULT_INPUT)

    def test_empty_production_inputs_are_valid_not_zero(self):
        fs=factors(); b=boq()
        self.assertTrue(eol.validate_end_of_life_assignments(pd.DataFrame(columns=eol.EOL_ASSIGNMENT_COLUMNS),b,fs).empty)
        self.assertTrue(eol.validate_d2_export_assignments(pd.DataFrame(columns=eol.D2_EXPORT_ASSIGNMENT_COLUMNS),flows(self.scenarios)).empty)
        self.assertTrue(eol.validate_d2_factor_schedule(pd.DataFrame(columns=eol.D2_FACTOR_SCHEDULE_COLUMNS),fs).empty)

    def test_golden_terminal_c1_c4_and_separate_d1(self):
        fs=factors(); b=boq(); a=eol.validate_end_of_life_assignments(assignment(),b,fs)
        cov=eol.build_eol_coverage(b,fs,a)
        ledger=eol.build_eol_ledger(b,fs,a,cov,[0],30)
        by=dict(zip(ledger.reported_module,ledger.gwp_kgco2e))
        self.assertAlmostEqual(by['C1'],10.0); self.assertAlmostEqual(by['C2'],10.0)
        self.assertAlmostEqual(by['C3'],140.0); self.assertAlmostEqual(by['C4'],15.0)
        self.assertAlmostEqual(by['D1'],-50.0)
        self.assertAlmostEqual(ledger.loc[ledger.reported_module.str.startswith('C'),'gwp_kgco2e'].sum(),175.0)
        self.assertTrue(ledger.lifecycle_event_id.isna().all())
        self.assertTrue(ledger.source_event_type.eq('RSP_ACCOUNTING_END_OF_LIFE').all())
        self.assertTrue(ledger.event_time_years.eq(30.0).all())

    def test_c3_c4_fractions_cannot_exceed_one(self):
        a=assignment(); a.loc[0,'c3_mass_fraction']=0.8; a.loc[0,'c4_mass_fraction']=0.3
        with self.assertRaisesRegex(ValueError,'cannot exceed'):
            eol.validate_end_of_life_assignments(a,boq(),factors())

    def test_missing_mass_blocks_mass_based_c2_c3_c4_d1(self):
        b=boq(); b.loc[0,'mass_kg']=np.nan; b.loc[0,'quantity_unit']='m2'; b.loc[0,'quantity']=10.0
        a=eol.validate_end_of_life_assignments(assignment(),b,factors())
        cov=eol.build_eol_coverage(b,factors(),a).iloc[0]
        self.assertTrue(cov.c2_status.startswith('BLOCKED_'))
        self.assertTrue(cov.c3_status.startswith('BLOCKED_'))
        self.assertTrue(cov.c4_status.startswith('BLOCKED_'))
        self.assertTrue(cov.d1_status.startswith('BLOCKED_'))

    def test_c2_requires_tkm_factor(self):
        fs=factors().copy(); fs.loc[fs.factor_set_id.eq('fs_c2'),'declared_unit']='kg'
        a=eol.validate_end_of_life_assignments(assignment(),boq(),fs)
        cov=eol.build_eol_coverage(boq(),fs,a)
        self.assertEqual(cov.c2_status.iloc[0],'BLOCKED_C2_MASS_OR_FACTOR')

    def test_c1_unit_mismatch_blocks(self):
        a=assignment(); a.loc[0,'c1_activity_unit']='mj'
        a=eol.validate_end_of_life_assignments(a,boq(),factors())
        cov=eol.build_eol_coverage(boq(),factors(),a)
        self.assertEqual(cov.c1_status.iloc[0],'BLOCKED_C1_FACTOR_OR_UNIT')

    def test_rsp_boundary_is_accounting_state_not_event(self):
        a=eol.validate_end_of_life_assignments(assignment(),boq(),factors())
        cov=eol.build_eol_coverage(boq(),factors(),a)
        ledger=eol.build_eol_ledger(boq(),factors(),a,cov,[0],50)
        self.assertTrue(ledger.lifecycle_event_id.isna().all())
        self.assertTrue(ledger.component_generation.eq(-1).all())
        self.assertTrue(ledger.event_time_years.eq(50.0).all())

    def test_d2_only_accepts_exported_flow(self):
        fl=flows(self.scenarios)
        raw=pd.DataFrame([['d2a','flow_self','scn_envelope_retrofit','sched_d2','TEST_ONLY_SYNTHETIC','fixture','2026-09-28','']],columns=eol.D2_EXPORT_ASSIGNMENT_COLUMNS)
        with self.assertRaisesRegex(ValueError,'EXPORTED'):
            eol.validate_d2_export_assignments(raw,fl)

    def test_d2_explicit_schedule_and_midyear_timing(self):
        fs=factors(); fl=flows(self.scenarios)
        ar=eol.validate_d2_export_assignments(pd.DataFrame([['d2a','flow_export','scn_envelope_retrofit','sched_d2','TEST_ONLY_SYNTHETIC','fixture','2026-09-28','']],columns=eol.D2_EXPORT_ASSIGNMENT_COLUMNS),fl)
        sr=eol.validate_d2_factor_schedule(pd.DataFrame([
            ['sched_d2','electricity',1,2027,'fs_d2_y1','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''],
            ['sched_d2','electricity',2,2028,'fs_d2_y2','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''],
        ],columns=eol.D2_FACTOR_SCHEDULE_COLUMNS),fs)
        cov=eol.build_d2_coverage(fl,ar,sr,2)
        ledger=eol.build_d2_ledger(fl,ar,sr,fs,cov,[0],2)
        self.assertEqual(len(ledger),2)
        self.assertEqual(sorted(ledger.event_time_years.tolist()),[0.5,1.5])
        self.assertTrue(ledger.reported_module.eq('D2').all())
        self.assertAlmostEqual(ledger.gwp_kgco2e.sum(),-9.0)

    def test_d2_schedule_carrier_mismatch_blocks(self):
        fs=factors(); fl=flows(self.scenarios)
        ar=eol.validate_d2_export_assignments(pd.DataFrame([['d2a','flow_export','scn_envelope_retrofit','sched_d2','TEST_ONLY_SYNTHETIC','fixture','2026-09-28','']],columns=eol.D2_EXPORT_ASSIGNMENT_COLUMNS),fl)
        sr=eol.validate_d2_factor_schedule(pd.DataFrame([
            ['sched_d2','gas',1,2027,'fs_d2_y1','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''],
            ['sched_d2','gas',2,2028,'fs_d2_y2','TEST_ONLY_SYNTHETIC','fixture','2026-09-28',''],
        ],columns=eol.D2_FACTOR_SCHEDULE_COLUMNS),fs)
        cov=eol.build_d2_coverage(fl,ar,sr,2)
        ledger=eol.build_d2_ledger(fl,ar,sr,fs,cov,[0],2)
        self.assertEqual(cov.d2_status.iloc[0],'BLOCKED_D2_FACTOR_SCHEDULE_CARRIER_MISMATCH')
        self.assertTrue(ledger.empty)

    def test_missing_d2_year_blocks_without_partial_credit(self):
        fs=factors(); fl=flows(self.scenarios)
        ar=eol.validate_d2_export_assignments(pd.DataFrame([['d2a','flow_export','scn_envelope_retrofit','sched_d2','TEST_ONLY_SYNTHETIC','fixture','2026-09-28','']],columns=eol.D2_EXPORT_ASSIGNMENT_COLUMNS),fl)
        sr=eol.validate_d2_factor_schedule(pd.DataFrame([['sched_d2','electricity',1,2027,'fs_d2_y1','TEST_ONLY_SYNTHETIC','fixture','2026-09-28','']],columns=eol.D2_FACTOR_SCHEDULE_COLUMNS),fs)
        cov=eol.build_d2_coverage(fl,ar,sr,2)
        ledger=eol.build_d2_ledger(fl,ar,sr,fs,cov,[0],2)
        self.assertEqual(cov.d2_status.iloc[0],'BLOCKED_INCOMPLETE_D2_FACTOR_SCHEDULE')
        self.assertTrue(ledger.empty)

    def test_append_preserves_existing_carbon_rows_and_d_stays_separate(self):
        fs=factors(); b=boq(); a=eol.validate_end_of_life_assignments(assignment(),b,fs)
        cov=eol.build_eol_coverage(b,fs,a); new=eol.build_eol_ledger(b,fs,a,cov,[0],30)
        old=new.iloc[[0]].copy(); old.loc[:,'carbon_consequence_id']='cc_existing'; old.loc[:,'reported_module']='B6'; old.loc[:,'gwp_kgco2e']=123.0
        out=eol.append_end_of_life_and_d(old,new)
        self.assertAlmostEqual(out.loc[out.carbon_consequence_id.eq('cc_existing'),'gwp_kgco2e'].iloc[0],123.0)
        self.assertAlmostEqual(out.loc[out.reported_module.eq('D1'),'gwp_kgco2e'].sum(),-50.0)

if __name__=='__main__': unittest.main()
