#!/usr/bin/env python3
"""Verify the Stock Harness global claim packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET_DIR = Path("dist/stock_harness_global_claim_packet")
PACKET_MANIFEST_NAME = "GLOBAL_CLAIM_PACKET_MANIFEST.json"
CLAIM_ID = "global_downside_verification_sota_grade_v0_1"
BENCHMARK_SUITE = "global_verification_v1"
CLAIM_STATUS = "supported_for_named_external_framework_benchmark_suite"
REQUIRED_FILES = [
    "global_claim_gate.json",
    "global_framework_comparison.json",
    "global_claim_contract.json",
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
    return {str(item.get("path")): item for item in files if isinstance(item, dict)}


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
    return {str(item.get("id")): item for item in assertions if isinstance(item, dict)}


def _all_assertions_passed(payload: Mapping[str, Any]) -> bool:
    assertions = payload.get("assertions", [])
    if not isinstance(assertions, list) or not assertions:
        return False
    return all(isinstance(item, dict) and item.get("passed") is True for item in assertions)


def _json_checks(packet_dir: Path) -> Dict[str, Any]:
    errors: List[str] = []

    def load(rel: str) -> Dict[str, Any]:
        try:
            return _load_json(packet_dir / rel)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(rel + ": " + str(exc))
            return {}

    gate = load("global_claim_gate.json")
    comparison = load("global_framework_comparison.json")
    contract = load("global_claim_contract.json")
    assertions = _assertion_map(gate)
    publication = comparison.get("publication_requirements", {})
    checks = {
        "gate_ready": gate.get("schema") == "stock_harness_global_claim_gate_v1"
        and gate.get("overall_status") == "passed"
        and gate.get("global_claim_ready") is True
        and _all_assertions_passed(gate),
        "gate_required_assertions": all(
            assertions.get(assertion_id, {}).get("passed") is True
            for assertion_id in [
                "all_required_external_adapters_executed",
                "external_adapter_versions_fingerprinted",
                "stock_harness_ranked_first_by_coverage_score",
                "stock_harness_score_strictly_exceeds_each_external_framework",
                "global_claim_status_supported",
            ]
        ),
        "comparison_scope": comparison.get("schema") == "stock_harness_global_framework_comparison_v1"
        and comparison.get("claim", {}).get("id") == CLAIM_ID
        and comparison.get("claim", {}).get("benchmark_suite") == BENCHMARK_SUITE
        and comparison.get("claim", {}).get("status") == CLAIM_STATUS,
        "comparison_external_frameworks": publication.get("passed") is True
        and publication.get("named_external_adapters_executed_count") == 6
        and publication.get("missing_external_frameworks") == [],
        "comparison_stock_harness_first": comparison.get("ranking", [{}])[0].get("id")
        == "angelos_stock_harness",
        "comparison_stock_harness_full_coverage": comparison.get("tools", {})
        .get("angelos_stock_harness", {})
        .get("coverage_score")
        == 1.0,
        "contract_scope": contract.get("schema") == "stock_harness_global_claim_contract_v1"
        and contract.get("claim_id") == CLAIM_ID
        and contract.get("benchmark_suite") == BENCHMARK_SUITE
        and contract.get("status_when_supported") == CLAIM_STATUS,
        "contract_requires_all_frameworks": contract.get("minimum_named_external_adapters_executed") == 6
        and len(contract.get("required_external_frameworks", [])) == 6,
        "contract_preserves_non_claims": (
            "No claim outside the named external frameworks and versions executed by this benchmark suite."
            in contract.get("non_claims", [])
        )
        and (
            "No investment-performance or alpha-generation claim."
            in contract.get("non_claims", [])
        ),
    }
    return {"passed": errors == [] and all(checks.values()), "checks": checks, "errors": errors}


def verify_global_claim_packet(packet_dir: Path = DEFAULT_PACKET_DIR) -> Dict[str, Any]:
    packet_dir = packet_dir if packet_dir.is_absolute() else ROOT / packet_dir
    manifest_path = packet_dir / PACKET_MANIFEST_NAME
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    checks = {
        "manifest": {
            "passed": bool(
                manifest
                and manifest.get("schema") == "stock_harness_global_claim_packet_v1"
                and manifest.get("status") == "passed"
                and manifest.get("claim_scope", {}).get("claim_id") == CLAIM_ID
                and manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
                and manifest.get("claim_scope", {}).get("publication_requirement") == "global_claim_ready: true"
            ),
            "manifest_path": str(manifest_path),
        },
        "required_files": _required_file_check(manifest),
        "hashes": _hash_checks(packet_dir, manifest),
        "json_payloads": _json_checks(packet_dir),
    }
    return {
        "schema": "stock_harness_global_claim_packet_verification_v1",
        "status": "passed" if all(item["passed"] for item in checks.values()) else "failed",
        "packet_dir": str(packet_dir),
        "checks": checks,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Stock Harness global claim packet.")
    parser.add_argument("--packet-dir", default=str(DEFAULT_PACKET_DIR), help="Global claim packet directory.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = verify_global_claim_packet(Path(args.packet_dir))
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
