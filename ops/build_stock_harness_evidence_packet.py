#!/usr/bin/env python3
"""Build a reviewer-facing Stock Harness evidence packet.

The packet materializes the scoped claim evidence into one deterministic
directory: benchmark output, claim comparison, release bundle manifest, release
audit output, and the machine-readable claim contract. It is still a verification
artifact only; it does not claim investment performance or live-trading safety.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.audit_stock_harness_release import run_audit  # noqa: E402
from ops.benchmark_stock_harness import run_benchmark_suite  # noqa: E402
from ops.build_stock_harness_release_bundle import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as RELEASE_BUNDLE_DIR,
    build_release_bundle,
)
from ops.compare_stock_harness_baselines import (  # noqa: E402
    CLAIM_CONTRACT_PATH,
    EXPECTED_SUMMARY_PATH,
    run_comparison,
)

DEFAULT_OUTPUT_DIR = Path("dist/stock_harness_evidence_packet")
EVIDENCE_MANIFEST_NAME = "EVIDENCE_MANIFEST.json"
CLAIM_STATUS = "supported_for_included_benchmark_suite"


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
    if resolved.name != "stock_harness_evidence_packet":
        raise ValueError("refusing to clean unexpected output directory: " + str(resolved))
    if resolved.exists():
        shutil.rmtree(str(resolved))


def _copy_evidence_file(src: Path, output_dir: Path, dst_name: str) -> None:
    dst = output_dir / dst_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))


def _file_entries(output_dir: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == EVIDENCE_MANIFEST_NAME:
            continue
        rel = path.relative_to(output_dir).as_posix()
        entries.append({"path": rel, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return entries


def _optional_release_gate_check(release_gate_json: Optional[Path]) -> Dict[str, Any]:
    if release_gate_json is None:
        return {"provided": False, "passed": True}
    if not release_gate_json.exists():
        return {"provided": True, "passed": False, "error": "missing release gate JSON"}
    payload = _load_json(release_gate_json)
    checks = {
        "schema": payload.get("schema") == "stock_harness_release_gate_v1",
        "claim_status": payload.get("claim", {}).get("status") == CLAIM_STATUS,
        "python_gate_passed": payload.get("python_gate_passed") is True,
    }
    return {"provided": True, "passed": all(checks.values()), "checks": checks}


def build_evidence_packet(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    clean: bool = False,
    release_gate_json: Optional[Path] = None,
) -> Dict[str, Any]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    release_gate_json = (
        release_gate_json if release_gate_json is None or release_gate_json.is_absolute() else ROOT / release_gate_json
    )
    if clean:
        _safe_clean_output(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    claim_contract = _load_json(ROOT / CLAIM_CONTRACT_PATH)
    benchmark = run_benchmark_suite()
    comparison = run_comparison()
    bundle = build_release_bundle(RELEASE_BUNDLE_DIR, clean=True)
    audit = run_audit(RELEASE_BUNDLE_DIR / "RELEASE_MANIFEST.json")

    _write_json(output_dir / "benchmark_stock_harness.json", benchmark)
    _write_json(output_dir / "claim_comparison.json", comparison)
    _write_json(output_dir / "release_bundle.json", bundle)
    _write_json(output_dir / "release_audit.json", audit)
    _copy_evidence_file(ROOT / CLAIM_CONTRACT_PATH, output_dir, "claim_contract.json")
    _copy_evidence_file(ROOT / EXPECTED_SUMMARY_PATH, output_dir, "expected_summary.json")
    _copy_evidence_file(ROOT / RELEASE_BUNDLE_DIR / "RELEASE_MANIFEST.json", output_dir, "release_bundle_manifest.json")

    release_gate_check = _optional_release_gate_check(release_gate_json)
    if release_gate_json is not None and release_gate_json.exists():
        _copy_evidence_file(release_gate_json, output_dir, "release_gate.json")

    checks = {
        "benchmark_all_passed": benchmark.get("all_passed") is True,
        "claim_status_supported": comparison.get("claim", {}).get("status") == CLAIM_STATUS,
        "claim_contract_diffs_absent": comparison.get("benchmark", {}).get("claim_contract_diffs") == [],
        "expected_summary_diffs_absent": comparison.get("benchmark", {}).get("expected_diffs") == [],
        "coverage_score_full": comparison.get("tools", {})
        .get("angelos_stock_harness", {})
        .get("coverage_score")
        == 1.0,
        "release_bundle_passed": bundle.get("status") == "passed",
        "release_audit_passed": audit.get("status") == "passed",
        "release_manifest_copied": (output_dir / "release_bundle_manifest.json").is_file(),
        "claim_contract_copied": (output_dir / "claim_contract.json").is_file(),
        "expected_summary_copied": (output_dir / "expected_summary.json").is_file(),
        "universal_external_dominance_excluded": "No universal external-framework dominance claim."
        in comparison.get("claim", {}).get("non_claims", []),
    }
    status_passed = all(checks.values()) and bool(release_gate_check.get("passed"))

    files = _file_entries(output_dir)
    manifest = {
        "schema": "stock_harness_evidence_packet_v1",
        "status": "passed" if status_passed else "failed",
        "generated_at_unix": int(time.time()),
        "source_root": str(ROOT),
        "output_dir": str(output_dir),
        "claim_scope": {
            "claim_id": claim_contract["claim_id"],
            "benchmark_suite": claim_contract["benchmark_suite"],
            "claim_limit": claim_contract["claim_limit"],
            "claim_contract_path": str(CLAIM_CONTRACT_PATH).replace("\\", "/"),
            "non_claims": claim_contract["non_claims"],
        },
        "checks": checks,
        "release_gate_json": release_gate_check,
        "file_count": len(files),
        "files": files,
    }
    _write_json(output_dir / EVIDENCE_MANIFEST_NAME, manifest)
    return manifest


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Stock Harness evidence packet.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for the packet.")
    parser.add_argument("--clean", action="store_true", help="Clean the default evidence packet before writing.")
    parser.add_argument("--release-gate-json", help="Optional release gate JSON to copy into the packet.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    release_gate_json = Path(args.release_gate_json) if args.release_gate_json else None
    report = build_evidence_packet(Path(args.output_dir), clean=args.clean, release_gate_json=release_gate_json)
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
