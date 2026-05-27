#!/usr/bin/env python3
"""Build the final publication evidence packet for the Stock Harness claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path("dist/stock_harness_official_claim_packet")
DEFAULT_OFFICIAL_CLAIM_GATE_JSON = Path("reports/stock_harness_official_claim_gate_ci.json")
DEFAULT_OFFICIAL_RELEASE_GATE_JSON = Path("reports/stock_harness_release_gate_official.json")
DEFAULT_OFFICIAL_REPLAY_JSON = Path("reports/stock_harness_release_candidate_replay_official.json")
DEFAULT_RELEASE_MANIFEST = Path("dist/stock_harness_release/RELEASE_MANIFEST.json")
DEFAULT_EVIDENCE_MANIFEST = Path("dist/stock_harness_evidence_packet/EVIDENCE_MANIFEST.json")
DEFAULT_CANDIDATE_MANIFEST = Path("dist/stock_harness_release_candidate/RELEASE_CANDIDATE_MANIFEST.json")
DEFAULT_CLAIM_CONTRACT = Path("benchmarks/downside_verification_v1/claim_contract.json")
PACKET_MANIFEST_NAME = "OFFICIAL_CLAIM_PACKET_MANIFEST.json"
CLAIM_STATUS = "supported_for_included_benchmark_suite"
BENCHMARK_SUITE = "downside_verification_v1"
CLAIM_ID = "downside_verification_sota_grade_v0_1"


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _safe_clean_output(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    dist_root = (ROOT / "dist").resolve()
    if not str(resolved).startswith(str(dist_root)):
        raise ValueError("refusing to clean outside dist/: " + str(resolved))
    if resolved.name != "stock_harness_official_claim_packet":
        raise ValueError("refusing to clean unexpected output directory: " + str(resolved))
    if resolved.exists():
        shutil.rmtree(str(resolved))


def _copy(src: Path, output_dir: Path, dst_name: str) -> None:
    dst = output_dir / dst_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))


def _file_entries(output_dir: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == PACKET_MANIFEST_NAME:
            continue
        rel = path.relative_to(output_dir).as_posix()
        entries.append({"path": rel, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return entries


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


def _official_claim_gate_checks(payload: Mapping[str, Any]) -> Dict[str, bool]:
    assertions = _assertion_map(payload)
    return {
        "schema": payload.get("schema") == "stock_harness_official_claim_gate_v1",
        "status": payload.get("status") == "passed",
        "official_claim_publishable": payload.get("official_claim_publishable") is True,
        "full_release_gate_official_ready": assertions.get("full_release_gate_official_ready", {}).get("passed") is True,
        "evidence_packet_verified_for_publication": assertions.get(
            "evidence_packet_verified_for_publication", {}
        ).get("passed") is True,
        "release_candidate_verified_for_publication": assertions.get(
            "release_candidate_verified_for_publication", {}
        ).get("passed") is True,
        "release_candidate_replayed_for_publication": assertions.get(
            "release_candidate_replayed_for_publication", {}
        ).get("passed") is True,
    }


def _release_gate_checks(payload: Mapping[str, Any]) -> Dict[str, bool]:
    assertions = _assertion_map(payload)
    return {
        "schema": payload.get("schema") == "stock_harness_release_gate_v1",
        "overall_status": payload.get("overall_status") == "passed",
        "official_claim_ready": payload.get("official_claim_ready") is True,
        "rust_status": payload.get("rust_status") == "required",
        "claim_supported": payload.get("claim", {}).get("status") == CLAIM_STATUS,
        "rust_unit_tests": assertions.get("rust_unit_tests_passed", {}).get("passed") is True,
        "rust_benchmark_cli": assertions.get("rust_benchmark_cli_passed", {}).get("passed") is True,
        "release_candidate_replayed": assertions.get("release_candidate_replayed", {}).get("passed") is True,
    }


def _replay_checks(payload: Mapping[str, Any]) -> Dict[str, bool]:
    assertions = _assertion_map(payload)
    return {
        "schema": payload.get("schema") == "stock_harness_release_candidate_replay_v1",
        "status": payload.get("status") == "passed",
        "requires_release_gate_json": payload.get("require_release_gate_json") is True,
        "requires_official_claim_ready": payload.get("require_official_claim_ready") is True,
        "rust_not_skipped": payload.get("skip_rust") is False,
        "all_assertions_passed": _all_assertions_passed(payload),
        "rust_unit_tests": assertions.get("extracted_rust_unit_tests_passed", {}).get("passed") is True,
        "rust_benchmark_cli": assertions.get("extracted_rust_benchmark_cli_passed", {}).get("passed") is True,
    }


def _manifest_checks(payload: Mapping[str, Any], schema: str) -> Dict[str, bool]:
    return {
        "schema": payload.get("schema") == schema,
        "status": payload.get("status") == "passed",
        "claim_id": payload.get("claim_scope", {}).get("claim_id") == CLAIM_ID,
        "benchmark_suite": payload.get("claim_scope", {}).get("benchmark_suite") == BENCHMARK_SUITE,
    }


def _claim_contract_checks(payload: Mapping[str, Any]) -> Dict[str, bool]:
    return {
        "schema": payload.get("schema") == "stock_harness_claim_contract_v1",
        "claim_id": payload.get("claim_id") == CLAIM_ID,
        "benchmark_suite": payload.get("benchmark_suite") == BENCHMARK_SUITE,
        "status_when_supported": payload.get("status_when_supported") == CLAIM_STATUS,
        "publication_assertions_present": "release_candidate_replayed_for_publication"
        in payload.get("required_publication_gate_assertions", []),
        "official_claim_packet_checks_present": "official_gate_publishable"
        in payload.get("required_official_claim_packet_checks", []),
        "universal_dominance_non_claim": "No universal external-framework dominance claim."
        in payload.get("non_claims", []),
    }


def build_official_claim_packet(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = False,
    official_claim_gate_json: Path = DEFAULT_OFFICIAL_CLAIM_GATE_JSON,
    official_release_gate_json: Path = DEFAULT_OFFICIAL_RELEASE_GATE_JSON,
    official_replay_json: Path = DEFAULT_OFFICIAL_REPLAY_JSON,
    release_manifest: Path = DEFAULT_RELEASE_MANIFEST,
    evidence_manifest: Path = DEFAULT_EVIDENCE_MANIFEST,
    candidate_manifest: Path = DEFAULT_CANDIDATE_MANIFEST,
    claim_contract: Path = DEFAULT_CLAIM_CONTRACT,
) -> Dict[str, Any]:
    output_dir = _resolve(output_dir)
    paths = {
        "official_claim_gate.json": _resolve(official_claim_gate_json),
        "official_release_gate.json": _resolve(official_release_gate_json),
        "official_release_candidate_replay.json": _resolve(official_replay_json),
        "release_manifest.json": _resolve(release_manifest),
        "evidence_manifest.json": _resolve(evidence_manifest),
        "release_candidate_manifest.json": _resolve(candidate_manifest),
        "claim_contract.json": _resolve(claim_contract),
    }
    if clean:
        _safe_clean_output(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = [name for name, path in paths.items() if not path.is_file()]
    if not missing:
        for name, path in paths.items():
            _copy(path, output_dir, name)

    payloads = {
        name: (_load_json(path) if path.is_file() else {})
        for name, path in paths.items()
    }
    checks = {
        "required_inputs_present": {
            "passed": missing == [],
            "missing": missing,
        },
        "official_claim_gate": {
            "checks": _official_claim_gate_checks(payloads["official_claim_gate.json"]),
        },
        "official_release_gate": {
            "checks": _release_gate_checks(payloads["official_release_gate.json"]),
        },
        "official_release_candidate_replay": {
            "checks": _replay_checks(payloads["official_release_candidate_replay.json"]),
        },
        "release_manifest": {
            "checks": _manifest_checks(payloads["release_manifest.json"], "stock_harness_release_bundle_v1"),
        },
        "evidence_manifest": {
            "checks": _manifest_checks(payloads["evidence_manifest.json"], "stock_harness_evidence_packet_v1"),
        },
        "release_candidate_manifest": {
            "checks": _manifest_checks(
                payloads["release_candidate_manifest.json"],
                "stock_harness_release_candidate_v1",
            ),
        },
        "claim_contract": {
            "checks": _claim_contract_checks(payloads["claim_contract.json"]),
        },
    }
    for value in checks.values():
        if "checks" in value:
            value["passed"] = all(value["checks"].values())

    files = _file_entries(output_dir)
    manifest = {
        "schema": "stock_harness_official_claim_packet_v1",
        "status": "passed" if all(check["passed"] for check in checks.values()) else "failed",
        "generated_at_unix": int(time.time()),
        "source_root": str(ROOT),
        "output_dir": str(output_dir),
        "claim_scope": {
            "claim_id": CLAIM_ID,
            "benchmark_suite": BENCHMARK_SUITE,
            "claim_limit": "SOTA-grade deterministic verification coverage only",
            "publication_requirement": "official_claim_publishable: true",
        },
        "checks": checks,
        "file_count": len(files),
        "files": files,
    }
    _write_json(output_dir / PACKET_MANIFEST_NAME, manifest)
    return manifest


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Stock Harness official claim packet.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for the packet.")
    parser.add_argument("--clean", action="store_true", help="Clean the default packet directory before writing.")
    parser.add_argument("--official-claim-gate-json", default=str(DEFAULT_OFFICIAL_CLAIM_GATE_JSON))
    parser.add_argument("--official-release-gate-json", default=str(DEFAULT_OFFICIAL_RELEASE_GATE_JSON))
    parser.add_argument("--official-replay-json", default=str(DEFAULT_OFFICIAL_REPLAY_JSON))
    parser.add_argument("--release-manifest", default=str(DEFAULT_RELEASE_MANIFEST))
    parser.add_argument("--evidence-manifest", default=str(DEFAULT_EVIDENCE_MANIFEST))
    parser.add_argument("--candidate-manifest", default=str(DEFAULT_CANDIDATE_MANIFEST))
    parser.add_argument("--claim-contract", default=str(DEFAULT_CLAIM_CONTRACT))
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_official_claim_packet(
        Path(args.output_dir),
        clean=args.clean,
        official_claim_gate_json=Path(args.official_claim_gate_json),
        official_release_gate_json=Path(args.official_release_gate_json),
        official_replay_json=Path(args.official_replay_json),
        release_manifest=Path(args.release_manifest),
        evidence_manifest=Path(args.evidence_manifest),
        candidate_manifest=Path(args.candidate_manifest),
        claim_contract=Path(args.claim_contract),
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
