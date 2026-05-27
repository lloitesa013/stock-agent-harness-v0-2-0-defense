#!/usr/bin/env python3
"""Verify the Stock Harness release candidate artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_DIR = Path("dist/stock_harness_release_candidate")
RELEASE_CANDIDATE_MANIFEST = "RELEASE_CANDIDATE_MANIFEST.json"
CLAIM_ID = "downside_verification_sota_grade_v0_1"
BENCHMARK_SUITE = "downside_verification_v1"
CLAIM_STATUS = "supported_for_included_benchmark_suite"

REQUIRED_COMPONENTS = [
    "stock_harness_release.zip",
    "stock_harness_evidence_packet.zip",
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


def _load_zip_json(zip_path: Path, member: str) -> Dict[str, Any]:
    with zipfile.ZipFile(str(zip_path), "r") as archive:
        with archive.open(member, "r") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object in zip member: " + member)
    return payload


def _component_map(manifest: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    components = manifest.get("components", [])
    if not isinstance(components, list):
        return {}
    return {
        str(component.get("path")): component
        for component in components
        if isinstance(component, dict) and isinstance(component.get("path"), str)
    }


def _component_checks(candidate_dir: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    component_map = _component_map(manifest)
    missing = [path for path in REQUIRED_COMPONENTS if path not in component_map]
    errors: List[Dict[str, Any]] = []
    for rel, component in sorted(component_map.items()):
        if rel.startswith("/") or "\\" in rel or ".." in Path(rel).parts:
            errors.append({"path": rel, "error": "unsafe_path"})
            continue
        path = candidate_dir / rel
        try:
            path.resolve().relative_to(candidate_dir.resolve())
        except ValueError:
            errors.append({"path": rel, "error": "unsafe_path"})
            continue
        if not path.is_file():
            errors.append({"path": rel, "error": "missing_file"})
            continue
        if path.stat().st_size != component.get("bytes"):
            errors.append({"path": rel, "error": "bytes_mismatch"})
        if _sha256(path) != component.get("sha256"):
            errors.append({"path": rel, "error": "sha256_mismatch"})
    checks = {
        "required_components_present": missing == [],
        "component_count_matches_manifest": manifest.get("component_count") == len(component_map),
        "component_hashes_match": errors == [],
    }
    return {"passed": all(checks.values()), "checks": checks, "missing": missing, "errors": errors}


def _zip_payload_checks(
    candidate_dir: Path,
    *,
    require_release_gate_json: bool,
    require_official_claim_ready: bool,
) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    errors: List[str] = []
    release_zip = candidate_dir / "stock_harness_release.zip"
    evidence_zip = candidate_dir / "stock_harness_evidence_packet.zip"

    try:
        release_manifest = _load_zip_json(release_zip, "RELEASE_MANIFEST.json")
    except (OSError, KeyError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        errors.append("stock_harness_release.zip: " + str(exc))
        release_manifest = {}
    try:
        evidence_manifest = _load_zip_json(evidence_zip, "EVIDENCE_MANIFEST.json")
    except (OSError, KeyError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        errors.append("stock_harness_evidence_packet.zip: " + str(exc))
        evidence_manifest = {}

    checks["release_manifest_passed"] = (
        release_manifest.get("schema") == "stock_harness_release_bundle_v1"
        and release_manifest.get("status") == "passed"
        and release_manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
    )
    checks["evidence_manifest_passed"] = (
        evidence_manifest.get("schema") == "stock_harness_evidence_packet_v1"
        and evidence_manifest.get("status") == "passed"
        and evidence_manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
    )

    release_gate = {}
    if require_release_gate_json or require_official_claim_ready:
        try:
            release_gate = _load_zip_json(evidence_zip, "release_gate.json")
        except (OSError, KeyError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            errors.append("stock_harness_evidence_packet.zip release_gate.json: " + str(exc))
    if release_gate:
        checks["release_gate_schema"] = release_gate.get("schema") == "stock_harness_release_gate_v1"
        checks["release_gate_claim_supported"] = release_gate.get("claim", {}).get("status") == CLAIM_STATUS
        checks["release_gate_python_passed"] = release_gate.get("python_gate_passed") is True
        checks["release_gate_official_ready"] = (
            release_gate.get("official_claim_ready") is True if require_official_claim_ready else True
        )
    else:
        checks["release_gate_presence"] = not (require_release_gate_json or require_official_claim_ready)
        if require_official_claim_ready:
            checks["release_gate_official_ready"] = False

    return {"passed": errors == [] and all(checks.values()), "checks": checks, "errors": errors}


def verify_release_candidate(
    candidate_dir: Path = DEFAULT_CANDIDATE_DIR,
    *,
    require_release_gate_json: bool = False,
    require_official_claim_ready: bool = False,
) -> Dict[str, Any]:
    candidate_dir = candidate_dir if candidate_dir.is_absolute() else ROOT / candidate_dir
    manifest_path = candidate_dir / RELEASE_CANDIDATE_MANIFEST
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    checks = {
        "manifest": {
            "passed": bool(
                manifest
                and manifest.get("schema") == "stock_harness_release_candidate_v1"
                and manifest.get("status") == "passed"
                and manifest.get("claim_scope", {}).get("claim_id") == CLAIM_ID
                and manifest.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE
            ),
            "manifest_path": str(manifest_path),
        },
        "components": _component_checks(candidate_dir, manifest),
        "zip_payloads": _zip_payload_checks(
            candidate_dir,
            require_release_gate_json=require_release_gate_json,
            require_official_claim_ready=require_official_claim_ready,
        ),
    }
    return {
        "schema": "stock_harness_release_candidate_verification_v1",
        "status": "passed" if all(item["passed"] for item in checks.values()) else "failed",
        "candidate_dir": str(candidate_dir),
        "require_release_gate_json": require_release_gate_json,
        "require_official_claim_ready": require_official_claim_ready,
        "checks": checks,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Stock Harness release candidate artifacts.")
    parser.add_argument("--candidate-dir", default=str(DEFAULT_CANDIDATE_DIR), help="Release candidate directory.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument(
        "--require-release-gate-json",
        action="store_true",
        help="Require release_gate.json inside the evidence packet zip.",
    )
    parser.add_argument(
        "--require-official-claim-ready",
        action="store_true",
        help="Require release_gate.json to report official_claim_ready: true.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = verify_release_candidate(
        Path(args.candidate_dir),
        require_release_gate_json=args.require_release_gate_json,
        require_official_claim_ready=args.require_official_claim_ready,
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
