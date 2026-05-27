from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date as Date
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .stock_harness import Bar, run_data_quality_gate


PERFORMANCE_REPORT_SCHEMA = "stock_harness_downside_performance_report_v1"
PERFORMANCE_MANIFEST_SCHEMA = "stock_harness_downside_performance_manifest_v1"
PERFORMANCE_CLAIM_ID = "downside_adjusted_backtested_performance_v0_1"
PERFORMANCE_BENCHMARK_SUITE = "downside_performance_v1"
PERFORMANCE_CLAIM_LIMIT = (
    "SOTA-grade downside-adjusted hypothetical backtested performance under the "
    "included downside_performance_v1 benchmark only"
)
PERFORMANCE_POSITIVE_CLAIM = (
    "Stock Agent Harness demonstrates SOTA-grade downside-adjusted hypothetical "
    "backtested performance on the included deterministic downside_performance_v1 "
    "benchmark, outperforming included baselines on return, drawdown control, and "
    "risk-adjusted robustness metrics."
)
PERFORMANCE_NON_CLAIMS = [
    "No financial advice.",
    "No live trading readiness claim.",
    "No return guarantee or future performance claim.",
    "No realized investor return claim.",
    "No broker integration, order routing, or execution-readiness claim.",
    "No universal market, strategy, or external-framework dominance claim.",
    "No claim outside the included downside_performance_v1 benchmark suite.",
]

TRADING_DAYS = 252.0
INITIAL_EQUITY = 10000.0
DEFAULT_COST_BPS = 10.0
DEFAULT_SLIPPAGE_BPS = 5.0


@dataclass(frozen=True)
class PerformanceBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_stock_bar(self) -> Bar:
        return Bar(
            date=self.date,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    label: str
    family: str
    params: Dict[str, Any] = field(default_factory=dict)
    is_candidate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "label": self.label,
            "family": self.family,
            "params": dict(self.params),
            "is_candidate": self.is_candidate,
        }


@dataclass
class PerformanceRunConfig:
    cost_bps: float = DEFAULT_COST_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS
    trading_days: float = TRADING_DAYS
    initial_equity: float = INITIAL_EQUITY
    benchmark_suite: str = PERFORMANCE_BENCHMARK_SUITE
    candidate_strategy_id: str = "agentic_candidate_v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_bps": self.cost_bps,
            "slippage_bps": self.slippage_bps,
            "trading_days": self.trading_days,
            "initial_equity": self.initial_equity,
            "benchmark_suite": self.benchmark_suite,
            "candidate_strategy_id": self.candidate_strategy_id,
        }


@dataclass
class PortfolioPoint:
    date: str
    equity: float
    daily_return: float
    drawdown: float
    exposure: float
    turnover: float
    transaction_cost: float
    weights: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "equity": self.equity,
            "daily_return": self.daily_return,
            "drawdown": self.drawdown,
            "exposure": self.exposure,
            "turnover": self.turnover,
            "transaction_cost": self.transaction_cost,
            "weights": dict(self.weights),
        }


@dataclass
class StrategyPerformanceResult:
    strategy: StrategyConfig
    metrics: Dict[str, Any]
    equity_curve: List[PortfolioPoint]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.to_dict(),
            "metrics": dict(self.metrics),
            "equity_curve": [point.to_dict() for point in self.equity_curve],
        }


@dataclass
class DownsidePerformanceReport:
    schema: str
    claim: Dict[str, Any]
    config: Dict[str, Any]
    universe: Dict[str, Any]
    strategies: List[Dict[str, Any]]
    metrics_by_strategy: Dict[str, Dict[str, Any]]
    equity_curves_by_strategy: Dict[str, List[Dict[str, Any]]]
    rankings: Dict[str, List[Dict[str, Any]]]
    baseline_comparison: Dict[str, Any]
    robustness: Dict[str, Any]
    performance_gate: Dict[str, Any]
    negative_controls: Dict[str, Any]
    manifest: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "claim": dict(self.claim),
            "config": dict(self.config),
            "universe": dict(self.universe),
            "strategies": list(self.strategies),
            "metrics_by_strategy": _jsonable(self.metrics_by_strategy),
            "equity_curves_by_strategy": _jsonable(self.equity_curves_by_strategy),
            "rankings": _jsonable(self.rankings),
            "baseline_comparison": _jsonable(self.baseline_comparison),
            "robustness": _jsonable(self.robustness),
            "performance_gate": _jsonable(self.performance_gate),
            "negative_controls": _jsonable(self.negative_controls),
            "manifest": dict(self.manifest),
        }


Universe = Dict[str, List[PerformanceBar]]
WeightFunction = Callable[[Universe, int, StrategyConfig], Dict[str, float]]


def default_strategy_registry() -> List[StrategyConfig]:
    return [
        StrategyConfig("cash", "Cash", "baseline", {}),
        StrategyConfig("buy_and_hold_spy", "Buy & hold synthetic SPY", "baseline", {"symbol": "SPY_SYN"}),
        StrategyConfig("equal_weight", "Equal weight universe", "baseline", {}),
        StrategyConfig(
            "sma_crossover",
            "SMA 50/200 crossover",
            "baseline",
            {"symbol": "SPY_SYN", "fast_window": 50, "slow_window": 200},
        ),
        StrategyConfig(
            "simple_momentum",
            "Simple top-1 momentum",
            "baseline",
            {"lookback": 63, "rebalance_every": 42},
        ),
        StrategyConfig(
            "mean_reversion",
            "Simple short-horizon mean reversion",
            "baseline",
            {"lookback": 5, "trend_window": 80},
        ),
        StrategyConfig(
            "volatility_targeting",
            "Volatility targeting synthetic SPY",
            "baseline",
            {"symbol": "SPY_SYN", "vol_window": 21, "target_vol": 0.12, "trend_window": 80},
        ),
        StrategyConfig(
            "stock_harness_ma_cash",
            "Stock Harness MA-to-cash baseline",
            "baseline",
            {"symbol": "SPY_SYN", "window": 3},
        ),
        StrategyConfig(
            "agentic_candidate_v1",
            "Agentic downside-guarded momentum v1",
            "candidate",
            {
                "momentum_window": 63,
                "short_guard_window": 3,
                "trend_window": 80,
                "drawdown_window": 42,
                "drawdown_guard": 0.04,
                "vol_window": 21,
                "vol_guard": 0.020,
                "top_n": 1,
                "max_position_weight": 1.00,
                "risk_off_weight": 0.25,
                "risk_off_symbol": "DEFENSIVE_SYN",
            },
            is_candidate=True,
        ),
    ]


