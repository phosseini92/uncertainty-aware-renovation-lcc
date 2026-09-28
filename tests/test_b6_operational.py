import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import renovation_lcc as m
import b6_operational as b6
from environmental_factors import ENVIRONMENTAL_FACTOR_COLUMNS, validate_environmental_factors


def env_factor(record="f_b6_y1", setid="fs_b6_y1", process="grid_y1", value=0.5,
               module="B6", unit="kwh", indicator="GWP_TOTAL", uncertainty_mode="DETERMINISTIC"):
    return {
        "factor_record_id":record,"factor_set_id":setid,"dataset_id":"test_dataset","product_or_process_id":process,
        "indicator_id":indicator,"indicator_value":value,"indicator_unit":"kgco2e","declared_unit":unit,"module_scope":module,
        "geography":"TEST","reference_year":2026,"source_type":"TEST_ONLY_SYNTHETIC","source_citation":"Synthetic fixture",
        "verification_status":"TEST_ONLY","data_quality_status":"TEST_ONLY","license_status":"TEST_ONLY","redistribution_allowed":False,
        "uncertainty_mode":uncertainty_mode,"uncertainty_semantics":"NOT_APPLICABLE" if uncertainty_mode=="DETERMINISTIC" else "EPISTEMIC",
        "uncertainty_parameter_1":np.nan,"uncertainty_parameter_2":np.nan,"uncertainty_parameter_3":np.nan,
        "uncertainty_basis":"","notes":"",
    }


