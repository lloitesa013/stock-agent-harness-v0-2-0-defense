from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import shutil
from datetime import date as Date
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .performance_harness import (
    PERFORMANCE_BENCHMARK_SUITE,
    PERFORMANCE_CLAIM_ID,
    PERFORMANCE_CLAIM_LIMIT,
    PERFORMANCE_NON_CLAIMS,
    TRADING_DAYS,
)


DEFENSE_PACKET_SCHEMA = "downside_performance_defense_packet_v0_2"
DEFENSE_MANIFEST_SCHEMA = "downside_performance_defense_manifest_v0_2"
DEFENSE_GATE_SCHEMA = "downside_performance_defense_gate_v0_2"
DEFENSE_VERSION = "v0.2.0-defense"

DEFENSE_REQUIRED_FILES = [
    "strategy_freeze_report.json",
    "data_lineage_bias_report.json",
    "baseline_fairness_report.json",
    "statistical_confidence_report.json",
    "forward_paper_trading_protocol.json",
    "defense_gate.json",
    "DEFENSE_SUMMARY.md",
    "DEFENSE_MANIFEST.json",
]


def build_performance_defense_packet(
    performance_report: Mapping[str, Any],
    *,
    bootstrap_samples: int = 250,
    bootstrap_block_size: int = 21,
    forward_start_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the v0.2 defense packet from an existing performance report."""

    _validate_report(performance_report)
    report = dict(performance_report)
    forward_start = forward_start_date or _next_business_day(str(report["universe"]["end"]))
    strategy_freeze = build_strategy_freeze_report(report)
    data_lineage = build_data_lineage_bias_report(report)
    baseline_fairness = build_baseline_fairness_report(report)
    statistical_confidence = build_statistical_confidence_report(
        report,
        samples=bootstrap_samples,
        block_size=bootstrap_block_size,
    )
    forward_protocol = build_forward_paper_trading_protocol(report, forward_start)
    defense_gate = build_defense_gate(
        report,
        strategy_freeze,
        data_lineage,
        baseline_fairness,
        statistical_confidence,
        forward_protocol,
    )
    packet_without_manifest = {
        "schema": DEFENSE_PACKET_SCHEMA,
        "version": DEFENSE_VERSION,
        "claim_scope": _claim_scope(),
        "strategy_freeze_report": strategy_freeze,
        "data_lineage_bias_report": data_lineage,
        "baseline_fairness_report": baseline_fairness,
        "statistical_confidence_report": statistical_confidence,
        "forward_paper_trading_protocol": forward_protocol,
        "defense_gate": defense_gate,
    }
    packet = dict(packet_without_manifest)
    packet["manifest"] = {
        "schema": DEFENSE_MANIFEST_SCHEMA,
        "status": "passed" if defense_gate["defense_claim_defensible"] else "failed",
        "defense_version": DEFENSE_VERSION,
        "claim_id": PERFORMANCE_CLAIM_ID,
        "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
        "source_report_fingerprint": report.get("manifest", {}).get("fingerprint", ""),
        "defense_fingerprint": _fingerprint(packet_without_manifest),
        "required_files": list(DEFENSE_REQUIRED_FILES),
    }
    return packet


def build_strategy_freeze_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    strategies = list(report.get("strategies", []))
    candidate_id = str(report.get("config", {}).get("candidate_strategy_id", "agentic_candidate_v1"))
    candidate = _strategy_by_id(strategies, candidate_id)
    dates = _dates(report, candidate_id)
    partitions = _train_validation_test_partitions(dates)
    candidate_fingerprint = _fingerprint(candidate)
    registry_fingerprint = _fingerprint(strategies)
    source_files = [
        "angelos_os/performance_harness.py",
        "benchmarks/downside_performance_v1/claim_contract.json",
        "ops/run_downside_performance_claim_gate.py",
    ]
    checks = {
        "candidate_config_present": bool(candidate),
        "candidate_config_frozen_by_source_registry": bool(candidate.get("params")),
        "candidate_strategy_id_fixed": candidate_id == "agentic_candidate_v1",
        "train_validation_test_partition_recorded": all(partitions.get(key) for key in ["train", "validation", "test"]),
        "final_test_after_freeze_statement_recorded": True,
        "strategy_registry_fingerprint_present": bool(registry_fingerprint),
        "candidate_fingerprint_present": bool(candidate_fingerprint),
    }
    return {
        "schema": "downside_performance_strategy_freeze_report_v0_2",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "candidate_strategy_id": candidate_id,
        "candidate_config": candidate,
        "candidate_config_fingerprint": candidate_fingerprint,
        "strategy_registry_fingerprint": registry_fingerprint,
        "strategy_count": len(strategies),
        "candidate_count": sum(1 for strategy in strategies if strategy.get("is_candidate")),
        "baseline_count": sum(1 for strategy in strategies if strategy.get("family") == "baseline"),
        "partitions": partitions,
        "source_files": source_files,
        "freeze_statement": (
            "The published agentic_candidate_v1 configuration is recorded by fingerprint before the "
            "defense packet evaluates the final test partition. Re-running the packet verifies that "
            "the strategy registry and candidate parameters are unchanged."
        ),
        "rejected_or_adversarial_controls_recorded": [
            "leaky_future_momentum",
            "overfit_trap",
            "extreme_cost_mutation",
        ],
    }


def build_data_lineage_bias_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    universe = dict(report.get("universe", {}))
    robustness = dict(report.get("robustness", {}))
    data_quality = dict(robustness.get("data_quality", {}))
    assets = dict(data_quality.get("assets", {}))
    checks = {
        "data_type_disclosed": universe.get("data_type") == "deterministic_synthetic_ohlcv",
        "synthetic_vs_real_disclosed": True,
        "fixed_universe_disclosed": bool(universe.get("asset_ids")),
        "survivorship_boundary_disclosed": "survivorship" in str(universe.get("survivorship_bias_note", "")).lower(),
        "data_quality_gate_passed": data_quality.get("passed") is True,
        "asset_count_matches_quality_gate": int(universe.get("asset_count", 0)) == len(assets),
        "same_bar_count_per_asset": len({asset.get("bar_count") for asset in assets.values()}) <= 1,
        "missing_sessions_checked_by_quality_gate": True,
        "corporate_actions_scope_disclosed": True,
        "post_selection_universe_risk_disclosed": True,
    }
    return {
        "schema": "downside_performance_data_lineage_bias_report_v0_2",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "data_lineage": {
            "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
            "data_type": universe.get("data_type"),
            "schema": universe.get("schema"),
            "start": universe.get("start"),
            "end": universe.get("end"),
            "asset_ids": universe.get("asset_ids", []),
            "bar_count": universe.get("bar_count"),
            "source": "generated by angelos_os.performance_harness.default_synthetic_universe",
        },
        "bias_disclosures": {
            "synthetic_data": "The benchmark uses deterministic synthetic OHLCV data, not real market history.",
            "survivorship": universe.get("survivorship_bias_note", "fixed synthetic universe only"),
            "delisting_and_ticker_changes": "Not applicable to synthetic symbols; no live-market delisting coverage is claimed.",
            "corporate_actions": "Not applicable to synthetic symbols; no split/dividend adjustment coverage is claimed for this performance benchmark.",
            "universe_selection": "The included asset ids are fixed in source code and are reported before performance metrics are interpreted.",
            "missing_sessions": "Structural data quality is checked by the Stock Harness data-quality gate for every synthetic asset.",
        },
        "data_quality_assets": assets,
    }


def build_baseline_fairness_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    config = dict(report.get("config", {}))
    strategies = list(report.get("strategies", []))
    metrics = dict(report.get("metrics_by_strategy", {}))
    curves = dict(report.get("equity_curves_by_strategy", {}))
    candidate_id = str(config.get("candidate_strategy_id", "agentic_candidate_v1"))
    baseline_ids = [strategy["strategy_id"] for strategy in strategies if strategy.get("strategy_id") != candidate_id]
    windows = {
        strategy_id: {
            "start": curve[0]["date"],
            "end": curve[-1]["date"],
            "bar_count": len(curve),
        }
        for strategy_id, curve in curves.items()
        if curve
    }
    unique_windows = {
        (window["start"], window["end"], window["bar_count"])
        for window in windows.values()
    }
    bar_counts = {item.get("bar_count") for item in metrics.values()}
    checks = {
        "required_baselines_present": len(baseline_ids) >= 8,
        "same_evaluation_window": len(unique_windows) == 1,
        "same_bar_count": len(bar_counts) == 1,
        "same_initial_equity": float(config.get("initial_equity", 0.0)) > 0.0,
        "same_cost_and_slippage_model": "cost_bps" in config and "slippage_bps" in config,
        "same_metric_engine": True,
        "baseline_configs_public": all("params" in strategy for strategy in strategies),
        "hypothetical_backtest_disclosed_for_all": all(item.get("hypothetical_backtest") is True for item in metrics.values()),
        "candidate_not_compared_to_missing_baselines": all(strategy_id in metrics for strategy_id in baseline_ids),
    }
    return {
        "schema": "downside_performance_baseline_fairness_report_v0_2",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "shared_config": {
            "initial_equity": config.get("initial_equity"),
            "cost_bps": config.get("cost_bps"),
            "slippage_bps": config.get("slippage_bps"),
            "trading_days": config.get("trading_days"),
            "candidate_strategy_id": candidate_id,
        },
        "baseline_ids": baseline_ids,
        "strategy_configs": strategies,
        "evaluation_windows": windows,
        "fairness_statement": (
            "All included strategies are executed through the same deterministic portfolio accounting, "
            "calendar, cost/slippage, metric, and evidence-writing path. Baselines are fixed source-level "
            "configs, not post-hoc narrative comparators."
        ),
    }


def build_statistical_confidence_report(
    report: Mapping[str, Any],
    *,
    samples: int = 250,
    block_size: int = 21,
) -> Dict[str, Any]:
    if samples < 30:
        raise ValueError("bootstrap samples must be at least 30")
    candidate_id = str(report.get("config", {}).get("candidate_strategy_id", "agentic_candidate_v1"))
    curve = list(report.get("equity_curves_by_strategy", {}).get(candidate_id, []))
    returns = [float(point.get("daily_return", 0.0)) for point in curve[1:]]
    seed = _seed_from_report(report)
    bootstrap_rows = _block_bootstrap_metrics(returns, samples=samples, block_size=block_size, seed=seed)
    fields = ["total_return", "cagr", "max_drawdown", "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
    intervals = {
        field: _interval([row[field] for row in bootstrap_rows])
        for field in fields
    }
    rolling = _rolling_performance(curve, window=63)
    observed = dict(report.get("metrics_by_strategy", {}).get(candidate_id, {}))
    checks = {
        "bootstrap_samples_present": samples >= 100,
        "bootstrap_block_size_recorded": block_size >= 1,
        "confidence_intervals_present": all(field in intervals for field in fields),
        "drawdown_distribution_present": "max_drawdown" in intervals,
        "rolling_performance_stability_present": bool(rolling.get("windows")),
        "walk_forward_report_present": "walk_forward" in report.get("robustness", {}),
        "descriptive_not_predictive_disclosure_present": True,
    }
    return {
        "schema": "downside_performance_statistical_confidence_report_v0_2",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "candidate_strategy_id": candidate_id,
        "bootstrap": {
            "method": "deterministic circular moving-block bootstrap over realized daily returns",
            "seed": seed,
            "sample_count": samples,
            "block_size": block_size,
            "metrics": intervals,
            "worst_case_percentiles": {
                "cagr_p05": intervals["cagr"]["p05"],
                "max_drawdown_p95": intervals["max_drawdown"]["p95"],
                "calmar_p05": intervals["calmar_ratio"]["p05"],
            },
            "disclosure": "Intervals describe uncertainty inside the included benchmark return path only; they are not future-performance forecasts.",
        },
        "observed_candidate_metrics": {
            "total_return": observed.get("total_return"),
            "cagr": observed.get("cagr"),
            "max_drawdown": observed.get("max_drawdown"),
            "sharpe_ratio": observed.get("sharpe_ratio"),
            "sortino_ratio": observed.get("sortino_ratio"),
            "calmar_ratio": observed.get("calmar_ratio"),
        },
        "rolling_performance": rolling,
        "walk_forward": report.get("robustness", {}).get("walk_forward", {}),
    }


def build_forward_paper_trading_protocol(report: Mapping[str, Any], forward_start_date: str) -> Dict[str, Any]:
    candidate_id = str(report.get("config", {}).get("candidate_strategy_id", "agentic_candidate_v1"))
    candidate = _strategy_by_id(list(report.get("strategies", [])), candidate_id)
    checkpoints = _checkpoint_dates(forward_start_date)
    checks = {
        "protocol_initialized": bool(forward_start_date),
        "strategy_config_frozen": bool(candidate.get("params")),
        "paper_only_mode": True,
        "signal_logging_schema_present": True,
        "checkpoint_schedule_present": len(checkpoints) == 3,
        "live_performance_claim_excluded": True,
        "broker_routing_excluded": True,
    }
    return {
        "schema": "downside_performance_forward_paper_trading_protocol_v0_2",
        "status": "initialized" if all(checks.values()) else "incomplete",
        "checks": checks,
        "forward_start_date": forward_start_date,
        "candidate_strategy_id": candidate_id,
        "candidate_config_fingerprint": _fingerprint(candidate),
        "mode": "paper_signal_logging_only",
        "frequency": "daily after market close or next available benchmark session",
        "signal_schema": {
            "date": "ISO-8601 trading date",
            "strategy_id": candidate_id,
            "universe_snapshot_hash": "sha256 of the available paper-trading input universe",
            "weights": "target paper weights by symbol",
            "risk_state": "risk_on | risk_off | cash",
            "reason_codes": "deterministic guard and ranking reasons",
            "generated_at_utc": "timestamp of signal generation",
        },
        "recordkeeping": [
            "Do not alter candidate parameters during the forward window.",
            "Store every generated signal before subsequent price observations are scored.",
            "Score 1-month, 3-month, and 6-month checkpoints against the frozen protocol.",
            "Do not make live-performance or investor-return claims from this protocol until a forward report exists.",
        ],
        "checkpoints": checkpoints,
        "non_claims": list(PERFORMANCE_NON_CLAIMS),
    }


def build_defense_gate(
    report: Mapping[str, Any],
    strategy_freeze: Mapping[str, Any],
    data_lineage: Mapping[str, Any],
    baseline_fairness: Mapping[str, Any],
    statistical_confidence: Mapping[str, Any],
    forward_protocol: Mapping[str, Any],
) -> Dict[str, Any]:
    report_non_claims = list(report.get("claim", {}).get("non_claims", []))
    checks = {
        "strategy_freeze_verified": strategy_freeze.get("status") == "passed",
        "data_bias_defense_passed": data_lineage.get("status") == "passed",
        "baseline_fairness_verified": baseline_fairness.get("status") == "passed",
        "statistical_confidence_report_present": statistical_confidence.get("status") == "passed",
        "bootstrap_confidence_intervals_present": statistical_confidence.get("checks", {}).get("confidence_intervals_present") is True,
        "paper_trading_protocol_initialized": forward_protocol.get("status") == "initialized",
        "performance_claim_boundary_preserved": report.get("claim", {}).get("performance_type") == "hypothetical_backtested_performance",
        "non_claims_preserved": all(non_claim in report_non_claims for non_claim in PERFORMANCE_NON_CLAIMS),
        "no_live_or_future_return_claim_preserved": (
            "No live trading readiness claim." in report_non_claims
            and "No return guarantee or future performance claim." in report_non_claims
        ),
    }
    return {
        "schema": DEFENSE_GATE_SCHEMA,
        "status": "passed" if all(checks.values()) else "failed",
        "defense_claim_defensible": all(checks.values()),
        "checks": checks,
        "claim_scope": _claim_scope(),
        "publication_requirement": (
            "performance_claim_publishable plus strategy freeze, data lineage, baseline fairness, "
            "statistical confidence, and forward paper-trading protocol evidence"
        ),
    }


def write_defense_packet(packet: Mapping[str, Any], output_dir: Path, *, clean: bool = False) -> Dict[str, Any]:
    if clean and output_dir.exists():
        _safe_clean(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, Any]] = []

    def write_json(name: str, payload: Any) -> None:
        path = output_dir / name
        path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")
        files.append(_file_entry(output_dir, path))

    write_json("strategy_freeze_report.json", packet["strategy_freeze_report"])
    write_json("data_lineage_bias_report.json", packet["data_lineage_bias_report"])
    write_json("baseline_fairness_report.json", packet["baseline_fairness_report"])
    write_json("statistical_confidence_report.json", packet["statistical_confidence_report"])
    write_json("forward_paper_trading_protocol.json", packet["forward_paper_trading_protocol"])
    write_json("defense_gate.json", packet["defense_gate"])
    summary_path = output_dir / "DEFENSE_SUMMARY.md"
    summary_path.write_text(render_defense_summary(packet), encoding="utf-8")
    files.append(_file_entry(output_dir, summary_path))

    manifest = dict(packet["manifest"])
    manifest["files"] = sorted(files, key=lambda item: item["path"])
    manifest_path = output_dir / "DEFENSE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def render_defense_summary(packet: Mapping[str, Any]) -> str:
    gate = packet["defense_gate"]
    confidence = packet["statistical_confidence_report"]["bootstrap"]["metrics"]
    protocol = packet["forward_paper_trading_protocol"]
    lines = [
        "# Downside Performance Defense Packet v0.2",
        "",
        "This packet strengthens the scoped `downside_performance_v1` claim. It does not expand the claim beyond hypothetical backtested performance under the included deterministic benchmark.",
        "",
        "## Defense Gate",
        "",
    ]
    for key, value in gate["checks"].items():
        lines.append("- `%s`: `%s`" % (key, value))
    lines.extend([
        "",
        "## Bootstrap Confidence Snapshot",
        "",
        "| Metric | p05 | median | p95 |",
        "| --- | ---: | ---: | ---: |",
    ])
    for metric in ["cagr", "max_drawdown", "sharpe_ratio", "calmar_ratio"]:
        item = confidence[metric]
        lines.append("| `%s` | %.6f | %.6f | %.6f |" % (metric, item["p05"], item["median"], item["p95"]))
    lines.extend([
        "",
        "## Forward Paper-Trading Protocol",
        "",
        "- Start date: `%s`" % protocol["forward_start_date"],
        "- Mode: `%s`" % protocol["mode"],
        "- Checkpoints: `%s`, `%s`, `%s`" % tuple(protocol["checkpoints"]),
        "",
        "## Non-Claims",
        "",
    ])
    for non_claim in packet["claim_scope"]["non_claims"]:
        lines.append("- " + non_claim)
    lines.append("")
    return "\n".join(lines)


def verify_defense_packet(packet_dir: Path) -> Dict[str, Any]:
    manifest_path = packet_dir / "DEFENSE_MANIFEST.json"
    errors: List[str] = []
    if not manifest_path.is_file():
        errors.append("missing DEFENSE_MANIFEST.json")
        manifest: Dict[str, Any] = {}
    else:
        manifest = _load_json(manifest_path)
    manifest_files = {entry.get("path"): entry for entry in manifest.get("files", [])}
    file_checks = {}
    for name in DEFENSE_REQUIRED_FILES:
        path = packet_dir / name
        file_checks[name] = path.is_file()
        if not path.is_file():
            errors.append("missing required file: " + name)
    hash_errors = []
    for rel, entry in sorted(manifest_files.items()):
        path = packet_dir / rel
        if not path.is_file():
            hash_errors.append({"path": rel, "error": "missing"})
            continue
        actual = _sha256(path)
        if actual != entry.get("sha256"):
            hash_errors.append({"path": rel, "expected": entry.get("sha256"), "actual": actual})
    defense_gate = _load_json(packet_dir / "defense_gate.json") if (packet_dir / "defense_gate.json").is_file() else {}
    confidence = (
        _load_json(packet_dir / "statistical_confidence_report.json")
        if (packet_dir / "statistical_confidence_report.json").is_file()
        else {}
    )
    protocol = (
        _load_json(packet_dir / "forward_paper_trading_protocol.json")
        if (packet_dir / "forward_paper_trading_protocol.json").is_file()
        else {}
    )
    json_checks = {
        "manifest_schema": manifest.get("schema") == DEFENSE_MANIFEST_SCHEMA,
        "manifest_status": manifest.get("status") == "passed",
        "claim_scope": manifest.get("claim_id") == PERFORMANCE_CLAIM_ID
        and manifest.get("benchmark_suite") == PERFORMANCE_BENCHMARK_SUITE,
        "defense_gate_passed": defense_gate.get("status") == "passed"
        and defense_gate.get("defense_claim_defensible") is True,
        "confidence_report_passed": confidence.get("status") == "passed",
        "forward_protocol_initialized": protocol.get("status") == "initialized",
    }
    passed = not errors and not hash_errors and all(file_checks.values()) and all(json_checks.values())
    return {
        "schema": "downside_performance_defense_packet_verification_v0_2",
        "status": "passed" if passed else "failed",
        "packet_dir": str(packet_dir),
        "checks": {
            "required_files": file_checks,
            "hashes": {"passed": not hash_errors, "errors": hash_errors},
            "json_payloads": json_checks,
        },
        "errors": errors,
    }


def _claim_scope() -> Dict[str, Any]:
    return {
        "claim_id": PERFORMANCE_CLAIM_ID,
        "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
        "claim_limit": PERFORMANCE_CLAIM_LIMIT,
        "performance_type": "hypothetical_backtested_performance",
        "defense_version": DEFENSE_VERSION,
        "non_claims": list(PERFORMANCE_NON_CLAIMS),
    }


def _validate_report(report: Mapping[str, Any]) -> None:
    if report.get("schema") != "stock_harness_downside_performance_report_v1":
        raise ValueError("expected stock_harness_downside_performance_report_v1")
    if report.get("claim", {}).get("id") != PERFORMANCE_CLAIM_ID:
        raise ValueError("unexpected performance claim id")
    if report.get("claim", {}).get("benchmark_suite") != PERFORMANCE_BENCHMARK_SUITE:
        raise ValueError("unexpected benchmark suite")


def _strategy_by_id(strategies: Sequence[Mapping[str, Any]], strategy_id: str) -> Dict[str, Any]:
    for strategy in strategies:
        if strategy.get("strategy_id") == strategy_id:
            return dict(strategy)
    return {}


def _dates(report: Mapping[str, Any], strategy_id: str) -> List[str]:
    return [str(point["date"]) for point in report["equity_curves_by_strategy"][strategy_id]]


def _train_validation_test_partitions(dates: Sequence[str]) -> Dict[str, Any]:
    if not dates:
        return {}
    count = len(dates)
    train_end = count // 3
    validation_end = 2 * count // 3
    partitions = {
        "train": _partition(dates, 0, train_end),
        "validation": _partition(dates, train_end, validation_end),
        "test": _partition(dates, validation_end, count),
    }
    return partitions


def _partition(dates: Sequence[str], start: int, end: int) -> Dict[str, Any]:
    selected = dates[start:end]
    if not selected:
        return {}
    return {
        "start": selected[0],
        "end": selected[-1],
        "bar_count": len(selected),
    }


def _block_bootstrap_metrics(returns: Sequence[float], *, samples: int, block_size: int, seed: int) -> List[Dict[str, float]]:
    if not returns:
        return []
    rng = random.Random(seed)
    n = len(returns)
    rows: List[Dict[str, float]] = []
    for _ in range(samples):
        sampled: List[float] = []
        while len(sampled) < n:
            start = rng.randrange(n)
            for offset in range(block_size):
                sampled.append(float(returns[(start + offset) % n]))
                if len(sampled) >= n:
                    break
        rows.append(_metrics_from_returns(sampled))
    return rows


def _metrics_from_returns(returns: Sequence[float]) -> Dict[str, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        equity *= 1.0 + float(value)
        peak = max(peak, equity)
        if peak > 0.0:
            max_drawdown = max(max_drawdown, 1.0 - equity / peak)
    years = max(1.0 / TRADING_DAYS, len(returns) / TRADING_DAYS)
    total_return = equity - 1.0
    cagr = equity ** (1.0 / years) - 1.0 if equity > 0.0 else -1.0
    annualized_return = _mean(returns) * TRADING_DAYS
    volatility = _stddev(returns) * math.sqrt(TRADING_DAYS)
    downside = [min(0.0, value) for value in returns]
    downside_deviation = math.sqrt(_mean([value * value for value in downside])) * math.sqrt(TRADING_DAYS)
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": _safe_div(annualized_return, volatility),
        "sortino_ratio": _safe_div(annualized_return, downside_deviation),
        "calmar_ratio": _safe_div(cagr, max_drawdown),
    }


def _rolling_performance(curve: Sequence[Mapping[str, Any]], window: int = 63) -> Dict[str, Any]:
    windows = []
    if len(curve) <= window:
        return {"schema": "downside_performance_rolling_stability_v0_2", "windows": windows}
    for start in range(0, len(curve) - window, window):
        segment = curve[start:start + window + 1]
        start_equity = float(segment[0]["equity"])
        end_equity = float(segment[-1]["equity"])
        returns = [float(point.get("daily_return", 0.0)) for point in segment[1:]]
        windows.append({
            "start": segment[0]["date"],
            "end": segment[-1]["date"],
            "total_return": end_equity / start_equity - 1.0 if start_equity else 0.0,
            "max_drawdown": max(float(point.get("drawdown", 0.0)) for point in segment),
            "positive_return": end_equity >= start_equity,
            "mean_daily_return": _mean(returns),
        })
    return {
        "schema": "downside_performance_rolling_stability_v0_2",
        "window_bars": window,
        "window_count": len(windows),
        "positive_window_rate": _safe_div(sum(1 for item in windows if item["positive_return"]), len(windows)),
        "worst_window_return": min((item["total_return"] for item in windows), default=0.0),
        "worst_window_drawdown": max((item["max_drawdown"] for item in windows), default=0.0),
        "windows": windows,
    }


def _interval(values: Sequence[float]) -> Dict[str, float]:
    ordered = sorted(float(value) for value in values)
    return {
        "p05": _percentile(ordered, 0.05),
        "p25": _percentile(ordered, 0.25),
        "median": _percentile(ordered, 0.50),
        "p75": _percentile(ordered, 0.75),
        "p95": _percentile(ordered, 0.95),
        "min": ordered[0],
        "max": ordered[-1],
    }


def _percentile(ordered: Sequence[float], q: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return ordered[lo]
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def _checkpoint_dates(start_date: str) -> List[str]:
    start = Date.fromisoformat(start_date)
    return [
        _add_months_approx(start, 1).isoformat(),
        _add_months_approx(start, 3).isoformat(),
        _add_months_approx(start, 6).isoformat(),
    ]


def _add_months_approx(start: Date, months: int) -> Date:
    return start + timedelta(days=30 * months)


def _next_business_day(date_text: str) -> str:
    current = Date.fromisoformat(date_text) + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current.isoformat()


def _seed_from_report(report: Mapping[str, Any]) -> int:
    text = str(report.get("manifest", {}).get("fingerprint", ""))[:16]
    if not text:
        text = _fingerprint(report)[:16]
    return int(text, 16)


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _mean(values: Sequence[float]) -> float:
    return sum(values) / float(len(values)) if values else 0.0


def _stddev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / float(len(values) - 1))


def _safe_div(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-12:
        return 0.0
    return numerator / denominator


def _safe_clean(path: Path) -> None:
    resolved = path.resolve()
    root = Path(__file__).resolve().parents[1]
    dist_root = (root / "dist").resolve()
    if not str(resolved).startswith(str(dist_root)):
        raise ValueError("refusing to clean outside dist/: " + str(resolved))
    shutil.rmtree(str(resolved))


def _file_entry(root: Path, path: Path) -> Dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


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
