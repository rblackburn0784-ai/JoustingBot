"""v2.9.4 asset preflight. Run from the checkout root:

python tools/audit_assets_v294.py
python tools/audit_assets_v294.py --strict
python tools/audit_assets_v294.py --json

Without --strict, missing optional art is a warning but corrupt art is an error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.asset_health import audit_assets


def main() -> int:
    parser = argparse.ArgumentParser(description="JoustingBot v2.9.4 graphics health")
    parser.add_argument("--strict", action="store_true", help="fail when artwork is missing")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    result = audit_assets()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"JoustingBot assets: {result['present']}/{result['expected']} present, "
              f"{result['missing']} missing, {len(result['errors'])} invalid")
        for group, numbers in result["groups"].items():
            print(f"  {group}: {numbers['present']}/{numbers['expected']}")
        for issue in result["errors"]:
            print("ERROR:", issue)
        for issue in result["warnings"]:
            print("MISSING:", issue)
    return 2 if result["errors"] else (1 if args.strict and result["missing"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
