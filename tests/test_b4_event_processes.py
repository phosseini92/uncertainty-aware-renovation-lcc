import unittest
from pathlib import Path
import numpy as np
import pandas as pd

import renovation_lcc as m
import b4_event_processes as b4p
import a4_transport as a4
from carbon_consequences import empty_carbon_consequence_ledger, CARBON_CONSEQUENCE_COLUMNS
from environmental_factors import validate_environmental_factors, ENVIRONMENTAL_FACTOR_COLUMNS
from physical_quantities import COMPONENT_BOQ_COLUMNS, EVENT_BOQ_COLUMNS
from lifecycle_events import LIFECYCLE_EVENT_COLUMNS


def env_factor(record, setid, process, unit, module, value=0.5, indicator="GWP_TOTAL"):
    return {
        "factor_record_id":record,"factor_set_id":setid,"dataset_id":"test_dataset",
        "product_or_process_id":process,"indicator_id":indicator,"indicator_value":value,
        "indicator_unit":"kgco2e","declared_unit":unit,"module_scope":module,
        "geography":"TEST","reference_year":2026,"source_type":"TEST_ONLY_SYNTHETIC",
        "source_citation":"Synthetic fixture","verification_status":"TEST_ONLY",
        "data_quality_status":"TEST_ONLY","license_status":"TEST_ONLY",
        "redistribution_allowed":False,"uncertainty_mode":"DETERMINISTIC",
        "uncertainty_semantics":"NOT_APPLICABLE","uncertainty_parameter_1":np.nan,
        "uncertainty_parameter_2":np.nan,"uncertainty_parameter_3":np.nan,
        "uncertainty_basis":"","notes":"",
    }


def transport_factor(record="tf_out", setid="tfs_out", value=0.1):
    d=env_factor(record,setid,"truck_transport","tkm","A4",value)
    d.update({"transport_mode":"ROAD","vehicle_class":"RIGID_TRUCK",
              "load_factor_basis":"DOCUMENTED_FACTOR_BASIS",
              "factor_system_boundary":"TANK_TO_WHEEL_PLUS_UPSTREAM",
              "retrieval_date":"2026-09-28"})
    return d


def boq_table(role="ASSESSMENT_INVENTORY", scenario="scn_envelope_retrofit", mass=1000.0):
    return pd.DataFrame([dict(zip(COMPONENT_BOQ_COLUMNS,(
        "boq_test",scenario,"ci_test","lineage_test","ctype_test","Test component","product_test",
        role,1000.0,"kg",mass,"TEST_ONLY_SYNTHETIC","fixture","EXPLICIT_TEST","",
    )))])


def event_tables(event_type="B4_REPLACEMENT", event_id="evt_test", future_id=0, generation=1, time=10.0):
    evt=pd.DataFrame([dict(zip(LIFECYCLE_EVENT_COLUMNS,(
        event_id,future_id,"scn_envelope_retrofit","ci_test","lineage_test",generation,event_type,time,np.nan,
        1.0,"unit","IN_SERVICE","REPLACED","","stream",10.0,"FULL_SERVICE_LIFE",
    )))])
    eb=pd.DataFrame([dict(zip(EVENT_BOQ_COLUMNS,(
        "eb_test",event_id,future_id,"scn_envelope_retrofit","ci_test","lineage_test",generation,event_type,
        "boq_test","product_test","ASSESSMENT_INVENTORY",1000.0,"kg",1000.0,"TEST_ONLY_SYNTHETIC","fixture",
    )))])
    return evt,eb


def env_registry():
    rows=[
        env_factor("f_install","fs_install","install","kwh","A5.2",0.5),
        env_factor("f_remove","fs_remove","remove","kwh","A5.1",0.25),
        env_factor("f_process","fs_process","process","kg","C3",0.2),
        env_factor("f_dispose","fs_dispose","dispose","kg","C4",0.1),
    ]
    return validate_environmental_factors(pd.DataFrame(rows,columns=ENVIRONMENTAL_FACTOR_COLUMNS))


def transport_registry():
    return a4.validate_transport_factors(pd.DataFrame([transport_factor()],columns=a4.TRANSPORT_FACTOR_COLUMNS))


