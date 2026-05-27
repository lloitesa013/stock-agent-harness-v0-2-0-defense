#!/usr/bin/env python3
"""Run the official deterministic agentic verification claim gate."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from angelos_os.agent_harness import (  # noqa: E402
    AGENTIC_BENCHMARK_SUITE,
    AGENTIC_CLAIM_ID,
    AGENTIC_NON_CLAIMS,
    AGENT_ROLES,
    AgentHarnessConfig,
    DeterministicAgentProvider,
    run_stock_agent_harness,
)

CLAIM_CONTRACT_PATH = Path("benchmarks/agentic_verification_v1/claim_contract.json")


def _load_claim_contract() -> Dict[str, Any]:
    with (ROOT / CLAIM_CONTRACT_PATH).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("agentic claim contract must be a JSON object")
    return payload


def _assertion(assertion_id: str, passed: bool, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"id": assertion_id, "passed": bool(passed)}
    payload.update(extra)
    return payload


def _roles(report: Mapping[str, Any]) -> List[str]:
    return [str(decision.get("role")) for decision in report.get("transcript", [])]


def _artifact_keys(report: Mapping[str, Any]) -> List[str]:
    return sorted(str(key) for key in report.get("stock_harness_results", {}).keys())


def _non_claims_preserved(report: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    report_non_claims = list(report.get("claim", {}).get("non_claims", []))
    contract_non_claims = list(contract.get("non_claims", []))
    return all(non_claim in report_non_claims for non_claim in AGENTIC_NON_CLAIMS) and all(
        non_claim in report_non_claims for non_claim in contract_non_claims
    )


def _build_assertions(report: Mapping[str, Any], replay: Mapping[str, Any], contract: Mapping[str, Any]) -> List[Dict[str, Any]]:
    required_roles = list(contract.get("required_roles", []))
    required_artifacts = list(contract.get("required_stock_harness_artifacts", []))
    executed_roles = _roles(report)
    artifact_keys = _artifact_keys(report)
    claim = report.get("claim", {})
    config = report.get("config", {})
    final_verdict = report.get("final_verdict", {})
    replay_manifest = replay.get("manifest", {})
    report_manifest = report.get("manifest", {})
    stock_results = report.get("stock_harness_results", {})

    assertions = [
        _assertion("agent_report_schema_valid", report.get("schema") == "stock_agent_harness_report_v1"),
        _assertion("agent_provider_deterministic", config.get("provider") == "deterministic"),
        _assertion(
            "all_required_roles_executed",
            executed_roles == required_roles == AGENT_ROLES,
            executed_roles=executed_roles,
        ),
        _assertion(
            "stock_harness_verification_artifacts_present",
            all(artifact in artifact_keys for artifact in required_artifacts),
            artifact_keys=artifact_keys,
        ),
        _assertion(
            "data_quality_gate_preserved",
            stock_results.get("data_quality", {}).get("verdict", {}).get("verdict") == "KEEP",
        ),
        _assertion(
            "lookahead_audit_preserved",
            stock_results.get("lookahead_audit", {}).get("passed") is True,
        ),
        _assertion(
            "stress_verification_preserved",
            stock_results.get("regime_stress", {}).get("verdict", {}).get("verdict") == "KEEP"
            and stock_results.get("cost_stress", {}).get("verdict", {}).get("verdict") == "KEEP"
            and stock_results.get("stress_matrix", {}).get("verdict", {}).get("verdict") == "KEEP",
        ),
        _assertion(
            "final_verdict_supported",
            final_verdict.get("verdict") == "KEEP"
            and claim.get("status") == "supported_for_included_benchmark_suite",
            final_verdict=final_verdict.get("verdict"),
        ),
        _assertion("non_claims_preserved", _non_claims_preserved(report, contract)),
        _assertion(
            "deterministic_replay_fingerprint_stable",
            report_manifest.get("fingerprint") == replay_manifest.get("fingerprint"),
            fingerprint=report_manifest.get("fingerprint"),
            replay_fingerprint=replay_manifest.get("fingerprint"),
        ),
        _assertion(
            "llm_provider_excluded_from_official_gate",
            config.get("provider") == "deterministic"
            and "No universal LLM trading dominance claim." in claim.get("non_claims", []),
        ),
        _assertion(
            "claim_contract_scope_preserved",
            contract.get("claim_id") == AGENTIC_CLAIM_ID
            and contract.get("benchmark_suite") == AGENTIC_BENCHMARK_SUITE
            and claim.get("id") == AGENTIC_CLAIM_ID
            and claim.get("benchmark_suite") == AGENTIC_BENCHMARK_SUITE,
        ),
    ]

    present = {assertion["id"] for assertion in assertions}
    required_assertions = list(contract.get("required_agentic_gate_assertions", []))
    assertions.append(
        _assertion(
            "claim_contract_required_assertions_present",
            all(assertion in present for assertion in required_assertions),
            required_assertions=required_assertions,
        )
    )
    return assertions


def run_agentic_claim_gate() -> Dict[str, Any]:
    contract = _load_claim_contract()
    config = AgentHarnessConfig(provider="deterministic")
    report = run_stock_agent_harness(config=config, provider=DeterministicAgentProvider()).to_dict()
    replay = run_stock_agent_harness(config=config, provider=DeterministicAgentProvider()).to_dict()
    assertions = _build_assertions(report, replay, contract)
    passed = all(assertion.get("passed") for assertion in assertions)
    return {
        "schema": "stock_agent_harness_claim_gate_v1",
        "status": "passed" if passed else "failed",
        "agentic_claim_ready": passed,
        "claim_scope": {
            "claim_id": AGENTIC_CLAIM_ID,
            "benchmark_suite": AGENTIC_BENCHMARK_SUITE,
            "claim_limit": contract.get("claim_limit"),
            "publication_requirement": "deterministic provider, all roles executed, Stock Harness gates integrated",
        },
        "assertions": assertions,
        "report": report,
        "generated_at_unix": int(time.time()),
        "root": str(ROOT),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_agentic_claim_gate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
