#!/usr/bin/env python3
"""Run the final Stock Harness official-claim publication gate.

This gate is stricter than the local release gate. It requires a full
Python+Cargo release gate, embeds that gate JSON into the evidence packet,
verifies the evidence packet and release candidate with official-readiness
checks enabled, and replays the packaged release source zip.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
CLAIM_STATUS = "supported_for_included_benchmark_suite"
BENCHMARK_SUITE = "downside_verification_v1"
OFFICIAL_RELEASE_GATE_JSON = Path("reports/stock_harness_release_gate_official.json")
OFFICIAL_REPLAY_JSON = Path("reports/stock_harness_release_candidate_replay_official.json")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_json_stdout(result: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        payload = json.loads(str(result.get("stdout", "")))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _command_for_report(result: Mapping[str, Any]) -> Dict[str, Any]:
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    return {
        "name": result.get("name"),
        "command": result.get("command"),
        "returncode": result.get("returncode"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "passed": result.get("passed"),
        "stdout_bytes": len(stdout.encode("utf-8")),
        "stderr_bytes": len(stderr.encode("utf-8")),
        "stdout_tail": _truncate(stdout),
        "stderr_tail": _truncate(stderr),
    }


def _assertion_lookup(assertions: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    return {str(assertion.get("id")): assertion for assertion in assertions if isinstance(assertion, dict)}


def _all_assertions_passed(assertions: Iterable[Mapping[str, Any]]) -> bool:
    items = [assertion for assertion in assertions if isinstance(assertion, dict)]
    return bool(items) and all(assertion.get("passed") is True for assertion in items)


def _build_assertions(
    commands: List[Dict[str, Any]],
    release_gate: Mapping[str, Any],
    evidence_verification: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_verification: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    release_assertions = _assertion_lookup(release_gate.get("assertions", []))
    replay_assertions = list(replay.get("assertions", []))
    release_gate_non_claims = release_gate.get("claim_scope", {}).get("non_claims_enforced", [])
    return [
        {
            "id": "full_release_gate_official_ready",
            "passed": bool(
                release_gate.get("schema") == "stock_harness_release_gate_v1"
                and release_gate.get("official_claim_ready") is True
                and release_gate.get("overall_status") == "passed"
                and release_gate.get("rust_status") == "required"
                and release_gate.get("python_gate_passed") is True
                and release_assertions.get("rust_unit_tests_passed", {}).get("passed") is True
                and release_assertions.get("rust_benchmark_cli_passed", {}).get("passed") is True
                and release_assertions.get("release_candidate_replayed", {}).get("passed") is True
            ),
        },
        {
            "id": "evidence_packet_verified_for_publication",
            "passed": bool(
                evidence_verification.get("schema")
                == "stock_harness_evidence_packet_verification_v1"
                and evidence_verification.get("status") == "passed"
                and evidence_verification.get("require_release_gate_json") is True
                and evidence_verification.get("require_official_claim_ready") is True
                and evidence_verification.get("checks", {})
                .get("json_payloads", {})
                .get("checks", {})
                .get("release_gate_official_ready")
                is True
            ),
        },
        {
            "id": "release_candidate_built_for_publication",
            "passed": bool(
                candidate.get("schema") == "stock_harness_release_candidate_v1"
                and candidate.get("status") == "passed"
                and candidate.get("component_count") == 2
            ),
        },
        {
            "id": "release_candidate_verified_for_publication",
            "passed": bool(
                candidate_verification.get("schema")
                == "stock_harness_release_candidate_verification_v1"
                and candidate_verification.get("status") == "passed"
                and candidate_verification.get("require_release_gate_json") is True
                and candidate_verification.get("require_official_claim_ready") is True
                and candidate_verification.get("checks", {})
                .get("zip_payloads", {})
                .get("checks", {})
                .get("release_gate_official_ready")
                is True
            ),
        },
        {
            "id": "release_candidate_replayed_for_publication",
            "passed": bool(
                replay.get("schema") == "stock_harness_release_candidate_replay_v1"
                and replay.get("status") == "passed"
                and replay.get("require_release_gate_json") is True
                and replay.get("require_official_claim_ready") is True
                and replay.get("skip_rust") is False
                and _all_assertions_passed(replay_assertions)
                and any(
                    assertion.get("id") == "extracted_rust_unit_tests_passed"
                    and assertion.get("passed") is True
                    for assertion in replay_assertions
                )
                and any(
                    assertion.get("id") == "extracted_rust_benchmark_cli_passed"
                    and assertion.get("passed") is True
                    for assertion in replay_assertions
                )
            ),
        },
        {
            "id": "scoped_non_claims_preserved",
            "passed": bool(
                release_gate.get("claim", {}).get("status") == CLAIM_STATUS
                and release_gate.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
                and "No universal external-framework dominance claim." in release_gate_non_claims
                and "No investment-performance or alpha-generation claim." in release_gate_non_claims
            ),
        },
        {
            "id": "official_commands_completed",
            "passed": all(command.get("passed") is True for command in commands),
        },
    ]


def run_official_claim_gate() -> Dict[str, Any]:
    env = dict(os.environ)
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    python = sys.executable
    release_gate_path = ROOT / OFFICIAL_RELEASE_GATE_JSON
    replay_path = ROOT / OFFICIAL_REPLAY_JSON

    commands: List[Dict[str, Any]] = []
    commands.append(
        _run_command(
            "full_release_gate",
            [
                python,
                "ops/run_stock_harness_release_gate.py",
                "--pretty",
                "--output",
                str(OFFICIAL_RELEASE_GATE_JSON).replace("\\", "/"),
            ],
            env,
        )
    )
    commands.append(
        _run_command(
            "evidence_packet",
            [
                python,
                "ops/build_stock_harness_evidence_packet.py",
                "--clean",
                "--pretty",
                "--release-gate-json",
                str(OFFICIAL_RELEASE_GATE_JSON).replace("\\", "/"),
            ],
            env,
        )
    )
    commands.append(
        _run_command(
            "evidence_packet_verification",
            [
                python,
                "ops/verify_stock_harness_evidence_packet.py",
                "--pretty",
                "--require-release-gate-json",
                "--require-official-claim-ready",
            ],
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
            [
                python,
                "ops/verify_stock_harness_release_candidate.py",
                "--pretty",
                "--require-release-gate-json",
                "--require-official-claim-ready",
            ],
            env,
        )
    )
    commands.append(
        _run_command(
            "release_candidate_replay",
            [
                python,
                "ops/replay_stock_harness_release_candidate.py",
                "--clean",
                "--pretty",
                "--require-release-gate-json",
                "--require-official-claim-ready",
                "--output",
                str(OFFICIAL_REPLAY_JSON).replace("\\", "/"),
            ],
            env,
        )
    )

    release_gate = _load_json(release_gate_path)
    evidence_verification = _parse_json_stdout(
        next(command for command in commands if command["name"] == "evidence_packet_verification")
    )
    candidate = _parse_json_stdout(next(command for command in commands if command["name"] == "release_candidate"))
    candidate_verification = _parse_json_stdout(
        next(command for command in commands if command["name"] == "release_candidate_verification")
    )
    replay = _load_json(replay_path)

    assertions = _build_assertions(
        commands,
        release_gate,
        evidence_verification,
        candidate,
        candidate_verification,
        replay,
    )
    official_claim_publishable = all(assertion["passed"] for assertion in assertions)
    return {
        "schema": "stock_harness_official_claim_gate_v1",
        "generated_at_unix": int(time.time()),
        "root": str(ROOT),
        "environment": {
            "python_executable": python,
            "python_version": sys.version,
            "platform": platform.platform(),
        },
        "claim_scope": {
            "benchmark_suite": BENCHMARK_SUITE,
            "positive_claim_limit": "verification coverage only",
            "publication_requirement": "Python plus Cargo full gate with official release candidate replay",
        },
        "official_claim_publishable": official_claim_publishable,
        "status": "passed" if official_claim_publishable else "failed",
        "release_gate_json": str(release_gate_path),
        "release_candidate_replay_json": str(replay_path),
        "assertions": assertions,
        "commands": [_command_for_report(command) for command in commands],
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the official Stock Harness claim publication gate.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument("--output", help="Optional path to write the final publication-gate JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_official_claim_gate()
    text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["official_claim_publishable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
