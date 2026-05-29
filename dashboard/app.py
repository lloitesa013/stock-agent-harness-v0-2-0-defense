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
PUBLIC_CLAIM_BOUNDARY = (
    "Scoped downside-adjusted hypothetical backtested performance under the included benchmark only."
)


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


def display_mode(value: Any) -> str:
    value_text = str(value or "").strip()
    if not value_text:
        return "Pending"
    if value_text == "sealed_csv_no_network":
        return "Sealed CSV"
    return value_text.replace("_", " ").title()


def safe_claim_boundary_text(evidence: Mapping[str, Any]) -> str:
    claim_contract = evidence.get("claim_contract", {})
    defense_gate = evidence.get("defense_gate", {})
    claim_scope = defense_gate.get("claim_scope", {})
    raw_boundary = str(
        claim_scope.get("claim_limit") or claim_contract.get("claim_id") or ""
    ).strip()
    if not raw_boundary:
        return "Pending"
    if "sota" in raw_boundary.lower():
        return PUBLIC_CLAIM_BOUNDARY
    return raw_boundary


def public_claim_scope(claim_scope: Mapping[str, Any]) -> Dict[str, Any]:
    public_scope = dict(claim_scope)
    claim_limit = str(public_scope.get("claim_limit", "")).strip()
    if "sota" in claim_limit.lower():
        public_scope["claim_limit"] = PUBLIC_CLAIM_BOUNDARY
    if "official_mode" in public_scope:
        public_scope["official_mode"] = display_mode(public_scope["official_mode"])
    return public_scope


def evidence_paths(root: Path) -> Dict[str, Path]:
    evidence = root / "evidence"
    defense = evidence / "downside_performance_v1_defense_packet"
    performance = evidence / "downside_performance_v1_evidence"
    repo_real_market = REPO_ROOT / "dist" / "real_market_data_v1_evidence"
    if root.resolve() != DEFAULT_EVIDENCE_ROOT.resolve():
        repo_real_market = root / "real_market_data_v1_evidence"
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
        "real_market_evidence": repo_real_market,
        "real_market_manifest": repo_real_market / "REAL_MARKET_EVIDENCE_MANIFEST.json",
        "real_market_gate": repo_real_market / "real_market_gate.json",
        "real_market_data_manifest": repo_real_market / "real_market_data_manifest.json",
        "real_market_metrics": repo_real_market / "metrics.json",
        "real_market_baseline": repo_real_market / "baseline_comparison.json",
        "real_market_cost_stress": repo_real_market / "cost_slippage_stress_report.json",
        "real_market_walk_forward": repo_real_market / "walk_forward_report.json",
        "real_market_bootstrap": repo_real_market / "bootstrap_confidence_report.json",
        "real_market_strategy_freeze": repo_real_market / "strategy_freeze_report.json",
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
    real_market_manifest = load_json(paths["real_market_manifest"])
    real_market_gate = load_json(paths["real_market_gate"])
    real_market_data_manifest = load_json(paths["real_market_data_manifest"])
    real_market_metrics = load_json(paths["real_market_metrics"])
    real_market_baseline = load_json(paths["real_market_baseline"])
    real_market_cost_stress = load_json(paths["real_market_cost_stress"])
    real_market_walk_forward = load_json(paths["real_market_walk_forward"])
    real_market_bootstrap = load_json(paths["real_market_bootstrap"])
    real_market_strategy_freeze = load_json(paths["real_market_strategy_freeze"])

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
        "real_market": {
            "manifest": real_market_manifest,
            "gate": real_market_gate,
            "data_manifest": real_market_data_manifest,
            "metrics": real_market_metrics,
            "baseline": real_market_baseline,
            "cost_stress": real_market_cost_stress,
            "walk_forward": real_market_walk_forward,
            "bootstrap": real_market_bootstrap,
            "strategy_freeze": real_market_strategy_freeze,
        },
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
            "real_market_evidence": bool_status(real_market_gate.get("real_market_claim_ready")),
        },
    }


