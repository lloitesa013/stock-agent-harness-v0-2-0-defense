from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .stock_harness import (
    BacktestConfig,
    Bar,
    HarnessVerdict,
    MovingAverageCashStrategy,
    audit_no_lookahead,
    load_ohlcv_csv,
    run_backtest,
    run_cost_stress,
    run_data_quality_gate,
    run_ma_parameter_sweep,
    run_regime_stress,
    run_stress_matrix,
    run_walk_forward,
)


AGENTIC_REPORT_SCHEMA = "stock_agent_harness_report_v1"
AGENTIC_MANIFEST_SCHEMA = "stock_agent_harness_manifest_v1"
AGENTIC_CLAIM_ID = "agentic_downside_verification_workflow_v0_1"
AGENTIC_BENCHMARK_SUITE = "agentic_verification_v1"
AGENTIC_CLAIM_LIMIT = "SOTA-inspired deterministic multi-agent verification workflow coverage only"
AGENTIC_POSITIVE_CLAIM = (
    "Stock Agent Harness provides SOTA-inspired deterministic multi-agent verification "
    "workflow coverage for downside-aware stock backtest research, integrated with "
    "Stock Harness verification gates."
)
AGENTIC_NON_CLAIMS = [
    "No financial advice.",
    "No live trading readiness claim.",
    "No alpha-generation, investment-performance, or profitability claim.",
    "No broker integration, order routing, or execution-readiness claim.",
    "No universal LLM trading dominance claim.",
    "No claim outside the included agentic_verification_v1 deterministic workflow.",
]

AGENT_ROLES = [
    "DataSentinel",
    "ResearchAnalyst",
    "StrategySynthesizer",
    "RiskSkeptic",
    "ExecutionAuditor",
    "VerificationChair",
]


@dataclass
class AgentHarnessConfig:
    provider: str = "deterministic"
    max_rounds: int = 2
    consensus_threshold: float = 0.70
    max_allowed_drawdown: float = 0.20
    include_global_comparison: bool = False
    benchmark_suite: str = AGENTIC_BENCHMARK_SUITE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "max_rounds": self.max_rounds,
            "consensus_threshold": self.consensus_threshold,
            "max_allowed_drawdown": self.max_allowed_drawdown,
            "include_global_comparison": self.include_global_comparison,
            "benchmark_suite": self.benchmark_suite,
        }


@dataclass
class AgentEvidenceItem:
    source: str
    kind: str
    summary: str
    confidence: float = 1.0
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind,
            "summary": self.summary,
            "confidence": self.confidence,
            "risk_flags": list(self.risk_flags),
        }


@dataclass
class AgentDecision:
    role: str
    verdict: str
    confidence: float
    rationale: str
    evidence_refs: List[str] = field(default_factory=list)
    proposed_actions: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "proposed_actions": list(self.proposed_actions),
            "risk_flags": list(self.risk_flags),
        }


@dataclass
class AgentHarnessReport:
    schema: str
    claim: Dict[str, Any]
    config: Dict[str, Any]
    roles: List[str]
    evidence: List[AgentEvidenceItem]
    transcript: List[AgentDecision]
    stock_harness_results: Dict[str, Any]
    final_verdict: Dict[str, Any]
    manifest: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "claim": dict(self.claim),
            "config": dict(self.config),
            "roles": list(self.roles),
            "evidence": [item.to_dict() for item in self.evidence],
            "transcript": [decision.to_dict() for decision in self.transcript],
            "agent_decisions": {
                decision.role: decision.to_dict() for decision in self.transcript
            },
            "stock_harness_results": _to_jsonable(self.stock_harness_results),
            "final_verdict": dict(self.final_verdict),
            "manifest": dict(self.manifest),
        }


class AgentHarnessProvider:
    name = "base"

    def decide(self, role: str, context: Mapping[str, Any]) -> AgentDecision:
        raise NotImplementedError


