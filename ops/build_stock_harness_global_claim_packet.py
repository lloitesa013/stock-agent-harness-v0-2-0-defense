#!/usr/bin/env python3
"""Build the publication packet for the global Stock Harness verification claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path("dist/stock_harness_global_claim_packet")
DEFAULT_GLOBAL_GATE_JSON = Path("reports/stock_harness_global_claim_gate_py310_latest.json")
DEFAULT_CLAIM_CONTRACT = Path("benchmarks/global_verification_v1/claim_contract.json")
PACKET_MANIFEST_NAME = "GLOBAL_CLAIM_PACKET_MANIFEST.json"
CLAIM_ID = "global_downside_verification_sota_grade_v0_1"
BENCHMARK_SUITE = "global_verification_v1"
CLAIM_STATUS = "supported_for_named_external_framework_benchmark_suite"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


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


def _safe_clean_output(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    dist_root = (ROOT / "dist").resolve()
    if not str(resolved).startswith(str(dist_root)):
        raise ValueError("refusing to clean outside dist/: " + str(resolved))
    if resolved.name != "stock_harness_global_claim_packet":
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
    return {str(item.get("id")): item for item in assertions if isinstance(item, dict)}


def _all_assertions_passed(payload: Mapping[str, Any]) -> bool:
    assertions = payload.get("assertions", [])
    if not isinstance(assertions, list) or not assertions:
        return False
    return all(isinstance(item, dict) and item.get("passed") is True for item in assertions)


def _global_gate_checks(payload: Mapping[str, Any]) -> Dict[str, bool]:
    assertions = _assertion_map(payload)
    comparison = payload.get("global_comparison", {})
    publication = comparison.get("publication_requirements", {})
    return {
        "schema": payload.get("schema") == "stock_harness_global_claim_gate_v1",
        "overall_status": payload.get("overall_status") == "passed",
        "global_claim_ready": payload.get("global_claim_ready") is True,
        "all_assertions_passed": _all_assertions_passed(payload),
        "all_required_external_adapters_executed": assertions.get(
            "all_required_external_adapters_executed", {}
        ).get("passed")
        is True,
        "external_adapter_versions_fingerprinted": assertions.get(
            "external_adapter_versions_fingerprinted", {}
        ).get("passed")
        is True,
        "comparison_claim_supported": comparison.get("claim", {}).get("status") == CLAIM_STATUS,
        "comparison_publication_passed": publication.get("passed") is True,
        "comparison_missing_frameworks_absent": publication.get("missing_external_frameworks") == [],
        "comparison_executed_framework_count": publication.get("named_external_adapters_executed_count") == 6,
    }


def _comparison_checks(payload: Mapping[str, Any]) -> Dict[str, bool]:
    return {
        "schema": payload.get("schema") == "stock_harness_global_framework_comparison_v1",
        "claim_id": payload.get("claim", {}).get("id") == CLAIM_ID,
        "benchmark_suite": payload.get("claim", {}).get("benchmark_suite") == BENCHMARK_SUITE,
        "claim_status": payload.get("claim", {}).get("status") == CLAIM_STATUS,
        "stock_harness_ranked_first": payload.get("ranking", [{}])[0].get("id") == "angelos_stock_harness",
        "stock_harness_coverage_full": payload.get("tools", {})
        .get("angelos_stock_harness", {})
        .get("coverage_score")
        == 1.0,
    }


def _claim_contract_checks(payload: Mapping[str, Any]) -> Dict[str, bool]:
    non_claims = list(payload.get("non_claims", []))
    return {
        "schema": payload.get("schema") == "stock_harness_global_claim_contract_v1",
        "claim_id": payload.get("claim_id") == CLAIM_ID,
        "benchmark_suite": payload.get("benchmark_suite") == BENCHMARK_SUITE,
        "status_when_supported": payload.get("status_when_supported") == CLAIM_STATUS,
        "minimum_external_count": payload.get("minimum_named_external_adapters_executed") == 6,
        "required_frameworks_present": set(payload.get("required_external_frameworks", []))
        == {
            "backtesting_py",
            "backtrader",
            "vectorbt",
            "zipline_reloaded",
            "quantconnect_lean",
            "nautilus_trader",
        },
        "global_boundary_non_claim_present": (
            "No claim outside the named external frameworks and versions executed by this benchmark suite."
            in non_claims
        ),
        "profile_only_non_claim_present": (
            "No claim for frameworks that are profile-only or missing from the direct adapter evidence."
            in non_claims
        ),
    }


def build_global_claim_packet(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = False,
    global_claim_gate_json: Path = DEFAULT_GLOBAL_GATE_JSON,
    claim_contract: Path = DEFAULT_CLAIM_CONTRACT,
) -> Dict[str, Any]:
    output_dir = _resolve(output_dir)
    gate_path = _resolve(global_claim_gate_json)
    contract_path = _resolve(claim_contract)
    paths = {
        "global_claim_gate.json": gate_path,
        "global_claim_contract.json": contract_path,
    }
    if clean:
        _safe_clean_output(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = [name for name, path in paths.items() if not path.is_file()]
    gate_payload = _load_json(gate_path) if gate_path.is_file() else {}
    comparison_payload = gate_payload.get("global_comparison", {}) if isinstance(gate_payload, dict) else {}
    contract_payload = _load_json(contract_path) if contract_path.is_file() else {}
    if not missing:
        for name, path in paths.items():
            _copy(path, output_dir, name)
        if isinstance(comparison_payload, dict):
            _write_json(output_dir / "global_framework_comparison.json", comparison_payload)

    checks = {
        "required_inputs_present": {"passed": missing == [], "missing": missing},
        "global_claim_gate": {"checks": _global_gate_checks(gate_payload)},
        "global_framework_comparison": {"checks": _comparison_checks(comparison_payload)},
        "global_claim_contract": {"checks": _claim_contract_checks(contract_payload)},
    }
    for value in checks.values():
        if "checks" in value:
            value["passed"] = all(value["checks"].values())

    files = _file_entries(output_dir)
    manifest = {
        "schema": "stock_harness_global_claim_packet_v1",
        "status": "passed" if all(check["passed"] for check in checks.values()) else "failed",
        "generated_at_unix": int(time.time()),
        "source_root": str(ROOT),
        "output_dir": str(output_dir),
        "claim_scope": {
            "claim_id": CLAIM_ID,
            "benchmark_suite": BENCHMARK_SUITE,
            "claim_limit": "Global SOTA-grade deterministic verification coverage only",
            "publication_requirement": "global_claim_ready: true",
        },
        "checks": checks,
        "file_count": len(files),
        "files": files,
    }
    _write_json(output_dir / PACKET_MANIFEST_NAME, manifest)
    return manifest


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Stock Harness global claim packet.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output packet directory.")
    parser.add_argument("--global-claim-gate-json", default=str(DEFAULT_GLOBAL_GATE_JSON))
    parser.add_argument("--claim-contract", default=str(DEFAULT_CLAIM_CONTRACT))
    parser.add_argument("--clean", action="store_true", help="Clean output directory before building.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_global_claim_packet(
        Path(args.output_dir),
        clean=args.clean,
        global_claim_gate_json=Path(args.global_claim_gate_json),
        claim_contract=Path(args.claim_contract),
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