def presentation_summary(evidence: Mapping[str, Any]) -> Dict[str, str]:
    real_market = evidence.get("real_market", {})
    gate = real_market.get("gate", {})
    data_manifest = real_market.get("data_manifest", {})
    metrics = real_market.get("metrics", {})
    candidate = metrics.get("agentic_candidate_v1", {})
    claim_scope = gate.get("claim_scope", {})
    tickers = data_manifest.get("tickers") or ["SPY", "QQQ", "TLT", "GLD", "IEF"]
    start = data_manifest.get("start", "2016-01-01")
    end = data_manifest.get("end", "2025-12-31")
    total_return = candidate.get("total_return")
    drawdown = candidate.get("max_drawdown")
    if isinstance(total_return, (int, float)) and total_return < 0:
        candidate_result = "WEAK, PRESERVED"
    elif isinstance(total_return, (int, float)):
        candidate_result = "POSITIVE, PRESERVED"
    else:
        candidate_result = "PENDING"
    return {
        "presentation_release": "v0.3.1-presentation-ui",
        "headline": "Evidence OS verifies, scopes, and seals financial AI claims on deterministic and sealed ETF evidence.",
        "real_market_status": bool_status(gate.get("real_market_claim_ready")),
        "official_mode": display_mode(claim_scope.get("official_mode", "sealed_csv_no_network")),
        "ticker_coverage": ", ".join(str(ticker) for ticker in tickers),
        "benchmark_period": f"{start} to {end}",
        "data_distribution": str(
            data_manifest.get("distribution_policy")
            or claim_scope.get(
                "distribution_policy",
                "public manifest/sample only; full CSV local/private",
            )
        ),
        "candidate_result": candidate_result,
        "candidate_total_return": percent(total_return),
        "candidate_max_drawdown": percent(drawdown),
        "non_claims": "No live trading readiness, future-return prediction, return guarantee, or market dominance claim.",
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
        "real_market_manifest",
        "real_market_gate",
        "real_market_data_manifest",
    ]
    rows = []
    for key in keys:
        path = paths[key]
        rows.append({"artifact": key, "status": file_status(path), "path": str(path)})
    return rows


def evidence_packet_map(evidence: Mapping[str, Any]) -> List[Dict[str, str]]:
    paths = evidence["paths"]
    groups = [
        (
            "Release gate",
            "release_seal",
            "Can this evidence packet be treated as sealed and publishable?",
        ),
        (
            "Claim contract",
            "claim_contract",
            "What exact benchmark claim is allowed, and what is excluded?",
        ),
        (
            "Defense gate",
            "defense_gate",
            "Did strategy freeze, data lineage, and defense checks pass?",
        ),
        (
            "Strategy freeze",
            "strategy_freeze",
            "Was the candidate fixed before the final evaluation?",
        ),
        (
            "Performance evidence",
            "metrics",
            "Which preserved metrics support or weaken the scoped claim?",
        ),
        (
            "Real-market evidence",
            "real_market_gate",
            "Is the sealed ETF evidence packet present and claim-ready?",
        ),
        (
            "Forward protocol",
            "forward_protocol_md",
            "What forward paper-trading boundary was initialized?",
        ),
        (
            "Public snapshot",
            "public_snapshot",
            "Which sanitized artifacts can be reviewed without full local data?",
        ),
        (
            "Official packet",
            "official_packet",
            "Which release bundle is the reviewer-facing evidence package?",
        ),
    ]
    rows = []
    for group, key, question in groups:
        rows.append(
            {
                "group": group,
                "artifact": key,
                "status": file_status(paths[key]),
                "reviewer_question": question,
            }
        )
    return rows


