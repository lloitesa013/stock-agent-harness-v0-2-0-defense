#!/usr/bin/env python3
"""Verify a Stock Harness evidence packet after it has been built."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET_DIR = Path("dist/stock_harness_evidence_packet")
EVIDENCE_MANIFEST_NAME = "EVIDENCE_MANIFEST.json"
CLAIM_STATUS = "supported_for_included_benchmark_suite"
CLAIM_ID = "downside_verification_sota_grade_v0_1"
BENCHMARK_SUITE = "downside_verification_v1"

REQUIRED_PACKET_FILES = [
    "benchmark_stock_harness.json",
    "claim_comparison.json",
    "claim_contract.json",
    "expected_summary.json",
    "release_audit.json",
    "release_bundle.json",
    "release_bundle_manifest.json",
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


def _hash_checks(packet_dir: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    file_map = _manifest_file_map(manifest)
    for rel, entry in sorted(file_map.items()):
        path = _safe_packet_path(packet_dir, rel)
        if path is None:
            errors.append({"path": rel, "error": "unsafe_path"})
            continue
        if not path.is_file():
            errors.append({"path": rel, "error": "missing_file"})
            continue
        if path.stat().st_size != entry.get("bytes"):
            errors.append(
                {
                    "path": rel,
                    "error": "bytes_mismatch",
                    "expected": entry.get("bytes"),
                    "actual": path.stat().st_size,
                }
            )
        actual_sha = _sha256(path)
        if actual_sha != entry.get("sha256"):
            errors.append(
                {
                    "path": rel,
                    "error": "sha256_mismatch",
                    "expected": entry.get("sha256"),
                    "actual": actual_sha,
                }
            )
    return {"passed": errors == [], "errors": errors}


def _required_file_check(
    manifest: Mapping[str, Any],
    *,
    require_release_gate_json: bool,
) -> Dict[str, Any]:
    file_map = _manifest_file_map(manifest)
    required = list(REQUIRED_PACKET_FILES)
    if require_release_gate_json:
        required.append("release_gate.json")
    missing = [path for path in required if path not in file_map]
    unsafe = [path for path in file_map if path.startswith("/") or "\\" in path or ".." in Path(path).parts]
    checks = {
        "required_files_present": missing == [],
        "file_count_matches_manifest": manifest.get("file_count") == len(file_map),
        "unsafe_paths_absent": unsafe == [],
    }
    return {"passed": all(checks.values()), "checks": checks, "missing": missing, "unsafe": unsafe}


def _json_schema_checks(
    packet_dir: Path,
    *,
    require_release_gate_json: bool,
    require_official_claim_ready: bool,
) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    errors: List[str] = []

    def load(rel: str) -> Dict[str, Any]:
        try:
            return _load_json(packet_dir / rel)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(rel + ": " + str(exc))
            return {}

    benchmark = load("benchmark_stock_harness.json")
    comparison = load("claim_comparison.json")
    contract = load("claim_contract.json")
    expected = load("expected_summary.json")
    release_audit = load("release_audit.json")
    release_bundle = load("release_bundle.json")
    release_bundle_manifest = load("release_bundle_manifest.json")
    release_gate = load("release_gate.json") if (packet_dir / "release_gate.json").exists() else {}

    checks["benchmark_all_passed"] = benchmark.get("all_passed") is True
    checks["comparison_claim_supported"] = comparison.get("claim", {}).get("status") == CLAIM_STATUS
    checks["comparison_contract_diffs_absent"] = comparison.get("benchmark", {}).get("claim_contract_diffs") == []
    checks["comparison_expected_diffs_absent"] = comparison.get("benchmark", {}).get("expected_diffs") == []
    checks["comparison_coverage_full"] = (
        comparison.get("tools", {}).get("angelos_stock_harness", {}).get("coverage_score") == 1.0
    )
    checks["claim_contract_scope"] = (
        contract.get("schema") == "stock_harness_claim_contract_v1"
        and contract.get("claim_id") == CLAIM_ID
        and contract.get("benchmark_suite") == BENCHMARK_SUITE
        and "No universal external-framework dominance claim." in contract.get("non_claims", [])
    )
    checks["expected_summary_scope"] = (
        expected.get("claim_id") == CLAIM_ID and expected.get("benchmark_suite") == BENCHMARK_SUITE
    )
    checks["release_audit_passed"] = (
        release_audit.get("schema") == "stock_harness_release_audit_v1"
        and release_audit.get("status") == "passed"
        and release_audit.get("checks", {}).get("broad_claim_phrases", {}).get("hits") == []
    )
    checks["release_bundle_passed"] = (
        release_bundle.get("schema") == "stock_harness_release_bundle_v1"
        and release_bundle.get("status") == "passed"
        and release_bundle.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
    )
    checks["release_bundle_manifest_passed"] = (
        release_bundle_manifest.get("schema") == "stock_harness_release_bundle_v1"
        and release_bundle_manifest.get("status") == "passed"
        and release_bundle_manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
    )
    checks["release_gate_presence"] = bool(release_gate) if require_release_gate_json else True
    if release_gate:
        checks["release_gate_schema"] = release_gate.get("schema") == "stock_harness_release_gate_v1"
        checks["release_gate_claim_supported"] = release_gate.get("claim", {}).get("status") == CLAIM_STATUS
        checks["release_gate_python_passed"] = release_gate.get("python_gate_passed") is True
        checks["release_gate_official_ready"] = (
            release_gate.get("official_claim_ready") is True if require_official_claim_ready else True
        )
    elif require_official_claim_ready:
        checks["release_gate_official_ready"] = False

    return {"passed": errors == [] and all(checks.values()), "checks": checks, "errors": errors}


def verify_evidence_packet(
    packet_dir: Path = DEFAULT_PACKET_DIR,
    *,
    require_release_gate_json: bool = False,
    require_official_claim_ready: bool = False,
) -> Dict[str, Any]:
    packet_dir = packet_dir if packet_dir.is_absolute() else ROOT / packet_dir
    manifest_path = packet_dir / EVIDENCE_MANIFEST_NAME
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    checks = {
        "manifest": {
            "passed": bool(
                manifest
                and manifest.get("schema") == "stock_harness_evidence_packet_v1"
                and manifest.get("status") == "passed"
                and manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
                and manifest.get("claim_scope", {}).get("claim_id") == CLAIM_ID
            ),
            "manifest_path": str(manifest_path),
        },
        "required_files": _required_file_check(
            manifest,
            require_release_gate_json=require_release_gate_json,
        ),
        "hashes": _hash_checks(packet_dir, manifest),
        "json_payloads": _json_schema_checks(
            packet_dir,
            require_release_gate_json=require_release_gate_json,
            require_official_claim_ready=require_official_claim_ready,
        ),
    }
    return {
        "schema": "stock_harness_evidence_packet_verification_v1",
        "status": "passed" if all(item["passed"] for item in checks.values()) else "failed",
        "packet_dir": str(packet_dir),
        "require_release_gate_json": require_release_gate_json,
        "require_official_claim_ready": require_official_claim_ready,
        "checks": checks,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Stock Harness evidence packet.")
    parser.add_argument("--packet-dir", default=str(DEFAULT_PACKET_DIR), help="Evidence packet directory.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument(
        "--require-release-gate-json",
        action="store_true",
        help="Require release_gate.json to be present inside the packet.",
    )
    parser.add_argument(
        "--require-official-claim-ready",
        action="store_true",
        help="Require release_gate.json to report official_claim_ready: true.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = verify_evidence_packet(
        Path(args.packet_dir),
        require_release_gate_json=args.require_release_gate_json,
        require_official_claim_ready=args.require_official_claim_ready,
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
