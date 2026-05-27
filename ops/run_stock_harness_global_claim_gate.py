#!/usr/bin/env python3
"""Run the Stock Harness global verification-claim gate.

This gate is intentionally stricter than the scoped official gate. It is not
allowed to pass until every required named external framework has direct adapter
evidence in the global_verification_v1 benchmark.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.compare_stock_harness_global_frameworks import run_global_comparison

PY_COMPILE_TARGETS = [
    "ops/compare_stock_harness_global_frameworks.py",
    "ops/run_stock_harness_global_claim_gate.py",
]


def _run_command(name: str, command: List[str]) -> Dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        return {
            "name": name,
            "command": command,
            "returncode": completed.returncode,
            "elapsed_seconds": round(time.time() - started, 6),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "passed": completed.returncode == 0,
        }
    except OSError as exc:
        return {
            "name": name,
            "command": command,
            "returncode": None,
            "elapsed_seconds": round(time.time() - started, 6),
            "stdout": "",
            "stderr": str(exc),
            "passed": False,
        }


def _build_assertions(global_report: Mapping[str, Any], py_compile_passed: bool) -> List[Dict[str, Any]]:
    publication = global_report.get("publication_requirements", {})
    checks = publication.get("checks", {})
    claim = global_report.get("claim", {})
    return [
        {"id": "global_gate_py_compile_passed", "passed": py_compile_passed},
        {
            "id": "global_comparison_schema_valid",
            "passed": global_report.get("schema") == "stock_harness_global_framework_comparison_v1",
        },
        {
            "id": "scoped_benchmark_still_passed",
            "passed": global_report.get("benchmark", {}).get("scoped_benchmark_all_passed") is True,
        },
        {
            "id": "stock_harness_global_coverage_full",
            "passed": checks.get("stock_harness_global_coverage_full") is True,
        },
        {
            "id": "all_required_external_adapters_executed",
            "passed": checks.get("all_required_external_adapters_executed") is True,
        },
        {
            "id": "external_adapter_versions_fingerprinted",
            "passed": checks.get("external_adapter_versions_fingerprinted") is True,
        },
        {
            "id": "stock_harness_ranked_first_by_coverage_score",
            "passed": checks.get("stock_harness_ranked_first_by_coverage_score") is True,
        },
        {
            "id": "stock_harness_score_strictly_exceeds_each_external_framework",
            "passed": checks.get("stock_harness_score_strictly_exceeds_each_external_framework") is True,
        },
        {
            "id": "global_non_claims_preserved",
            "passed": checks.get("global_non_claims_preserved") is True,
        },
        {
            "id": "profile_only_frameworks_excluded_from_supported_claim",
            "passed": checks.get("profile_only_frameworks_excluded_from_supported_claim") is True,
        },
        {
            "id": "global_claim_status_supported",
            "passed": claim.get("status") == "supported_for_named_external_framework_benchmark_suite",
        },
    ]


def run_global_claim_gate(run_external_adapters: bool = True) -> Dict[str, Any]:
    python = sys.executable
    commands = [
        _run_command("py_compile", [python, "-m", "py_compile"] + PY_COMPILE_TARGETS),
    ]
    global_report = run_global_comparison(run_external_adapters=run_external_adapters)
    assertions = _build_assertions(global_report, py_compile_passed=commands[0]["passed"])
    global_claim_ready = all(assertion["passed"] for assertion in assertions)
    return {
        "schema": "stock_harness_global_claim_gate_v1",
        "generated_at_unix": int(time.time()),
        "root": str(ROOT),
        "environment": {
            "python_executable": python,
            "python_version": sys.version,
            "platform": platform.platform(),
        },
        "claim_scope": {
            "benchmark_suite": "global_verification_v1",
            "positive_claim_limit": "global deterministic verification coverage only",
            "publication_requirement": "all named external framework adapters executed with version fingerprints",
        },
        "global_claim_ready": global_claim_ready,
        "overall_status": "passed" if global_claim_ready else "not_global_claim_ready",
        "assertions": assertions,
        "commands": commands,
        "global_comparison": global_report,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Stock Harness global verification claim gate.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument("--output", help="Optional path to write the evidence JSON.")
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="Do not execute external adapters. This always prevents a supported global claim.",
    )
    parser.add_argument(
        "--allow-not-supported",
        action="store_true",
        help="Exit 0 even when the global claim is not ready. Useful for generating gap reports.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = run_global_claim_gate(run_external_adapters=not args.profile_only)
    text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if report["global_claim_ready"] or args.allow_not_supported:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
