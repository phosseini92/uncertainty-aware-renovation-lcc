import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import renovation_lcc as m
import a5_construction as a5
import a4_transport as a4
from component_lifecycle import load_components
from physical_quantities import COMPONENT_BOQ_COLUMNS


class A5ConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.components = load_components(m.DEFAULT_COMPONENTS, m.load_scenarios(m.DEFAULT_INPUT))
        cls.p = cls.components.iloc[6]  # short-life component gives B4 events too

    def tables(self, waste_basis="BOQ_WASTE_RATE"):
        p = self.p
        boq = pd.DataFrame([dict(zip(COMPONENT_BOQ_COLUMNS, (
            "boq_a5_test", p.scenario_id, p.component_instance_id, p.comparison_lineage_id,
            p.component_type_id, "Synthetic A5 item", "product_a5_test", "ASSESSMENT_INVENTORY",
            1000.0, "kg", 1000.0, "TEST_ONLY_SYNTHETIC", "Synthetic A5 fixture", "", "",
        )))])
        factors = pd.DataFrame([
            self.factor("pf_a5", "pfs_a5", "product_a5", "kg", "A1-A3", 2.5),
            self.factor("a52f", "a52fs", "installation_energy", "kwh", "A5.2", 0.5),
            self.factor("a53f", "a53fs", "waste_process", "kg", "A5.3", 0.2),
        ], columns=a4.ENVIRONMENTAL_FACTOR_COLUMNS)
        proc = pd.DataFrame([dict(zip(a5.CONSTRUCTION_PROCESS_SCENARIO_COLUMNS, (
            "cps_a5", "ELECTRICITY", "kwh", "a52fs", "TEST_ONLY_SYNTHETIC",
            "Synthetic A5.2 process", "2026-09-28", "",
        )))])
        if waste_basis == "BOQ_WASTE_RATE":
            wr, wq, wu, wfs = 0.05, np.nan, "", "a53fs"
        elif waste_basis == "EXPLICIT_WASTE_QUANTITY":
            wr, wq, wu, wfs = np.nan, 50.0, "kg", "a53fs"
        else:
            wr, wq, wu, wfs = np.nan, np.nan, "", ""
        assign = pd.DataFrame([dict(zip(a5.BOQ_CONSTRUCTION_PROCESS_ASSIGNMENT_COLUMNS, (
            "a5a_test", "boq_a5_test", p.scenario_id, "cps_a5", "a5flow_test", True,
            "EXPLICIT_ACTIVITY_QUANTITY", 20.0, waste_basis, wr, wq, wu, wfs,
            "TEST_ONLY_SYNTHETIC", "Synthetic explicit A5 mapping", "",
        )))])
        return boq, factors, proc, assign

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

    def test_golden_a52_and_a53(self):
        boq, factors, proc, assign = self.tables()
        factors = a4.validate_transport_factors(pd.DataFrame(columns=a4.TRANSPORT_FACTOR_COLUMNS)) if False else factors
        from environmental_factors import validate_environmental_factors
        factors = validate_environmental_factors(factors)
        proc = a5.validate_construction_process_scenarios(proc, factors)
        assign = a5.validate_boq_construction_process_assignments(assign, boq, proc, factors)
        comp, cov, ledger, summary, status = a5.assess_initial_a5(boq, proc, factors, assign, [0,1])
        # A5.2 = 20 kWh * 0.5 = 10; A5.3 = 1000 kg * 5% * 0.2 = 10.
        self.assertEqual(ledger.loc[ledger.reported_module.eq("A5.2"), "gwp_kgco2e"].tolist(), [10.0,10.0])
        self.assertEqual(ledger.loc[ledger.reported_module.eq("A5.3"), "gwp_kgco2e"].tolist(), [10.0,10.0])
        self.assertEqual(status["a5_2_gate_pass_lines"], 1)
        self.assertEqual(status["a5_3_gate_pass_lines"], 1)

    def test_explicit_waste_quantity_matches_rate_fixture(self):
        from environmental_factors import validate_environmental_factors
        vals=[]
        for basis in ("BOQ_WASTE_RATE", "EXPLICIT_WASTE_QUANTITY"):
            boq,factors,proc,assign=self.tables(basis)
            factors=validate_environmental_factors(factors); proc=a5.validate_construction_process_scenarios(proc,factors)
            assign=a5.validate_boq_construction_process_assignments(assign,boq,proc,factors)
            vals.append(a5.assess_initial_a5(boq,proc,factors,assign,[0])[2].loc[lambda x:x.reported_module.eq("A5.3"),"gwp_kgco2e"].iloc[0])
        self.assertEqual(vals,[10.0,10.0])

    def test_none_waste_does_not_create_a53(self):
        from environmental_factors import validate_environmental_factors
        boq,factors,proc,assign=self.tables("NONE")
        factors=validate_environmental_factors(factors); proc=a5.validate_construction_process_scenarios(proc,factors)
        assign=a5.validate_boq_construction_process_assignments(assign,boq,proc,factors)
        comp,cov,ledger,_,_=a5.assess_initial_a5(boq,proc,factors,assign,[0])
        self.assertEqual(set(ledger.reported_module),{"A5.2"})
        self.assertEqual(comp.a5_3_gate_status.iloc[0],"NOT_APPLICABLE_NO_CURRENT_CONSTRUCTION_WASTE")

    def test_wrong_a52_scope_blocks_without_reclassifying(self):
        from environmental_factors import validate_environmental_factors
        boq,factors,proc,assign=self.tables()
        factors.loc[factors.factor_set_id.eq("a52fs"),"module_scope"]="A5.3"
        factors=validate_environmental_factors(factors); proc=a5.validate_construction_process_scenarios(proc,factors)
        assign=a5.validate_boq_construction_process_assignments(assign,boq,proc,factors)
        comp,_,ledger,_,_=a5.assess_initial_a5(boq,proc,factors,assign,[0])
        self.assertEqual(comp.a5_2_gate_status.iloc[0],"BLOCKED_A5_2_GWP_TOTAL_MISSING")
        self.assertFalse(ledger.consequence_type.eq("A5_2_CONSTRUCTION_INSTALLATION").any())

    def test_wrong_a53_scope_blocks(self):
        from environmental_factors import validate_environmental_factors
        boq,factors,proc,assign=self.tables()
        factors.loc[factors.factor_set_id.eq("a53fs"),"module_scope"]="A5.2"
        factors=validate_environmental_factors(factors); proc=a5.validate_construction_process_scenarios(proc,factors)
        assign=a5.validate_boq_construction_process_assignments(assign,boq,proc,factors)
        comp,_,ledger,_,_=a5.assess_initial_a5(boq,proc,factors,assign,[0])
        self.assertEqual(comp.a5_3_gate_status.iloc[0],"BLOCKED_A5_3_GWP_TOTAL_MISSING")
        self.assertFalse(ledger.consequence_type.eq("A5_3_CURRENT_CONSTRUCTION_WASTE").any())

    def test_missing_mass_for_mass_based_waste_blocks(self):
        from environmental_factors import validate_environmental_factors
        boq,factors,proc,assign=self.tables()
        boq.loc[0,["quantity","quantity_unit","mass_kg"]]=[10.0,"m2",np.nan]
        factors=validate_environmental_factors(factors); proc=a5.validate_construction_process_scenarios(proc,factors)
        assign=a5.validate_boq_construction_process_assignments(assign,boq,proc,factors)
        comp,_,ledger,_,_=a5.assess_initial_a5(boq,proc,factors,assign,[0])
        self.assertEqual(comp.a5_3_gate_status.iloc[0],"BLOCKED_A5_3_WASTE_UNIT_OR_MASS")
        self.assertFalse(ledger.reported_module.eq("A5.3").any())

    def test_duplicate_flow_and_scope_leak_are_hard_failures(self):
        from environmental_factors import validate_environmental_factors
        boq,factors,proc,assign=self.tables(); factors=validate_environmental_factors(factors)
        proc=a5.validate_construction_process_scenarios(proc,factors)
        dup=pd.concat([assign,assign.assign(assignment_id="a5a_second",boq_line_id="boq_a5_test")],ignore_index=True)
        with self.assertRaises(ValueError): a5.validate_boq_construction_process_assignments(dup,boq,proc,factors)
        bad=assign.copy(); bad.loc[0,"scenario_id"]="foreign_scope"
        with self.assertRaisesRegex(ValueError,"scope leakage"): a5.validate_boq_construction_process_assignments(bad,boq,proc,factors)

    def run_fixture(self,horizon="legacy_30",with_a5=True):
        boq,factors,proc,assign=self.tables()
        p=self.p
        # product mapping for same line
        prodmap=pd.DataFrame([{"assignment_id":"pa_a5","boq_line_id":"boq_a5_test","factor_set_id":"pfs_a5",
                              "mapping_basis":"TEST_ONLY_SYNTHETIC","mapping_reference":"fixture","notes":""}])
        # no transport in this fixture, to isolate A5
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); paths={}
            for key,table in [("component_boq_path",boq),("environmental_factors_path",factors),
                              ("boq_factor_assignments_path",prodmap),
                              ("construction_process_scenarios_path",proc),
                              ("boq_construction_process_assignments_path",assign if with_a5 else assign.iloc[:0])]:
                path=root/(key+".csv"); table.to_csv(path,index=False); paths[key]=path
            out=root/"out"
            m.run(output_dir=out,simulations=2,charts=False,convergence_enabled=False,horizon_mode=horizon,**paths)
            return {x.name:x.read_bytes() for x in out.iterdir() if x.is_file()}

    def test_a5_is_t0_and_horizon_invariant(self):
        totals=[]
        for h in ("legacy_30","levels_50","rics_60"):
            files=self.run_fixture(h)
            ledger=pd.read_csv(io.BytesIO(files["carbon_consequence_ledger.csv"]),low_memory=False)
            a5rows=ledger.loc[ledger.reported_module.isin(["A5.2","A5.3"])]
            self.assertTrue(a5rows.event_time_years.eq(0).all())
            self.assertTrue(a5rows.lifecycle_event_id.isna().all())
            totals.append(a5rows.groupby("future_id").gwp_kgco2e.sum().tolist())
        self.assertEqual(totals,[[20.0,20.0]]*3)

    def test_a5_addition_does_not_change_product_subengine(self):
        old=self.run_fixture(with_a5=False); new=self.run_fixture(with_a5=True)
        for name in ("assessed_product_carbon_by_module.csv","product_carbon_coverage.csv","carbon_engine_status.json",
                     "lifecycle_event_ledger.csv","lifecycle_replacements.csv","simulation_results.csv","scenario_summary.csv"):
            self.assertEqual(old[name],new[name],name)

    def test_production_empty_is_not_assessed_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td); m.run(output_dir=out,simulations=2,charts=False,convergence_enabled=False)
            status=json.loads((out/"a5_construction_engine_status.json").read_text())
            self.assertEqual(status["status"],"NO_ASSESSMENT_BOQ_LINES")
            self.assertFalse(status["missing_data_treated_as_zero"])
            self.assertTrue(pd.read_csv(out/"assessed_a5_construction_carbon_by_module.csv").empty)
            self.assertIn("A5.1_PRECONSTRUCTION_REMOVAL",status["explicitly_deferred"])


if __name__ == "__main__":
    unittest.main()
