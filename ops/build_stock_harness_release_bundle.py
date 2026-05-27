#!/usr/bin/env python3
"""Build a clean Stock Harness release bundle from the larger workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path("dist/stock_harness_release")
CLAIM_CONTRACT_PATH = Path("benchmarks/downside_verification_v1/claim_contract.json")

RELEASE_FILES: List[str] = [
    "LICENSE",
    "README.md",
    ".github/workflows/stock-harness-ci.yml",
    "angelos_os/__init__.py",
    "angelos_os/agent_harness.py",
    "angelos_os/performance_defense.py",
    "angelos_os/performance_harness.py",
    "angelos_os/engine.py",
    "angelos_os/profiles.py",
    "angelos_os/providers.py",
    "angelos_os/safety.py",
    "angelos_os/schemas.py",
    "angelos_os/score_core.py",
    "angelos_os/stock_harness.py",
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
    "benchmarks/downside_verification_v1/README.md",
    "benchmarks/downside_verification_v1/expected_summary.json",
    "benchmarks/downside_verification_v1/claim_contract.json",
    "benchmarks/global_verification_v1/README.md",
    "benchmarks/global_verification_v1/claim_contract.json",
    "benchmarks/agentic_verification_v1/README.md",
    "benchmarks/agentic_verification_v1/claim_contract.json",
    "benchmarks/downside_performance_v1/README.md",
    "benchmarks/downside_performance_v1/claim_contract.json",
    "docs/BENCHMARK.md",
    "docs/CLAIMS.md",
    "docs/FIRST_TIME_READER_GUIDE_KO.md",
    "docs/LIMITATIONS.md",
    "docs/PERFORMANCE_BENCHMARK_METHOD.md",
    "docs/PERFORMANCE_CLAIMS.md",
    "docs/PERFORMANCE_DEFENSE.md",
    "docs/PERFORMANCE_NON_CLAIMS.md",
    "docs/RELEASE_GATE.md",
    "docs/THREAT_MODEL.md",
    "paper/SOTA_CLAIM_TECHNICAL_REPORT.md",
    "rust_stock_harness/Cargo.lock",
    "rust_stock_harness/Cargo.toml",
    "rust_stock_harness/README.md",
    "rust_stock_harness/src/lib.rs",
    "rust_stock_harness/src/main.rs",
]

DISALLOWED_PREFIXES = (
    "external_models/",
    "external_repos/",
    "datasets/",
    "checkpoints/",
    "scenario_",
    "rust_stock_harness/target/",
)


def _load_claim_contract() -> Dict[str, Any]:
    with (ROOT / CLAIM_CONTRACT_PATH).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("/")


def _validate_release_files(files: Iterable[str] = RELEASE_FILES) -> List[str]:
    errors: List[str] = []
    seen = set()
    for rel in files:
        normalized = _normalize(rel)
        if normalized in seen:
            errors.append("duplicate release file: " + normalized)
        seen.add(normalized)
        if any(normalized.startswith(prefix) for prefix in DISALLOWED_PREFIXES):
            errors.append("disallowed release file: " + normalized)
        if not (ROOT / normalized).is_file():
            errors.append("missing release file: " + normalized)
    return errors


def _safe_clean_output(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    dist_root = (ROOT / "dist").resolve()
    if not str(resolved).startswith(str(dist_root)):
        raise ValueError("refusing to clean outside dist/: " + str(resolved))
    if resolved.name != "stock_harness_release":
        raise ValueError("refusing to clean unexpected output directory: " + str(resolved))
    if resolved.exists():
        shutil.rmtree(str(resolved))


def build_release_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR, clean: bool = False) -> Dict[str, Any]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    errors = _validate_release_files()
    if errors:
        return {
            "schema": "stock_harness_release_bundle_v1",
            "status": "failed",
            "errors": errors,
            "output_dir": str(output_dir),
        }

    claim_contract = _load_claim_contract()
    if clean:
        _safe_clean_output(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_files: List[Dict[str, Any]] = []
    for rel in RELEASE_FILES:
        normalized = _normalize(rel)
        src = ROOT / normalized
        dst = output_dir / normalized
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        manifest_files.append(
            {
                "path": normalized,
                "bytes": dst.stat().st_size,
                "sha256": _sha256(dst),
            }
        )

    manifest = {
        "schema": "stock_harness_release_bundle_v1",
        "status": "passed",
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
        "file_count": len(manifest_files),
        "files": manifest_files,
    }
    manifest_path = output_dir / "RELEASE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest

def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the clean Stock Harness release bundle.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for the bundle.")
    parser.add_argument("--clean", action="store_true", help="Clean the default dist bundle before writing.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_release_bundle(Path(args.output_dir), clean=args.clean)
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