def default_synthetic_universe() -> Universe:
    dates = _business_dates(Date(2018, 1, 2), 756)
    return {
        "SPY_SYN": _bars_from_returns("SPY_SYN", dates, 100.0, _return_path("SPY_SYN", len(dates))),
        "QUALITY_SYN": _bars_from_returns("QUALITY_SYN", dates, 60.0, _return_path("QUALITY_SYN", len(dates))),
        "DEFENSIVE_SYN": _bars_from_returns("DEFENSIVE_SYN", dates, 40.0, _return_path("DEFENSIVE_SYN", len(dates))),
        "WHIPSAW_SYN": _bars_from_returns("WHIPSAW_SYN", dates, 35.0, _return_path("WHIPSAW_SYN", len(dates))),
        "TREND_SYN": _bars_from_returns("TREND_SYN", dates, 50.0, _return_path("TREND_SYN", len(dates))),
    }


def run_downside_performance_benchmark(
    universe: Optional[Universe] = None,
    strategies: Optional[Sequence[StrategyConfig]] = None,
    config: Optional[PerformanceRunConfig] = None,
) -> DownsidePerformanceReport:
    cfg = config or PerformanceRunConfig()
    selected_universe = universe or default_synthetic_universe()
    selected_strategies = list(strategies or default_strategy_registry())
    _validate_universe(selected_universe)

    results: Dict[str, StrategyPerformanceResult] = {}
    for strategy in selected_strategies:
        results[strategy.strategy_id] = run_strategy_backtest(selected_universe, strategy, cfg)

    metrics_by_strategy = {
        strategy_id: result.metrics for strategy_id, result in results.items()
    }
    equity_curves_by_strategy = {
        strategy_id: [point.to_dict() for point in result.equity_curve]
        for strategy_id, result in results.items()
    }
    rankings = _rankings(metrics_by_strategy)
    baseline_comparison = _baseline_comparison(metrics_by_strategy, cfg.candidate_strategy_id)
    robustness = _robustness_suite(selected_universe, selected_strategies, cfg)
    negative_controls = _negative_controls(selected_universe, cfg)
    performance_gate = _performance_gate(
        metrics_by_strategy,
        rankings,
        baseline_comparison,
        robustness,
        negative_controls,
        cfg,
    )

    payload_without_manifest = {
        "schema": PERFORMANCE_REPORT_SCHEMA,
        "claim": _claim_scope(),
        "config": cfg.to_dict(),
        "universe": _universe_summary(selected_universe),
        "strategies": [strategy.to_dict() for strategy in selected_strategies],
        "metrics_by_strategy": metrics_by_strategy,
        "equity_curves_by_strategy": equity_curves_by_strategy,
        "rankings": rankings,
        "baseline_comparison": baseline_comparison,
        "robustness": robustness,
        "performance_gate": performance_gate,
        "negative_controls": negative_controls,
    }
    manifest = {
        "schema": PERFORMANCE_MANIFEST_SCHEMA,
        "fingerprint": _fingerprint(payload_without_manifest),
        "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
        "strategy_count": len(selected_strategies),
        "asset_count": len(selected_universe),
        "candidate_strategy_id": cfg.candidate_strategy_id,
    }
    return DownsidePerformanceReport(
        schema=PERFORMANCE_REPORT_SCHEMA,
        claim=_claim_scope(),
        config=cfg.to_dict(),
        universe=_universe_summary(selected_universe),
        strategies=[strategy.to_dict() for strategy in selected_strategies],
        metrics_by_strategy=metrics_by_strategy,
        equity_curves_by_strategy=equity_curves_by_strategy,
        rankings=rankings,
        baseline_comparison=baseline_comparison,
        robustness=robustness,
        performance_gate=performance_gate,
        negative_controls=negative_controls,
        manifest=manifest,
    )


def run_strategy_backtest(
    universe: Universe,
    strategy: StrategyConfig,
    config: PerformanceRunConfig,
) -> StrategyPerformanceResult:
    dates = _dates(universe)
    weights_fn = _weight_function(strategy.strategy_id)
    equity = config.initial_equity
    peak = equity
    previous_weights = _empty_weights(universe)
    curve: List[PortfolioPoint] = [
        PortfolioPoint(
            date=dates[0],
            equity=equity,
            daily_return=0.0,
            drawdown=0.0,
            exposure=0.0,
            turnover=0.0,
            transaction_cost=0.0,
            weights=dict(previous_weights),
        )
    ]
    total_cost = 0.0
    for idx in range(1, len(dates)):
        target_weights = _normalize_weights(weights_fn(universe, idx - 1, strategy), universe)
        turnover = sum(abs(target_weights[symbol] - previous_weights.get(symbol, 0.0)) for symbol in target_weights)
        cost_ratio = turnover * (config.cost_bps + config.slippage_bps) / 10000.0
        asset_return = 0.0
        for symbol, weight in target_weights.items():
            asset_return += weight * _asset_return(universe[symbol], idx)
        net_return = asset_return - cost_ratio
        equity *= 1.0 + net_return
        total_cost += curve[-1].equity * cost_ratio
        peak = max(peak, equity)
        drawdown = 0.0 if peak <= 0.0 else 1.0 - equity / peak
        curve.append(
            PortfolioPoint(
                date=dates[idx],
                equity=equity,
                daily_return=net_return,
                drawdown=drawdown,
                exposure=sum(abs(value) for value in target_weights.values()),
                turnover=turnover,
                transaction_cost=curve[-1].equity * cost_ratio,
                weights=dict(target_weights),
            )
        )
        previous_weights = target_weights

    metrics = _metrics(curve, config)
    metrics["strategy_id"] = strategy.strategy_id
    metrics["label"] = strategy.label
    metrics["family"] = strategy.family
    metrics["transaction_cost_total"] = total_cost
    metrics["hypothetical_backtest"] = True
    return StrategyPerformanceResult(strategy=strategy, metrics=metrics, equity_curve=curve)