def assignment_rows():
    return pd.DataFrame([
        ["a_install","boq_test","scn_envelope_retrofit","flow_install","INSTALLATION","ENVIRONMENTAL","fs_install","A5.2","EXPLICIT_ACTIVITY",20.0,"kwh",np.nan,True,"TEST_ONLY_SYNTHETIC","fixture","TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""],
        ["a_remove","boq_test","scn_envelope_retrofit","flow_remove","REMOVAL","ENVIRONMENTAL","fs_remove","A5.1","EXPLICIT_ACTIVITY",8.0,"kwh",np.nan,True,"TEST_ONLY_SYNTHETIC","fixture","TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""],
        ["a_transport","boq_test","scn_envelope_retrofit","flow_out","OUTBOUND_WASTE_TRANSPORT","TRANSPORT","tfs_out","A4","BOQ_TONNE_KM",np.nan,"",100.0,True,"TEST_ONLY_SYNTHETIC","fixture","TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""],
        ["a_process","boq_test","scn_envelope_retrofit","flow_process","WASTE_PROCESSING","ENVIRONMENTAL","fs_process","C3","BOQ_MASS",np.nan,"",np.nan,True,"TEST_ONLY_SYNTHETIC","fixture","TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""],
        ["a_dispose","boq_test","scn_envelope_retrofit","flow_dispose","WASTE_DISPOSAL","ENVIRONMENTAL","fs_dispose","C4","BOQ_MASS",np.nan,"",np.nan,True,"TEST_ONLY_SYNTHETIC","fixture","TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""],
    ],columns=b4p.B4_EVENT_PROCESS_ASSIGNMENT_COLUMNS)


class B4EventProcessTests(unittest.TestCase):
    def setUp(self):
        self.boq=boq_table(); self.evt,self.eb=event_tables(); self.env=env_registry(); self.tf=transport_registry()

    def test_golden_complete_b4_event_process_family(self):
        ass=b4p.validate_b4_event_process_assignments(assignment_rows(),self.boq,self.env,self.tf)
        comp,cov,ledger,summary,meta=b4p.assess_b4_event_processes(self.boq,self.evt,self.eb,self.env,self.tf,ass)
        self.assertEqual(len(ledger),5)
        self.assertTrue(ledger.reported_module.eq("B4").all())
        self.assertTrue(ledger.lifecycle_event_id.eq("evt_test").all())
        self.assertTrue(ledger.source_event_type.eq("B4_REPLACEMENT").all())
        by=dict(zip(ledger.consequence_type,ledger.gwp_kgco2e))
        self.assertAlmostEqual(by["B4_REPLACEMENT_INSTALLATION"],10.0)
        self.assertAlmostEqual(by["B4_REPLACEMENT_REMOVAL"],2.0)
        self.assertAlmostEqual(by["B4_REPLACEMENT_WASTE_TRANSPORT"],10.0)
        self.assertAlmostEqual(by["B4_REPLACEMENT_WASTE_PROCESSING"],200.0)
        self.assertAlmostEqual(by["B4_REPLACEMENT_WASTE_DISPOSAL"],100.0)
        self.assertAlmostEqual(summary.assessed_gwp_kgco2e.iloc[0],322.0)
        self.assertEqual(meta["status"],"EXECUTABLE_B4_EVENT_PROCESS_MAPPING_AVAILABLE")

    def test_source_modules_retained_but_reported_to_b4(self):
        ass=b4p.validate_b4_event_process_assignments(assignment_rows(),self.boq,self.env,self.tf)
        _,_,ledger,_,_=b4p.assess_b4_event_processes(self.boq,self.evt,self.eb,self.env,self.tf,ass)
        self.assertEqual(set(ledger.source_factor_module_scope),{"A5.1","A5.2","A4","C3","C4"})
        self.assertEqual(set(ledger.reported_module),{"B4"})

    def test_wrong_source_module_rejected(self):
        ass=assignment_rows(); ass.loc[0,"expected_source_module"]="C3"
        with self.assertRaises(ValueError): b4p.validate_b4_event_process_assignments(ass,self.boq,self.env,self.tf)

    def test_wrong_factor_registry_rejected(self):
        ass=assignment_rows(); ass.loc[0,"factor_registry"]="TRANSPORT"
        with self.assertRaises(ValueError): b4p.validate_b4_event_process_assignments(ass,self.boq,self.env,self.tf)

    def test_duplicate_active_flow_rejected(self):
        ass=pd.concat([assignment_rows(),assignment_rows().iloc[[0]]],ignore_index=True)
        ass.loc[len(ass)-1,"assignment_id"]="a_install2"
        with self.assertRaises(ValueError): b4p.validate_b4_event_process_assignments(ass,self.boq,self.env,self.tf)

    def test_scope_leakage_rejected(self):
        ass=assignment_rows(); ass.loc[0,"scenario_id"]="scn_deep_pv"
        with self.assertRaises(ValueError): b4p.validate_b4_event_process_assignments(ass,self.boq,self.env,self.tf)

    def test_information_only_boq_rejected(self):
        with self.assertRaises(ValueError): b4p.validate_b4_event_process_assignments(assignment_rows(),boq_table("INFORMATION_ONLY"),self.env,self.tf)

    def test_synthetic_mapping_requires_test_only_basis(self):
        ass=assignment_rows(); ass.loc[0,"mapping_basis"]="DOCUMENTED_PROCESS"
        with self.assertRaises(ValueError): b4p.validate_b4_event_process_assignments(ass,self.boq,self.env,self.tf)

    def test_mass_missing_blocks_mass_based_flows(self):
        b=boq_table(mass=np.nan); b.loc[0,"quantity_unit"]="m2"; b.loc[0,"quantity"]=10.0
        ass=assignment_rows().loc[lambda d:d.process_role.eq("WASTE_PROCESSING")]
        ass=b4p.validate_b4_event_process_assignments(ass,b,self.env,self.tf)
        comp=b4p.build_b4_event_process_compatibility(b,self.env,self.tf,ass)
        self.assertEqual(comp.compatibility_gate_status.iloc[0],"BLOCKED_B4_PROCESS_MASS_MISSING")

    def test_explicit_activity_unit_mismatch_blocks(self):
        ass=assignment_rows().loc[lambda d:d.process_role.eq("INSTALLATION")].copy(); ass.loc[:,"activity_unit"]="mj"
        ass=b4p.validate_b4_event_process_assignments(ass,self.boq,self.env,self.tf)
        comp=b4p.build_b4_event_process_compatibility(self.boq,self.env,self.tf,ass)
        self.assertEqual(comp.compatibility_gate_status.iloc[0],"BLOCKED_B4_PROCESS_UNIT_MISMATCH")

    def test_no_b4_events_is_not_applicable_not_zero(self):
        evt,eb=event_tables(event_type="TEST_EVENT")
        ass=b4p.validate_b4_event_process_assignments(assignment_rows().iloc[[0]],self.boq,self.env,self.tf)
        _,cov,ledger,summary,meta=b4p.assess_b4_event_processes(self.boq,evt,eb,self.env,self.tf,ass)
        self.assertEqual(cov.compatibility_gate_status.iloc[0],"NOT_APPLICABLE_NO_B4_EVENTS_WITHIN_RSP")
        self.assertTrue(ledger.empty); self.assertTrue(summary.empty)
        self.assertFalse(meta["missing_data_treated_as_zero"])

    def test_missing_gwp_total_blocks(self):
        raw=env_factor("f_sub","fs_sub","install","kwh","A5.2",0.5,"GWP_FOSSIL")
        env=validate_environmental_factors(pd.DataFrame([raw],columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        ass=assignment_rows().loc[lambda d:d.process_role.eq("INSTALLATION")].copy(); ass.loc[:,"factor_set_id"]="fs_sub"
        ass=b4p.validate_b4_event_process_assignments(ass,self.boq,env,self.tf)
        comp=b4p.build_b4_event_process_compatibility(self.boq,env,self.tf,ass)
        self.assertEqual(comp.compatibility_gate_status.iloc[0],"BLOCKED_B4_PROCESS_GWP_TOTAL_MISSING")

    def test_non_b4_event_never_generates_consequence(self):
        evt,eb=event_tables(event_type="TEST_EVENT")
        ass=b4p.validate_b4_event_process_assignments(assignment_rows().iloc[[0]],self.boq,self.env,self.tf)
        comp=b4p.build_b4_event_process_compatibility(self.boq,self.env,self.tf,ass)
        ledger=b4p.build_b4_event_process_ledger(evt,eb,self.boq,self.env,self.tf,ass,comp)
        self.assertTrue(ledger.empty)

    def test_append_is_additive_and_preserves_existing_rows(self):
        ass=b4p.validate_b4_event_process_assignments(assignment_rows().iloc[[0]],self.boq,self.env,self.tf)
        _,_,ledger,_,_=b4p.assess_b4_event_processes(self.boq,self.evt,self.eb,self.env,self.tf,ass)
        old=empty_carbon_consequence_ledger()
        row={c:np.nan for c in CARBON_CONSEQUENCE_COLUMNS}; row.update({"carbon_consequence_id":"cc_existing","future_id":0,"scenario_id":"scn_envelope_retrofit","consequence_type":"INITIAL_PRODUCT_STAGE","reported_module":"A1-A3","gwp_kgco2e":1.0})
        old=pd.DataFrame([row],columns=CARBON_CONSEQUENCE_COLUMNS)
        out=b4p.append_b4_event_processes(old,ledger)
        self.assertEqual(out.loc[out.carbon_consequence_id.eq("cc_existing"),"gwp_kgco2e"].iloc[0],1.0)
        self.assertEqual(len(out),2)

    def test_stable_consequence_ids_under_assignment_row_reorder(self):
        ass1=b4p.validate_b4_event_process_assignments(assignment_rows(),self.boq,self.env,self.tf)
        ass2=b4p.validate_b4_event_process_assignments(assignment_rows().iloc[::-1].reset_index(drop=True),self.boq,self.env,self.tf)
        _,_,l1,_,_=b4p.assess_b4_event_processes(self.boq,self.evt,self.eb,self.env,self.tf,ass1)
        _,_,l2,_,_=b4p.assess_b4_event_processes(self.boq,self.evt,self.eb,self.env,self.tf,ass2)
        self.assertEqual(set(l1.carbon_consequence_id),set(l2.carbon_consequence_id))

    def test_event_nesting_controls_b4_process_row_count(self):
        ass=b4p.validate_b4_event_process_assignments(assignment_rows().iloc[[0]],self.boq,self.env,self.tf)
        evt1,eb1=event_tables(event_id="evt_1",future_id=0,generation=1,time=10.0)
        evt2,eb2=event_tables(event_id="evt_2",future_id=0,generation=2,time=20.0)
        evt3,eb3=event_tables(event_id="evt_3",future_id=0,generation=3,time=30.0)
        ledgers=[]
        for evts,ebs in ((evt1,eb1),(pd.concat([evt1,evt2],ignore_index=True),pd.concat([eb1,eb2],ignore_index=True)),
                         (pd.concat([evt1,evt2,evt3],ignore_index=True),pd.concat([eb1,eb2,eb3],ignore_index=True))):
            _,_,ledger,_,_=b4p.assess_b4_event_processes(self.boq,evts,ebs,self.env,self.tf,ass)
            ledgers.append(ledger)
        self.assertEqual([len(x) for x in ledgers],[1,2,3])
        self.assertTrue(set(ledgers[0].carbon_consequence_id).issubset(set(ledgers[1].carbon_consequence_id)))
        self.assertTrue(set(ledgers[1].carbon_consequence_id).issubset(set(ledgers[2].carbon_consequence_id)))

    def test_default_production_input_is_cleanly_not_assessed(self):
        ass=b4p.load_b4_event_process_assignments(m.DEFAULT_B4_EVENT_PROCESS_ASSIGNMENTS,
                                                  m.load_component_boq(m.DEFAULT_COMPONENT_BOQ,m.load_components(m.DEFAULT_COMPONENTS,m.load_scenarios(m.DEFAULT_INPUT)),pd.DataFrame(columns=[])) if False else self.boq,
                                                  self.env,self.tf)
        # Production input is header-only; loader therefore returns an empty table without fabricating flows.
        self.assertTrue(ass.empty)


if __name__=="__main__": unittest.main()