def release_comparison_rows(evidence: Mapping[str, Any]) -> List[Dict[str, str]]:
    paths = evidence["paths"]
    release_seal = evidence.get("release_seal", {})
    public_manifest = _load_manifest(paths["public_snapshot"], "PUBLIC_SNAPSHOT_MANIFEST.json")
    official_manifest = _load_manifest(paths["official_packet"], "OFFICIAL_CLAIM_PACKET_MANIFEST.json")
    candidate_manifest = _load_manifest(paths["release_candidate"], "RELEASE_CANDIDATE_MANIFEST.json")
    real_market_manifest = evidence.get("real_market", {}).get("manifest", {})
    return [
        {
            "release_layer": "Sealed release",
            "artifact": "RELEASE_SEAL_MANIFEST.json",
            "visibility": "Private/local evidence index",
            "artifact_status": file_status(paths["release_seal"]),
            "manifest_status": _manifest_status(release_seal),
            "file_count": str(release_seal.get("file_count", "Pending")),
            "reviewer_use": "Confirms the release packet was sealed and all copied sources were recorded.",
            "boundary": "Sanitized claim wording is shown in the dashboard before public review.",
        },
        {
            "release_layer": "Public snapshot",
            "artifact": "downside_performance_v1_public_snapshot",
            "visibility": "Public-safe evidence subset",
            "artifact_status": file_status(paths["public_snapshot"]),
            "manifest_status": _manifest_status(public_manifest),
            "file_count": str(public_manifest.get("file_count", "Pending")),
            "reviewer_use": "Lets a reviewer inspect metrics, visual artifacts, paper text, and defense summaries without full local data.",
            "boundary": "Public subset only; full raw workspace and private local CSV paths are not required for review.",
        },
        {
            "release_layer": "Official packet",
            "artifact": "stock_harness_official_claim_packet",
            "visibility": "Reviewer-facing verification packet",
            "artifact_status": file_status(paths["official_packet"]),
            "manifest_status": _manifest_status(official_manifest),
            "file_count": str(official_manifest.get("file_count", "Pending")),
            "reviewer_use": "Shows official claim gate, release gate, replay evidence, and claim contract.",
            "boundary": safe_claim_boundary_text(
                {"claim_contract": {}, "defense_gate": {"claim_scope": official_manifest.get("claim_scope", {})}}
            ),
        },
        {
            "release_layer": "Release candidate",
            "artifact": "stock_harness_release_candidate",
            "visibility": "Build/replay candidate bundle",
            "artifact_status": file_status(paths["release_candidate"]),
            "manifest_status": _manifest_status(candidate_manifest),
            "file_count": str(candidate_manifest.get("component_count", "Pending")),
            "reviewer_use": "Checks that release and evidence zip components exist before official publication.",
            "boundary": safe_claim_boundary_text(
                {"claim_contract": {}, "defense_gate": {"claim_scope": candidate_manifest.get("claim_scope", {})}}
            ),
        },
        {
            "release_layer": "Real-market evidence",
            "artifact": "real_market_data_v1_evidence",
            "visibility": "Sealed ETF evidence; public manifest/sample only",
            "artifact_status": file_status(paths["real_market_evidence"]),
            "manifest_status": _manifest_status(real_market_manifest),
            "file_count": str(real_market_manifest.get("file_count", "Pending")),
            "reviewer_use": "Separates sealed real ETF evidence readiness from any live-trading claim.",
            "boundary": presentation_summary(evidence)["non_claims"],
        },
    ]


def tamper_walkthrough_rows(evidence: Mapping[str, Any]) -> List[Dict[str, str]]:
    paths = evidence["paths"]
    defense_checks = evidence.get("defense_gate", {}).get("checks", {})
    seal_checks = evidence.get("release_seal", {}).get("checks", {})
    real_market_gate = evidence.get("real_market", {}).get("gate", {})
    safe_boundary = safe_claim_boundary_text(evidence)
    return [
        {
            "tamper_case": "Release seal missing",
            "gate_or_check": "release_seal",
            "current_status": file_status(paths["release_seal"]),
            "expected_failure": "Reviewer cannot treat the packet as sealed or complete.",
        },
        {
            "tamper_case": "Strategy changed after freeze",
            "gate_or_check": "strategy_freeze_verified",
            "current_status": bool_status(defense_checks.get("strategy_freeze_verified")),
            "expected_failure": "Claim should move to pending until freeze evidence is regenerated.",
        },
        {
            "tamper_case": "Public snapshot missing",
            "gate_or_check": "public_snapshot",
            "current_status": file_status(paths["public_snapshot"]),
            "expected_failure": "Public review loses the sanitized evidence bundle.",
        },
        {
            "tamper_case": "Claim wording expands beyond boundary",
            "gate_or_check": "safe_claim_boundary_text",
            "current_status": "PASS" if "SOTA" not in safe_boundary else "FAIL",
            "expected_failure": "Dashboard replaces unsupported public wording with the scoped benchmark boundary.",
        },
        {
            "tamper_case": "Forward/live readiness implied",
            "gate_or_check": "no_live_claims_preserved",
            "current_status": bool_status(seal_checks.get("no_live_claims_preserved")),
            "expected_failure": "Public claim is blocked if live trading or future-return language appears.",
        },
        {
            "tamper_case": "Real-market packet not ready",
            "gate_or_check": "real_market_claim_ready",
            "current_status": bool_status(real_market_gate.get("real_market_claim_ready")),
            "expected_failure": "Real-market evidence remains pending and cannot be used as a claim.",
        },
    ]


def _load_manifest(root: Path, filename: str) -> Dict[str, Any]:
    return load_json(root / filename)


