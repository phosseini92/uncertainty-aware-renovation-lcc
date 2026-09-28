"""Run an unmodified model with read-only CSV integrity checks for audit capture.

The same harness is used for baseline and candidate. It changes no model input,
calculation or CSV serialization; it checks each completed export against the
in-memory row count and rechecks its hash after the entire model returns.
"""
import csv
import hashlib
from pathlib import Path
import runpy
import sys

import pandas as pd


def main():
    target = Path(sys.argv[1]).resolve()
    sys.argv = sys.argv[1:]
    sys.path.insert(0, str(target.parent))
    original = pd.DataFrame.to_csv
    written = {}

    def checked_csv(table, path_or_buf=None, *args, **kwargs):
        result = original(table, path_or_buf, *args, **kwargs)
        if isinstance(path_or_buf, (str, Path)):
            path = Path(path_or_buf)
            payload = path.read_bytes()
            with path.open(newline="", encoding="utf-8") as stream:
                rows = sum(1 for _ in csv.reader(stream)) - 1
            if rows != len(table):
                raise RuntimeError(f"CSV export row-count mismatch: {path.name}: {rows} != {len(table)}")
            written[path] = hashlib.sha256(payload).hexdigest()
        return result

    pd.DataFrame.to_csv = checked_csv
    try:
        runpy.run_path(str(target), run_name="__main__")
        for path, expected in written.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"CSV artifact changed after export: {path.name}")
        print(f"CSV_INTEGRITY_PASS: {len(written)} files; all row counts and final hashes verified.")
    finally:
        pd.DataFrame.to_csv = original


if __name__ == "__main__":
    main()