def flow_row(flow_id="flow_import", flow_type="IMPORTED", q=100.0, first=1, last=2, schedule="sched_b6",
             scenario="scn_envelope_retrofit", carrier="electricity"):
    return [flow_id,scenario,carrier,flow_type,q,first,last,schedule,
            "TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""]


def schedule_row(year=1, calendar=2027, setid="fs_b6_y1", schedule="sched_b6", carrier="electricity"):
    return [schedule,carrier,year,calendar,setid,"TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""]


class B6OperationalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = m.load_scenarios(m.DEFAULT_INPUT)

    def factors_two_years(self):
        return validate_environmental_factors(pd.DataFrame([
            env_factor("f_b6_y1","fs_b6_y1","grid_y1",0.5),
            env_factor("f_b6_y2","fs_b6_y2","grid_y2",0.4),
        ], columns=ENVIRONMENTAL_FACTOR_COLUMNS))

    def flows(self, rows):
        return b6.validate_operational_energy_flows(pd.DataFrame(rows, columns=b6.OPERATIONAL_ENERGY_FLOW_COLUMNS), self.scenarios)

    def schedule(self, rows, factors):
        return b6.validate_operational_factor_schedule(pd.DataFrame(rows, columns=b6.OPERATIONAL_FACTOR_SCHEDULE_COLUMNS), factors)

    def test_empty_production_schema_is_valid(self):
        self.assertTrue(b6.validate_operational_energy_flows(b6.empty_operational_energy_flows(), self.scenarios).empty)
        self.assertTrue(b6.validate_operational_factor_schedule(b6.empty_operational_factor_schedule(), validate_environmental_factors(pd.DataFrame(columns=ENVIRONMENTAL_FACTOR_COLUMNS))).empty)

    def test_import_requires_explicit_schedule(self):
        with self.assertRaisesRegex(ValueError, "requires an explicit"):
            self.flows([flow_row(schedule="")])

    def test_non_import_cannot_carry_b6_schedule(self):
        with self.assertRaisesRegex(ValueError, "Only IMPORTED"):
            self.flows([flow_row(flow_type="GENERATED", schedule="sched_b6")])

    def test_negative_energy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            self.flows([flow_row(q=-1.0)])

    def test_overlapping_piecewise_flow_intervals_are_rejected(self):
        rows=[flow_row("flow_a", first=1,last=2), flow_row("flow_b",first=2,last=3)]
        with self.assertRaisesRegex(ValueError, "Overlapping operational flow intervals"):
            self.flows(rows)

    def test_declared_pv_balance_is_checked_year_by_year(self):
        rows=[
            flow_row("flow_gen","GENERATED",50,1,2,""),
            flow_row("flow_self","SELF_CONSUMED",40,1,2,""),
            flow_row("flow_export","EXPORTED",20,1,2,""),
        ]
        with self.assertRaisesRegex(ValueError, r"SELF_CONSUMED \+ EXPORTED exceeds GENERATED"):
            self.flows(rows)

    def test_pv_balance_allows_documented_curtailment(self):
        rows=[
            flow_row("flow_gen","GENERATED",100,1,2,""),
            flow_row("flow_self","SELF_CONSUMED",50,1,2,""),
            flow_row("flow_export","EXPORTED",20,1,2,""),
        ]
        self.assertEqual(len(self.flows(rows)),3)

    def test_schedule_requires_exact_b6_gwp_total_kwh(self):
        wrong_scope=validate_environmental_factors(pd.DataFrame([env_factor(module="A4")],columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        with self.assertRaisesRegex(ValueError,"exact B6 scope"):
            self.schedule([schedule_row()],wrong_scope)
        wrong_unit=validate_environmental_factors(pd.DataFrame([env_factor(unit="mj")],columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        with self.assertRaisesRegex(ValueError,"kwh declared unit"):
            self.schedule([schedule_row()],wrong_unit)
        wrong_indicator=validate_environmental_factors(pd.DataFrame([env_factor(indicator="GWP_FOSSIL")],columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        with self.assertRaisesRegex(ValueError,"GWP_TOTAL"):
            self.schedule([schedule_row()],wrong_indicator)

    def test_negative_b6_factor_credit_is_rejected(self):
        factors=validate_environmental_factors(pd.DataFrame([env_factor(value=-0.1)],columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        with self.assertRaisesRegex(ValueError,"negative credits"):
            self.schedule([schedule_row()],factors)

    def test_schedule_calendar_mapping_must_be_consistent(self):
        factors=self.factors_two_years()
        rows=[schedule_row(1,2027,"fs_b6_y1"), schedule_row(2,2029,"fs_b6_y2")]
        with self.assertRaisesRegex(ValueError,"inconsistent analysis-year/calendar-year mapping"):
            self.schedule(rows,factors)

    def test_missing_schedule_year_blocks_whole_import_flow(self):
        factors=self.factors_two_years()
        flows=self.flows([flow_row()])
        schedule=self.schedule([schedule_row(1,2027,"fs_b6_y1")],factors)
        cov,ledger,_,meta=b6.assess_operational_energy(flows,schedule,factors,[0],2)
        self.assertEqual(cov.b6_status.iloc[0],"BLOCKED_INCOMPLETE_B6_FACTOR_SCHEDULE")
        self.assertTrue(ledger.empty)
        self.assertTrue(meta["future_factor_policy"].startswith("EXPLICIT_ANNUAL_SCHEDULE"))

    def test_schedule_carrier_mismatch_blocks_execution(self):
        factors=self.factors_two_years()
        flows=self.flows([flow_row()])
        schedule=self.schedule([
            schedule_row(1,2027,"fs_b6_y1",carrier="gas"),
            schedule_row(2,2028,"fs_b6_y2",carrier="gas"),
        ],factors)
        cov,ledger,_,_=b6.assess_operational_energy(flows,schedule,factors,[0],2)
        self.assertEqual(cov.b6_status.iloc[0],"BLOCKED_FACTOR_SCHEDULE_CARRIER_MISMATCH")
        self.assertTrue(ledger.empty)

    def test_closed_form_two_year_b6_and_midyear_timing(self):
        factors=self.factors_two_years()
        flows=self.flows([flow_row(q=100.0)])
        schedule=self.schedule([
            schedule_row(1,2027,"fs_b6_y1"),schedule_row(2,2028,"fs_b6_y2")
        ],factors)
        cov,ledger,summary,meta=b6.assess_operational_energy(flows,schedule,factors,[0,1],2)
        self.assertEqual(cov.b6_status.iloc[0],"PASS_COMPLETE_B6_FACTOR_SCHEDULE")
        self.assertEqual(len(ledger),4)
        self.assertAlmostEqual(ledger.loc[ledger.future_id.eq(0),"gwp_kgco2e"].sum(),90.0)
        self.assertEqual(sorted(ledger.event_time_years.unique().tolist()),[0.5,1.5])
        self.assertTrue(ledger.reported_module.eq("B6").all())
        self.assertTrue(ledger.lifecycle_event_id.isna().all())
        self.assertAlmostEqual(summary.loc[summary.future_id.eq(0),"assessed_gwp_kgco2e"].iloc[0],90.0)
        self.assertFalse(meta["factor_uncertainty_applied"])

    def test_horizon_truncates_active_years_without_scaling(self):
        factors=self.factors_two_years()
        flows=self.flows([flow_row(q=100.0,first=1,last=2)])
        schedule=self.schedule([schedule_row(1,2027,"fs_b6_y1"),schedule_row(2,2028,"fs_b6_y2")],factors)
        _,ledger,_,_=b6.assess_operational_energy(flows,schedule,factors,[0],1)
        self.assertEqual(len(ledger),1)
        self.assertAlmostEqual(float(ledger.gwp_kgco2e.iloc[0]),50.0)

    def test_export_is_tracked_but_never_credited_or_netted(self):
        factors=self.factors_two_years()
        flows=self.flows([
            flow_row("flow_import","IMPORTED",100,1,2,"sched_b6"),
            flow_row("flow_gen","GENERATED",50,1,2,""),
            flow_row("flow_self","SELF_CONSUMED",30,1,2,""),
            flow_row("flow_export","EXPORTED",20,1,2,""),
        ])
        schedule=self.schedule([schedule_row(1,2027,"fs_b6_y1"),schedule_row(2,2028,"fs_b6_y2")],factors)
        cov,ledger,_,meta=b6.assess_operational_energy(flows,schedule,factors,[0],2)
        export_cov=cov.loc[cov.flow_type.eq("EXPORTED")].iloc[0]
        self.assertEqual(export_cov.export_treatment,"TRACKED_ONLY_D2_DEFERRED_NOT_NETTED_IN_A_C")
        self.assertEqual(len(ledger),2)
        self.assertFalse(meta["export_credit_calculated"])
        self.assertFalse(meta["export_credit_netted_into_a_c"])
        self.assertEqual(meta["d2_status"],"DEFERRED_SEPARATE_BEYOND_BOUNDARY_MILESTONE")

    def test_explicit_zero_import_is_not_missing_and_emits_no_zero_row(self):
        factors=self.factors_two_years()
        flows=self.flows([flow_row(q=0.0)])
        schedule=self.schedule([schedule_row(1,2027,"fs_b6_y1"),schedule_row(2,2028,"fs_b6_y2")],factors)
        cov,ledger,summary,meta=b6.assess_operational_energy(flows,schedule,factors,[0],2)
        self.assertEqual(cov.b6_status.iloc[0],"PASS_EXPLICIT_ZERO_IMPORTED_ENERGY")
        self.assertTrue(ledger.empty); self.assertTrue(summary.empty)
        self.assertEqual(meta["b6_explicit_zero_import_flow_rows"],1)
        self.assertFalse(meta["missing_data_treated_as_zero"])

    def test_factor_uncertainty_metadata_is_retained_not_sampled(self):
        factor=env_factor(uncertainty_mode="TRIANGULAR")
        factor["uncertainty_parameter_1"]=0.4;factor["uncertainty_parameter_2"]=0.5;factor["uncertainty_parameter_3"]=0.6;factor["uncertainty_basis"]="fixture"
        factors=validate_environmental_factors(pd.DataFrame([factor],columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        flows=self.flows([flow_row(first=1,last=1)])
        schedule=self.schedule([schedule_row()],factors)
        _,ledger,_,_=b6.assess_operational_energy(flows,schedule,factors,[0],1)
        self.assertEqual(ledger.factor_uncertainty_mode.iloc[0],"TRIANGULAR")
        self.assertEqual(bool(ledger.factor_uncertainty_applied.iloc[0]),False)

    def test_default_production_run_is_clean_not_assessed(self):
        with tempfile.TemporaryDirectory() as td:
            m.run(output_dir=Path(td),simulations=5,charts=False,convergence_enabled=False)
            status=__import__('json').loads((Path(td)/"b6_operational_energy_engine_status.json").read_text())
            self.assertEqual(status["status"],"NO_OPERATIONAL_ENERGY_FLOWS")
            self.assertFalse(status["missing_data_treated_as_zero"])
            self.assertFalse(status["legacy_annual_energy_savings_proxy_used_for_carbon"])
            self.assertTrue((Path(td)/"resolved_operational_energy_flows.csv").exists())
            self.assertTrue((Path(td)/"operational_energy_coverage.csv").exists())
            self.assertTrue((Path(td)/"assessed_operational_carbon_by_module.csv").exists())

    def test_full_run_populated_b6_is_integrated_and_legacy_proxy_isolated(self):
        factors = pd.DataFrame([
            env_factor("f_b6_y1","fs_b6_y1","grid_y1",0.5),
            env_factor("f_b6_y2","fs_b6_y2","grid_y2",0.4),
        ], columns=ENVIRONMENTAL_FACTOR_COLUMNS)
        flows = pd.DataFrame([
            flow_row("flow_import","IMPORTED",100,1,2,"sched_b6"),
            flow_row("flow_gen","GENERATED",50,1,2,""),
            flow_row("flow_self","SELF_CONSUMED",30,1,2,""),
            flow_row("flow_export","EXPORTED",20,1,2,""),
        ], columns=b6.OPERATIONAL_ENERGY_FLOW_COLUMNS)
        schedule = pd.DataFrame([
            schedule_row(1,2027,"fs_b6_y1"), schedule_row(2,2028,"fs_b6_y2"),
        ], columns=b6.OPERATIONAL_FACTOR_SCHEDULE_COLUMNS)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            factors_path=root/"environmental_factors.csv"; factors.to_csv(factors_path,index=False)
            flows_path=root/"operational_energy_flows.csv"; flows.to_csv(flows_path,index=False)
            schedule_path=root/"operational_energy_factor_schedule.csv"; schedule.to_csv(schedule_path,index=False)
            out1=root/"out1"
            m.run(output_dir=out1,simulations=2,charts=False,convergence_enabled=False,
                  environmental_factors_path=factors_path,
                  operational_energy_flows_path=flows_path,
                  operational_energy_factor_schedule_path=schedule_path)
            ledger1=pd.read_csv(out1/"carbon_consequence_ledger.csv")
            b6rows1=ledger1.loc[ledger1.reported_module.eq("B6")].copy()
            self.assertEqual(len(b6rows1),4)
            self.assertAlmostEqual(b6rows1.loc[b6rows1.future_id.eq(0),"gwp_kgco2e"].sum(),90.0)
            self.assertTrue(b6rows1.consequence_type.eq("B6_OPERATIONAL_ENERGY_IMPORT").all())
            self.assertFalse((ledger1.reported_module.astype(str)=="D2").any())

            # Change the legacy economic energy-savings proxy drastically. B6 must remain byte-equivalent
            # in its consequence values because operational carbon consumes only explicit physical flows.
            scenarios=pd.read_csv(m.DEFAULT_INPUT)
            mask=scenarios["is_reference"].eq(0)
            scenarios.loc[mask,"annual_energy_savings_kwh"] = scenarios.loc[mask,"annual_energy_savings_kwh"] * 9 + 12345
            scenarios_path=root/"renovation_scenarios_modified.csv"; scenarios.to_csv(scenarios_path,index=False)
            out2=root/"out2"
            m.run(input_path=scenarios_path,output_dir=out2,simulations=2,charts=False,convergence_enabled=False,
                  environmental_factors_path=factors_path,
                  operational_energy_flows_path=flows_path,
                  operational_energy_factor_schedule_path=schedule_path)
            ledger2=pd.read_csv(out2/"carbon_consequence_ledger.csv")
            b6rows2=ledger2.loc[ledger2.reported_module.eq("B6")].copy()
            cols=["future_id","scenario_id","event_time_years","assignment_id","factor_record_id","gwp_kgco2e"]
            pd.testing.assert_frame_equal(b6rows1[cols].reset_index(drop=True), b6rows2[cols].reset_index(drop=True))


if __name__ == "__main__":
    unittest.main()