class DeterministicAgentProvider(AgentHarnessProvider):
    name = "deterministic"

    def decide(self, role: str, context: Mapping[str, Any]) -> AgentDecision:
        results = context["stock_harness_results"]
        evidence = context["evidence_by_key"]
        final_preview = context.get("final_preview", {})

        if role == "DataSentinel":
            data_quality = _verdict(results.get("data_quality"))
            if data_quality != "KEEP":
                return AgentDecision(
                    role=role,
                    verdict="REJECT",
                    confidence=0.99,
                    rationale="Hard data-quality gate failed before strategy review.",
                    evidence_refs=[evidence["data_quality"]],
                    risk_flags=["data_quality_failure"],
                )
            return AgentDecision(
                role=role,
                verdict="KEEP",
                confidence=0.96,
                rationale="OHLCV structure passed the deterministic data-quality gate.",
                evidence_refs=[evidence["data_quality"]],
            )

        if role == "ResearchAnalyst":
            return AgentDecision(
                role=role,
                verdict="KEEP",
                confidence=0.88,
                rationale=(
                    "SOTA intake patterns are used as verification design constraints, "
                    "not as profitability evidence."
                ),
                evidence_refs=[evidence["research_intake"]],
                proposed_actions=[
                    "Preserve scoped claim language.",
                    "Keep external frameworks as design references unless directly benchmarked.",
                ],
            )

        if role == "StrategySynthesizer":
            backtest_verdict = _verdict(results.get("backtest"))
            if backtest_verdict == "REJECT":
                return AgentDecision(
                    role=role,
                    verdict="ITERATE",
                    confidence=0.84,
                    rationale="Candidate strategy was generated, but Stock Harness rejected the run.",
                    evidence_refs=[evidence["backtest"]],
                    proposed_actions=["Revise strategy hypothesis before promotion."],
                    risk_flags=["candidate_backtest_rejected"],
                )
            return AgentDecision(
                role=role,
                verdict="KEEP",
                confidence=0.86,
                rationale=(
                    "Candidate is a deterministic moving-average cash-filter research hypothesis; "
                    "no alpha or profitability claim is made."
                ),
                evidence_refs=[evidence["backtest"]],
            )

        if role == "RiskSkeptic":
            failing_refs = _failing_downside_refs(results, evidence)
            if not bool(_field(results.get("lookahead_audit"), "passed", False)):
                return AgentDecision(
                    role=role,
                    verdict="REJECT",
                    confidence=0.99,
                    rationale="Lookahead mutation audit failed; future leakage is a hard veto.",
                    evidence_refs=[evidence["lookahead_audit"]],
                    risk_flags=["lookahead_failure"],
                )
            if failing_refs:
                return AgentDecision(
                    role=role,
                    verdict="ITERATE",
                    confidence=0.91,
                    rationale="One or more downside, walk-forward, or stress gates require iteration.",
                    evidence_refs=failing_refs,
                    proposed_actions=["Tighten downside rules and rerun deterministic verification."],
                    risk_flags=["risk_gate_objection"],
                )
            return AgentDecision(
                role=role,
                verdict="KEEP",
                confidence=0.93,
                rationale="Downside, walk-forward, regime, and cost stress objections are resolved.",
                evidence_refs=[
                    evidence["backtest"],
                    evidence["walk_forward"],
                    evidence["regime_stress"],
                    evidence["cost_stress"],
                ],
            )

        if role == "ExecutionAuditor":
            execution_refs = _failing_execution_refs(results, evidence)
            if execution_refs:
                return AgentDecision(
                    role=role,
                    verdict="ITERATE",
                    confidence=0.90,
                    rationale="Execution realism checks require iteration.",
                    evidence_refs=execution_refs,
                    risk_flags=["execution_realism_objection"],
                )
            return AgentDecision(
                role=role,
                verdict="KEEP",
                confidence=0.92,
                rationale="Cost, delay, liquidity, and stress-matrix checks are preserved.",
                evidence_refs=[evidence["cost_stress"], evidence["stress_matrix"]],
            )

        if role == "VerificationChair":
            return AgentDecision(
                role=role,
                verdict=str(final_preview.get("verdict", "ITERATE")),
                confidence=float(final_preview.get("confidence", 0.80)),
                rationale="Final verdict follows hard gates, risk objections, and scoped non-claims.",
                evidence_refs=list(evidence.values()),
                proposed_actions=list(final_preview.get("next_actions", [])),
                risk_flags=list(final_preview.get("risk_flags", [])),
            )

        return AgentDecision(
            role=role,
            verdict="ITERATE",
            confidence=0.0,
            rationale="Unknown role.",
            risk_flags=["unknown_role"],
        )


