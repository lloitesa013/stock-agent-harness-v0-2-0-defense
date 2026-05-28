#!/usr/bin/env python3
"""Replay a Stock Harness release candidate from its packaged source zip."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_DIR = Path("dist/stock_harness_release_candidate")
DEFAULT_OUTPUT_DIR = Path("dist/stock_harness_release_candidate_replay")
RELEASE_ZIP_NAME = "stock_harness_release.zip"
CLAIM_STATUS = "supported_for_included_benchmark_suite"

PY_COMPILE_TARGETS = [
    "angelos_os/agent_harness.py",
    "angelos_os/performance_defense.py",
    "angelos_os/performance_harness.py",
    "angelos_os/real_market_harness.py",
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
    "dashboard/app.py",
    "ops/benchmark_stock_harness.py",
    "ops/compare_stock_harness_baselines.py",
    "ops/compare_stock_harness_global_frameworks.py",
    "ops/run_stock_agent_harness.py",
    "ops/run_stock_agent_harness_claim_gate.py",
    "ops/run_downside_performance_benchmark.py",
    "ops/run_downside_performance_claim_gate.py",
    "ops/download_real_market_data.py",
    "ops/run_real_market_data_defense.py",
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
    "tests/test_dashboard_app.py",
    "tests/test_productization_docs.py",
    "tests/test_real_market_harness.py",
    "tests/test_stock_agent_harness.py",
    "tests/test_stock_harness.py",
]


def _safe_clean_output(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    dist_root = (ROOT / "dist").resolve()
    if not str(resolved).startswith(str(dist_root)):
        raise ValueError("refusing to clean outside dist/: " + str(resolved))
    if resolved.name != "stock_harness_release_candidate_replay":
        raise ValueError("refusing to clean unexpected output directory: " + str(resolved))
    if resolved.exists():
        shutil.rmtree(str(resolved))


def _safe_extract_zip(zip_path: Path, output_dir: Path) -> List[str]:
    extracted: List[str] = []
    with zipfile.ZipFile(str(zip_path), "r") as archive:
        for info in archive.infolist():
            rel = info.filename
            if rel.endswith("/"):
                continue
            parts = Path(rel).parts
            if rel.startswith("/") or "\\" in rel or ".." in parts:
                raise ValueError("unsafe zip member: " + rel)
            dst = output_dir / rel
            try:
                dst.resolve().relative_to(output_dir.resolve())
            except ValueError:
                raise ValueError("unsafe zip destination: " + rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as src:
                dst.write_bytes(src.read())
            extracted.append(rel)
    return extracted


def _run_command(name: str, command: List[str], cwd: Path, env: Mapping[str, str]) -> Dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
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


def _parse_json_stdout(result: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        payload = json.loads(str(result.get("stdout", "")))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _command_map(commands: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    return {str(command["name"]): command for command in commands}


def _find_cargo() -> Optional[str]:
    cargo_path = shutil.which("cargo")
    if cargo_path:
        return cargo_path
    home_cargo = Path.home() / ".cargo" / "bin" / ("cargo.exe" if os.name == "nt" else "cargo")
    if home_cargo.is_file():
        return str(home_cargo)
    return None


def _build_assertions(commands: List[Dict[str, Any]], *, rust_required: bool) -> List[Dict[str, Any]]:
    by_name = _command_map(commands)
    benchmark = _parse_json_stdout(by_name.get("benchmark", {}))
    comparison = _parse_json_stdout(by_name.get("claim_comparison", {}))
    audit = _parse_json_stdout(by_name.get("release_audit", {}))
    candidate = _parse_json_stdout(by_name.get("candidate_verification_from_extracted_source", {}))
    assertions = [
        {"id": "extracted_py_compile_passed", "passed": bool(by_name.get("py_compile", {}).get("passed"))},
        {"id": "extracted_unit_tests_passed", "passed": bool(by_name.get("unit_tests", {}).get("passed"))},
        {"id": "extracted_benchmark_passed", "passed": benchmark.get("all_passed") is True},
        {
            "id": "extracted_claim_supported",
            "passed": comparison.get("claim", {}).get("status") == CLAIM_STATUS
            and comparison.get("benchmark", {}).get("claim_contract_diffs") == [],
        },
        {
            "id": "extracted_release_audit_passed",
            "passed": audit.get("schema") == "stock_harness_release_audit_v1"
            and audit.get("status") == "passed",
        },
        {
            "id": "candidate_verifier_from_extracted_source_passed",
            "passed": candidate.get("schema") == "stock_harness_release_candidate_verification_v1"
            and candidate.get("status") == "passed",
        },
    ]
    if rust_required:
        assertions.extend(
            [
                {"id": "extracted_rust_unit_tests_passed", "passed": bool(by_name.get("rust_tests", {}).get("passed"))},
                {
                    "id": "extracted_rust_benchmark_cli_passed",
                    "passed": bool(by_name.get("rust_benchmark", {}).get("passed")),
                },
            ]
        )
    return assertions


def replay_release_candidate(
    candidate_dir: Path = DEFAULT_CANDIDATE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = False,
    skip_rust: bool = False,
    require_release_gate_json: bool = False,
    require_official_claim_ready: bool = False,
) -> Dict[str, Any]:
    candidate_dir = candidate_dir if candidate_dir.is_absolute() else ROOT / candidate_dir
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    if clean:
        _safe_clean_output(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_root = output_dir / "stock_harness_release"
    if extracted_root.exists():
        shutil.rmtree(str(extracted_root))
    extracted_root.mkdir(parents=True, exist_ok=True)

    release_zip = candidate_dir / RELEASE_ZIP_NAME
    extracted_files = _safe_extract_zip(release_zip, extracted_root)

    env = dict(os.environ)
    env["STOCK_HARNESS_REPLAY_MODE"] = "1"
    tmpdir = output_dir / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    env["STOCK_HARNESS_TMPDIR"] = str(tmpdir)

    python = sys.executable
    commands: List[Dict[str, Any]] = []
    commands.append(_run_command("py_compile", [python, "-m", "py_compile"] + PY_COMPILE_TARGETS, extracted_root, env))
    commands.append(_run_command("unit_tests", [python, "-m", "unittest", "tests/test_stock_harness.py"], extracted_root, env))
    commands.append(_run_command("benchmark", [python, "ops/benchmark_stock_harness.py", "--pretty"], extracted_root, env))
    commands.append(
        _run_command(
            "claim_comparison",
            [python, "ops/compare_stock_harness_baselines.py", "--pretty"],
            extracted_root,
            env,
        )
    )
    commands.append(
        _run_command(
            "release_audit",
            [python, "ops/audit_stock_harness_release.py", "--manifest", "RELEASE_MANIFEST.json", "--pretty"],
            extracted_root,
            env,
        )
    )
    candidate_verify_command = [
        python,
        "ops/verify_stock_harness_release_candidate.py",
        "--candidate-dir",
        str(candidate_dir),
        "--pretty",
    ]
    if require_release_gate_json:
        candidate_verify_command.append("--require-release-gate-json")
    if require_official_claim_ready:
        candidate_verify_command.append("--require-official-claim-ready")
    commands.append(
        _run_command(
            "candidate_verification_from_extracted_source",
            candidate_verify_command,
            extracted_root,
            env,
        )
    )

    rust_required = not skip_rust
    cargo_path = _find_cargo()
    if rust_required and cargo_path:
        commands.append(
            _run_command(
                "rust_tests",
                [cargo_path, "test", "--manifest-path", "rust_stock_harness/Cargo.toml"],
                extracted_root,
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
                extracted_root,
                env,
            )
        )
    elif rust_required:
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

    assertions = _build_assertions(commands, rust_required=rust_required)
    return {
        "schema": "stock_harness_release_candidate_replay_v1",
        "status": "passed" if all(assertion["passed"] for assertion in assertions) else "failed",
        "candidate_dir": str(candidate_dir),
        "output_dir": str(output_dir),
        "extracted_root": str(extracted_root),
        "extracted_file_count": len(extracted_files),
        "skip_rust": skip_rust,
        "require_release_gate_json": require_release_gate_json,
        "require_official_claim_ready": require_official_claim_ready,
        "assertions": assertions,
        "commands": commands,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the Stock Harness release candidate source zip.")
    parser.add_argument("--candidate-dir", default=str(DEFAULT_CANDIDATE_DIR), help="Release candidate directory.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Replay extraction/output directory.")
    parser.add_argument("--clean", action="store_true", help="Clean the replay output directory before writing.")
    parser.add_argument("--skip-rust", action="store_true", help="Skip Rust replay checks on hosts without Cargo.")
    parser.add_argument("--require-release-gate-json", action="store_true", help="Require release_gate.json in the evidence zip.")
    parser.add_argument(
        "--require-official-claim-ready",
        action="store_true",
        help="Require embedded release_gate.json to report official_claim_ready: true.",
    )
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument("--output", help="Optional path to write replay JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = replay_release_candidate(
        Path(args.candidate_dir),
        Path(args.output_dir),
        clean=args.clean,
        skip_rust=args.skip_rust,
        require_release_gate_json=args.require_release_gate_json,
        require_official_claim_ready=args.require_official_claim_ready,
    )
    text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