def _manifest_status(manifest: Mapping[str, Any]) -> str:
    return str(manifest.get("status") or ("passed" if manifest.get("checks") else "Pending")).upper()


def reproduction_command_rows() -> List[Dict[str, str]]:
    return [
        {
            "purpose": "Dashboard tests",
            "command": "python -m unittest -v tests.test_dashboard_app",
            "boundary": "Verifies the read-only viewer and missing-evidence behavior.",
        },
        {
            "purpose": "Core unit tests",
            "command": "python -m unittest discover -s tests",
            "boundary": "Runs the existing harness tests without changing sealed evidence.",
        },
        {
            "purpose": "Open viewer",
            "command": "streamlit run dashboard/app.py",
            "boundary": "Reads the sealed packet; does not run backtests or place orders.",
        },
    ]


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


def reviewer_checklist(evidence: Mapping[str, Any]) -> List[Dict[str, str]]:
    paths = evidence["paths"]
    claim_contract = evidence.get("claim_contract", {})
    defense_gate = evidence.get("defense_gate", {})
    claim_scope = defense_gate.get("claim_scope", {})
    non_claims = claim_scope.get("non_claims") or claim_contract.get("non_claims") or []
    status = evidence.get("status", {})
    return [
        {
            "check": "Read-only viewer",
            "status": "PASS",
            "evidence": "Dashboard loads sealed artifacts and does not run backtests or rewrite files.",
        },
        {
            "check": "Claim boundary present",
            "status": "PASS" if claim_scope or claim_contract else "PENDING",
            "evidence": safe_claim_boundary_text(evidence),
        },
        {
            "check": "Non-claims present",
            "status": "PASS" if non_claims else "PENDING",
            "evidence": "; ".join(str(item) for item in non_claims[:3]) if non_claims else "Pending",
        },
        {
            "check": "Strategy freeze",
            "status": status.get("strategy_freeze", "PENDING"),
            "evidence": str(evidence.get("strategy_freeze", {}).get("freeze_statement", "Pending")),
        },
        {
            "check": "Data integrity",
            "status": status.get("data_integrity", "PENDING"),
            "evidence": "Data lineage and bias defense report loaded.",
        },
        {
            "check": "Release artifacts",
            "status": "PASS" if paths["official_packet"].exists() and paths["release_candidate"].exists() else "PENDING",
            "evidence": "Official packet and release candidate are present." if paths["official_packet"].exists() and paths["release_candidate"].exists() else "Pending sealed artifacts.",
        },
        {
            "check": "Financial boundary",
            "status": "PASS",
            "evidence": "No financial advice, no live trading readiness, no future-return promise.",
        },
    ]


def _render_status_cards(st: Any, status: Mapping[str, str]) -> None:
    cols = st.columns(3)
    items = list(status.items())
    for index, (label, value) in enumerate(items):
        cols[index % 3].metric(label.replace("_", " ").title(), value)


def _render_presentation_overview(st: Any, evidence: Mapping[str, Any]) -> None:
    summary = presentation_summary(evidence)
    st.subheader("Executive Summary")
    st.write(summary["headline"])
    cols = st.columns(4)
    cols[0].metric("Claim Status", evidence["status"].get("claim_status", "PENDING"))
    cols[1].metric("Real Market Evidence", summary["real_market_status"])
    cols[2].metric("Data Mode", summary["official_mode"])
    cols[3].metric("Candidate Result", summary["candidate_result"])
    st.table(
        [
            {"item": "ETF coverage", "value": summary["ticker_coverage"]},
            {"item": "Benchmark period", "value": summary["benchmark_period"]},
            {"item": "Data distribution", "value": summary["data_distribution"]},
            {"item": "Candidate total return", "value": summary["candidate_total_return"]},
            {"item": "Candidate max drawdown", "value": summary["candidate_max_drawdown"]},
            {"item": "Boundary", "value": summary["non_claims"]},
        ]
    )
    st.info(
        "v0.3 proves the evidence pipeline works on sealed real ETF data. "
        "v0.3.1 improves presentation only; it does not expand the claim."
    )


