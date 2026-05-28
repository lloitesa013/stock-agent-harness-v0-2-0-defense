"""Streamlit evidence viewer for Financial Agent Evidence OS.

The dashboard is intentionally read-only. It reads the sealed
v0.2.0-defense evidence packet and never runs backtests or rewrites files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_ROOT = REPO_ROOT / "release_evidence" / "v0.2.0-defense-final"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def bool_status(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "PENDING"


def file_status(path: Path) -> str:
    return "FOUND" if path.exists() else "PENDING"


def percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}%"
    return "Pending"


def decimal(value: Any, digits: int = 2) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return "Pending"


def evidence_paths(root: Path) -> Dict[str, Path]:
    evidence = root / "evidence"
    defense = evidence / "downside_performance_v1_defense_packet"
    performance = evidence / "downside_performance_v1_evidence"
    return {
        "root": root,
        "release_seal": root / "RELEASE_SEAL_MANIFEST.json",
        "one_page_summary": root / "ONE_PAGE_SUMMARY.md",
        "technical_paper": root / "paper" / "DOWNSIDE_PERFORMANCE_CLAIM_PAPER.pdf",
        "forward_protocol_md": root / "forward" / "FORWARD_PAPER_TRADING_START.md",
        "defense_gate": defense / "defense_gate.json",
        "strategy_freeze": defense / "strategy_freeze_report.json",
        "baseline_fairness": defense / "baseline_fairness_report.json",
        "data_lineage": defense / "data_lineage_bias_report.json",
        "statistical_confidence": defense / "statistical_confidence_report.json",
        "forward_protocol_json": defense / "forward_paper_trading_protocol.json",
        "metrics": performance / "metrics.json",
        "performance_gate": performance / "performance_gate.json",
        "claim_contract": performance / "claim_contract.json",
        "robustness": performance / "robustness_report.json",
        "equity_curves": performance / "equity_curves.csv",
        "trades": performance / "trades.csv",
        "official_packet": root / "official" / "stock_harness_official_claim_packet",
        "release_candidate": root / "official" / "stock_harness_release_candidate",
        "public_snapshot": root / "public_snapshot" / "downside_performance_v1_public_snapshot",
    }


def collect_evidence(root: Optional[Path] = None) -> Dict[str, Any]:
    root = root or DEFAULT_EVIDENCE_ROOT
    paths = evidence_paths(root)
    release_seal = load_json(paths["release_seal"])
    defense_gate = load_json(paths["defense_gate"])
    performance_gate = load_json(paths["performance_gate"])
    strategy_freeze = load_json(paths["strategy_freeze"])
    metrics = load_json(paths["metrics"])
    claim_contract = load_json(paths["claim_contract"])
    statistical_confidence = load_json(paths["statistical_confidence"])
    baseline_fairness = load_json(paths["baseline_fairness"])
    data_lineage = load_json(paths["data_lineage"])
    forward_protocol = load_json(paths["forward_protocol_json"])

    seal_checks = release_seal.get("checks", {})
    defense_checks = defense_gate.get("checks", {})
    performance_checks = performance_gate.get("checks", {})
    candidate_metrics = metrics.get("agentic_candidate_v1", {})

    return {
        "root": str(root),
        "paths": paths,
        "release_seal": release_seal,
        "defense_gate": defense_gate,
        "performance_gate": performance_gate,
        "strategy_freeze": strategy_freeze,
        "metrics": metrics,
        "candidate_metrics": candidate_metrics,
        "claim_contract": claim_contract,
        "statistical_confidence": statistical_confidence,
        "baseline_fairness": baseline_fairness,
        "data_lineage": data_lineage,
        "forward_protocol": forward_protocol,
        "status": {
            "claim_status": bool_status(seal_checks.get("performance_claim_publishable")),
            "strategy_freeze": bool_status(defense_checks.get("strategy_freeze_verified")),
            "data_integrity": bool_status(defense_checks.get("data_bias_defense_passed")),
            "overfitting_risk": "Medium"
            if defense_checks.get("bootstrap_confidence_intervals_present")
            else "Pending",
            "cost_stress": bool_status(performance_checks.get("cost_stress_survived")),
            "forward_validation": "Started"
            if defense_checks.get("paper_trading_protocol_initialized")
            or seal_checks.get("forward_paper_trading_started")
            else "Pending",
        },
    }


def artifact_rows(paths: Mapping[str, Path]) -> List[Dict[str, str]]:
    keys = [
        "release_seal",
        "one_page_summary",
        "technical_paper",
        "forward_protocol_md",
        "claim_contract",
        "metrics",
        "performance_gate",
        "defense_gate",
        "strategy_freeze",
        "equity_curves",
        "trades",
        "official_packet",
        "release_candidate",
        "public_snapshot",
    ]
    rows = []
    for key in keys:
        path = paths[key]
        rows.append({"artifact": key, "status": file_status(path), "path": str(path)})
    return rows


def metric_rows(metrics: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for strategy_id, payload in metrics.items():
        rows.append(
            {
                "strategy_id": strategy_id,
                "label": str(payload.get("label", strategy_id)),
                "family": str(payload.get("family", "")),
                "total_return": percent(payload.get("total_return")),
                "cagr": percent(payload.get("cagr")),
                "max_drawdown": percent(payload.get("max_drawdown")),
                "sharpe": decimal(payload.get("sharpe_ratio")),
                "calmar": decimal(payload.get("calmar_ratio")),
                "turnover": decimal(payload.get("total_turnover")),
            }
        )
    rows.sort(key=lambda row: (row["family"] != "candidate", row["strategy_id"]))
    return rows


def _render_status_cards(st: Any, status: Mapping[str, str]) -> None:
    cols = st.columns(3)
    items = list(status.items())
    for index, (label, value) in enumerate(items):
        cols[index % 3].metric(label.replace("_", " ").title(), value)


def _render_claim_registry(st: Any, evidence: Mapping[str, Any]) -> None:
    defense_gate = evidence["defense_gate"]
    claim_scope = defense_gate.get("claim_scope", {})
    st.subheader("Allowed Claim")
    st.write(claim_scope.get("claim_limit", "Pending"))
    st.subheader("Claim Scope")
    st.json(claim_scope)
    st.subheader("Non-Claims")
    non_claims = claim_scope.get("non_claims", [])
    if non_claims:
        for item in non_claims:
            st.write(f"- {item}")
    else:
        st.write("Pending")


def _render_strategy_freeze(st: Any, evidence: Mapping[str, Any]) -> None:
    freeze = evidence["strategy_freeze"]
    st.subheader("Freeze Statement")
    st.write(freeze.get("freeze_statement", "Pending"))
    st.subheader("Fingerprints")
    st.json(
        {
            "candidate_config_fingerprint": freeze.get("candidate_config_fingerprint"),
            "strategy_registry_fingerprint": freeze.get("strategy_registry_fingerprint"),
        }
    )
    st.subheader("Partitions")
    st.json(freeze.get("partitions", {}))


def _render_performance(st: Any, evidence: Mapping[str, Any]) -> None:
    candidate = evidence["candidate_metrics"]
    st.subheader("Candidate Metrics")
    st.json(
        {
            "return_multiple": candidate.get("return_multiple"),
            "total_return": candidate.get("total_return"),
            "cagr": candidate.get("cagr"),
            "max_drawdown": candidate.get("max_drawdown"),
            "sharpe_ratio": candidate.get("sharpe_ratio"),
            "sortino_ratio": candidate.get("sortino_ratio"),
            "calmar_ratio": candidate.get("calmar_ratio"),
            "volatility": candidate.get("volatility"),
            "worst_month": candidate.get("worst_month"),
            "worst_year": candidate.get("worst_year"),
            "total_turnover": candidate.get("total_turnover"),
        }
    )
    st.subheader("Strategy Comparison")
    st.table(metric_rows(evidence["metrics"]))


def _render_overfitting(st: Any, evidence: Mapping[str, Any]) -> None:
    st.subheader("Defense Gate Checks")
    st.json(evidence["defense_gate"].get("checks", {}))
    st.subheader("Statistical Confidence")
    st.json(evidence["statistical_confidence"])
    st.subheader("Baseline Fairness")
    st.json(evidence["baseline_fairness"])
    st.subheader("Data Lineage and Bias")
    st.json(evidence["data_lineage"])


def _render_exports(st: Any, evidence: Mapping[str, Any]) -> None:
    st.subheader("Sealed Artifacts")
    st.table(artifact_rows(evidence["paths"]))


def render_dashboard(st: Any, evidence: Mapping[str, Any]) -> None:
    st.set_page_config(page_title="Financial Agent Evidence OS", layout="wide")
    st.title("Financial Agent Evidence OS")
    st.caption(
        "Read-only evidence viewer. This dashboard does not run backtests, place orders, or regenerate claims."
    )
    st.info(
        "This is not a trading bot. This is a claim-governed verification and evidence system for financial AI agents."
    )

    tabs = st.tabs(
        [
            "Main Dashboard",
            "Claim Registry",
            "Strategy Freeze",
            "Performance & Risk",
            "Overfitting Audit",
            "Evidence Packet Export",
        ]
    )

    with tabs[0]:
        _render_status_cards(st, evidence["status"])
        st.subheader("Evidence Root")
        st.code(evidence["root"])
    with tabs[1]:
        _render_claim_registry(st, evidence)
    with tabs[2]:
        _render_strategy_freeze(st, evidence)
    with tabs[3]:
        _render_performance(st, evidence)
    with tabs[4]:
        _render_overfitting(st, evidence)
    with tabs[5]:
        _render_exports(st, evidence)


def main() -> int:
    try:
        import streamlit as st  # type: ignore
    except ImportError:
        print("Streamlit is not installed. Install with: pip install -r requirements-dashboard.txt")
        return 1

    root = Path(os.environ.get("EVIDENCE_ROOT", str(DEFAULT_EVIDENCE_ROOT)))
    render_dashboard(st, collect_evidence(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

