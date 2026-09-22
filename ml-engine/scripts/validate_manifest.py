#!/usr/bin/env python3
"""
validate_manifest.py
SIH 2026 PS 26011 — ML Engine, Phase 1

Validates all dataset manifests in datasets/manifests/ against the
dataset_manifest.json JSON Schema.

Usage:
    python scripts/validate_manifest.py
    python scripts/validate_manifest.py --manifest datasets/manifests/specific.json

Exits with code 1 if any manifest fails validation.
"""
import argparse
import json
import pathlib
import sys

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "dataset_manifest.json"
MANIFESTS_DIR = PROJECT_ROOT / "datasets" / "manifests"

ALLOWED_STATUS = {"REAL", "DERIVED", "SYNTHETIC", "INFERRED", "MIXED"}


def load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_manifest(path: pathlib.Path, schema: dict) -> list[str]:
    """Returns list of error messages; empty list = valid."""
    errors = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {e}")
        return errors

    # Schema validation
    validator = jsonschema.Draft7Validator(schema)
    for err in validator.iter_errors(data):
        errors.append(f"Schema: {err.path} — {err.message}")

    # Additional business rules
    status = data.get("status", "")
    if status not in ALLOWED_STATUS:
        errors.append(f"status '{status}' not in allowed values: {ALLOWED_STATUS}")

    url = data.get("url", "")
    if not url.startswith("http"):
        errors.append(f"url does not start with http: '{url}'")

    if not data.get("limitations", "").strip():
        errors.append("limitations field is empty — must document known limitations")

    if not data.get("intended_use", "").strip():
        errors.append("intended_use field is empty")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate dataset manifests.")
    parser.add_argument(
        "--manifest", type=pathlib.Path, default=None,
        help="Path to a single manifest file. If omitted, validates all manifests."
    )
    args = parser.parse_args()

    schema = load_schema()

    if args.manifest:
        targets = [args.manifest]
    else:
        targets = sorted(MANIFESTS_DIR.glob("*.json"))
        # Exclude .gitkeep and schema files
        targets = [p for p in targets if p.name != ".gitkeep"]

    if not targets:
        print("No manifests found. Nothing to validate.")
        sys.exit(0)

    all_passed = True
    results = []
    for path in targets:
        if not path.exists():
            print(f"MISSING: {path}")
            all_passed = False
            continue
        errors = validate_manifest(path, schema)
        status = "PASS" if not errors else "FAIL"
        results.append((path.name, status, errors))
        if errors:
            all_passed = False

    # Report
    print(f"\n{'='*60}")
    print(f"MANIFEST VALIDATION REPORT")
    print(f"{'='*60}")
    for name, status, errors in results:
        marker = "[+]" if status == "PASS" else "[-]"
        print(f"  {marker} {status}  {name}")
        for e in errors:
            print(f"       ERROR: {e}")
    print(f"{'='*60}")
    print(f"Total: {len(results)} | Passed: {sum(1 for _,s,_ in results if s=='PASS')} | Failed: {sum(1 for _,s,_ in results if s=='FAIL')}")
    print()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