class LLMAgentProvider(AgentHarnessProvider):
    name = "llm"

    def __init__(self, api_key_env: str = "OPENAI_API_KEY") -> None:
        self.api_key_env = api_key_env

    def decide(self, role: str, context: Mapping[str, Any]) -> AgentDecision:
        if not os.environ.get(self.api_key_env):
            raise RuntimeError(
                "LLMAgentProvider requires an API key and is excluded from official deterministic gates."
            )
        raise RuntimeError(
            "LLMAgentProvider is an optional extension point; official agentic_verification_v1 "
            "uses DeterministicAgentProvider only."
        )


def default_agent_harness_bars() -> List[Bar]:
    prices = [100, 105, 110, 115, 120, 119, 118, 117, 116, 115, 100, 90, 80] * 2
    bars: List[Bar] = []
    for index, close in enumerate(prices, start=1):
        bars.append(
            Bar(
                date="2020-01-%02d" % index,
                open=float(close),
                high=float(close) * 1.01,
                low=float(close) * 0.99,
                close=float(close),
                volume=1000.0 + index,
            )
        )
    return bars


def run_stock_agent_harness(
    bars: Optional[Sequence[Bar]] = None,
    strategy_factory: Optional[Callable[[], Any]] = None,
    config: Optional[AgentHarnessConfig] = None,
    provider: Optional[AgentHarnessProvider] = None,
) -> AgentHarnessReport:
    cfg = config or AgentHarnessConfig()
    selected_bars = list(bars) if bars is not None else default_agent_harness_bars()
    strategy_factory = strategy_factory or (lambda: MovingAverageCashStrategy(window=3))
    selected_provider = provider or _provider_from_config(cfg)

    stock_results = _run_stock_verification(selected_bars, strategy_factory, cfg)
    evidence, evidence_by_key = _build_evidence(stock_results, cfg)
    final_preview = _determine_final_verdict(stock_results)
    context: Dict[str, Any] = {
        "config": cfg.to_dict(),
        "evidence": evidence,
        "evidence_by_key": evidence_by_key,
        "stock_harness_results": stock_results,
        "final_preview": final_preview,
    }

    transcript: List[AgentDecision] = []
    for role in AGENT_ROLES:
        transcript.append(selected_provider.decide(role, context))

    final_verdict = _chair_limited_final_verdict(final_preview, transcript, cfg)
    report_payload_without_manifest = {
        "schema": AGENTIC_REPORT_SCHEMA,
        "claim": _claim_scope(),
        "config": cfg.to_dict(),
        "roles": list(AGENT_ROLES),
        "evidence": [item.to_dict() for item in evidence],
        "transcript": [decision.to_dict() for decision in transcript],
        "stock_harness_results": stock_results,
        "final_verdict": final_verdict,
    }
    fingerprint = _fingerprint(report_payload_without_manifest)
    manifest = {
        "schema": AGENTIC_MANIFEST_SCHEMA,
        "fingerprint": fingerprint,
        "artifact_keys": sorted(stock_results.keys()),
        "role_count": len(AGENT_ROLES),
        "provider": cfg.provider,
        "benchmark_suite": cfg.benchmark_suite,
    }
    return AgentHarnessReport(
        schema=AGENTIC_REPORT_SCHEMA,
        claim=_claim_scope(),
        config=cfg.to_dict(),
        roles=list(AGENT_ROLES),
        evidence=evidence,
        transcript=transcript,
        stock_harness_results=stock_results,
        final_verdict=final_verdict,
        manifest=manifest,
    )


