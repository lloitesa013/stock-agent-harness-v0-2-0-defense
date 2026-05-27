from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _temporary_directory():
    base = os.environ.get('STOCK_HARNESS_TMPDIR')
    if base:
        Path(base).mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)
    return tempfile.TemporaryDirectory()


from angelos_os import (
    BacktestConfig,
    Bar,
    DataQualityConfig,
    ExternalEngineEquityPoint,
    ExternalEngineFill,
    ExternalEngineOrderIntent,
    ExternalEngineTrade,
    MarketCalendarProfile,
    MovingAverageCashStrategy,
    MultiAssetBenchmarkCase,
    audit_no_lookahead,
    create_experiment_manifest,
    run_backtest,
    run_cost_stress,
    run_data_quality_gate,
    run_engine_parity_check,
    run_ma_parameter_sweep,
    run_multi_asset_benchmark,
    run_regime_stress,
    run_stress_matrix,
    run_walk_forward,
    write_multi_asset_benchmark_report,
)


DEFAULT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    prices: Sequence[float]
    window: int = 3
    max_allowed_drawdown: float = 0.20


def benchmark_cases() -> List[BenchmarkCase]:
    return [
        BenchmarkCase(name="steady_up", prices=[100, 101, 102, 103, 104, 105, 106]),
        BenchmarkCase(name="crash", prices=[100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
        BenchmarkCase(name="whipsaw", prices=[100, 103, 99, 104, 98, 105, 97, 106]),
        BenchmarkCase(name="flat_then_spike", prices=[100, 100, 100, 200, 200]),
    ]


def run_oracle_case(case: BenchmarkCase) -> Dict[str, Any]:
    bars = _bars_from_prices(case.prices)
    config = BacktestConfig(max_allowed_drawdown=case.max_allowed_drawdown)
    strategy = MovingAverageCashStrategy(window=case.window)
    harness = run_backtest(bars, strategy, config)
    oracle = _oracle_ma_cash(bars, window=case.window, config=config)
    parity = _parity_report(harness, oracle)
    oracle_summary = {key: value for key, value in oracle.items() if key not in {"equity_curve", "trades", "order_intents"}}
    return {
        "case": asdict(case),
        "harness": {
            "verdict": harness.verdict.verdict,
            "reasons": harness.verdict.reasons,
            "total_return": harness.metrics["total_return"],
            "max_drawdown": harness.metrics["max_drawdown"],
            "benchmark_total_return": harness.benchmark_metrics["total_return"],
            "benchmark_max_drawdown": harness.benchmark_metrics["max_drawdown"],
            "trade_count": len(harness.trades),
            "final_equity": harness.equity_curve[-1].equity,
        },
        "oracle": oracle_summary,
        "parity": parity,
    }


def run_benchmark_suite() -> Dict[str, Any]:
    cases = [run_oracle_case(case) for case in benchmark_cases()]
    config = BacktestConfig(max_allowed_drawdown=0.20)
    lookahead_audit = audit_no_lookahead(
        lambda: MovingAverageCashStrategy(window=3),
        _bars_from_prices([100, 101, 102, 103, 104]),
    )
    walk_forward = run_walk_forward(
        _bars_from_prices([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75, 100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
        lambda: MovingAverageCashStrategy(window=3),
        train_size=3,
        test_size=8,
        step_size=11,
        config=config,
    )
    regime_stress = run_regime_stress(
        lambda: MovingAverageCashStrategy(window=3),
        config=config,
    )
    parameter_sweep = run_ma_parameter_sweep(
        _bars_from_prices([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75, 100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
        [2, 3, 4],
        train_size=3,
        test_size=8,
        step_size=11,
        config=config,
    )
    cost_stress = run_cost_stress(
        _bars_from_prices([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75, 100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
        lambda: MovingAverageCashStrategy(window=3),
        config=config,
    )
    stress_matrix_bars = _bars_from_prices(
        [100, 105, 110, 115, 120, 119, 118, 117, 116, 115, 100, 90, 80] * 2
    )
    stress_matrix = run_stress_matrix(
        stress_matrix_bars,
        lambda: MovingAverageCashStrategy(window=3),
        config=config,
    )
    multi_asset_benchmark = run_multi_asset_benchmark(
        [
            MultiAssetBenchmarkCase(
                name="synthetic_crash_asset",
                bars=_bars_from_prices([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
                tags={"regime": "crash", "source": "synthetic"},
            ),
            MultiAssetBenchmarkCase(
                name="synthetic_whipsaw_asset",
                bars=_bars_from_prices([100, 103, 99, 104, 98, 105, 97, 106]),
                tags={"regime": "whipsaw", "source": "synthetic"},
            ),
        ],
        lambda: MovingAverageCashStrategy(window=3),
        config=config,
        min_pass_rate=1.0,
    )
    manifest_bars = _bars_from_prices([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75])
    data_quality = run_data_quality_gate(manifest_bars)
    calendar_data_quality = run_data_quality_gate(
        [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-03", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-06", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        ],
        DataQualityConfig(
            market_calendar=MarketCalendarProfile(
                name="synthetic_calendar_profile",
                holidays=("2020-01-02",),
                half_days=("2020-01-03",),
            )
        ),
    )
    adjusted_ohlc_data_quality = run_data_quality_gate(
        [
            Bar(
                date="2020-01-01",
                open=100.0,
                high=102.0,
                low=98.0,
                close=101.0,
                volume=1000.0,
                adjusted_close=50.5,
                adjusted_open=50.0,
                adjusted_high=51.0,
                adjusted_low=49.0,
            ),
            Bar(
                date="2020-01-02",
                open=102.0,
                high=104.0,
                low=100.0,
                close=103.0,
                volume=1000.0,
                adjusted_close=51.5,
                adjusted_open=51.0,
                adjusted_high=52.0,
                adjusted_low=50.0,
            ),
        ]
    )
    manifest_backtest = run_backtest(manifest_bars, MovingAverageCashStrategy(window=3), config)
    oracle_trace = _oracle_ma_cash(manifest_bars, window=3, config=config)
    engine_parity = run_engine_parity_check(
        manifest_backtest,
        [
            ExternalEngineEquityPoint(
                date=point["date"],
                equity=point["equity"],
                benchmark_equity=point["benchmark_equity"],
            )
            for point in oracle_trace["equity_curve"]
        ],
        [
            ExternalEngineTrade(
                date=trade["date"],
                action=trade["action"],
                price=trade["price"],
                shares=trade["shares"],
                gross_value=trade["gross_value"],
            )
            for trade in oracle_trace["trades"]
        ],
        reference_fills=[
            ExternalEngineFill(
                date=trade["date"],
                action=trade["action"],
                price=trade["price"],
                shares=trade["shares"],
                gross_value=trade["gross_value"],
                fee=trade["fee"],
                pnl=trade["pnl"],
                target_exposure=trade["target_exposure"],
            )
            for trade in oracle_trace["trades"]
        ],
        reference_order_intents=[
            ExternalEngineOrderIntent(
                date=intent["date"],
                action=intent["action"],
                target_exposure=intent["target_exposure"],
                current_exposure=intent["current_exposure"],
                desired_shares=intent["desired_shares"],
                estimated_price=intent["estimated_price"],
            )
            for intent in oracle_trace["order_intents"]
        ],
        engine_name="no_dependency_oracle_trace_v1",
    )
    manifest = create_experiment_manifest(
        strategy_name="ma_cash_3",
        bars=manifest_bars,
        config=config,
        data_quality=data_quality,
        engine_parity=engine_parity,
        backtest=manifest_backtest,
        lookahead_audit=lookahead_audit,
        walk_forward=walk_forward,
        regime_stress=regime_stress,
        parameter_sweep=parameter_sweep,
        cost_stress=cost_stress,
        stress_matrix=stress_matrix,
        multi_asset_benchmark=multi_asset_benchmark,
    )
    with _temporary_directory() as tmpdir:
        multi_asset_report_paths = write_multi_asset_benchmark_report(multi_asset_benchmark, tmpdir)
        with Path(multi_asset_report_paths["case_manifest"]).open(newline="", encoding="utf-8") as handle:
            case_artifact_count = max(0, sum(1 for _ in handle) - 1)
    return {
        "benchmark": "stock_harness_no_dependency_oracle_v1",
        "all_passed": (
            all(case["parity"]["passed"] for case in cases)
            and data_quality.verdict.verdict == "KEEP"
            and calendar_data_quality.verdict.verdict == "KEEP"
            and adjusted_ohlc_data_quality.verdict.verdict == "KEEP"
            and engine_parity.verdict.verdict == "KEEP"
            and lookahead_audit.passed
            and walk_forward.verdict.verdict == "KEEP"
            and regime_stress.verdict.verdict == "KEEP"
            and parameter_sweep.verdict.verdict == "KEEP"
            and cost_stress.verdict.verdict == "KEEP"
            and stress_matrix.verdict.verdict == "KEEP"
            and multi_asset_benchmark.verdict.verdict == "KEEP"
            and manifest["schema"] == "angelos_stock_experiment_manifest_v1"
            and case_artifact_count == len(multi_asset_benchmark.cases)
        ),
        "cases": cases,
        "data_quality": {
            "verdict": asdict(data_quality.verdict),
            "metrics": data_quality.metrics,
        },
        "calendar_data_quality": {
            "verdict": asdict(calendar_data_quality.verdict),
            "metrics": calendar_data_quality.metrics,
        },
        "adjusted_ohlc_data_quality": {
            "verdict": asdict(adjusted_ohlc_data_quality.verdict),
            "metrics": adjusted_ohlc_data_quality.metrics,
        },
        "engine_parity": engine_parity.to_dict(),
        "lookahead_audit": asdict(lookahead_audit),
        "walk_forward": {
            "verdict": asdict(walk_forward.verdict),
            "metrics": walk_forward.metrics,
        },
        "regime_stress": {
            "verdict": asdict(regime_stress.verdict),
            "metrics": regime_stress.metrics,
        },
        "parameter_sweep": {
            "verdict": asdict(parameter_sweep.verdict),
            "metrics": parameter_sweep.metrics,
            "best_window": parameter_sweep.best_window,
        },
        "cost_stress": {
            "verdict": asdict(cost_stress.verdict),
            "metrics": cost_stress.metrics,
        },
        "stress_matrix": {
            "verdict": asdict(stress_matrix.verdict),
            "metrics": stress_matrix.metrics,
        },
        "multi_asset_benchmark": {
            "verdict": asdict(multi_asset_benchmark.verdict),
            "metrics": multi_asset_benchmark.metrics,
            "report_artifact_keys": sorted(multi_asset_report_paths.keys()),
            "case_artifact_count": case_artifact_count,
        },
        "manifest": {
            "schema": manifest["schema"],
            "fingerprint": manifest["data"]["fingerprint"],
            "artifact_keys": sorted(manifest["artifacts"].keys()),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run no-dependency oracle parity checks for the stock harness.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = run_benchmark_suite()
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["all_passed"] else 1


def _bars_from_prices(prices: Sequence[float]) -> List[Bar]:
    return [
        Bar(
            date=f"2020-01-{idx + 1:02d}",
            open=float(price),
            high=float(price),
            low=float(price),
            close=float(price),
            volume=1000.0,
        )
        for idx, price in enumerate(prices)
    ]


def _oracle_ma_cash(bars: Sequence[Bar], *, window: int, config: BacktestConfig) -> Dict[str, Any]:
    cash = config.initial_capital
    shares = 0.0
    entry_cost = 0.0
    gross_turnover = 0.0
    completed_exits = 0
    winning_exits = 0
    trades = []
    order_intents = []
    equity_curve = []
    fee_rate = config.fee_bps / 10000.0
    slippage_rate = config.slippage_bps / 10000.0
    equity_peak = config.initial_capital
    benchmark_peak = config.initial_capital
    benchmark_start = bars[0].close

    for idx, bar in enumerate(bars):
        history = bars[:idx]
        target = _oracle_target_exposure(history, window)
        if target > 0.5 and shares <= 0.0:
            fill_price = bar.open * (1.0 + slippage_rate)
            desired_shares = cash / (fill_price * (1.0 + fee_rate))
            order_intents.append(
                {
                    "date": bar.date,
                    "action": "buy",
                    "target_exposure": target,
                    "current_exposure": _oracle_portfolio_exposure(cash, shares, bar.close),
                    "desired_shares": desired_shares,
                    "estimated_price": fill_price,
                }
            )
            shares = desired_shares
            gross_value = shares * fill_price
            fee = gross_value * fee_rate
            cash -= gross_value + fee
            entry_cost = gross_value + fee
            gross_turnover += gross_value
            trades.append(
                {
                    "date": bar.date,
                    "action": "buy",
                    "price": fill_price,
                    "shares": shares,
                    "gross_value": gross_value,
                    "fee": fee,
                    "pnl": 0.0,
                    "target_exposure": 1.0,
                }
            )
        elif target <= 0.5 and shares > 0.0:
            fill_price = bar.open * (1.0 - slippage_rate)
            order_intents.append(
                {
                    "date": bar.date,
                    "action": "sell",
                    "target_exposure": target,
                    "current_exposure": _oracle_portfolio_exposure(cash, shares, bar.close),
                    "desired_shares": shares,
                    "estimated_price": fill_price,
                }
            )
            gross_value = shares * fill_price
            fee = gross_value * fee_rate
            proceeds = gross_value - fee
            pnl = proceeds - entry_cost
            cash += proceeds
            gross_turnover += gross_value
            completed_exits += 1
            if pnl > 0.0:
                winning_exits += 1
            trades.append(
                {
                    "date": bar.date,
                    "action": "sell",
                    "price": fill_price,
                    "shares": shares,
                    "gross_value": gross_value,
                    "fee": fee,
                    "pnl": pnl,
                    "target_exposure": 0.0,
                }
            )
            shares = 0.0
            entry_cost = 0.0

        equity = cash + shares * bar.close
        equity_peak = max(equity_peak, equity)
        benchmark_equity = config.initial_capital * (bar.close / benchmark_start)
        benchmark_peak = max(benchmark_peak, benchmark_equity)
        equity_curve.append(
            {
                "date": bar.date,
                "equity": equity,
                "benchmark_equity": benchmark_equity,
                "drawdown": 0.0 if equity_peak <= 0.0 else 1.0 - equity / equity_peak,
                "benchmark_drawdown": 0.0 if benchmark_peak <= 0.0 else 1.0 - benchmark_equity / benchmark_peak,
                "exposure": 0.0 if equity <= 0.0 else max(0.0, min(1.0, shares * bar.close / equity)),
            }
        )

    total_return = equity_curve[-1]["equity"] / config.initial_capital - 1.0
    benchmark_total_return = equity_curve[-1]["benchmark_equity"] / config.initial_capital - 1.0
    max_drawdown = max(point["drawdown"] for point in equity_curve)
    benchmark_max_drawdown = max(point["benchmark_drawdown"] for point in equity_curve)
    verdict = _oracle_verdict(
        bar_count=len(bars),
        window=window,
        max_drawdown=max_drawdown,
        benchmark_max_drawdown=benchmark_max_drawdown,
        max_allowed_drawdown=config.max_allowed_drawdown,
    )
    return {
        "verdict": verdict,
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "benchmark_total_return": benchmark_total_return,
        "benchmark_max_drawdown": benchmark_max_drawdown,
        "trade_count": len(trades),
        "trade_actions": [(trade["action"], trade["date"]) for trade in trades],
        "trades": trades,
        "order_intents": order_intents,
        "equity_curve": equity_curve,
        "final_equity": equity_curve[-1]["equity"],
        "exposure_ratio": sum(point["exposure"] for point in equity_curve) / len(equity_curve),
        "turnover": gross_turnover / config.initial_capital,
        "win_rate": 0.0 if completed_exits == 0 else winning_exits / completed_exits,
    }


def _oracle_target_exposure(history: Sequence[Bar], window: int) -> float:
    if len(history) < window:
        return 0.0
    moving_average = sum(bar.close for bar in history[-window:]) / float(window)
    return 1.0 if history[-1].close > moving_average else 0.0


def _oracle_portfolio_exposure(cash: float, shares: float, close: float) -> float:
    equity = cash + shares * close
    if equity <= 0.0:
        return 0.0
    return max(0.0, min(1.0, shares * close / equity))


def _oracle_verdict(
    *,
    bar_count: int,
    window: int,
    max_drawdown: float,
    benchmark_max_drawdown: float,
    max_allowed_drawdown: float,
) -> str:
    if bar_count <= window:
        return "ITERATE"
    if max_drawdown > max_allowed_drawdown or max_drawdown >= benchmark_max_drawdown:
        return "REJECT"
    return "KEEP"


def _parity_report(harness: Any, oracle: Dict[str, Any]) -> Dict[str, Any]:
    checks = {
        "verdict": harness.verdict.verdict == oracle["verdict"],
        "total_return": _close(harness.metrics["total_return"], oracle["total_return"]),
        "max_drawdown": _close(harness.metrics["max_drawdown"], oracle["max_drawdown"]),
        "benchmark_total_return": _close(
            harness.benchmark_metrics["total_return"],
            oracle["benchmark_total_return"],
        ),
        "benchmark_max_drawdown": _close(
            harness.benchmark_metrics["max_drawdown"],
            oracle["benchmark_max_drawdown"],
        ),
        "trade_count": len(harness.trades) == oracle["trade_count"],
        "final_equity": _close(harness.equity_curve[-1].equity, oracle["final_equity"]),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
    }


def _close(left: float, right: float, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


if __name__ == "__main__":
    raise SystemExit(main())

