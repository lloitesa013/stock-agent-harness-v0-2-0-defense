#!/usr/bin/env python3
"""Build a distributable Stock Harness release candidate artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = Path("dist/stock_harness_release")
EVIDENCE_DIR = Path("dist/stock_harness_evidence_packet")
DEFAULT_OUTPUT_DIR = Path("dist/stock_harness_release_candidate")
CLAIM_CONTRACT_PATH = Path("benchmarks/downside_verification_v1/claim_contract.json")
RELEASE_CANDIDATE_MANIFEST = "RELEASE_CANDIDATE_MANIFEST.json"


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
    if resolved.name != "stock_harness_release_candidate":
        raise ValueError("refusing to clean unexpected output directory: " + str(resolved))
    if resolved.exists():
        shutil.rmtree(str(resolved))


def _zip_directory(source_dir: Path, zip_path: Path) -> Dict[str, Any]:
    files = [path for path in sorted(source_dir.rglob("*")) if path.is_file()]
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(zip_path), "w") as archive:
        for path in files:
            rel = path.relative_to(source_dir).as_posix()
            info = zipfile.ZipInfo(rel)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return {
        "path": zip_path.name,
        "bytes": zip_path.stat().st_size,
        "sha256": _sha256(zip_path),
        "source_dir": str(source_dir),
        "source_file_count": len(files),
    }


def _input_checks(release_dir: Path, evidence_dir: Path) -> Dict[str, bool]:
    release_manifest = release_dir / "RELEASE_MANIFEST.json"
    evidence_manifest = evidence_dir / "EVIDENCE_MANIFEST.json"
    release_payload = _load_json(release_manifest) if release_manifest.exists() else {}
    evidence_payload = _load_json(evidence_manifest) if evidence_manifest.exists() else {}
    return {
        "release_manifest_passed": release_payload.get("schema") == "stock_harness_release_bundle_v1"
        and release_payload.get("status") == "passed",
        "evidence_manifest_passed": evidence_payload.get("schema") == "stock_harness_evidence_packet_v1"
        and evidence_payload.get("status") == "passed",
        "release_dir_present": release_dir.is_dir(),
        "evidence_dir_present": evidence_dir.is_dir(),
    }


def build_release_candidate(output_dir: Path = DEFAULT_OUTPUT_DIR, clean: bool = False) -> Dict[str, Any]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    release_dir = ROOT / RELEASE_DIR
    evidence_dir = ROOT / EVIDENCE_DIR
    claim_contract = _load_json(ROOT / CLAIM_CONTRACT_PATH)
    checks = _input_checks(release_dir, evidence_dir)
    if clean:
        _safe_clean_output(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    components: List[Dict[str, Any]] = []
    status_passed = all(checks.values())
    if status_passed:
        components.append(_zip_directory(release_dir, output_dir / "stock_harness_release.zip"))
        components.append(_zip_directory(evidence_dir, output_dir / "stock_harness_evidence_packet.zip"))

    manifest = {
        "schema": "stock_harness_release_candidate_v1",
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
        "component_count": len(components),
        "components": components,
    }
    _write_json(output_dir / RELEASE_CANDIDATE_MANIFEST, manifest)
    return manifest


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Stock Harness release candidate artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for candidate artifacts.")
    parser.add_argument("--clean", action="store_true", help="Clean the release candidate directory before writing.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_release_candidate(Path(args.output_dir), clean=args.clean)
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