def load_agent_harness_bars_csv(path: Path) -> List[Bar]:
    return list(load_ohlcv_csv(path))


def write_agent_harness_report(report: AgentHarnessReport, output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "stock_agent_harness_report.json"
    markdown_path = output_dir / "stock_agent_harness_report.md"
    payload = report.to_dict()
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_agent_harness_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def render_agent_harness_markdown(report: AgentHarnessReport) -> str:
    payload = report.to_dict()
    lines = [
        "# Stock Agent Harness Report",
        "",
        "## Claim Scope",
        "",
        payload["claim"]["positive_claim"],
        "",
        "## Final Verdict",
        "",
        "- verdict: %s" % payload["final_verdict"]["verdict"],
        "- confidence: %.2f" % float(payload["final_verdict"]["confidence"]),
        "- fingerprint: %s" % payload["manifest"]["fingerprint"],
        "",
        "## Non-Claims",
        "",
    ]
    for non_claim in payload["claim"]["non_claims"]:
        lines.append("- " + non_claim)
    lines.extend(["", "## Agent Decisions", ""])
    for decision in payload["transcript"]:
        lines.append(
            "- %s: %s (confidence %.2f)"
            % (decision["role"], decision["verdict"], float(decision["confidence"]))
        )
    lines.extend(["", "## Stock Harness Artifacts", ""])
    for key in sorted(payload["stock_harness_results"].keys()):
        lines.append("- " + key)
    lines.append("")
    return "\n".join(lines)


def _provider_from_config(config: AgentHarnessConfig) -> AgentHarnessProvider:
    if config.provider == "deterministic":
        return DeterministicAgentProvider()
    if config.provider == "llm":
        return LLMAgentProvider()
    raise ValueError("unsupported agent harness provider: " + config.provider)


def _run_stock_verification(
    bars: Sequence[Bar],
    strategy_factory: Callable[[], Any],
    config: AgentHarnessConfig,
) -> Dict[str, Any]:
    backtest_config = BacktestConfig(max_allowed_drawdown=config.max_allowed_drawdown)
    data_quality = run_data_quality_gate(bars)
    strategy = strategy_factory()
    backtest = run_backtest(bars, strategy, backtest_config)
    lookahead = audit_no_lookahead(strategy_factory, bars)
    train_size, test_size, step_size = _walk_forward_sizes(len(bars))
    walk_forward = run_walk_forward(
        bars,
        strategy_factory,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
        config=backtest_config,
    )
    regime_stress = run_regime_stress(strategy_factory, config=backtest_config)
    parameter_sweep = run_ma_parameter_sweep(
        bars,
        [2, 3, 4],
        config=backtest_config,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
    )
    cost_stress = run_cost_stress(bars, strategy_factory, config=backtest_config)
    stress_matrix = run_stress_matrix(bars, strategy_factory, config=backtest_config)

    return {
        "data_quality": _to_jsonable(data_quality),
        "backtest": _to_jsonable(backtest),
        "lookahead_audit": _to_jsonable(lookahead),
        "walk_forward": _to_jsonable(walk_forward),
        "regime_stress": _to_jsonable(regime_stress),
        "parameter_sweep": _to_jsonable(parameter_sweep),
        "cost_stress": _to_jsonable(cost_stress),
        "stress_matrix": _to_jsonable(stress_matrix),
    }


def _walk_forward_sizes(bar_count: int) -> Tuple[int, int, int]:
    if bar_count >= 22:
        return 3, 8, 11
    if bar_count >= 9:
        return 3, 3, 3
    if bar_count >= 6:
        return 2, 2, 2
    return 2, 1, 1


def _build_evidence(
    stock_results: Mapping[str, Any],
    config: AgentHarnessConfig,
) -> Tuple[List[AgentEvidenceItem], Dict[str, str]]:
    items = [
        AgentEvidenceItem(
            source="stock_harness:data_quality",
            kind="data_quality_gate",
            summary="OHLCV structure, dates, volume, calendar, and adjustment checks.",
            risk_flags=[] if _verdict(stock_results.get("data_quality")) == "KEEP" else ["data_quality_failure"],
        ),
        AgentEvidenceItem(
            source="stock_harness:backtest",
            kind="downside_backtest",
            summary="MDD-first backtest verdict and benchmark comparison.",
            risk_flags=[] if _verdict(stock_results.get("backtest")) == "KEEP" else ["backtest_not_keep"],
        ),
        AgentEvidenceItem(
            source="stock_harness:lookahead_audit",
            kind="future_mutation_audit",
            summary="Signal invariance under future-bar mutation.",
            risk_flags=[]
            if bool(_field(stock_results.get("lookahead_audit"), "passed", False))
            else ["lookahead_failure"],
        ),
        AgentEvidenceItem(
            source="stock_harness:walk_forward",
            kind="walk_forward_downside_validation",
            summary="Out-of-sample fold verdicts tied to downside limits.",
            risk_flags=[] if _verdict(stock_results.get("walk_forward")) == "KEEP" else ["walk_forward_not_keep"],
        ),
        AgentEvidenceItem(
            source="stock_harness:regime_stress",
            kind="regime_stress_validation",
            summary="Synthetic steady-up, crash, whipsaw, and spike regime checks.",
            risk_flags=[] if _verdict(stock_results.get("regime_stress")) == "KEEP" else ["regime_stress_not_keep"],
        ),
        AgentEvidenceItem(
            source="stock_harness:cost_stress",
            kind="cost_slippage_validation",
            summary="Fee and slippage sensitivity checks.",
            risk_flags=[] if _verdict(stock_results.get("cost_stress")) == "KEEP" else ["cost_stress_not_keep"],
        ),
        AgentEvidenceItem(
            source="stock_harness:stress_matrix",
            kind="execution_stress_validation",
            summary="Delay, gap, liquidity, market-impact, and cash-yield stress matrix.",
            risk_flags=[] if _verdict(stock_results.get("stress_matrix")) == "KEEP" else ["stress_matrix_not_keep"],
        ),
        AgentEvidenceItem(
            source="sota_landscape:design_patterns",
            kind="research_intake",
            summary=(
                "Uses TradingAgents-style debate, FinRobot-style sequence, Riskfolio-style "
                "risk focus, Qlib-style research abstraction, and Nautilus/LEAN/vectorbt-style "
                "execution/reference mindset without claiming external framework dominance."
            ),
            confidence=0.86,
            risk_flags=["external_patterns_not_vendor_imports"]
            if not config.include_global_comparison
            else [],
        ),
    ]
    by_key = {
        "data_quality": items[0].source,
        "backtest": items[1].source,
        "lookahead_audit": items[2].source,
        "walk_forward": items[3].source,
        "regime_stress": items[4].source,
        "cost_stress": items[5].source,
        "stress_matrix": items[6].source,
        "research_intake": items[7].source,
    }
    return items, by_key


def _determine_final_verdict(stock_results: Mapping[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    risk_flags: List[str] = []
    next_actions: List[str] = []

    if _verdict(stock_results.get("data_quality")) != "KEEP":
        reasons.append("data_quality_gate_failed")
        risk_flags.append("data_quality_failure")
        next_actions.append("Repair OHLCV input before agent debate.")
        return _final("REJECT", 0.99, reasons, risk_flags, next_actions)

    if not bool(_field(stock_results.get("lookahead_audit"), "passed", False)):
        reasons.append("lookahead_audit_failed")
        risk_flags.append("lookahead_failure")
        next_actions.append("Remove future leakage before rerunning verification.")
        return _final("REJECT", 0.99, reasons, risk_flags, next_actions)

    gate_names = [
        "backtest",
        "walk_forward",
        "regime_stress",
        "parameter_sweep",
        "cost_stress",
        "stress_matrix",
    ]
    soft_failures = [name for name in gate_names if _verdict(stock_results.get(name)) != "KEEP"]
    if soft_failures:
        reasons.append("verification_gates_require_iteration: " + ",".join(soft_failures))
        risk_flags.extend([name + "_not_keep" for name in soft_failures])
        next_actions.append("Iterate strategy hypothesis and rerun Stock Harness verification gates.")
        return _final("ITERATE", 0.90, reasons, risk_flags, next_actions)

    reasons.append("all_required_stock_harness_gates_keep")
    reasons.append("agentic_non_claims_preserved")
    return _final("KEEP", 0.94, reasons, risk_flags, next_actions)


def _chair_limited_final_verdict(
    final_preview: Mapping[str, Any],
    transcript: Sequence[AgentDecision],
    config: AgentHarnessConfig,
) -> Dict[str, Any]:
    non_chair = [decision for decision in transcript if decision.role != "VerificationChair"]
    if any(decision.verdict == "REJECT" for decision in non_chair):
        if str(final_preview.get("verdict")) == "REJECT":
            return dict(final_preview)
        return _final(
            "REJECT",
            0.97,
            ["agent_role_hard_reject"],
            ["agent_reject_veto"],
            ["Resolve rejecting agent objection before promotion."],
        )
    iterate_count = sum(1 for decision in non_chair if decision.verdict == "ITERATE")
    consensus = 0.0 if not non_chair else 1.0 - (iterate_count / float(len(non_chair)))
    if consensus < config.consensus_threshold and str(final_preview.get("verdict")) == "KEEP":
        return _final(
            "ITERATE",
            0.88,
            ["agent_consensus_below_threshold"],
            ["agent_consensus_failure"],
            ["Resolve outstanding agent objections and rerun."],
        )
    return dict(final_preview)


def _failing_downside_refs(results: Mapping[str, Any], evidence: Mapping[str, str]) -> List[str]:
    refs: List[str] = []
    for name in ["backtest", "walk_forward", "regime_stress", "parameter_sweep", "cost_stress"]:
        if _verdict(results.get(name)) != "KEEP":
            refs.append(evidence.get(name, name))
    return refs


def _failing_execution_refs(results: Mapping[str, Any], evidence: Mapping[str, str]) -> List[str]:
    refs: List[str] = []
    for name in ["cost_stress", "stress_matrix"]:
        if _verdict(results.get(name)) != "KEEP":
            refs.append(evidence.get(name, name))
    return refs


def _claim_scope() -> Dict[str, Any]:
    return {
        "id": AGENTIC_CLAIM_ID,
        "benchmark_suite": AGENTIC_BENCHMARK_SUITE,
        "claim_limit": AGENTIC_CLAIM_LIMIT,
        "positive_claim": AGENTIC_POSITIVE_CLAIM,
        "status": "supported_for_included_benchmark_suite",
        "non_claims": list(AGENTIC_NON_CLAIMS),
    }


def _final(
    verdict: str,
    confidence: float,
    reasons: Sequence[str],
    risk_flags: Sequence[str],
    next_actions: Sequence[str],
) -> Dict[str, Any]:
    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasons": list(reasons),
        "risk_flags": list(risk_flags),
        "next_actions": list(next_actions),
    }


def _verdict(value: Any) -> str:
    verdict_obj = _field(value, "verdict", None)
    if isinstance(verdict_obj, HarnessVerdict):
        return verdict_obj.verdict
    if isinstance(verdict_obj, Mapping):
        return str(verdict_obj.get("verdict", ""))
    if isinstance(verdict_obj, str):
        return verdict_obj
    return ""


def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _to_jsonable(value.to_dict())
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_to_jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
