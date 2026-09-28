"""Reproduce M2.1 -> M2.2 default and populated-fixture parity.

Usage: python scripts/audit_m2_2.py --baseline /path/to/extracted/M2.1 --output-root /tmp/audit
The baseline must be the unmodified verified M2.1 package. Large output trees
stay outside the deliverable. Synthetic fixture data never enter production.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HORIZONS = ("legacy_30", "levels_50", "rics_60")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(old, new):
    a = {p.name: p for p in old.iterdir() if p.is_file() and p.name != "run_manifest.json"}
    b = {p.name: p for p in new.iterdir() if p.is_file() and p.name != "run_manifest.json"}
    common = sorted(a.keys() & b.keys())
    hashes = {name: {"m21": digest(a[name]), "m22": digest(b[name])} for name in common}
    different = [name for name in common if hashes[name]["m21"] != hashes[name]["m22"]]
    return {"common_nonmanifest_count": len(common), "byte_identical_count": len(common)-len(different),
            "different_common_nonmanifest": different, "new_only": sorted(b.keys()-a.keys()),
            "old_only": sorted(a.keys()-b.keys()), "sha256": hashes}


def run(project, out, horizon, n, fixture, is_new):
    args = [sys.executable, str(ROOT/"scripts/audit_model_runner.py"), str(project/"renovation_lcc.py"), "--output-dir", str(out),
            "--simulations", str(n), "--seed", "20260726", "--horizon-mode", horizon,
            "--no-charts", "--skip-convergence"]
    if fixture:
        p = ROOT/"tests/fixtures/m22_transport_synthetic"
        for flag, name in [("--component-boq", "component_boq"), ("--environmental-factors", "environmental_factors"),
                           ("--boq-factor-assignments", "boq_environmental_factor_assignments")]:
            args += [flag, str(p/(name+".csv"))]
        if is_new:
            for flag, name in [("--transport-scenarios", "transport_scenarios"), ("--transport-factors", "transport_factors"),
                               ("--boq-transport-assignments", "boq_transport_assignments")]:
                args += [flag, str(p/(name+".csv"))]
    print("RUN", project.name, horizon, "synthetic" if fixture else "production", flush=True)
    with (out.parent/(out.name+".log")).open("w") as log:
        subprocess.run(args, cwd=project, stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--simulations", type=int, default=10000)
    parser.add_argument("--reuse-verified-baseline-default", action="store_true",
                        help="Reuse only M2.1 default runs after verifying manifest source/input hashes, seed and N.")
    args = parser.parse_args()
    baseline, out = args.baseline.resolve(), args.output_root.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {"simulations": args.simulations, "seed": 20260726, "capture": "READ_ONLY_CSV_ROW_COUNT_AND_FINAL_HASH_CHECKS_ON_BOTH_VERSIONS", "production": {}, "synthetic": {}}
    reference_a4 = None
    for fixture in (False, True):
        for horizon in HORIZONS:
            suffix = ("synthetic_" if fixture else "") + horizon
            old, new = out/("m21_"+suffix), out/("m22_"+suffix)
            if args.reuse_verified_baseline_default and not fixture:
                meta = json.loads((old/"run_manifest.json").read_text())
                assert meta["simulations"] == args.simulations and meta["seed"] == 20260726
                assert meta["migration_checkpoint"] == "v3-M2.1" and meta["horizon_mode"] == horizon
                assert not meta["charts_requested"] and not meta["convergence_enabled"]
                assert all(digest(baseline/name) == sha for name, sha in meta["source_sha256"].items())
                names = {"config": "model_config", "scenarios": "renovation_scenarios", "stress_cases": "climate_stress_scenarios"}
                for label, sha in meta["input_sha256"].items():
                    file = baseline/"inputs"/(names.get(label, label)+(".json" if label == "config" else ".csv"))
                    assert digest(file) == sha
            else:
                run(baseline, old, horizon, args.simulations, fixture, False)
            run(ROOT, new, horizon, args.simulations, fixture, True)
            result = compare(old, new)
            assert not result["old_only"]
            if not fixture:
                assert not result["different_common_nonmanifest"], result
                events = pd.read_csv(new/"lifecycle_event_ledger.csv")
                result["lifecycle_event_count"] = len(events)
            else:
                assert result["different_common_nonmanifest"] == ["carbon_consequence_ledger.csv"]
                # Strip appended A4 CSV records without reserializing the product rows.
                # This tests product consequences byte-for-byte as serialized by each run.
                old_lines = (old/"carbon_consequence_ledger.csv").read_bytes().splitlines(keepends=True)
                new_lines = (new/"carbon_consequence_ledger.csv").read_bytes().splitlines(keepends=True)
                product_lines = [line for line in new_lines if b",INITIAL_TRANSPORT_TO_SITE," not in line]
                assert product_lines == old_lines, "Product ledger bytes changed"
                ledger = pd.read_csv(new/"carbon_consequence_ledger.csv", low_memory=False)
                product = ledger.loc[ledger.reported_module.ne("A4")]
                a4 = ledger.loc[ledger.reported_module.eq("A4")].reset_index(drop=True)
                assert len(a4) == args.simulations and a4.gwp_kgco2e.eq(10.0).all()
                assert a4.event_time_years.eq(0.0).all() and a4.lifecycle_event_id.isna().all()
                assert {"A1-A3", "B4"}.issubset(set(product.reported_module))
                if reference_a4 is not None:
                    pd.testing.assert_frame_equal(reference_a4, a4)
                reference_a4 = a4
                result.update(product_rows_byte_identical=True, product_row_count=len(product),
                              product_rows_by_module=product.reported_module.value_counts().to_dict(),
                              a4_row_count=len(a4), a4_gwp_per_future_kgco2e=10.0,
                              a4_horizon_invariance=True)
            report["synthetic" if fixture else "production"][horizon] = result
            (out/"M2.2_PARITY_DETAILS.json").write_text(json.dumps(report, indent=2)+"\n")
            print("PASS", suffix, flush=True)
    report["result"] = "PASS"
    (out/"M2.2_PARITY_DETAILS.json").write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main()
