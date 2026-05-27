#!/usr/bin/env python3
"""Verify the final Stock Harness official claim packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET_DIR = Path("dist/stock_harness_official_claim_packet")
PACKET_MANIFEST_NAME = "OFFICIAL_CLAIM_PACKET_MANIFEST.json"
CLAIM_ID = "downside_verification_sota_grade_v0_1"
BENCHMARK_SUITE = "downside_verification_v1"
REQUIRED_FILES = [
    "official_claim_gate.json",
    "official_release_gate.json",
    "official_release_candidate_replay.json",
    "release_manifest.json",
    "evidence_manifest.json",
    "release_candidate_manifest.json",
    "claim_contract.json",
]
REQUIRED_OFFICIAL_CLAIM_PACKET_CHECKS = [
    "official_gate_publishable",
    "official_gate_assertions",
    "release_gate_official_ready",
    "release_gate_rust_assertions",
    "replay_official_ready",
    "replay_rust_assertions",
    "release_manifest_scope",
    "evidence_manifest_scope",
    "candidate_manifest_scope",
    "claim_contract_scope",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object: " + str(path))
    return payload


def _safe_packet_path(packet_dir: Path, rel: str) -> Optional[Path]:
    if rel.startswith("/") or "\\" in rel or ".." in Path(rel).parts:
        return None
    path = packet_dir / rel
    try:
        path.resolve().relative_to(packet_dir.resolve())
    except ValueError:
        return None
    return path


def _manifest_file_map(manifest: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return {}
    return {
        str(entry.get("path")): entry
        for entry in files
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }


def _required_file_check(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    file_map = _manifest_file_map(manifest)
    missing = [path for path in REQUIRED_FILES if path not in file_map]
    unsafe = [path for path in file_map if path.startswith("/") or "\\" in path or ".." in Path(path).parts]
    checks = {
        "required_files_present": missing == [],
        "file_count_matches_manifest": manifest.get("file_count") == len(file_map),
        "unsafe_paths_absent": unsafe == [],
    }
    return {"passed": all(checks.values()), "checks": checks, "missing": missing, "unsafe": unsafe}


def _hash_checks(packet_dir: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    for rel, entry in sorted(_manifest_file_map(manifest).items()):
        path = _safe_packet_path(packet_dir, rel)
        if path is None:
            errors.append({"path": rel, "error": "unsafe_path"})
            continue
        if not path.is_file():
            errors.append({"path": rel, "error": "missing_file"})
            continue
        if path.stat().st_size != entry.get("bytes"):
            errors.append({"path": rel, "error": "bytes_mismatch"})
        if _sha256(path) != entry.get("sha256"):
            errors.append({"path": rel, "error": "sha256_mismatch"})
    return {"passed": errors == [], "errors": errors}


def _assertion_map(payload: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    assertions = payload.get("assertions", [])
    if not isinstance(assertions, list):
        return {}
    return {
        str(assertion.get("id")): assertion
        for assertion in assertions
        if isinstance(assertion, dict)
    }


def _all_assertions_passed(payload: Mapping[str, Any]) -> bool:
    assertions = payload.get("assertions", [])
    if not isinstance(assertions, list) or not assertions:
        return False
    return all(isinstance(assertion, dict) and assertion.get("passed") is True for assertion in assertions)


def _json_checks(packet_dir: Path) -> Dict[str, Any]:
    errors: List[str] = []

    def load(rel: str) -> Dict[str, Any]:
        try:
            return _load_json(packet_dir / rel)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(rel + ": " + str(exc))
            return {}

    official_gate = load("official_claim_gate.json")
    release_gate = load("official_release_gate.json")
    replay = load("official_release_candidate_replay.json")
    release_manifest = load("release_manifest.json")
    evidence_manifest = load("evidence_manifest.json")
    candidate_manifest = load("release_candidate_manifest.json")
    claim_contract = load("claim_contract.json")

    official_assertions = _assertion_map(official_gate)
    release_assertions = _assertion_map(release_gate)
    replay_assertions = _assertion_map(replay)
    required_packet_checks = list(claim_contract.get("required_official_claim_packet_checks", []))
    checks = {
        "official_gate_publishable": official_gate.get("schema") == "stock_harness_official_claim_gate_v1"
        and official_gate.get("status") == "passed"
        and official_gate.get("official_claim_publishable") is True,
        "official_gate_assertions": all(
            official_assertions.get(assertion_id, {}).get("passed") is True
            for assertion_id in [
                "full_release_gate_official_ready",
                "evidence_packet_verified_for_publication",
                "release_candidate_verified_for_publication",
                "release_candidate_replayed_for_publication",
            ]
        ),
        "release_gate_official_ready": release_gate.get("schema") == "stock_harness_release_gate_v1"
        and release_gate.get("official_claim_ready") is True
        and release_gate.get("overall_status") == "passed"
        and release_gate.get("rust_status") == "required",
        "release_gate_rust_assertions": release_assertions.get("rust_unit_tests_passed", {}).get("passed") is True
        and release_assertions.get("rust_benchmark_cli_passed", {}).get("passed") is True,
        "replay_official_ready": replay.get("schema") == "stock_harness_release_candidate_replay_v1"
        and replay.get("status") == "passed"
        and replay.get("require_release_gate_json") is True
        and replay.get("require_official_claim_ready") is True
        and replay.get("skip_rust") is False
        and _all_assertions_passed(replay),
        "replay_rust_assertions": replay_assertions.get("extracted_rust_unit_tests_passed", {}).get("passed") is True
        and replay_assertions.get("extracted_rust_benchmark_cli_passed", {}).get("passed") is True,
        "release_manifest_scope": release_manifest.get("schema") == "stock_harness_release_bundle_v1"
        and release_manifest.get("status") == "passed"
        and release_manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE,
        "evidence_manifest_scope": evidence_manifest.get("schema") == "stock_harness_evidence_packet_v1"
        and evidence_manifest.get("status") == "passed"
        and evidence_manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE,
        "candidate_manifest_scope": candidate_manifest.get("schema") == "stock_harness_release_candidate_v1"
        and candidate_manifest.get("status") == "passed"
        and candidate_manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE,
        "claim_contract_packet_checks": all(
            check in required_packet_checks
            for check in REQUIRED_OFFICIAL_CLAIM_PACKET_CHECKS
        ),
        "claim_contract_scope": claim_contract.get("schema") == "stock_harness_claim_contract_v1"
        and claim_contract.get("claim_id") == CLAIM_ID
        and claim_contract.get("benchmark_suite") == BENCHMARK_SUITE
        and "release_candidate_replayed_for_publication"
        in claim_contract.get("required_publication_gate_assertions", []),
    }
    return {"passed": errors == [] and all(checks.values()), "checks": checks, "errors": errors}


def verify_official_claim_packet(packet_dir: Path = DEFAULT_PACKET_DIR) -> Dict[str, Any]:
    packet_dir = packet_dir if packet_dir.is_absolute() else ROOT / packet_dir
    manifest_path = packet_dir / PACKET_MANIFEST_NAME
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    checks = {
        "manifest": {
            "passed": bool(
                manifest
                and manifest.get("schema") == "stock_harness_official_claim_packet_v1"
                and manifest.get("status") == "passed"
                and manifest.get("claim_scope", {}).get("claim_id") == CLAIM_ID
                and manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
                and manifest.get("claim_scope", {}).get("publication_requirement")
                == "official_claim_publishable: true"
            ),
            "manifest_path": str(manifest_path),
        },
        "required_files": _required_file_check(manifest),
        "hashes": _hash_checks(packet_dir, manifest),
        "json_payloads": _json_checks(packet_dir),
    }
    return {
        "schema": "stock_harness_official_claim_packet_verification_v1",
        "status": "passed" if all(item["passed"] for item in checks.values()) else "failed",
        "packet_dir": str(packet_dir),
        "checks": checks,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Stock Harness official claim packet.")
    parser.add_argument("--packet-dir", default=str(DEFAULT_PACKET_DIR), help="Official claim packet directory.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = verify_official_claim_packet(Path(args.packet_dir))
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
