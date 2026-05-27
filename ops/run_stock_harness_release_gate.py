#!/usr/bin/env python3
"""Run the scoped Stock Harness release gate and emit evidence JSON.

The gate is intentionally claim-scoped. It does not run unrelated CARLA tests and
it does not claim market performance or dominance over named third-party engines.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
CLAIM_STATUS = "supported_for_included_benchmark_suite"
CLAIM_CONTRACT_PATH = Path("benchmarks/downside_verification_v1/claim_contract.json")

PY_COMPILE_TARGETS = [
    "angelos_os/agent_harness.py",
    "angelos_os/performance_defense.py",
    "angelos_os/performance_harness.py",
    "angelos_os/stock_harness.py",
    "angelos_os/__init__.py",
    "angelos_os/engine.py",
    "angelos_os/profiles.py",
    "angelos_os/providers.py",
    "angelos_os/safety.py",
    "angelos_os/schemas.py",
    "angelos_os/score_core.py",
    "angelos_os/validation.py",
    "angelos_os/version.py",
    "ops/benchmark_stock_harness.py",
    "ops/compare_stock_harness_baselines.py",
    "ops/compare_stock_harness_global_frameworks.py",
    "ops/run_stock_agent_harness.py",
    "ops/run_stock_agent_harness_claim_gate.py",
    "ops/run_downside_performance_benchmark.py",
    "ops/run_downside_performance_claim_gate.py",
    "ops/build_downside_performance_defense_packet.py",
    "ops/verify_downside_performance_defense_packet.py",
    "ops/build_downside_performance_public_artifacts.py",
    "ops/seal_v0_2_0_defense_release.py",
    "ops/run_stock_harness_global_claim_gate.py",
    "ops/build_stock_harness_global_claim_packet.py",
    "ops/verify_stock_harness_global_claim_packet.py",
    "ops/run_stock_harness_release_gate.py",
    "ops/run_stock_harness_official_claim_gate.py",
    "ops/build_stock_harness_release_bundle.py",
    "ops/build_stock_harness_evidence_packet.py",
    "ops/verify_stock_harness_evidence_packet.py",
    "ops/build_stock_harness_release_candidate.py",
    "ops/verify_stock_harness_release_candidate.py",
    "ops/replay_stock_harness_release_candidate.py",
    "ops/build_stock_harness_official_claim_packet.py",
    "ops/verify_stock_harness_official_claim_packet.py",
    "ops/audit_stock_harness_release.py",
    "tests/test_downside_performance_harness.py",
    "tests/test_downside_performance_defense.py",
    "tests/test_stock_agent_harness.py",
    "tests/test_stock_harness.py",
]


def _load_claim_contract() -> Dict[str, Any]:
    with (ROOT / CLAIM_CONTRACT_PATH).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _run_command(name: str, command: List[str], env: Mapping[str, str]) -> Dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=dict(env),
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


def _parse_json_stdout(result: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if not result.get("stdout"):
        return None
    try:
        payload = json.loads(str(result["stdout"]))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _command_report_by_name(results: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    return {str(result["name"]): result for result in results}


def _find_cargo() -> Optional[str]:
    cargo_path = shutil.which("cargo")
    if cargo_path:
        return cargo_path
    home_cargo = Path.home() / ".cargo" / "bin" / ("cargo.exe" if os.name == "nt" else "cargo")
    if home_cargo.is_file():
        return str(home_cargo)
    return None


def _build_assertions(results: List[Dict[str, Any]], *, rust_required: bool) -> List[Dict[str, Any]]:
    by_name = _command_report_by_name(results)
    benchmark_payload = _parse_json_stdout(by_name.get("benchmark", {}))
    comparison_payload = _parse_json_stdout(by_name.get("claim_comparison", {}))
    bundle_payload = _parse_json_stdout(by_name.get("release_bundle", {}))
    audit_payload = _parse_json_stdout(by_name.get("release_audit", {}))
    evidence_payload = _parse_json_stdout(by_name.get("evidence_packet", {}))
    evidence_verification_payload = _parse_json_stdout(by_name.get("evidence_packet_verification", {}))
    candidate_payload = _parse_json_stdout(by_name.get("release_candidate", {}))
    candidate_verification_payload = _parse_json_stdout(by_name.get("release_candidate_verification", {}))
    candidate_replay_payload = _parse_json_stdout(by_name.get("release_candidate_replay", {}))

    assertions = [
        {
            "id": "python_compile_passed",
            "passed": bool(by_name.get("py_compile", {}).get("passed")),
        },
        {
            "id": "stock_harness_unit_suite_passed",
            "passed": bool(by_name.get("unit_tests", {}).get("passed")),
        },
        {
            "id": "benchmark_all_passed",
            "passed": bool(benchmark_payload and benchmark_payload.get("all_passed") is True),
        },
        {
            "id": "claim_status_supported",
            "passed": bool(
                comparison_payload
                and comparison_payload.get("claim", {}).get("status") == CLAIM_STATUS
            ),
        },
        {
            "id": "coverage_score_full",
            "passed": bool(
                comparison_payload
                and comparison_payload.get("tools", {})
                .get("angelos_stock_harness", {})
                .get("coverage_score")
                == 1.0
            ),
        },
        {
            "id": "universal_external_dominance_excluded",
            "passed": bool(
                comparison_payload
                and "No universal external-framework dominance claim."
                in comparison_payload.get("claim", {}).get("non_claims", [])
            ),
        },
        {
            "id": "release_bundle_passed",
            "passed": bool(
                bundle_payload
                and bundle_payload.get("schema") == "stock_harness_release_bundle_v1"
                and bundle_payload.get("status") == "passed"
                and bundle_payload.get("file_count", 0) >= 20
            ),
        },
        {
            "id": "release_audit_passed",
            "passed": bool(
                audit_payload
                and audit_payload.get("schema") == "stock_harness_release_audit_v1"
                and audit_payload.get("status") == "passed"
            ),
        },
        {
            "id": "evidence_packet_passed",
            "passed": bool(
                evidence_payload
                and evidence_payload.get("schema") == "stock_harness_evidence_packet_v1"
                and evidence_payload.get("status") == "passed"
                and evidence_payload.get("file_count", 0) >= 7
                and evidence_payload.get("checks", {}).get("benchmark_all_passed") is True
                and evidence_payload.get("checks", {}).get("claim_status_supported") is True
                and evidence_payload.get("checks", {}).get("release_bundle_passed") is True
                and evidence_payload.get("checks", {}).get("release_audit_passed") is True
            ),
        },
        {
            "id": "evidence_packet_verified",
            "passed": bool(
                evidence_verification_payload
                and evidence_verification_payload.get("schema")
                == "stock_harness_evidence_packet_verification_v1"
                and evidence_verification_payload.get("status") == "passed"
                and evidence_verification_payload.get("checks", {}).get("hashes", {}).get("passed") is True
                and evidence_verification_payload.get("checks", {}).get("json_payloads", {}).get("passed") is True
            ),
        },
        {
            "id": "release_candidate_passed",
            "passed": bool(
                candidate_payload
                and candidate_payload.get("schema") == "stock_harness_release_candidate_v1"
                and candidate_payload.get("status") == "passed"
                and candidate_payload.get("component_count") == 2
            ),
        },
        {
            "id": "release_candidate_verified",
            "passed": bool(
                candidate_verification_payload
                and candidate_verification_payload.get("schema")
                == "stock_harness_release_candidate_verification_v1"
                and candidate_verification_payload.get("status") == "passed"
                and candidate_verification_payload.get("checks", {}).get("components", {}).get("passed") is True
                and candidate_verification_payload.get("checks", {}).get("zip_payloads", {}).get("passed") is True
            ),
        },
        {
            "id": "release_candidate_replayed",
            "passed": bool(
                candidate_replay_payload
                and candidate_replay_payload.get("schema")
                == "stock_harness_release_candidate_replay_v1"
                and candidate_replay_payload.get("status") == "passed"
                and len(candidate_replay_payload.get("assertions", [])) >= 6
                and all(
                    assertion.get("passed") is True
                    for assertion in candidate_replay_payload.get("assertions", [])
                )
            ),
        },
        {
            "id": "release_bundle_scope_enforced",
            "passed": bool(
                bundle_payload
                and bundle_payload.get("claim_scope", {}).get("benchmark_suite") == "downside_verification_v1"
                and bundle_payload.get("claim_scope", {}).get("claim_limit")
                == "SOTA-grade deterministic verification coverage only"
                and "No universal external-framework dominance claim."
                in bundle_payload.get("claim_scope", {}).get("non_claims", [])
            ),
        },
    ]

    if rust_required:
        assertions.extend(
            [
                {
                    "id": "rust_unit_tests_passed",
                    "passed": bool(by_name.get("rust_tests", {}).get("passed")),
                },
                {
                    "id": "rust_benchmark_cli_passed",
                    "passed": bool(by_name.get("rust_benchmark", {}).get("passed")),
                },
            ]
        )

    claim_contract = _load_claim_contract()
    required_assertions = list(claim_contract.get("required_release_gate_assertions", []))
    if not rust_required:
        required_assertions = [
            assertion_id
            for assertion_id in required_assertions
            if not assertion_id.startswith("rust_")
        ]
    present_assertions = set(assertion["id"] for assertion in assertions)
    present_assertions.add("claim_contract_required_assertions_present")
    assertions.append(
        {
            "id": "claim_contract_required_assertions_present",
            "passed": all(
                assertion_id in present_assertions for assertion_id in required_assertions
            ),
            "required_assertions": required_assertions,
        }
    )
    return assertions


def run_release_gate(skip_rust: bool = False) -> Dict[str, Any]:
    env = dict(os.environ)
    tmpdir = env.get("STOCK_HARNESS_TMPDIR")
    if tmpdir:
        Path(tmpdir).mkdir(parents=True, exist_ok=True)

    python = sys.executable
    commands: List[Dict[str, Any]] = []
    commands.append(
        _run_command("py_compile", [python, "-m", "py_compile"] + PY_COMPILE_TARGETS, env)
    )
    commands.append(
        _run_command("unit_tests", [python, "-m", "unittest", "tests/test_stock_harness.py"], env)
    )
    commands.append(
        _run_command("benchmark", [python, "ops/benchmark_stock_harness.py", "--pretty"], env)
    )
    commands.append(
        _run_command(
            "claim_comparison",
            [python, "ops/compare_stock_harness_baselines.py", "--pretty"],
            env,
        )
    )

    commands.append(
        _run_command(
            "release_bundle",
            [python, "ops/build_stock_harness_release_bundle.py", "--clean", "--pretty"],
            env,
        )
    )

    commands.append(
        _run_command(
            "release_audit",
            [python, "ops/audit_stock_harness_release.py", "--pretty"],
            env,
        )
    )

    commands.append(
        _run_command(
            "evidence_packet",
            [python, "ops/build_stock_harness_evidence_packet.py", "--clean", "--pretty"],
            env,
        )
    )

    commands.append(
        _run_command(
            "evidence_packet_verification",
            [python, "ops/verify_stock_harness_evidence_packet.py", "--pretty"],
            env,
        )
    )

    commands.append(
        _run_command(
            "release_candidate",
            [python, "ops/build_stock_harness_release_candidate.py", "--clean", "--pretty"],
            env,
        )
    )

    commands.append(
        _run_command(
            "release_candidate_verification",
            [python, "ops/verify_stock_harness_release_candidate.py", "--pretty"],
            env,
        )
    )

    replay_command = [python, "ops/replay_stock_harness_release_candidate.py", "--clean", "--pretty"]
    if skip_rust:
        replay_command.append("--skip-rust")
    commands.append(
        _run_command(
            "release_candidate_replay",
            replay_command,
            env,
        )
    )

    cargo_path = _find_cargo()
    rust_required = not skip_rust
    if skip_rust:
        rust_status = "skipped_by_request"
    elif not cargo_path:
        rust_status = "missing_cargo"
        commands.append(
            {
                "name": "rust_toolchain",
                "command": ["cargo", "--version"],
                "returncode": None,
                "elapsed_seconds": 0.0,
                "stdout": "",
                "stderr": "cargo executable was not found on PATH",
                "passed": False,
            }
        )
    else:
        rust_status = "required"
        commands.append(
            _run_command(
                "rust_tests",
                [cargo_path, "test", "--manifest-path", "rust_stock_harness/Cargo.toml"],
                env,
            )
        )
        commands.append(
            _run_command(
                "rust_benchmark",
                [
                    cargo_path,
                    "run",
                    "--manifest-path",
                    "rust_stock_harness/Cargo.toml",
                    "--bin",
                    "stock-harness-benchmark",
                    "--",
                    "--pretty",
                ],
                env,
            )
        )

    assertions = _build_assertions(commands, rust_required=rust_required)
    all_assertions_passed = all(assertion["passed"] for assertion in assertions)
    python_gate_passed = all(command["passed"] for command in commands if not command["name"].startswith("rust"))
    official_claim_ready = all_assertions_passed and rust_required and rust_status == "required"

    comparison_payload = _parse_json_stdout(_command_report_by_name(commands).get("claim_comparison", {}))
    claim = comparison_payload.get("claim", {}) if comparison_payload else {}

    return {
        "schema": "stock_harness_release_gate_v1",
        "generated_at_unix": int(time.time()),
        "root": str(ROOT),
        "environment": {
            "python_executable": python,
            "python_version": sys.version,
            "platform": platform.platform(),
            "stock_harness_tmpdir": env.get("STOCK_HARNESS_TMPDIR", ""),
            "cargo_path": cargo_path or "",
        },
        "claim": claim,
        "claim_scope": {
            "benchmark_suite": "downside_verification_v1",
            "positive_claim_limit": "verification coverage only",
            "non_claims_enforced": [
                "No financial advice.",
                "No live trading readiness claim.",
                "No order routing or broker integration claim.",
                "No investment-performance or alpha-generation claim.",
                "No universal external-framework dominance claim.",
            ],
        },
        "rust_status": rust_status,
        "python_gate_passed": python_gate_passed,
        "official_claim_ready": official_claim_ready,
        "overall_status": "passed" if official_claim_ready else "not_official_full_gate",
        "assertions": assertions,
        "commands": commands,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the scoped Stock Harness release gate.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument("--output", help="Optional path to write the evidence JSON.")
    parser.add_argument(
        "--skip-rust",
        action="store_true",
        help="Run only the Python claim gate. This is useful on local hosts without cargo and is not a full official release gate.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_release_gate(skip_rust=args.skip_rust)
    text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["official_claim_ready"] or (args.skip_rust and report["python_gate_passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
