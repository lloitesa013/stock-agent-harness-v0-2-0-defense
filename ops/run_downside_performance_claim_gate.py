#!/usr/bin/env python3
"""Run the official downside_performance_v1 claim gate."""

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

from angelos_os.performance_harness import (  # noqa: E402
    PERFORMANCE_BENCHMARK_SUITE,
    PERFORMANCE_CLAIM_ID,
    PERFORMANCE_NON_CLAIMS,
    run_downside_performance_benchmark,
    write_performance_evidence_packet,
)

CLAIM_CONTRACT_PATH = Path("benchmarks/downside_performance_v1/claim_contract.json")
DEFAULT_EVIDENCE_DIR = Path("dist/downside_performance_v1_evidence")
REQUIRED_METRICS = [
    "total_return",
    "return_multiple",
    "cagr",
    "annualized_return",
    "max_drawdown",
    "volatility",
    "downside_deviation",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "worst_month",
    "worst_year",
    "total_turnover",
    "average_exposure",
]


def _load_claim_contract() -> Dict[str, Any]:
    with (ROOT / CLAIM_CONTRACT_PATH).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("performance claim contract must be a JSON object")
    return payload


def _assertion(assertion_id: str, passed: bool, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"id": assertion_id, "passed": bool(passed)}
    payload.update(extra)
    return payload


def _non_claims_preserved(report: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    report_non_claims = list(report.get("claim", {}).get("non_claims", []))
    contract_non_claims = list(contract.get("non_claims", []))
    return all(non_claim in report_non_claims for non_claim in PERFORMANCE_NON_CLAIMS) and all(
        non_claim in report_non_claims for non_claim in contract_non_claims
    )


def _build_assertions(
    report: Mapping[str, Any],
    replay: Mapping[str, Any],
    evidence_manifest: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    strategy_ids = [strategy["strategy_id"] for strategy in report.get("strategies", [])]
    required_strategies = list(contract.get("required_strategies", []))
    candidate_id = str(contract.get("candidate_strategy_id", "agentic_candidate_v1"))
    metrics_by_strategy = report.get("metrics_by_strategy", {})
    candidate_metrics = metrics_by_strategy.get(candidate_id, {})
    gate = report.get("performance_gate", {})
    checks = gate.get("checks", {})
    rankings = report.get("rankings", {})

    assertions = [
        _assertion("performance_report_schema_valid", report.get("schema") == "stock_harness_downside_performance_report_v1"),
        _assertion(
            "claim_contract_scope_preserved",
            contract.get("claim_id") == PERFORMANCE_CLAIM_ID
            and contract.get("benchmark_suite") == PERFORMANCE_BENCHMARK_SUITE
            and report.get("claim", {}).get("id") == PERFORMANCE_CLAIM_ID,
        ),
        _assertion(
            "all_required_strategies_executed",
            all(strategy in strategy_ids for strategy in required_strategies),
            strategy_ids=strategy_ids,
        ),
        _assertion(
            "required_metrics_present",
            all(metric in candidate_metrics for metric in REQUIRED_METRICS),
            required_metrics=REQUIRED_METRICS,
        ),
        _assertion(
            "candidate_total_return_top_ranked",
            rankings.get("total_return", [{}])[0].get("strategy_id") == candidate_id,
        ),
        _assertion("candidate_cagr_beats_baselines", checks.get("return_beats_baselines") is True),
        _assertion("candidate_calmar_top_ranked", checks.get("calmar_top_ranked") is True),
        _assertion("candidate_drawdown_control_passed", checks.get("drawdown_control_passed") is True),
        _assertion("walk_forward_passed", checks.get("walk_forward_passed") is True),
        _assertion("cost_stress_survived", checks.get("cost_stress_survived") is True),
        _assertion("lookahead_audit_passed", checks.get("lookahead_audit_passed") is True),
        _assertion("data_quality_passed", checks.get("data_quality_passed") is True),
        _assertion("negative_controls_detected", checks.get("negative_controls_detected") is True),
        _assertion("performance_gate_publishable", gate.get("performance_claim_publishable") is True),
        _assertion(
            "deterministic_replay_fingerprint_stable",
            report.get("manifest", {}).get("fingerprint") == replay.get("manifest", {}).get("fingerprint"),
            fingerprint=report.get("manifest", {}).get("fingerprint"),
            replay_fingerprint=replay.get("manifest", {}).get("fingerprint"),
        ),
        _assertion(
            "evidence_packet_manifest_passed",
            evidence_manifest.get("schema") == "downside_performance_evidence_packet_manifest_v1"
            and evidence_manifest.get("status") == "passed",
        ),
        _assertion("non_claims_preserved", _non_claims_preserved(report, contract)),
    ]

    present = {assertion["id"] for assertion in assertions}
    required_assertions = list(contract.get("required_performance_gate_assertions", []))
    assertions.append(
        _assertion(
            "claim_contract_required_assertions_present",
            all(assertion in present for assertion in required_assertions),
            required_assertions=required_assertions,
        )
    )
    return assertions


def run_downside_performance_claim_gate(evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> Dict[str, Any]:
    contract = _load_claim_contract()
    report_obj = run_downside_performance_benchmark()
    replay_obj = run_downside_performance_benchmark()
    evidence_root = evidence_dir if evidence_dir.is_absolute() else ROOT / evidence_dir
    evidence_manifest = write_performance_evidence_packet(report_obj, evidence_root, clean=True)
    report = report_obj.to_dict()
    replay = replay_obj.to_dict()
    assertions = _build_assertions(report, replay, evidence_manifest, contract)
    passed = all(assertion.get("passed") for assertion in assertions)
    return {
        "schema": "downside_performance_claim_gate_v1",
        "status": "passed" if passed else "failed",
        "performance_claim_publishable": passed,
        "claim_scope": {
            "claim_id": PERFORMANCE_CLAIM_ID,
            "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
            "claim_limit": contract.get("claim_limit"),
            "performance_type": "hypothetical_backtested_performance",
            "publication_requirement": "deterministic benchmark, evidence packet, replay-stable fingerprint",
        },
        "assertions": assertions,
        "report": report,
        "evidence_manifest": evidence_manifest,
        "generated_at_unix": int(time.time()),
        "root": str(ROOT),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_downside_performance_claim_gate(evidence_dir=args.evidence_dir)
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
