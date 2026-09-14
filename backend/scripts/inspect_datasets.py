"""
Phase 1 entrypoint: inspect every registered dataset and render the reports.

    python scripts/inspect_datasets.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocessing.dataset_inspector import inspect_all, REPORTS  # noqa: E402


def main():
    print("=" * 74)
    print("PHASE 1 -- DATASET INSPECTION")
    print("=" * 74)
    results = inspect_all()
    print()
    print("wrote %s" % (REPORTS / "inspection.json"))

    ok = [k for k, v in results.items() if "inspection" in v]
    missing = [k for k, v in results.items() if not v.get("exists")]
    failed = [k for k, v in results.items() if "error" in v]
    print("inspected=%d  missing=%d  failed=%d" % (len(ok), len(missing), len(failed)))
    if missing:
        print("missing: %s" % ", ".join(missing))
    if failed:
        for k in failed:
            print("failed : %s -> %s" % (k, results[k]["error"]))


if __name__ == "__main__":
    main()