def _render_claim_registry(st: Any, evidence: Mapping[str, Any]) -> None:
    defense_gate = evidence["defense_gate"]
    claim_scope = defense_gate.get("claim_scope", {})
    public_scope = public_claim_scope(claim_scope)
    st.subheader("Allowed Claim")
    st.write(public_scope.get("claim_limit", "Pending"))
    st.subheader("Claim Scope")
    st.json(public_scope)
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
    st.info(
        "These metrics are preserved evidence records. They are not investment advice, "
        "live trading readiness, or a future-return claim."
    )
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
    st.subheader("Evidence Packet Map")
    st.write(
        "Reviewer navigation for the sealed packet. These rows explain what to inspect; "
        "they do not regenerate results."
    )
    for row in evidence_packet_map(evidence):
        st.markdown(
            f"**{row['group']}** - `{row['artifact']}` - **{row['status']}**  \n"
            f"{row['reviewer_question']}"
        )
    st.subheader("Read-Only Reproduction Commands")
    for row in reproduction_command_rows():
        st.markdown(f"**{row['purpose']}**")
        st.code(row["command"])
        st.caption(row["boundary"])
    st.subheader("Sealed Artifacts")
    st.table(artifact_rows(evidence["paths"]))


def _render_reviewer_checklist(st: Any, evidence: Mapping[str, Any]) -> None:
    st.subheader("Reviewer Checklist")
    st.write(
        "This tab answers whether the claim is scoped, evidenced, frozen, and reviewable. "
        "It intentionally does not recommend trades or regenerate results."
    )
    st.table(reviewer_checklist(evidence))


def _render_real_market(st: Any, evidence: Mapping[str, Any]) -> None:
    real_market = evidence["real_market"]
    gate = real_market["gate"]
    data_manifest = real_market["data_manifest"]
    checks = gate.get("checks", {})
    claim_scope = public_claim_scope(gate.get("claim_scope", {}))
    st.subheader("v0.3 Real Market Evidence")
    st.write(
        claim_scope.get(
            "claim_limit",
            "Pending real-market evidence. Missing evidence is expected before v0.3 artifacts are generated.",
        )
    )
    st.json(
        {
            "status": bool_status(gate.get("real_market_claim_ready")),
            "official_mode": claim_scope.get("official_mode", "Pending"),
            "provider": data_manifest.get("provider", "Pending"),
            "period": {
                "start": data_manifest.get("start", "Pending"),
                "end": data_manifest.get("end", "Pending"),
            },
            "tickers": data_manifest.get("tickers", []),
            "common_date_count": data_manifest.get("common_date_count", "Pending"),
            "sealed_data_fingerprint": data_manifest.get("fingerprint", "Pending"),
        }
    )
    st.subheader("Gate Checks")
    st.json(checks if checks else {"status": "PENDING"})
    st.subheader("Robustness Evidence")
    st.json(
        {
            "cost_slippage_stress": real_market["cost_stress"].get("schema", "PENDING"),
            "cost_slippage_passed": real_market["cost_stress"].get("passed", "PENDING"),
            "walk_forward": real_market["walk_forward"].get("schema", "PENDING"),
            "walk_forward_passed": real_market["walk_forward"].get("passed", "PENDING"),
            "bootstrap": real_market["bootstrap"].get("schema", "PENDING"),
            "strategy_freeze": real_market["strategy_freeze"].get("schema", "PENDING"),
        }
    )
    st.subheader("Non-Claims")
    non_claims = gate.get("claim_scope", {}).get("non_claims", [])
    if non_claims:
        for item in non_claims:
            st.write(f"- {item}")
    else:
        st.write("Pending")


def _render_release_comparison(st: Any, evidence: Mapping[str, Any]) -> None:
    st.subheader("Release Comparison")
    st.write(
        "This tab compares the sealed release, public snapshot, official packet, "
        "release candidate, and real-market evidence layer. It is read-only and "
        "does not rerun benchmarks."
    )
    st.table(release_comparison_rows(evidence))
    st.subheader("Tamper Walkthrough")
    st.write(
        "These rows show the expected failure mode when an evidence boundary is "
        "missing, stale, or expanded beyond its allowed claim."
    )
    st.table(tamper_walkthrough_rows(evidence))
    st.info(
        "The dashboard should make failures visible. PASS means the preserved "
        "artifact or boundary is currently present; it does not mean investment "
        "readiness."
    )


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
            "Backtest Evidence",
            "Overfitting Audit",
            "Real Market Evidence",
            "Release Comparison",
            "Reviewer Checklist",
            "Evidence Packet Export",
        ]
    )

    with tabs[0]:
        _render_presentation_overview(st, evidence)
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
        _render_real_market(st, evidence)
    with tabs[6]:
        _render_release_comparison(st, evidence)
    with tabs[7]:
        _render_reviewer_checklist(st, evidence)
    with tabs[8]:
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
