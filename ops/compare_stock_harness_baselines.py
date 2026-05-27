#!/usr/bin/env python3
"""Compare stock-harness verification coverage against local baseline profiles.

This is a deterministic evidence script. It does not import external engines,
download data, or run a performance shootout. The goal is to make the public
SOTA-grade claim boundary machine-checkable for the included benchmark suite.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.benchmark_stock_harness import run_benchmark_suite


CLAIM_ID = "downside_verification_sota_grade_v0_1"
BENCHMARK_DIR = Path("benchmarks/downside_verification_v1")
EXPECTED_SUMMARY_PATH = BENCHMARK_DIR / "expected_summary.json"
CLAIM_CONTRACT_PATH = BENCHMARK_DIR / "claim_contract.json"


CAPABILITIES: List[Dict[str, str]] = [
    {
        "id": "local_csv_no_dependency",
        "label": "Local CSV, no-network, no-dependency benchmark execution",
    },
    {
        "id": "lagged_no_lookahead_execution",
        "label": "Lagged signal execution with no same-bar lookahead trading",
    },
    {
        "id": "mdd_first_verdict",
        "label": "MDD-first verdict and downside report fields",
    },
    {
        "id": "no_dependency_oracle_parity",
        "label": "Independent no-dependency oracle benchmark parity",
    },
    {
        "id": "lookahead_mutation_audit",
        "label": "Lookahead mutation audit that detects unsafe execution",
    },
    {
        "id": "data_quality_structural_gate",
        "label": "Data-quality gate for invalid, duplicate, missing, and zero-volume sessions",
    },
    {
        "id": "market_calendar_profile",
        "label": "Market-calendar expected-session profile checks",
    },
    {
        "id": "adjusted_ohlc_consistency",
        "label": "Adjusted OHLC completeness and ratio-consistency checks",
    },
    {
        "id": "external_equity_trade_fill_parity",
        "label": "External-engine style equity, trade, and fill parity",
    },
    {
        "id": "order_intent_parity",
        "label": "Order-intent parity before execution side effects",
    },
    {
        "id": "walk_forward_downside_validation",
        "label": "Walk-forward downside validation",
    },
    {
        "id": "regime_stress_validation",
        "label": "Regime stress validation",
    },
    {
        "id": "parameter_overfit_sweep",
        "label": "Parameter overfit sweep",
    },
    {
        "id": "cost_slippage_stress",
        "label": "Cost and slippage stress",
    },
    {
        "id": "expanded_execution_stress",
        "label": "Delay, gap, cash-yield, liquidity, and market-impact stress",
    },
    {
        "id": "multi_asset_group_metrics",
        "label": "Multi-asset grouped downside metrics",
    },
    {
        "id": "per_case_artifact_bundle",
        "label": "Per-case artifact bundle writer",
    },
    {
        "id": "reproducible_manifest",
        "label": "Deterministic experiment manifest",
    },
]


FULL_COVERAGE = {capability["id"]: True for capability in CAPABILITIES}


BASELINE_PROFILES: Dict[str, Dict[str, Any]] = {
    "minimal_ma_backtest_baseline": {
        "description": "A small local moving-average backtest with basic downside reporting.",
        "coverage": {
            "local_csv_no_dependency": True,
            "lagged_no_lookahead_execution": True,
            "mdd_first_verdict": True,
            "no_dependency_oracle_parity": False,
            "lookahead_mutation_audit": False,
            "data_quality_structural_gate": False,
            "market_calendar_profile": False,
            "adjusted_ohlc_consistency": False,
            "external_equity_trade_fill_parity": False,
            "order_intent_parity": False,
            "walk_forward_downside_validation": False,
            "regime_stress_validation": False,
            "parameter_overfit_sweep": False,
            "cost_slippage_stress": False,
            "expanded_execution_stress": False,
            "multi_asset_group_metrics": False,
            "per_case_artifact_bundle": False,
            "reproducible_manifest": False,
        },
    },
    "generic_backtesting_engine_with_custom_hooks": {
        "description": (
            "A generic external-engine profile assuming custom hooks are added by the user. "
            "This is a coverage profile, not a claim about any named third-party project."
        ),
        "coverage": {
            "local_csv_no_dependency": False,
            "lagged_no_lookahead_execution": True,
            "mdd_first_verdict": True,
            "no_dependency_oracle_parity": False,
            "lookahead_mutation_audit": False,
            "data_quality_structural_gate": False,
            "market_calendar_profile": False,
            "adjusted_ohlc_consistency": False,
            "external_equity_trade_fill_parity": False,
            "order_intent_parity": False,
            "walk_forward_downside_validation": True,
            "regime_stress_validation": True,
            "parameter_overfit_sweep": True,
            "cost_slippage_stress": True,
            "expanded_execution_stress": False,
            "multi_asset_group_metrics": True,
            "per_case_artifact_bundle": False,
            "reproducible_manifest": False,
        },
    },
    "angelos_stock_harness": {
        "description": "The included deterministic downside-aware verification harness.",
        "coverage": FULL_COVERAGE,
    },
}


def _coverage_score(coverage: Mapping[str, bool]) -> float:
    if not CAPABILITIES:
        return 0.0
    covered = sum(1 for capability in CAPABILITIES if coverage.get(capability["id"], False))
    return round(covered / len(CAPABILITIES), 6)


def _missing_capabilities(coverage: Mapping[str, bool]) -> List[str]:
    return [
        capability["id"]
        for capability in CAPABILITIES
        if not coverage.get(capability["id"], False)
    ]


def _load_expected_summary(path: Path = EXPECTED_SUMMARY_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_claim_contract(path: Path = CLAIM_CONTRACT_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _claim_contract_diffs(contract: Mapping[str, Any]) -> List[str]:
    capability_ids = [capability["id"] for capability in CAPABILITIES]
    required_capabilities = list(contract.get("required_capabilities", []))
    diffs: List[str] = []
    if contract.get("claim_id") != CLAIM_ID:
        diffs.append("claim_id_mismatch")
    if contract.get("benchmark_suite") != "downside_verification_v1":
        diffs.append("benchmark_suite_mismatch")
    if required_capabilities != capability_ids:
        diffs.append("required_capabilities_mismatch")
    if "No universal external-framework dominance claim." not in contract.get("non_claims", []):
        diffs.append("universal_dominance_non_claim_missing")
    return diffs


def _extract_benchmark_subset(benchmark: Mapping[str, Any]) -> Dict[str, Any]:
    engine_parity = benchmark["engine_parity"]
    calendar_data_quality = benchmark["calendar_data_quality"]
    adjusted_ohlc_data_quality = benchmark["adjusted_ohlc_data_quality"]
    multi_asset_benchmark = benchmark["multi_asset_benchmark"]
    stress_matrix = benchmark["stress_matrix"]

    return {
        "all_passed": benchmark["all_passed"],
        "oracle_case_count": len(benchmark["cases"]),
        "engine_parity_diff_count": engine_parity["metrics"]["diff_count"],
        "engine_parity_compared_order_intents": engine_parity["metrics"][
            "compared_order_intents"
        ],
        "calendar_expected_sessions": calendar_data_quality["metrics"][
            "calendar_expected_sessions"
        ],
        "adjusted_ohlc_checks_applied": adjusted_ohlc_data_quality["metrics"][
            "adjusted_ohlc_checks_applied"
        ],
        "multi_asset_case_artifact_count": multi_asset_benchmark["case_artifact_count"],
        "stress_matrix_case_count": stress_matrix["metrics"]["case_count"],
    }


def _compare_expected_subset(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    diffs: List[Dict[str, Any]] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            diffs.append(
                {
                    "key": key,
                    "expected": expected_value,
                    "actual": actual_value,
                }
            )
    return diffs


def _build_tool_reports() -> Dict[str, Dict[str, Any]]:
    reports: Dict[str, Dict[str, Any]] = {}
    for name, profile in BASELINE_PROFILES.items():
        coverage = dict(profile["coverage"])
        reports[name] = {
            "description": profile["description"],
            "coverage_score": _coverage_score(coverage),
            "covered_count": len(CAPABILITIES) - len(_missing_capabilities(coverage)),
            "total_count": len(CAPABILITIES),
            "missing_capabilities": _missing_capabilities(coverage),
            "coverage": coverage,
        }
    return reports


def run_comparison() -> Dict[str, Any]:
    benchmark = run_benchmark_suite()
    expected_summary = _load_expected_summary()
    claim_contract = _load_claim_contract()
    claim_contract_diffs = _claim_contract_diffs(claim_contract)
    actual_subset = _extract_benchmark_subset(benchmark)
    expected_diffs = _compare_expected_subset(
        expected_summary["expected"], actual_subset
    )
    tool_reports = _build_tool_reports()
    harness_score = tool_reports["angelos_stock_harness"]["coverage_score"]
    supported = (
        benchmark["all_passed"]
        and not expected_diffs
        and not claim_contract_diffs
        and harness_score == 1.0
    )

    return {
        "claim": {
            "id": claim_contract["claim_id"],
            "benchmark_suite": claim_contract["benchmark_suite"],
            "contract_path": str(CLAIM_CONTRACT_PATH).replace("\\", "/"),
            "status": (
                claim_contract["status_when_supported"] if supported else "not_supported"
            ),
            "positive_claim": claim_contract["positive_claim"],
            "claim_limit": claim_contract["claim_limit"],
            "non_claims": claim_contract["non_claims"],
        },
        "capabilities": CAPABILITIES,
        "tools": tool_reports,
        "benchmark": {
            "name": benchmark["benchmark"],
            "all_passed": benchmark["all_passed"],
            "expected_summary_path": str(EXPECTED_SUMMARY_PATH),
            "expected_subset": expected_summary["expected"],
            "actual_subset": actual_subset,
            "expected_diffs": expected_diffs,
            "claim_contract_path": str(CLAIM_CONTRACT_PATH).replace("\\", "/"),
            "claim_contract_diffs": claim_contract_diffs,
        },
    }

def _write_json(report: Mapping[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, sort_keys=True))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare deterministic stock-harness verification coverage."
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print indented JSON.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = run_comparison()
    _write_json(report, pretty=args.pretty)
    return 0 if report["claim"]["status"] == "supported_for_included_benchmark_suite" else 1


if __name__ == "__main__":
    raise SystemExit(main())
