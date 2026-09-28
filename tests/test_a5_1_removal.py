import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import renovation_lcc as m
import a5_1_removal as a51
import a4_transport as a4
from environmental_factors import validate_environmental_factors
from physical_quantities import COMPONENT_BOQ_COLUMNS


class A51RemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        cls.scenario_id = "scn_envelope_retrofit"
        cls.empty_boq = pd.DataFrame(columns=COMPONENT_BOQ_COLUMNS)

    @staticmethod
    def factor(record, setid, process, unit, module, value):
        return {
            "factor_record_id": record, "factor_set_id": setid, "dataset_id": "test_dataset",
            "product_or_process_id": process, "indicator_id": "GWP_TOTAL", "indicator_value": value,
            "indicator_unit": "kgco2e", "declared_unit": unit, "module_scope": module, "geography": "TEST",
            "reference_year": 2026, "source_type": "TEST_ONLY_SYNTHETIC", "source_citation": "Synthetic fixture",
            "verification_status": "TEST_ONLY", "data_quality_status": "TEST_ONLY", "license_status": "TEST_ONLY",
            "redistribution_allowed": False, "uncertainty_mode": "DETERMINISTIC", "uncertainty_semantics": "NOT_APPLICABLE",
            "uncertainty_parameter_1": np.nan, "uncertainty_parameter_2": np.nan, "uncertainty_parameter_3": np.nan,
            "uncertainty_basis": "", "notes": "",
        }

    @staticmethod
    def transport_factor():
        d = A51RemovalTests.factor("tf_remove", "tfs_remove", "truck_transport", "tkm", "A4", 0.1)
        d.update({
            "transport_mode": "ROAD", "vehicle_class": "RIGID_TRUCK", "load_factor_basis": "DOCUMENTED_FACTOR_BASIS",
            "factor_system_boundary": "TANK_TO_WHEEL_PLUS_UPSTREAM", "retrieval_date": "2026-09-28",
        })
        return d

    def tables(self):
        env = validate_environmental_factors(pd.DataFrame([
            self.factor("rf_remove", "rfs_remove", "strip_out_energy", "kwh", "A5.1", 0.5),
            self.factor("wf_remove", "wfs_remove", "waste_processing", "kg", "C3", 0.2),
        ], columns=a4.ENVIRONMENTAL_FACTOR_COLUMNS))
        tf = a4.validate_transport_factors(pd.DataFrame([self.transport_factor()], columns=a4.TRANSPORT_FACTOR_COLUMNS))
        tr = pd.DataFrame([dict(zip(a51.REMOVAL_TRANSPORT_SCENARIO_COLUMNS, (
            "rts_remove", "PROJECT_SITE", "WASTE_PROCESSING_FACILITY", 100.0,
            "ROAD", "RIGID_TRUCK", "DOCUMENTED_FACTOR_BASIS", "tfs_remove",
            "TEST_ONLY_SYNTHETIC", "Synthetic outbound route", "2026-09-28", "",
        )))])
        wr = pd.DataFrame([dict(zip(a51.WASTE_ROUTE_SCENARIO_COLUMNS, (
            "wrs_remove", "PROCESSING", "C3", "wfs_remove", "WASTE_PROCESSING_FACILITY",
            "TEST_ONLY_SYNTHETIC", "Synthetic waste route", "2026-09-28", "",
        )))])
        rem = pd.DataFrame([dict(zip(a51.PRECONSTRUCTION_REMOVAL_COLUMNS, (
            "rem_remove", self.scenario_id, "rboq_remove", "removed_window_old", "lineage_window_existing",
            "existing_window_system", "rfs_remove", 20.0, "kwh", 1000.0, "kg", 1000.0,
            "rts_remove", "wrs_remove", "", True, "TEST_ONLY_SYNTHETIC", "TEST_ONLY_SYNTHETIC",
            "Synthetic removed-at-t0 fixture", "2026-09-28", "TEST_ONLY_SYNTHETIC", "",
        )))])
        tr = a51.validate_removal_transport_scenarios(tr, tf)
        wr = a51.validate_preconstruction_waste_routes(wr, env)
        rem = a51.validate_preconstruction_removal_scenarios(rem, self.scenarios, self.empty_boq, env, tr, wr)
        return env, tf, tr, wr, rem

    def test_golden_three_subconsequences(self):
        env,tf,tr,wr,rem=self.tables()
        comp,cov,ledger,summary,status=a51.assess_a5_1(rem,env,tr,tf,wr,[0,1])
        bytype=ledger.groupby("consequence_type").gwp_kgco2e.unique().to_dict()
        self.assertEqual(bytype["A5_1_PRECONSTRUCTION_REMOVAL_ACTIVITY"].tolist(),[10.0])
        self.assertEqual(bytype["A5_1_REMOVED_MATERIAL_TRANSPORT"].tolist(),[10.0])
        self.assertEqual(bytype["A5_1_REMOVED_MATERIAL_WASTE_TREATMENT"].tolist(),[200.0])
        self.assertEqual(summary.assessed_gwp_kgco2e.tolist(),[220.0,220.0])
        self.assertEqual(status["status"],"COMPLETE_EXECUTABLE_A5_1_REMOVAL_MAPPING")
        self.assertEqual(cov.overall_a5_1_status.iloc[0],"PASS_COMPLETE_A5_1_REMOVAL_ACCOUNTING")

    def test_source_process_modules_are_reclassified_only_for_reporting(self):
        env,tf,tr,wr,rem=self.tables()
        ledger=a51.assess_a5_1(rem,env,tr,tf,wr,[0])[2]
        self.assertTrue(ledger.reported_module.eq("A5.1").all())
        src=dict(zip(ledger.consequence_type,ledger.source_factor_module_scope))
        self.assertEqual(src["A5_1_PRECONSTRUCTION_REMOVAL_ACTIVITY"],"A5.1")
        self.assertEqual(src["A5_1_REMOVED_MATERIAL_TRANSPORT"],"A4")
        self.assertEqual(src["A5_1_REMOVED_MATERIAL_WASTE_TREATMENT"],"C3")

    def test_t0_no_lifecycle_event_and_no_c_stage_reporting(self):
        env,tf,tr,wr,rem=self.tables(); ledger=a51.assess_a5_1(rem,env,tr,tf,wr,[0])[2]
        self.assertTrue(ledger.event_time_years.eq(0).all())
        self.assertTrue(ledger.component_generation.eq(0).all())
        self.assertTrue(ledger.lifecycle_event_id.isna().all())
        self.assertFalse(ledger.reported_module.isin(["A5.3","C1","C2","C3","C4"]).any())

    def test_missing_mass_blocks_transport_not_other_subflows(self):
        env,tf,tr,wr,rem=self.tables()
        rem.loc[0,"removed_quantity_unit"]="m2"; rem.loc[0,"removed_mass_kg"]=np.nan
        rem=a51.validate_preconstruction_removal_scenarios(rem,self.scenarios,self.empty_boq,env,tr,wr)
        comp,cov,ledger,_,_=a51.assess_a5_1(rem,env,tr,tf,wr,[0])
        self.assertEqual(comp.transport_gate_status.iloc[0],"BLOCKED_A5_1_REMOVAL_TRANSPORT_MASS_MISSING")
        self.assertTrue(comp.removal_activity_gate_status.iloc[0].startswith("PASS_"))
        self.assertEqual(comp.waste_gate_status.iloc[0],"BLOCKED_A5_1_WASTE_UNIT_OR_MASS")
        self.assertEqual(set(ledger.consequence_type),{"A5_1_PRECONSTRUCTION_REMOVAL_ACTIVITY"})

    def test_missing_distance_blocks_transport_without_zero_default(self):
        env,tf,tr,wr,rem=self.tables(); tr.loc[0,"distance_km"]=np.nan
        tr=a51.validate_removal_transport_scenarios(tr,tf)
        comp=a51.build_a5_1_compatibility(rem,env,tr,tf,wr)
        self.assertEqual(comp.transport_gate_status.iloc[0],"BLOCKED_A5_1_REMOVAL_TRANSPORT_DISTANCE_MISSING")

    def test_documented_zero_distance_is_valid_zero(self):
        env,tf,tr,wr,rem=self.tables(); tr.loc[0,"distance_km"]=0.0
        tr=a51.validate_removal_transport_scenarios(tr,tf)
        ledger=a51.assess_a5_1(rem,env,tr,tf,wr,[0])[2]
        row=ledger.loc[ledger.consequence_type.eq("A5_1_REMOVED_MATERIAL_TRANSPORT")].iloc[0]
        self.assertEqual(row.gwp_kgco2e,0.0)

    def test_wrong_removal_activity_scope_blocks(self):
        env,tf,tr,wr,rem=self.tables()
        raw=env.copy(); raw.loc[raw.factor_set_id.eq("rfs_remove"),"module_scope"]="A5.2"
        env=validate_environmental_factors(raw)
        comp=a51.build_a5_1_compatibility(rem,env,tr,tf,wr)
        self.assertEqual(comp.removal_activity_gate_status.iloc[0],"BLOCKED_A5_1_REMOVAL_GWP_TOTAL_MISSING")

    def test_waste_route_module_type_mismatch_is_hard_failure(self):
        env,tf,tr,wr,rem=self.tables(); bad=wr.copy(); bad.loc[0,"expected_source_module"]="C4"
        with self.assertRaisesRegex(ValueError,"conflicts"):
            a51.validate_preconstruction_waste_routes(bad,env)

    def test_removed_inventory_cannot_reuse_current_construction_ids(self):
        env,tf,tr,wr,rem=self.tables()
        boq=pd.DataFrame([dict(zip(COMPONENT_BOQ_COLUMNS, (
            "rboq_remove", self.scenario_id, "removed_window_old", "lineage_x", "type_x", "x", "x",
            "ASSESSMENT_INVENTORY", 1.0, "kg", 1.0, "TEST_ONLY_SYNTHETIC", "fixture", "", "",
        )))])
        with self.assertRaisesRegex(ValueError,"disjoint"):
            a51.validate_preconstruction_removal_scenarios(rem,self.scenarios,boq,env,tr,wr)

    def test_reference_scope_rejected(self):
        env,tf,tr,wr,rem=self.tables(); rem.loc[0,"scenario_id"]="scn_reference_minimum_intervention"
        with self.assertRaisesRegex(ValueError,"reference"):
            a51.validate_preconstruction_removal_scenarios(rem,self.scenarios,self.empty_boq,env,tr,wr)

    def test_d1_declaration_is_recorded_but_not_calculated(self):
        env,tf,tr,wr,rem=self.tables(); rem.loc[0,"d1_recovery_scenario_id"]="d1_future_recovery"
        rem=a51.validate_preconstruction_removal_scenarios(rem,self.scenarios,self.empty_boq,env,tr,wr)
        status=a51.assess_a5_1(rem,env,tr,tf,wr,[0])[4]
        self.assertEqual(status["d1_recovery_declarations_present"],1)
        self.assertFalse(status["d1_recovery_credit_calculated"])

    def run_fixture(self,horizon):
        env,tf,tr,wr,rem=self.tables()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            paths={}
            for key,table in [
                ("environmental_factors_path",env), ("transport_factors_path",tf),
                ("removal_transport_scenarios_path",tr), ("preconstruction_waste_routes_path",wr),
                ("preconstruction_removal_scenarios_path",rem),
            ]:
                path=root/(key+".csv"); table.to_csv(path,index=False); paths[key]=path
            out=root/"out"
            m.run(output_dir=out,simulations=2,charts=False,convergence_enabled=False,horizon_mode=horizon,**paths)
            return {x.name:x.read_bytes() for x in out.iterdir() if x.is_file()}

    def test_a51_is_horizon_invariant(self):
        totals=[]
        for h in ("legacy_30","levels_50","rics_60"):
            files=self.run_fixture(h)
            ledger=pd.read_csv(io.BytesIO(files["carbon_consequence_ledger.csv"]),low_memory=False)
            rows=ledger.loc[ledger.reported_module.eq("A5.1")]
            totals.append(rows.groupby("future_id").gwp_kgco2e.sum().tolist())
        self.assertEqual(totals,[[220.0,220.0]]*3)

    def test_production_empty_is_not_assessed_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td); m.run(output_dir=out,simulations=2,charts=False,convergence_enabled=False)
            status=json.loads((out/"a5_1_preconstruction_removal_engine_status.json").read_text())
            self.assertEqual(status["status"],"NO_PRECONSTRUCTION_REMOVAL_INVENTORY")
            self.assertFalse(status["missing_data_treated_as_zero"])
            self.assertTrue(pd.read_csv(out/"assessed_a5_1_preconstruction_removal_carbon_by_module.csv").empty)


if __name__ == "__main__":
    unittest.main()
