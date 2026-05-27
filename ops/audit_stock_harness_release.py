#!/usr/bin/env python3
"""Audit the Stock Harness release claim surface.

This script is intentionally conservative. It checks that the clean release bundle,
claim contract, documentation, and CI workflow agree on the scoped public claim.
It does not evaluate investment performance or external framework dominance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.build_stock_harness_release_bundle import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    DISALLOWED_PREFIXES,
    RELEASE_FILES,
    _normalize,
    _validate_release_files,
)
from ops.compare_stock_harness_baselines import (  # noqa: E402
    CAPABILITIES,
    CLAIM_CONTRACT_PATH,
    CLAIM_ID,
    EXPECTED_SUMMARY_PATH,
)

TEXT_EXTENSIONS = {".md", ".py", ".json", ".yml", ".yaml", ".toml", ".lock", ".txt"}
REQUIRED_DOCS = [
    "README.md",
    "docs/CLAIMS.md",
    "docs/BENCHMARK.md",
    "docs/RELEASE_GATE.md",
    "docs/LIMITATIONS.md",
    "docs/THREAT_MODEL.md",
    "docs/FIRST_TIME_READER_GUIDE_KO.md",
    "paper/SOTA_CLAIM_TECHNICAL_REPORT.md",
]
REQUIRED_CI_SNIPPETS = [
    "python3 ops/build_stock_harness_evidence_packet.py --clean --pretty --release-gate-json reports/stock_harness_release_gate_ci.json",
    "python3 ops/verify_stock_harness_evidence_packet.py --pretty --require-release-gate-json --require-official-claim-ready",
    "python3 ops/build_stock_harness_release_candidate.py --clean --pretty",
    "python3 ops/verify_stock_harness_release_candidate.py --pretty --require-release-gate-json --require-official-claim-ready",
    "python3 ops/replay_stock_harness_release_candidate.py --clean --pretty --require-release-gate-json --require-official-claim-ready --output reports/stock_harness_release_candidate_replay_ci.json",
    "python3 ops/run_stock_harness_official_claim_gate.py --pretty --output reports/stock_harness_official_claim_gate_ci.json",
    "python3 ops/build_stock_harness_official_claim_packet.py --clean --pretty --official-claim-gate-json reports/stock_harness_official_claim_gate_ci.json --official-release-gate-json reports/stock_harness_release_gate_official.json --official-replay-json reports/stock_harness_release_candidate_replay_official.json",
    "python3 ops/verify_stock_harness_official_claim_packet.py --pretty",
    "python3 ops/run_stock_harness_release_gate.py --pretty --output reports/stock_harness_release_gate_ci.json",
    "cargo test --manifest-path rust_stock_harness/Cargo.toml",
    "cargo run --manifest-path rust_stock_harness/Cargo.toml --bin stock-harness-benchmark -- --pretty",
]
REQUIRED_RELEASE_ASSERTIONS = [
    "python_compile_passed",
    "stock_harness_unit_suite_passed",
    "benchmark_all_passed",
    "claim_status_supported",
    "coverage_score_full",
    "universal_external_dominance_excluded",
    "release_bundle_passed",
    "release_bundle_scope_enforced",
    "release_audit_passed",
    "evidence_packet_passed",
    "evidence_packet_verified",
    "release_candidate_passed",
    "release_candidate_verified",
    "release_candidate_replayed",
    "claim_contract_required_assertions_present",
    "rust_unit_tests_passed",
    "rust_benchmark_cli_passed",
]
REQUIRED_PUBLICATION_ASSERTIONS = [
    "full_release_gate_official_ready",
    "evidence_packet_verified_for_publication",
    "release_candidate_built_for_publication",
    "release_candidate_verified_for_publication",
    "release_candidate_replayed_for_publication",
    "scoped_non_claims_preserved",
    "official_commands_completed",
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
FORBIDDEN_BROAD_CLAIM_PHRASES = [
    " ".join(("best", "stock", "trading", "system")),
    " ".join(("sota", "investment", "performance")),
    " ".join(("proven", "alpha")),
    " ".join(("broker-ready", "execution", "engine")),
    " ".join(("guaranteed", "drawdown", "control")),
    " ".join(("externally", "certified", "sota")),
    " ".join(("guaranteed", "returns")),
]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object: " + str(path))
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_files(paths: Iterable[str]) -> List[str]:
    return [path for path in paths if Path(path).suffix.lower() in TEXT_EXTENSIONS]


def _control_char_errors(paths: Iterable[str]) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    allowed = {"\n", "\r", "\t"}
    for rel in _text_files(paths):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for index, char in enumerate(text):
            if ord(char) < 32 and char not in allowed:
                errors.append({"path": rel, "index": index, "codepoint": ord(char)})
                break
    return errors


def _claim_contract_check(contract: Mapping[str, Any]) -> Dict[str, Any]:
    capability_ids = [capability["id"] for capability in CAPABILITIES]
    required_capabilities = list(contract.get("required_capabilities", []))
    required_assertions = list(contract.get("required_release_gate_assertions", []))
    required_publication_assertions = list(contract.get("required_publication_gate_assertions", []))
    required_official_claim_packet_checks = list(contract.get("required_official_claim_packet_checks", []))
    checks = {
        "schema": contract.get("schema") == "stock_harness_claim_contract_v1",
        "claim_id": contract.get("claim_id") == CLAIM_ID,
        "benchmark_suite": contract.get("benchmark_suite") == "downside_verification_v1",
        "status_when_supported": contract.get("status_when_supported") == "supported_for_included_benchmark_suite",
        "capabilities_exact": required_capabilities == capability_ids,
        "release_assertions_include_required": all(
            assertion in required_assertions for assertion in REQUIRED_RELEASE_ASSERTIONS
        ),
        "publication_assertions_include_required": all(
            assertion in required_publication_assertions
            for assertion in REQUIRED_PUBLICATION_ASSERTIONS
        ),
        "official_claim_packet_checks_include_required": all(
            check in required_official_claim_packet_checks
            for check in REQUIRED_OFFICIAL_CLAIM_PACKET_CHECKS
        ),
        "universal_dominance_non_claim_present": "No universal external-framework dominance claim."
        in contract.get("non_claims", []),
    }
    return {"passed": all(checks.values()), "checks": checks}


def _release_file_check() -> Dict[str, Any]:
    normalized = [_normalize(path) for path in RELEASE_FILES]
    validation_errors = _validate_release_files()
    checks = {
        "validation_errors_absent": validation_errors == [],
        "audit_script_included": "ops/audit_stock_harness_release.py" in normalized,
        "official_claim_gate_included": "ops/run_stock_harness_official_claim_gate.py" in normalized,
        "official_claim_packet_builder_included": "ops/build_stock_harness_official_claim_packet.py" in normalized,
        "official_claim_packet_verifier_included": "ops/verify_stock_harness_official_claim_packet.py" in normalized,
        "evidence_packet_builder_included": "ops/build_stock_harness_evidence_packet.py" in normalized,
        "evidence_packet_verifier_included": "ops/verify_stock_harness_evidence_packet.py" in normalized,
        "release_candidate_builder_included": "ops/build_stock_harness_release_candidate.py" in normalized,
        "release_candidate_verifier_included": "ops/verify_stock_harness_release_candidate.py" in normalized,
        "release_candidate_replay_included": "ops/replay_stock_harness_release_candidate.py" in normalized,
        "claim_contract_included": "benchmarks/downside_verification_v1/claim_contract.json" in normalized,
        "no_duplicate_paths": len(normalized) == len(set(normalized)),
        "no_disallowed_paths": not any(
            path.startswith(prefix) for path in normalized for prefix in DISALLOWED_PREFIXES
        ),
    }
    return {"passed": all(checks.values()), "checks": checks, "validation_errors": validation_errors}


def _manifest_check(manifest_path: Path, contract: Mapping[str, Any]) -> Dict[str, Any]:
    if not manifest_path.exists():
        return {"passed": False, "checks": {"manifest_exists": False}}
    manifest = _load_json(manifest_path)
    manifest_paths = [entry.get("path") for entry in manifest.get("files", [])]
    expected_paths = [_normalize(path) for path in RELEASE_FILES]
    hash_errors: List[Dict[str, Any]] = []
    bundle_dir = manifest_path.parent
    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            hash_errors.append({"path": "", "error": "invalid_manifest_entry"})
            continue
        rel = str(entry.get("path", ""))
        path = bundle_dir / rel
        try:
            path.resolve().relative_to(bundle_dir.resolve())
        except ValueError:
            hash_errors.append({"path": rel, "error": "unsafe_path"})
            continue
        if not path.is_file():
            hash_errors.append({"path": rel, "error": "missing_file"})
            continue
        if path.stat().st_size != entry.get("bytes"):
            hash_errors.append({"path": rel, "error": "bytes_mismatch"})
        if _sha256(path) != entry.get("sha256"):
            hash_errors.append({"path": rel, "error": "sha256_mismatch"})
    checks = {
        "manifest_exists": True,
        "schema": manifest.get("schema") == "stock_harness_release_bundle_v1",
        "status": manifest.get("status") == "passed",
        "file_count": manifest.get("file_count") == len(expected_paths),
        "file_set_exact": sorted(manifest_paths) == sorted(expected_paths),
        "file_hashes_match": hash_errors == [],
        "claim_id": manifest.get("claim_scope", {}).get("claim_id") == contract.get("claim_id"),
        "benchmark_suite": manifest.get("claim_scope", {}).get("benchmark_suite") == contract.get("benchmark_suite"),
        "claim_contract_path": manifest.get("claim_scope", {}).get("claim_contract_path")
        == str(CLAIM_CONTRACT_PATH).replace("\\", "/"),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "manifest_path": str(manifest_path),
        "hash_errors": hash_errors,
    }


def _plain_text(text: str) -> str:
    return " ".join(text.replace("`", "").split())


def _strip_allowed_claim_examples(path: str, text: str) -> str:
    if path != "docs/CLAIMS.md":
        return text
    start = text.find("Avoid wording like:")
    end = text.find("## Versioned Claim", start)
    if start == -1 or end == -1:
        return text
    return text[:start] + text[end:]


def _broad_claim_phrase_check(paths: Iterable[str] = RELEASE_FILES) -> Dict[str, Any]:
    hits: List[Dict[str, str]] = []
    for rel in _text_files(paths):
        text = (ROOT / rel).read_text(encoding="utf-8")
        normalized = _plain_text(_strip_allowed_claim_examples(rel, text)).lower()
        for phrase in FORBIDDEN_BROAD_CLAIM_PHRASES:
            if phrase in normalized:
                hits.append({"path": rel, "phrase": phrase})
    return {"passed": hits == [], "hits": hits}


def _docs_check(contract: Mapping[str, Any]) -> Dict[str, Any]:
    positive_claim = str(contract.get("positive_claim", ""))
    non_claims: Sequence[str] = list(contract.get("non_claims", []))
    missing_docs = [path for path in REQUIRED_DOCS if not (ROOT / path).is_file()]
    doc_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8") for path in REQUIRED_DOCS if (ROOT / path).is_file()
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    release_gate = (ROOT / "docs/RELEASE_GATE.md").read_text(encoding="utf-8")
    claims = (ROOT / "docs/CLAIMS.md").read_text(encoding="utf-8")
    paper = (ROOT / "paper/SOTA_CLAIM_TECHNICAL_REPORT.md").read_text(encoding="utf-8")
    checks = {
        "required_docs_present": not missing_docs,
        "positive_claim_in_readme": _plain_text(positive_claim) in _plain_text(readme),
        "release_gate_mentions_audit": "release_audit_passed" in release_gate,
        "release_gate_mentions_evidence_packet": "evidence_packet_passed" in release_gate,
        "release_gate_mentions_evidence_verification": "evidence_packet_verified" in release_gate,
        "release_gate_mentions_release_candidate": "release_candidate_passed" in release_gate,
        "release_gate_mentions_candidate_verification": "release_candidate_verified" in release_gate,
        "release_gate_mentions_candidate_replay": "release_candidate_replayed" in release_gate,
        "release_gate_mentions_official_publication_gate": "run_stock_harness_official_claim_gate.py" in release_gate,
        "release_gate_mentions_official_claim_packet": "stock_harness_official_claim_packet" in release_gate,
        "readme_mentions_official_claim_packet": "stock_harness_official_claim_packet" in readme,
        "claims_mentions_official_claim_packet": "official claim packet" in claims.lower(),
        "paper_mentions_official_claim_packet": "official claim packet" in paper.lower(),
        "all_non_claims_documented": all(non_claim in doc_text for non_claim in non_claims),
    }
    return {"passed": all(checks.values()), "checks": checks, "missing_docs": missing_docs}


def _ci_check() -> Dict[str, Any]:
    workflow_path = ROOT / ".github/workflows/stock-harness-ci.yml"
    if not workflow_path.exists():
        return {"passed": False, "checks": {"workflow_exists": False}}
    workflow = workflow_path.read_text(encoding="utf-8")
    checks = {
        "workflow_exists": True,
        "required_snippets_present": all(snippet in workflow for snippet in REQUIRED_CI_SNIPPETS),
        "repo_wide_unittest_discover_absent": "unittest discover" not in workflow,
        "audit_script_compiled": "ops/audit_stock_harness_release.py" in workflow,
        "official_claim_gate_compiled": "ops/run_stock_harness_official_claim_gate.py" in workflow,
        "official_claim_packet_builder_compiled": "ops/build_stock_harness_official_claim_packet.py" in workflow,
        "official_claim_packet_verifier_compiled": "ops/verify_stock_harness_official_claim_packet.py" in workflow,
        "evidence_packet_builder_compiled": "ops/build_stock_harness_evidence_packet.py" in workflow,
        "evidence_packet_verifier_compiled": "ops/verify_stock_harness_evidence_packet.py" in workflow,
        "release_candidate_builder_compiled": "ops/build_stock_harness_release_candidate.py" in workflow,
        "release_candidate_verifier_compiled": "ops/verify_stock_harness_release_candidate.py" in workflow,
        "release_candidate_replay_compiled": "ops/replay_stock_harness_release_candidate.py" in workflow,
        "evidence_packet_artifact_uploaded": "stock-harness-evidence-packet" in workflow,
        "release_candidate_artifact_uploaded": "stock-harness-release-candidate" in workflow,
        "release_candidate_replay_artifact_uploaded": "stock-harness-release-candidate-replay" in workflow,
        "official_claim_gate_artifact_uploaded": "stock-harness-official-claim-gate" in workflow,
        "official_claim_gate_internal_release_gate_uploaded": "reports/stock_harness_release_gate_official.json" in workflow,
        "official_claim_gate_internal_replay_uploaded": "reports/stock_harness_release_candidate_replay_official.json" in workflow,
        "official_claim_packet_artifact_uploaded": "stock-harness-official-claim-packet" in workflow,
    }
    return {"passed": all(checks.values()), "checks": checks}


def _expected_summary_check(contract: Mapping[str, Any]) -> Dict[str, Any]:
    expected = _load_json(ROOT / EXPECTED_SUMMARY_PATH)
    checks = {
        "claim_id_matches_contract": expected.get("claim_id") == contract.get("claim_id"),
        "benchmark_suite_matches_contract": expected.get("benchmark_suite") == contract.get("benchmark_suite"),
    }
    return {"passed": all(checks.values()), "checks": checks}


def run_audit(manifest_path: Path = DEFAULT_OUTPUT_DIR / "RELEASE_MANIFEST.json") -> Dict[str, Any]:
    manifest_path = manifest_path if manifest_path.is_absolute() else ROOT / manifest_path
    contract = _load_json(ROOT / CLAIM_CONTRACT_PATH)
    control_char_errors = _control_char_errors(RELEASE_FILES)
    checks = {
        "claim_contract": _claim_contract_check(contract),
        "release_files": _release_file_check(),
        "manifest": _manifest_check(manifest_path, contract),
        "docs": _docs_check(contract),
        "ci": _ci_check(),
        "expected_summary": _expected_summary_check(contract),
        "broad_claim_phrases": _broad_claim_phrase_check(),
        "text_control_chars": {
            "passed": control_char_errors == [],
            "errors": control_char_errors,
        },
    }
    return {
        "schema": "stock_harness_release_audit_v1",
        "status": "passed" if all(item["passed"] for item in checks.values()) else "failed",
        "claim_contract_path": str(CLAIM_CONTRACT_PATH).replace("\\", "/"),
        "manifest_path": str(manifest_path),
        "checks": checks,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the scoped Stock Harness release claim surface.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_OUTPUT_DIR / "RELEASE_MANIFEST.json"),
        help="Release manifest path to audit.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = run_audit(Path(args.manifest))
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