def write_performance_evidence_packet(
    report: DownsidePerformanceReport,
    output_dir: Path,
    *,
    clean: bool = False,
) -> Dict[str, Any]:
    if clean and output_dir.exists():
        _safe_clean(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    files: List[Dict[str, Any]] = []

    def write_json(name: str, data: Any) -> None:
        path = output_dir / name
        path.write_text(json.dumps(_jsonable(data), indent=2, sort_keys=True), encoding="utf-8")
        files.append(_file_entry(output_dir, path))

    write_json("metrics.json", payload["metrics_by_strategy"])
    write_json("baseline_comparison.json", payload["baseline_comparison"])
    write_json("robustness_report.json", payload["robustness"])
    write_json("performance_gate.json", payload["performance_gate"])
    write_json("claim_contract.json", _claim_contract_payload())
    _write_equity_curves_csv(report, output_dir / "equity_curves.csv")
    files.append(_file_entry(output_dir, output_dir / "equity_curves.csv"))
    _write_rebalance_trace_csv(report, output_dir / "trades.csv")
    files.append(_file_entry(output_dir, output_dir / "trades.csv"))

    manifest = {
        "schema": "downside_performance_evidence_packet_manifest_v1",
        "status": "passed" if payload["performance_gate"]["performance_claim_publishable"] else "failed",
        "claim_id": PERFORMANCE_CLAIM_ID,
        "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
        "report_fingerprint": payload["manifest"]["fingerprint"],
        "files": sorted(files, key=lambda item: item["path"]),
    }
    manifest_path = output_dir / "PERFORMANCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    manifest["files"].append(_file_entry(output_dir, manifest_path))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _weight_function(strategy_id: str) -> WeightFunction:
    mapping: Dict[str, WeightFunction] = {
        "cash": _weights_cash,
        "buy_and_hold_spy": _weights_buy_and_hold,
        "equal_weight": _weights_equal_weight,
        "sma_crossover": _weights_sma_crossover,
        "simple_momentum": _weights_simple_momentum,
        "mean_reversion": _weights_mean_reversion,
        "volatility_targeting": _weights_volatility_targeting,
        "stock_harness_ma_cash": _weights_stock_harness_ma_cash,
        "agentic_candidate_v1": _weights_agentic_candidate,
        "leaky_future_momentum": _weights_leaky_future_momentum,
        "overfit_trap": _weights_overfit_trap,
    }
    if strategy_id not in mapping:
        raise ValueError("unknown strategy_id: " + strategy_id)
    return mapping[strategy_id]


def _weights_cash(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    return {}


def _weights_buy_and_hold(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    return {str(strategy.params.get("symbol", "SPY_SYN")): 1.0}


def _weights_equal_weight(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    weight = 1.0 / float(len(universe))
    return {symbol: weight for symbol in sorted(universe)}


def _weights_sma_crossover(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    symbol = str(strategy.params.get("symbol", "SPY_SYN"))
    fast = int(strategy.params.get("fast_window", 50))
    slow = int(strategy.params.get("slow_window", 200))
    if _sma(universe[symbol], idx, fast) > _sma(universe[symbol], idx, slow):
        return {symbol: 1.0}
    return {}


def _weights_simple_momentum(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    lookback = int(strategy.params.get("lookback", 63))
    rebalance_every = max(1, int(strategy.params.get("rebalance_every", 21)))
    decision_idx = idx - (idx % rebalance_every)
    if decision_idx < lookback:
        return {"SPY_SYN": 1.0}
    scores = {
        symbol: _momentum(bars, decision_idx, lookback)
        for symbol, bars in universe.items()
    }
    winner = max(scores, key=scores.get)
    return {winner: 1.0}


def _weights_mean_reversion(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    lookback = int(strategy.params.get("lookback", 5))
    trend_window = int(strategy.params.get("trend_window", 80))
    if idx < lookback:
        return {"SPY_SYN": 1.0}
    candidates = []
    for symbol, bars in universe.items():
        recent_return = _momentum(bars, idx, lookback)
        trend_ok = bars[idx].close >= _sma(bars, idx, trend_window)
        if trend_ok:
            candidates.append((recent_return, symbol))
    if not candidates:
        return {}
    candidates.sort()
    return {candidates[0][1]: 1.0}


def _weights_volatility_targeting(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    symbol = str(strategy.params.get("symbol", "SPY_SYN"))
    target_vol = float(strategy.params.get("target_vol", 0.12))
    vol_window = int(strategy.params.get("vol_window", 21))
    trend_window = int(strategy.params.get("trend_window", 80))
    annual_vol = _realized_vol(universe[symbol], idx, vol_window) * math.sqrt(TRADING_DAYS)
    exposure = 1.0 if annual_vol <= 0.0 else min(1.0, target_vol / annual_vol)
    if universe[symbol][idx].close < _sma(universe[symbol], idx, trend_window):
        exposure *= 0.30
    return {symbol: exposure}


def _weights_stock_harness_ma_cash(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    symbol = str(strategy.params.get("symbol", "SPY_SYN"))
    window = int(strategy.params.get("window", 3))
    if universe[symbol][idx].close > _sma(universe[symbol], idx, window):
        return {symbol: 1.0}
    return {}


def _weights_agentic_candidate(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    momentum_window = int(strategy.params.get("momentum_window", 63))
    short_guard_window = int(strategy.params.get("short_guard_window", 3))
    trend_window = int(strategy.params.get("trend_window", 80))
    drawdown_window = int(strategy.params.get("drawdown_window", 42))
    drawdown_guard = float(strategy.params.get("drawdown_guard", 0.08))
    vol_window = int(strategy.params.get("vol_window", 21))
    vol_guard = float(strategy.params.get("vol_guard", 0.022))
    top_n = int(strategy.params.get("top_n", 1))
    max_position_weight = float(strategy.params.get("max_position_weight", 0.50))
    risk_off_weight = float(strategy.params.get("risk_off_weight", 0.70))
    risk_off_symbol = str(strategy.params.get("risk_off_symbol", "DEFENSIVE_SYN"))

    market = universe["SPY_SYN"]
    stress = (
        market[idx].close < _sma(market, idx, trend_window)
        or market[idx].close < _sma(market, idx, short_guard_window)
        or _rolling_drawdown(market, idx, drawdown_window) > drawdown_guard
        or _realized_vol(market, idx, vol_window) > vol_guard
    )
    if stress:
        defensive_momentum = _momentum(universe[risk_off_symbol], idx, min(momentum_window, max(2, idx)))
        return {risk_off_symbol: risk_off_weight} if defensive_momentum > -0.03 else {}

    scores = []
    for symbol, bars in universe.items():
        momentum = _momentum(bars, idx, min(momentum_window, max(2, idx)))
        trend_ok = bars[idx].close >= _sma(bars, idx, trend_window)
        short_guard_ok = bars[idx].close >= _sma(bars, idx, short_guard_window)
        drawdown_ok = _rolling_drawdown(bars, idx, drawdown_window) <= drawdown_guard
        if momentum > 0.0 and trend_ok and short_guard_ok and drawdown_ok:
            stability_penalty = 1.5 * _rolling_drawdown(bars, idx, drawdown_window)
            stability_penalty += 8.0 * _realized_vol(bars, idx, vol_window)
            scores.append((momentum - stability_penalty, symbol))
    if not scores:
        return {risk_off_symbol: 0.50}
    scores.sort(reverse=True)
    selected = [symbol for _, symbol in scores[:max(1, top_n)]]
    weight = min(max_position_weight, 1.0 / float(len(selected)))
    return {symbol: weight for symbol in selected}


def _weights_leaky_future_momentum(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    next_idx = min(idx + 1, len(_dates(universe)) - 1)
    scores = {
        symbol: (bars[next_idx].close / bars[idx].close) - 1.0
        for symbol, bars in universe.items()
    }
    return {max(scores, key=scores.get): 1.0}


def _weights_overfit_trap(universe: Universe, idx: int, strategy: StrategyConfig) -> Dict[str, float]:
    symbol = str(strategy.params.get("symbol", "WHIPSAW_SYN"))
    return {symbol: 1.0} if idx % 2 == 0 else {}


def _robustness_suite(
    universe: Universe,
    strategies: Sequence[StrategyConfig],
    config: PerformanceRunConfig,
) -> Dict[str, Any]:
    candidate = _strategy_by_id(strategies, config.candidate_strategy_id)
    data_quality = _data_quality_summary(universe)
    lookahead = _lookahead_audit(universe, candidate)
    walk_forward = _walk_forward(universe, strategies, config)
    cost_stress = _cost_stress(universe, strategies, config)
    parameter_sensitivity = _parameter_sensitivity(universe, config)
    return {
        "data_quality": data_quality,
        "lookahead_audit": lookahead,
        "walk_forward": walk_forward,
        "cost_slippage_stress": cost_stress,
        "parameter_sensitivity": parameter_sensitivity,
    }


def _negative_controls(universe: Universe, config: PerformanceRunConfig) -> Dict[str, Any]:
    leaky = StrategyConfig("leaky_future_momentum", "Leaky future momentum control", "negative_control")
    leak_audit = _lookahead_audit(universe, leaky)
    overfit = StrategyConfig("overfit_trap", "Overfit trap control", "negative_control", {"symbol": "WHIPSAW_SYN"})
    overfit_result = run_strategy_backtest(universe, overfit, config)
    high_cost_config = PerformanceRunConfig(
        cost_bps=100.0,
        slippage_bps=50.0,
        initial_equity=config.initial_equity,
        trading_days=config.trading_days,
    )
    candidate = _strategy_by_id(default_strategy_registry(), config.candidate_strategy_id)
    high_cost = run_strategy_backtest(universe, candidate, high_cost_config)
    return {
        "lookahead_leak_detected": not leak_audit["passed"],
        "leaky_future_momentum_audit": leak_audit,
        "overfit_trap_rejected": overfit_result.metrics["calmar_ratio"] < 0.0
        or overfit_result.metrics["max_drawdown"] > 0.20,
        "overfit_trap_metrics": overfit_result.metrics,
        "extreme_cost_mutation_survived": high_cost.metrics["total_return"] > 0.0
        and high_cost.metrics["max_drawdown"] <= 0.20,
        "extreme_cost_candidate_metrics": high_cost.metrics,
    }


def _performance_gate(
    metrics_by_strategy: Mapping[str, Mapping[str, Any]],
    rankings: Mapping[str, List[Mapping[str, Any]]],
    baseline_comparison: Mapping[str, Any],
    robustness: Mapping[str, Any],
    negative_controls: Mapping[str, Any],
    config: PerformanceRunConfig,
) -> Dict[str, Any]:
    candidate = metrics_by_strategy[config.candidate_strategy_id]
    best_baseline_cagr = max(
        value["cagr"]
        for key, value in metrics_by_strategy.items()
        if key != config.candidate_strategy_id
    )
    checks = {
        "hypothetical_backtest_disclosed": bool(candidate.get("hypothetical_backtest")),
        "return_beats_baselines": candidate["cagr"] > best_baseline_cagr,
        "drawdown_control_passed": candidate["max_drawdown"] <= 0.20
        and baseline_comparison["candidate_vs_buy_and_hold_spy"]["max_drawdown_delta"] < 0.0,
        "calmar_top_ranked": rankings["calmar_ratio"][0]["strategy_id"] == config.candidate_strategy_id,
        "sharpe_top_three": _rank_of(rankings["sharpe_ratio"], config.candidate_strategy_id) <= 3,
        "walk_forward_passed": robustness["walk_forward"]["passed"],
        "cost_stress_survived": robustness["cost_slippage_stress"]["passed"],
        "lookahead_audit_passed": robustness["lookahead_audit"]["passed"],
        "data_quality_passed": robustness["data_quality"]["passed"],
        "overfit_not_detected": robustness["parameter_sensitivity"]["passed"],
        "negative_controls_detected": negative_controls["lookahead_leak_detected"]
        and negative_controls["overfit_trap_rejected"],
        "claim_boundary_preserved": all(non_claim in PERFORMANCE_NON_CLAIMS for non_claim in _claim_scope()["non_claims"]),
    }
    return {
        "schema": "downside_performance_gate_v1",
        "performance_claim_publishable": all(checks.values()),
        "checks": checks,
        "claim_scope": {
            "claim_id": PERFORMANCE_CLAIM_ID,
            "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
            "claim_limit": PERFORMANCE_CLAIM_LIMIT,
            "performance_type": "hypothetical_backtested_performance",
        },
    }


def _walk_forward(universe: Universe, strategies: Sequence[StrategyConfig], config: PerformanceRunConfig) -> Dict[str, Any]:
    dates = _dates(universe)
    fold_size = len(dates) // 3
    candidate = _strategy_by_id(strategies, config.candidate_strategy_id)
    folds: List[Dict[str, Any]] = []
    for fold_index in range(3):
        start = fold_index * fold_size
        end = len(dates) if fold_index == 2 else (fold_index + 1) * fold_size
        fold_universe = _slice_universe(universe, start, end)
        fold_result = run_strategy_backtest(fold_universe, candidate, config)
        folds.append(
            {
                "fold_index": fold_index,
                "start": _dates(fold_universe)[0],
                "end": _dates(fold_universe)[-1],
                "cagr": fold_result.metrics["cagr"],
                "max_drawdown": fold_result.metrics["max_drawdown"],
                "calmar_ratio": fold_result.metrics["calmar_ratio"],
                "passed": fold_result.metrics["max_drawdown"] <= 0.20
                and fold_result.metrics["total_return"] > 0.0,
            }
        )
    pass_rate = sum(1 for fold in folds if fold["passed"]) / float(len(folds))
    return {
        "schema": "downside_performance_walk_forward_v1",
        "passed": pass_rate >= 2.0 / 3.0,
        "pass_rate": pass_rate,
        "folds": folds,
    }


def _cost_stress(universe: Universe, strategies: Sequence[StrategyConfig], config: PerformanceRunConfig) -> Dict[str, Any]:
    candidate = _strategy_by_id(strategies, config.candidate_strategy_id)
    cases = []
    for cost_bps, slippage_bps in [(0.0, 0.0), (10.0, 5.0), (25.0, 10.0), (50.0, 25.0)]:
        case_config = PerformanceRunConfig(
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            trading_days=config.trading_days,
            initial_equity=config.initial_equity,
        )
        result = run_strategy_backtest(universe, candidate, case_config)
        cases.append(
            {
                "cost_bps": cost_bps,
                "slippage_bps": slippage_bps,
                "total_return": result.metrics["total_return"],
                "cagr": result.metrics["cagr"],
                "max_drawdown": result.metrics["max_drawdown"],
                "calmar_ratio": result.metrics["calmar_ratio"],
                "passed": result.metrics["total_return"] > 0.0 and result.metrics["max_drawdown"] <= 0.20,
            }
        )
    return {
        "schema": "downside_performance_cost_stress_v1",
        "passed": all(case["passed"] for case in cases),
        "cases": cases,
    }


def _parameter_sensitivity(universe: Universe, config: PerformanceRunConfig) -> Dict[str, Any]:
    variants = []
    for momentum_window in [42, 63, 84]:
        for trend_window in [60, 80, 100]:
            strategy = StrategyConfig(
                "agentic_candidate_v1",
                "Agentic downside-guarded momentum variant",
                "candidate_variant",
                {
                    "momentum_window": momentum_window,
                    "short_guard_window": 3,
                    "trend_window": trend_window,
                    "drawdown_window": 42,
                    "drawdown_guard": 0.04,
                    "vol_window": 21,
                    "vol_guard": 0.020,
                    "top_n": 1,
                    "max_position_weight": 1.00,
                    "risk_off_weight": 0.25,
                    "risk_off_symbol": "DEFENSIVE_SYN",
                },
                is_candidate=True,
            )
            result = run_strategy_backtest(universe, strategy, config)
            variants.append(
                {
                    "momentum_window": momentum_window,
                    "trend_window": trend_window,
                    "cagr": result.metrics["cagr"],
                    "max_drawdown": result.metrics["max_drawdown"],
                    "calmar_ratio": result.metrics["calmar_ratio"],
                    "passed": result.metrics["total_return"] > 0.0
                    and result.metrics["max_drawdown"] <= 0.20
                    and result.metrics["calmar_ratio"] > 1.0,
                }
            )
    pass_rate = sum(1 for item in variants if item["passed"]) / float(len(variants))
    calmars = [item["calmar_ratio"] for item in variants]
    return {
        "schema": "downside_performance_parameter_sensitivity_v1",
        "passed": pass_rate >= 0.75 and min(calmars) > 0.5,
        "pass_rate": pass_rate,
        "min_calmar_ratio": min(calmars),
        "max_calmar_ratio": max(calmars),
        "variants": variants,
    }


def _lookahead_audit(universe: Universe, strategy: StrategyConfig) -> Dict[str, Any]:
    fn = _weight_function(strategy.strategy_id)
    changed = 0
    checked = 0
    for idx in range(1, len(_dates(universe)) - 1):
        mutated = _future_mutated_universe(universe, decision_idx=idx, multiplier=5.0)
        baseline = _normalize_weights(fn(universe, idx, strategy), universe)
        attacked = _normalize_weights(fn(mutated, idx, strategy), mutated)
        checked += 1
        if any(abs(baseline.get(symbol, 0.0) - attacked.get(symbol, 0.0)) > 1e-12 for symbol in universe):
            changed += 1
            if strategy.strategy_id != "leaky_future_momentum":
                break
    return {
        "schema": "downside_performance_lookahead_audit_v1",
        "passed": changed == 0,
        "checked_decisions": checked,
        "changed_decisions": changed,
        "reasons": ["weights_invariant_to_future_mutation"] if changed == 0 else ["future_mutation_changed_weights"],
    }


def _data_quality_summary(universe: Universe) -> Dict[str, Any]:
    asset_results = {}
    passed = True
    for symbol, bars in universe.items():
        result = run_data_quality_gate([bar.to_stock_bar() for bar in bars]).to_dict()
        asset_results[symbol] = {
            "verdict": result["verdict"]["verdict"],
            "error_count": result["metrics"]["error_count"],
            "warning_count": result["metrics"]["warning_count"],
            "bar_count": result["metrics"]["bar_count"],
        }
        passed = passed and result["verdict"]["verdict"] == "KEEP"
    return {
        "schema": "downside_performance_data_quality_v1",
        "passed": passed,
        "assets": asset_results,
    }


def _baseline_comparison(metrics_by_strategy: Mapping[str, Mapping[str, Any]], candidate_id: str) -> Dict[str, Any]:
    candidate = metrics_by_strategy[candidate_id]
    comparisons = {}
    for strategy_id, metrics in metrics_by_strategy.items():
        if strategy_id == candidate_id:
            continue
        comparisons["candidate_vs_" + strategy_id] = {
            "cagr_delta": candidate["cagr"] - metrics["cagr"],
            "total_return_multiple": _safe_div(1.0 + candidate["total_return"], 1.0 + metrics["total_return"]),
            "max_drawdown_delta": candidate["max_drawdown"] - metrics["max_drawdown"],
            "calmar_delta": candidate["calmar_ratio"] - metrics["calmar_ratio"],
            "sharpe_delta": candidate["sharpe_ratio"] - metrics["sharpe_ratio"],
        }
    return comparisons


def _rankings(metrics_by_strategy: Mapping[str, Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    ranking_fields = ["total_return", "cagr", "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
    rankings: Dict[str, List[Dict[str, Any]]] = {}
    for field_name in ranking_fields:
        rankings[field_name] = [
            {"rank": idx + 1, "strategy_id": strategy_id, "value": metrics[field_name]}
            for idx, (strategy_id, metrics) in enumerate(
                sorted(metrics_by_strategy.items(), key=lambda item: item[1][field_name], reverse=True)
            )
        ]
    rankings["max_drawdown"] = [
        {"rank": idx + 1, "strategy_id": strategy_id, "value": metrics["max_drawdown"]}
        for idx, (strategy_id, metrics) in enumerate(
            sorted(metrics_by_strategy.items(), key=lambda item: item[1]["max_drawdown"])
        )
    ]
    return rankings


def _metrics(curve: Sequence[PortfolioPoint], config: PerformanceRunConfig) -> Dict[str, Any]:
    returns = [point.daily_return for point in curve[1:]]
    equity_values = [point.equity for point in curve]
    total_return = equity_values[-1] / equity_values[0] - 1.0
    years = max(1.0 / config.trading_days, len(returns) / config.trading_days)
    cagr = (equity_values[-1] / equity_values[0]) ** (1.0 / years) - 1.0
    mean_daily = _mean(returns)
    volatility = _stddev(returns) * math.sqrt(config.trading_days)
    downside_returns = [min(0.0, value) for value in returns]
    downside_deviation = math.sqrt(_mean([value * value for value in downside_returns])) * math.sqrt(config.trading_days)
    annualized_return = mean_daily * config.trading_days
    max_drawdown = max(point.drawdown for point in curve)
    sharpe = _safe_div(annualized_return, volatility)
    sortino = _safe_div(annualized_return, downside_deviation)
    calmar = _safe_div(cagr, max_drawdown)
    return {
        "total_return": total_return,
        "return_multiple": 1.0 + total_return,
        "cagr": cagr,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "downside_deviation": downside_deviation,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "worst_month": _worst_period(curve, 7),
        "worst_year": _worst_period(curve, 4),
        "average_turnover": _mean([point.turnover for point in curve[1:]]),
        "total_turnover": sum(point.turnover for point in curve[1:]),
        "average_exposure": _mean([point.exposure for point in curve[1:]]),
        "trade_days": sum(1 for point in curve[1:] if point.turnover > 1e-12),
        "win_rate": _safe_div(sum(1 for value in returns if value > 0.0), len(returns)),
        "final_equity": equity_values[-1],
        "bar_count": len(curve),
    }


def _worst_period(curve: Sequence[PortfolioPoint], key_len: int) -> Dict[str, Any]:
    grouped: Dict[str, Tuple[float, float]] = {}
    for point in curve:
        key = point.date[:key_len]
        if key not in grouped:
            grouped[key] = (point.equity, point.equity)
        else:
            grouped[key] = (grouped[key][0], point.equity)
    returns = {key: end / start - 1.0 for key, (start, end) in grouped.items() if start > 0.0}
    if not returns:
        return {"period": "", "return": 0.0}
    period = min(returns, key=returns.get)
    return {"period": period, "return": returns[period]}


def _business_dates(start: Date, count: int) -> List[str]:
    dates: List[str] = []
    current = start
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _return_path(symbol: str, count: int) -> List[float]:
    values: List[float] = []
    for idx in range(count):
        regime = _regime(idx)
        seasonal = math.sin(idx / 17.0) * 0.0007 + math.cos(idx / 31.0) * 0.0004
        if symbol == "SPY_SYN":
            base = {
                "bull": 0.00100,
                "crash": -0.00320,
                "recovery": 0.00120,
                "sideways": 0.00005,
                "shock": -0.00220,
                "late_recovery": 0.00095,
            }[regime]
        elif symbol == "QUALITY_SYN":
            base = {
                "bull": 0.00135,
                "crash": -0.00120,
                "recovery": 0.00155,
                "sideways": 0.00045,
                "shock": -0.00100,
                "late_recovery": 0.00125,
            }[regime]
        elif symbol == "DEFENSIVE_SYN":
            base = {
                "bull": 0.00035,
                "crash": 0.00038,
                "recovery": 0.00030,
                "sideways": 0.00028,
                "shock": 0.00022,
                "late_recovery": 0.00025,
            }[regime]
        elif symbol == "TREND_SYN":
            base = {
                "bull": 0.00145,
                "crash": -0.00025,
                "recovery": 0.00165,
                "sideways": 0.00050,
                "shock": -0.00035,
                "late_recovery": 0.00135,
            }[regime]
        else:
            base = {
                "bull": 0.00160,
                "crash": -0.00460,
                "recovery": 0.00110,
                "sideways": 0.00010,
                "shock": -0.00350,
                "late_recovery": 0.00140,
            }[regime]
            seasonal *= 2.2
            if idx % 9 == 0:
                base -= 0.010
        if idx in {188, 189, 190, 515, 516} and symbol in {"SPY_SYN", "WHIPSAW_SYN"}:
            base -= 0.035
        if idx in {194, 195, 522} and symbol == "QUALITY_SYN":
            base -= 0.006
        if idx in {191, 517} and symbol == "TREND_SYN":
            base -= 0.004
        values.append(base + seasonal)
    return values


def _regime(idx: int) -> str:
    if idx < 180:
        return "bull"
    if idx < 260:
        return "crash"
    if idx < 430:
        return "recovery"
    if idx < 540:
        return "sideways"
    if idx < 610:
        return "shock"
    return "late_recovery"


def _bars_from_returns(symbol: str, dates: Sequence[str], start_price: float, returns: Sequence[float]) -> List[PerformanceBar]:
    bars: List[PerformanceBar] = []
    close = start_price
    for idx, day in enumerate(dates):
        open_price = close
        if idx > 0:
            close = max(1.0, close * (1.0 + returns[idx]))
        high = max(open_price, close) * 1.004
        low = min(open_price, close) * 0.996
        bars.append(
            PerformanceBar(
                date=day,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=1000000.0 + idx * 100.0 + len(symbol),
            )
        )
    return bars


def _dates(universe: Universe) -> List[str]:
    first = next(iter(universe.values()))
    return [bar.date for bar in first]


def _validate_universe(universe: Universe) -> None:
    if not universe:
        raise ValueError("universe must contain at least one asset")
    dates = None
    for symbol, bars in universe.items():
        if not bars:
            raise ValueError("empty bars for " + symbol)
        current = [bar.date for bar in bars]
        if dates is None:
            dates = current
        elif dates != current:
            raise ValueError("all assets must share dates")


def _empty_weights(universe: Universe) -> Dict[str, float]:
    return {symbol: 0.0 for symbol in universe}


def _normalize_weights(weights: Mapping[str, float], universe: Universe) -> Dict[str, float]:
    normalized = _empty_weights(universe)
    for symbol, weight in weights.items():
        if symbol not in universe:
            raise ValueError("weight references unknown symbol: " + symbol)
        normalized[symbol] = max(0.0, float(weight))
    total = sum(normalized.values())
    if total > 1.0:
        normalized = {symbol: value / total for symbol, value in normalized.items()}
    return normalized


def _asset_return(bars: Sequence[PerformanceBar], idx: int) -> float:
    previous = bars[idx - 1].close
    return 0.0 if previous <= 0.0 else bars[idx].close / previous - 1.0


def _sma(bars: Sequence[PerformanceBar], idx: int, window: int) -> float:
    start = max(0, idx - window + 1)
    values = [bar.close for bar in bars[start : idx + 1]]
    return _mean(values)


def _momentum(bars: Sequence[PerformanceBar], idx: int, lookback: int) -> float:
    if idx <= 0:
        return 0.0
    previous_idx = max(0, idx - lookback)
    previous = bars[previous_idx].close
    return 0.0 if previous <= 0.0 else bars[idx].close / previous - 1.0


def _rolling_drawdown(bars: Sequence[PerformanceBar], idx: int, window: int) -> float:
    start = max(0, idx - window + 1)
    closes = [bar.close for bar in bars[start : idx + 1]]
    peak = max(closes)
    return 0.0 if peak <= 0.0 else 1.0 - closes[-1] / peak


def _realized_vol(bars: Sequence[PerformanceBar], idx: int, window: int) -> float:
    if idx <= 1:
        return 0.0
    start = max(1, idx - window + 1)
    returns = [_asset_return(bars, item_idx) for item_idx in range(start, idx + 1)]
    return _stddev(returns)


def _mean(values: Sequence[float]) -> float:
    return 0.0 if not values else sum(values) / float(len(values))


def _stddev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / float(len(values) - 1))


def _safe_div(numerator: float, denominator: float) -> float:
    if abs(denominator) < 1e-12:
        if numerator > 0.0:
            return 999.0
        if numerator < 0.0:
            return -999.0
        return 0.0
    return numerator / denominator


def _rank_of(ranking: Sequence[Mapping[str, Any]], strategy_id: str) -> int:
    for item in ranking:
        if item["strategy_id"] == strategy_id:
            return int(item["rank"])
    return 999


def _strategy_by_id(strategies: Sequence[StrategyConfig], strategy_id: str) -> StrategyConfig:
    for strategy in strategies:
        if strategy.strategy_id == strategy_id:
            return strategy
    raise ValueError("strategy not found: " + strategy_id)


def _slice_universe(universe: Universe, start: int, end: int) -> Universe:
    return {symbol: list(bars[start:end]) for symbol, bars in universe.items()}


def _future_mutated_universe(universe: Universe, decision_idx: int, multiplier: float) -> Universe:
    mutated: Universe = {}
    for symbol, bars in universe.items():
        symbol_index = sorted(universe).index(symbol)
        copied = []
        for idx, bar in enumerate(bars):
            if idx <= decision_idx:
                factor = 1.0
            else:
                factor = multiplier if (idx + symbol_index) % 2 == 0 else 1.0 / multiplier
            copied.append(
                PerformanceBar(
                    date=bar.date,
                    open=bar.open * factor,
                    high=bar.high * factor,
                    low=bar.low * factor,
                    close=bar.close * factor,
                    volume=bar.volume,
                )
            )
        mutated[symbol] = copied
    return mutated


def _universe_summary(universe: Universe) -> Dict[str, Any]:
    dates = _dates(universe)
    return {
        "schema": "downside_performance_synthetic_universe_v1",
        "asset_ids": sorted(universe),
        "asset_count": len(universe),
        "bar_count": len(dates),
        "start": dates[0],
        "end": dates[-1],
        "data_type": "deterministic_synthetic_ohlcv",
        "survivorship_bias_note": "fixed included synthetic universe; no live market survivorship claim",
    }


def _claim_scope() -> Dict[str, Any]:
    return {
        "id": PERFORMANCE_CLAIM_ID,
        "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
        "claim_limit": PERFORMANCE_CLAIM_LIMIT,
        "positive_claim": PERFORMANCE_POSITIVE_CLAIM,
        "status": "supported_for_included_benchmark_suite",
        "performance_type": "hypothetical_backtested_performance",
        "non_claims": list(PERFORMANCE_NON_CLAIMS),
    }


def _claim_contract_payload() -> Dict[str, Any]:
    return {
        "schema": "downside_performance_claim_contract_v1",
        "claim_id": PERFORMANCE_CLAIM_ID,
        "benchmark_suite": PERFORMANCE_BENCHMARK_SUITE,
        "status_when_supported": "supported_for_included_benchmark_suite",
        "claim_limit": PERFORMANCE_CLAIM_LIMIT,
        "positive_claim": PERFORMANCE_POSITIVE_CLAIM,
        "non_claims": list(PERFORMANCE_NON_CLAIMS),
        "required_strategies": [strategy.strategy_id for strategy in default_strategy_registry()],
        "required_gate_checks": [
            "hypothetical_backtest_disclosed",
            "return_beats_baselines",
            "drawdown_control_passed",
            "calmar_top_ranked",
            "sharpe_top_three",
            "walk_forward_passed",
            "cost_stress_survived",
            "lookahead_audit_passed",
            "data_quality_passed",
            "overfit_not_detected",
            "negative_controls_detected",
            "claim_boundary_preserved",
        ],
    }


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _safe_clean(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    root = Path(__file__).resolve().parents[1].resolve()
    dist = (root / "dist").resolve()
    if dist not in resolved.parents and resolved != dist:
        raise ValueError("refusing to clean outside dist/: " + str(resolved))
    for child in output_dir.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            _safe_clean(child)
            child.rmdir()


def _file_entry(root: Path, path: Path) -> Dict[str, Any]:
    return {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_equity_curves_csv(report: DownsidePerformanceReport, path: Path) -> None:
    payload = report.to_dict()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "strategy_id", "equity", "daily_return", "drawdown", "exposure"],
        )
        writer.writeheader()
        for strategy_id, curve in sorted(payload["equity_curves_by_strategy"].items()):
            for point in curve:
                writer.writerow(
                    {
                        "date": point["date"],
                        "strategy_id": strategy_id,
                        "equity": point["equity"],
                        "daily_return": point["daily_return"],
                        "drawdown": point["drawdown"],
                        "exposure": point["exposure"],
                    }
                )


def _write_rebalance_trace_csv(report: DownsidePerformanceReport, path: Path) -> None:
    payload = report.to_dict()
    symbols = list(payload["universe"]["asset_ids"])
    fieldnames = ["date", "strategy_id", "turnover", "transaction_cost", "exposure"] + [
        "weight_" + symbol for symbol in symbols
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for strategy_id, curve in sorted(payload["equity_curves_by_strategy"].items()):
            for point in curve:
                if point["turnover"] <= 1e-12 and point["transaction_cost"] <= 1e-12:
                    continue
                row = {
                    "date": point["date"],
                    "strategy_id": strategy_id,
                    "turnover": point["turnover"],
                    "transaction_cost": point["transaction_cost"],
                    "exposure": point["exposure"],
                }
                for symbol in symbols:
                    row["weight_" + symbol] = point["weights"].get(symbol, 0.0)
                writer.writerow(row)
