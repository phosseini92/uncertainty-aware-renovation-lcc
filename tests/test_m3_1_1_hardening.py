import json
import unittest
from pathlib import Path

import pandas as pd

import renovation_lcc as m
import b6_operational as b6
from environmental_factors import ENVIRONMENTAL_FACTOR_COLUMNS, validate_environmental_factors


class M311HardeningTests(unittest.TestCase):
    def test_default_config_declares_release_policies(self):
        cfg = m.load_config(m.DEFAULT_CONFIG)
        self.assertEqual(cfg["assessment_convention"], "EN15978_2026_INFORMED")
        self.assertEqual(cfg["generated_energy_reporting_approach"], "PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED")
        self.assertEqual(cfg["factor_extrapolation_policy"], "ERROR_IF_MISSING")

    def test_unsupported_b6_runtime_policies_are_rejected(self):
        cfg = json.loads(Path(m.DEFAULT_CONFIG).read_text())
        cfg["factor_extrapolation_policy"] = "HOLD_LAST_VALUE"
        with self.assertRaisesRegex(ValueError, "ERROR_IF_MISSING"):
            m.validate_config(cfg)
        cfg = json.loads(Path(m.DEFAULT_CONFIG).read_text())
        cfg["generated_energy_reporting_approach"] = "NOT_CONFIGURED"
        with self.assertRaisesRegex(ValueError, "PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED"):
            m.validate_config(cfg)

    def test_reference_year_is_provenance_vintage_not_application_year(self):
        scenarios = m.load_scenarios(m.DEFAULT_INPUT)
        factor = {
            "factor_record_id":"f_b6_vintage","factor_set_id":"fs_b6_vintage","dataset_id":"test_dataset",
            "product_or_process_id":"grid","indicator_id":"GWP_TOTAL","indicator_value":0.25,
            "indicator_unit":"kgco2e","declared_unit":"kwh","module_scope":"B6","geography":"TEST",
            "reference_year":2020,"source_type":"TEST_ONLY_SYNTHETIC","source_citation":"fixture",
            "verification_status":"TEST_ONLY","data_quality_status":"TEST_ONLY","license_status":"TEST_ONLY",
            "redistribution_allowed":False,"uncertainty_mode":"DETERMINISTIC","uncertainty_semantics":"NOT_APPLICABLE",
            "uncertainty_parameter_1":float('nan'),"uncertainty_parameter_2":float('nan'),"uncertainty_parameter_3":float('nan'),
            "uncertainty_basis":"","notes":"",
        }
        factors = validate_environmental_factors(pd.DataFrame([factor], columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        schedule = pd.DataFrame([["sched","electricity",1,2035,"fs_b6_vintage","TEST_ONLY_SYNTHETIC","fixture","2026-09-28",""]],
                                columns=b6.OPERATIONAL_FACTOR_SCHEDULE_COLUMNS)
        validated = b6.validate_operational_factor_schedule(schedule, factors)
        self.assertEqual(int(validated.calendar_year.iloc[0]), 2035)
        self.assertEqual(int(factors.reference_year.iloc[0]), 2020)

    def test_b6_meta_echoes_explicit_runtime_policy(self):
        empty_flows = b6.empty_operational_energy_flows()
        empty_schedule = b6.empty_operational_factor_schedule()
        factors = validate_environmental_factors(pd.DataFrame(columns=ENVIRONMENTAL_FACTOR_COLUMNS))
        _, ledger, _, meta = b6.assess_operational_energy(
            empty_flows, empty_schedule, factors, [0], 30,
            factor_extrapolation_policy="ERROR_IF_MISSING",
            generated_energy_reporting_approach="PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED",
        )
        self.assertTrue(ledger.empty)
        self.assertEqual(meta["factor_extrapolation_policy"], "ERROR_IF_MISSING")
        self.assertEqual(meta["generated_energy_reporting_approach"], "PHYSICAL_FLOWS_B6_IMPORT_ONLY_D2_DEFERRED")
        self.assertEqual(meta["factor_reference_year_semantics"], "DATASET_OR_SOURCE_REFERENCE_VINTAGE_NOT_APPLICATION_YEAR")

    def test_public_readme_does_not_link_to_uncommitted_outputs(self):
        readme = (m.PROJECT_DIR / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("](outputs/", readme)
        self.assertNotIn("](outputs/", readme)
        self.assertIn("Release history and provenance", readme)
        self.assertIn("bounded research release closing the current lifecycle-carbon architecture.", readme)
        self.assertIn("Generated `outputs/` files are **not committed** to the public source repository.", readme)


if __name__ == "__main__":
    unittest.main()
