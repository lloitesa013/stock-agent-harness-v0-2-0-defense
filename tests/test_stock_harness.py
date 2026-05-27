import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

def _temporary_directory():
    base = os.environ.get('STOCK_HARNESS_TMPDIR')
    if base:
        Path(base).mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)
    return tempfile.TemporaryDirectory()


from ops.benchmark_stock_harness import benchmark_cases, run_benchmark_suite, run_oracle_case
from ops.compare_stock_harness_baselines import run_comparison
from ops.compare_stock_harness_global_frameworks import (
    EXTERNAL_FRAMEWORK_PROFILES,
    _evaluate_publication_requirements,
    _load_claim_contract as _load_global_claim_contract,
    run_global_comparison,
)
from ops.run_stock_harness_release_gate import _build_assertions, _parse_json_stdout
from ops.run_stock_harness_official_claim_gate import (
    _build_assertions as _build_official_claim_assertions,
)
from ops.build_stock_harness_official_claim_packet import build_official_claim_packet
from ops.verify_stock_harness_official_claim_packet import verify_official_claim_packet
from ops.build_stock_harness_release_bundle import DEFAULT_OUTPUT_DIR, RELEASE_FILES, build_release_bundle, _validate_release_files
from ops.build_stock_harness_evidence_packet import (
    DEFAULT_OUTPUT_DIR as EVIDENCE_PACKET_OUTPUT_DIR,
    build_evidence_packet,
)
from ops.verify_stock_harness_evidence_packet import verify_evidence_packet
from ops.build_stock_harness_release_candidate import (
    DEFAULT_OUTPUT_DIR as RELEASE_CANDIDATE_OUTPUT_DIR,
    build_release_candidate,
)
from ops.verify_stock_harness_release_candidate import verify_release_candidate
from ops.replay_stock_harness_release_candidate import replay_release_candidate
from ops.audit_stock_harness_release import (
    CLAIM_CONTRACT_PATH as AUDIT_CLAIM_CONTRACT_PATH,
    _broad_claim_phrase_check,
    _ci_check,
    _claim_contract_check,
    _docs_check,
    _expected_summary_check,
    _manifest_check,
    _release_file_check,
    run_audit,
)

from angelos_os import (
    BacktestConfig,
    Bar,
    CostStressCase,
    DataQualityConfig,
    ExternalEngineEquityPoint,
    ExternalEngineFill,
    ExternalEngineOrderIntent,
    ExternalEngineTrade,
    MarketCalendarProfile,
    MovingAverageCashStrategy,
    MultiAssetBenchmarkCase,
    StressMatrixCase,
    audit_no_lookahead,
    create_experiment_manifest,
    default_cost_stress_cases,
    default_regime_stress_cases,
    default_stress_matrix_cases,
    load_engine_equity_csv,
    load_engine_fills_csv,
    load_engine_order_intents_csv,
    load_engine_trades_csv,
    load_market_calendar_csv,
    load_multi_asset_csv_directory,
    load_ohlcv_csv,
    run_backtest,
    run_cost_stress,
    run_data_quality_gate,
    run_engine_parity_check,
    run_ma_parameter_sweep,
    run_multi_asset_benchmark,
    run_regime_stress,
    run_stress_matrix,
    run_walk_forward,
    write_engine_parity_report,
    write_experiment_manifest,
    write_multi_asset_case_artifacts,
    write_multi_asset_benchmark_report,
    write_stock_report,
)


def make_bars(prices):
    bars = []
    for idx, price in enumerate(prices, start=1):
        bars.append(
            Bar(
                date=f"2020-01-{idx:02d}",
                open=float(price),
                high=float(price),
                low=float(price),
                close=float(price),
                volume=1000.0,
            )
        )
    return bars


def external_equity_from_result(result):
    return [
        ExternalEngineEquityPoint(
            date=point.date,
            equity=point.equity,
            benchmark_equity=point.benchmark_equity,
        )
        for point in result.equity_curve
    ]


def external_trades_from_result(result):
    return [
        ExternalEngineTrade(
            date=trade.date,
            action=trade.action,
            price=trade.price,
            shares=trade.shares,
            gross_value=trade.gross_value,
        )
        for trade in result.trades
    ]


def external_fills_from_result(result):
    return [
        ExternalEngineFill(
            date=trade.date,
            action=trade.action,
            price=trade.price,
            shares=trade.shares,
            gross_value=trade.gross_value,
            fee=trade.fee,
            pnl=trade.pnl,
            target_exposure=trade.target_exposure,
        )
        for trade in result.trades
    ]


def external_order_intents_from_result(result):
    return [
        ExternalEngineOrderIntent(
            date=intent.date,
            action=intent.action,
            target_exposure=intent.target_exposure,
            current_exposure=intent.current_exposure,
            desired_shares=intent.desired_shares,
            estimated_price=intent.estimated_price,
        )
        for intent in result.order_intents
    ]


class AlwaysLongStrategy:
    name = "always_long"
    min_history = 0

    def target_exposure(self, history):
        return 1.0


class FuturePeekStrategy:
    name = "future_peek"
    min_history = 0

    def __init__(self, bars):
        self.bars = bars

    def target_exposure(self, history):
        if not history:
            return 0.0
        next_idx = len(history)
        if next_idx >= len(self.bars):
            return 0.0
        return 1.0 if self.bars[next_idx].close > history[-1].close else 0.0


class StockHarnessTest(unittest.TestCase):
    def test_csv_parser_accepts_valid_ohlcv(self):
        with _temporary_directory() as tmpdir:
            path = Path(tmpdir) / "bars.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "date",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "Adj Open",
                        "Adj High",
                        "Adj Low",
                        "Adj Close",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2020-01-01",
                        "open": "100",
                        "high": "101",
                        "low": "99",
                        "close": "100.5",
                        "volume": "1000",
                        "Adj Open": "99.25",
                        "Adj High": "100.25",
                        "Adj Low": "98.25",
                        "Adj Close": "99.75",
                    }
                )

            bars = load_ohlcv_csv(path)

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].date, "2020-01-01")
        self.assertAlmostEqual(bars[0].close, 100.5)
        self.assertAlmostEqual(bars[0].adjusted_open or 0.0, 99.25)
        self.assertAlmostEqual(bars[0].adjusted_high or 0.0, 100.25)
        self.assertAlmostEqual(bars[0].adjusted_low or 0.0, 98.25)
        self.assertAlmostEqual(bars[0].adjusted_close or 0.0, 99.75)

    def test_csv_parser_rejects_missing_and_invalid_fields(self):
        with _temporary_directory() as tmpdir:
            missing = Path(tmpdir) / "missing.csv"
            missing.write_text("date,open,high,low,close\n2020-01-01,1,1,1,1\n", encoding="utf-8")
            invalid = Path(tmpdir) / "invalid.csv"
            invalid.write_text(
                "date,open,high,low,close,volume\n2020-01-01,100,90,99,100,1000\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_ohlcv_csv(missing)
            with self.assertRaises(ValueError):
                load_ohlcv_csv(invalid)

    def test_ma_strategy_is_lagged_and_cannot_react_to_future_spike(self):
        strategy = MovingAverageCashStrategy(window=3)
        spike_only = run_backtest(make_bars([100, 100, 100, 200]), strategy)
        self.assertEqual(spike_only.trades, [])

        next_day = run_backtest(make_bars([100, 100, 100, 200, 200]), strategy)
        self.assertEqual(len(next_day.trades), 1)
        self.assertEqual(next_day.trades[0].action, "buy")
        self.assertEqual(next_day.trades[0].date, "2020-01-05")

    def test_buy_and_hold_benchmark_is_produced_for_every_run(self):
        result = run_backtest(make_bars([100, 101, 102, 103, 104]), MovingAverageCashStrategy(window=3))

        self.assertIn("total_return", result.benchmark_metrics)
        self.assertEqual(len(result.equity_curve), 5)
        self.assertAlmostEqual(result.equity_curve[0].benchmark_equity, 10000.0)
        self.assertGreater(result.equity_curve[-1].benchmark_equity, result.equity_curve[0].benchmark_equity)

    def test_data_quality_gate_keeps_clean_daily_bars(self):
        result = run_data_quality_gate(make_bars([100, 101, 102, 103, 104]))

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.verdict.reasons, ["data_quality_clean"])
        self.assertEqual(result.metrics["bar_count"], 5)
        self.assertEqual(result.metrics["error_count"], 0)
        self.assertTrue(result.metrics["date_checks_applied"])

    def test_data_quality_gate_rejects_structural_csv_defects(self):
        bars = [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=0.0),
            Bar(date="2020-01-03", open=100.0, high=99.0, low=98.0, close=100.0, volume=1000.0),
        ]

        result = run_data_quality_gate(bars)
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("duplicate_date", codes)
        self.assertIn("non_monotonic_date", codes)
        self.assertIn("invalid_ohlcv", codes)
        self.assertIn("zero_volume", codes)
        self.assertEqual(result.metrics["duplicate_dates"], 1)
        self.assertEqual(result.metrics["zero_volume_count"], 1)

    def test_data_quality_gate_detects_missing_dates_and_split_like_jumps(self):
        bars = [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-10", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-13", open=50.0, high=51.0, low=49.0, close=50.0, volume=1000.0),
        ]

        result = run_data_quality_gate(bars)
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("missing_business_dates", codes)
        self.assertIn("suspicious_open_gap", codes)
        self.assertIn("split_like_close_jump", codes)
        self.assertGreaterEqual(result.metrics["missing_business_days"], 6)
        self.assertGreater(result.metrics["max_close_jump_ratio"], 0.45)

    def test_data_quality_gate_detects_adjusted_close_ratio_jumps(self):
        bars = [
            Bar(
                date="2020-01-01",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0,
                adjusted_close=100.0,
            ),
            Bar(
                date="2020-01-02",
                open=101.0,
                high=102.0,
                low=100.0,
                close=101.0,
                volume=1000.0,
                adjusted_close=101.0,
            ),
            Bar(
                date="2020-01-03",
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.0,
                volume=1000.0,
                adjusted_close=50.0,
            ),
        ]

        result = run_data_quality_gate(bars)
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("adjustment_ratio_jump", codes)
        self.assertTrue(result.metrics["adjustment_checks_applied"])
        self.assertEqual(result.metrics["adjusted_close_count"], 3)
        self.assertGreater(result.metrics["max_adjustment_ratio_change"], 0.50)

    def test_data_quality_gate_rejects_mixed_adjusted_close_coverage(self):
        bars = [
            Bar(
                date="2020-01-01",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0,
                adjusted_close=100.0,
            ),
            Bar(date="2020-01-02", open=101.0, high=102.0, low=100.0, close=101.0, volume=1000.0),
        ]

        result = run_data_quality_gate(bars)
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("mixed_adjusted_close", codes)
        self.assertFalse(result.metrics["adjustment_checks_applied"])
        self.assertEqual(result.metrics["adjusted_close_count"], 1)

    def test_data_quality_gate_accepts_consistent_adjusted_ohlc(self):
        bars = [
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

        result = run_data_quality_gate(bars)

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertTrue(result.metrics["adjusted_ohlc_checks_applied"])
        self.assertEqual(result.metrics["adjusted_ohlc_count"], 2)
        self.assertEqual(result.metrics["partial_adjusted_ohlc_count"], 0)
        self.assertEqual(result.metrics["max_adjusted_ohlc_ratio_spread"], 0.0)

    def test_data_quality_gate_rejects_adjusted_ohlc_ratio_mismatch(self):
        bars = [
            Bar(
                date="2020-01-01",
                open=100.0,
                high=102.0,
                low=98.0,
                close=101.0,
                volume=1000.0,
                adjusted_close=50.5,
                adjusted_open=100.0,
                adjusted_high=102.0,
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

        result = run_data_quality_gate(bars)
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("adjusted_ohlc_ratio_mismatch", codes)
        self.assertGreater(result.metrics["max_adjusted_ohlc_ratio_spread"], 0.40)

    def test_data_quality_gate_rejects_mixed_adjusted_ohlc_coverage(self):
        bars = [
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
            ),
        ]

        result = run_data_quality_gate(bars)
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("mixed_adjusted_ohlc", codes)
        self.assertFalse(result.metrics["adjusted_ohlc_checks_applied"])
        self.assertEqual(result.metrics["adjusted_ohlc_count"], 1)
        self.assertEqual(result.metrics["partial_adjusted_ohlc_count"], 1)

    def test_data_quality_gate_can_tolerate_sparse_local_feeds_by_config(self):
        bars = [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-10", open=100.0, high=101.0, low=99.0, close=100.0, volume=0.0),
        ]

        result = run_data_quality_gate(
            bars,
            DataQualityConfig(max_missing_business_days_per_gap=10, max_zero_volume_ratio=0.50),
        )

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["zero_volume_ratio"], 0.50)
        self.assertEqual(result.metrics["error_count"], 0)

    def test_market_calendar_csv_loader_accepts_local_status_file(self):
        with _temporary_directory() as tmpdir:
            path = Path(tmpdir) / "calendar.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "status"])
                writer.writeheader()
                writer.writerow({"date": "2020-01-01", "status": "open"})
                writer.writerow({"date": "2020-01-02", "status": "half_day"})
                writer.writerow({"date": "2020-01-03", "status": "holiday"})

            profile = load_market_calendar_csv(path, name="unit_calendar")

        self.assertEqual(profile.name, "unit_calendar")
        self.assertEqual(profile.expected_sessions, ("2020-01-01", "2020-01-02"))
        self.assertEqual(profile.half_days, ("2020-01-02",))
        self.assertEqual(profile.holidays, ("2020-01-03",))

    def test_data_quality_gate_applies_market_calendar_holidays_and_half_days(self):
        profile = MarketCalendarProfile(
            name="unit_xnys",
            holidays=("2020-01-02",),
            half_days=("2020-01-03",),
        )
        bars = [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-03", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-06", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        ]

        result = run_data_quality_gate(bars, DataQualityConfig(market_calendar=profile))

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertTrue(result.metrics["calendar_profile_applied"])
        self.assertEqual(result.metrics["calendar_profile_name"], "unit_xnys")
        self.assertEqual(result.metrics["calendar_expected_sessions"], 3)
        self.assertEqual(result.metrics["calendar_missing_sessions"], 0)
        self.assertEqual(result.metrics["calendar_unexpected_sessions"], 0)
        self.assertEqual(result.metrics["calendar_half_day_count"], 1)

    def test_data_quality_gate_rejects_missing_market_calendar_session(self):
        profile = MarketCalendarProfile(
            name="explicit_unit_calendar",
            expected_sessions=("2020-01-01", "2020-01-02", "2020-01-03"),
        )
        bars = [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-03", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        ]

        result = run_data_quality_gate(bars, DataQualityConfig(market_calendar=profile))
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("missing_calendar_sessions", codes)
        self.assertEqual(result.metrics["calendar_expected_sessions"], 3)
        self.assertEqual(result.metrics["calendar_missing_sessions"], 1)

    def test_data_quality_gate_rejects_bar_on_closed_market_calendar_session(self):
        profile = MarketCalendarProfile(name="unit_holiday_calendar", holidays=("2020-01-02",))
        bars = [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-02", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        ]

        result = run_data_quality_gate(bars, DataQualityConfig(market_calendar=profile))
        codes = {issue.code for issue in result.issues}

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertIn("non_trading_session", codes)
        self.assertEqual(result.metrics["calendar_unexpected_sessions"], 1)

    def test_engine_parity_accepts_matching_external_trace(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
            MovingAverageCashStrategy(window=3),
            BacktestConfig(max_allowed_drawdown=0.20),
        )

        parity = run_engine_parity_check(
            result,
            external_equity_from_result(result),
            external_trades_from_result(result),
            reference_fills=external_fills_from_result(result),
            reference_order_intents=external_order_intents_from_result(result),
            engine_name="unit_reference",
        )

        self.assertEqual(parity.verdict.verdict, "KEEP")
        self.assertTrue(all(parity.checks.values()))
        self.assertEqual(parity.metrics["compared_equity_points"], len(result.equity_curve))
        self.assertEqual(parity.metrics["compared_fills"], len(result.trades))
        self.assertEqual(parity.metrics["compared_order_intents"], len(result.order_intents))

    def test_engine_parity_rejects_external_equity_drift(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90]),
            MovingAverageCashStrategy(window=3),
        )
        reference = external_equity_from_result(result)
        reference[-1] = ExternalEngineEquityPoint(
            date=reference[-1].date,
            equity=reference[-1].equity + 25.0,
            benchmark_equity=reference[-1].benchmark_equity,
        )

        parity = run_engine_parity_check(result, reference, external_trades_from_result(result))

        self.assertEqual(parity.verdict.verdict, "REJECT")
        self.assertFalse(parity.checks["equity_values"])
        self.assertGreater(parity.metrics["max_equity_abs_error"], 20.0)
        self.assertEqual(parity.metrics["diff_count"], 1)
        self.assertFalse(parity.metrics["diffs_truncated"])
        self.assertEqual(len(parity.diffs), 1)
        self.assertEqual(parity.diffs[0].code, "equity_value_mismatch")
        self.assertEqual(parity.diffs[0].field, "equity")
        self.assertEqual(parity.to_dict()["diffs"][0]["code"], "equity_value_mismatch")

    def test_engine_parity_caps_compact_diff_samples(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90]),
            MovingAverageCashStrategy(window=3),
        )
        reference = external_equity_from_result(result)
        reference[0] = ExternalEngineEquityPoint(
            date=reference[0].date,
            equity=reference[0].equity + 10.0,
            benchmark_equity=reference[0].benchmark_equity,
        )
        reference[-1] = ExternalEngineEquityPoint(
            date=reference[-1].date,
            equity=reference[-1].equity + 25.0,
            benchmark_equity=reference[-1].benchmark_equity,
        )

        parity = run_engine_parity_check(result, reference, external_trades_from_result(result), max_diffs=1)

        self.assertEqual(parity.verdict.verdict, "REJECT")
        self.assertEqual(parity.metrics["diff_count"], 2)
        self.assertTrue(parity.metrics["diffs_truncated"])
        self.assertEqual(len(parity.diffs), 1)
        self.assertEqual(parity.diffs[0].index, 0)

    def test_engine_parity_rejects_trade_trace_mismatch(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
            MovingAverageCashStrategy(window=3),
        )
        trades = external_trades_from_result(result)
        trades[0] = ExternalEngineTrade(
            date=trades[0].date,
            action="sell",
            price=trades[0].price,
            shares=trades[0].shares,
            gross_value=trades[0].gross_value,
        )

        parity = run_engine_parity_check(result, external_equity_from_result(result), trades)

        self.assertEqual(parity.verdict.verdict, "REJECT")
        self.assertFalse(parity.checks["trade_actions"])
        self.assertEqual(parity.diffs[0].code, "trade_action_mismatch")

    def test_engine_parity_rejects_fill_ledger_mismatch(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
            MovingAverageCashStrategy(window=3),
        )
        fills = external_fills_from_result(result)
        fills[0] = ExternalEngineFill(
            date=fills[0].date,
            action=fills[0].action,
            price=fills[0].price,
            shares=fills[0].shares,
            gross_value=fills[0].gross_value,
            fee=(fills[0].fee or 0.0) + 1.0,
            pnl=fills[0].pnl,
            target_exposure=fills[0].target_exposure,
        )

        parity = run_engine_parity_check(
            result,
            external_equity_from_result(result),
            external_trades_from_result(result),
            reference_fills=fills,
        )

        self.assertEqual(parity.verdict.verdict, "REJECT")
        self.assertFalse(parity.checks["fill_values"])
        self.assertGreater(parity.metrics["max_fill_fee_abs_error"], 0.9)
        self.assertEqual(parity.diffs[0].code, "fill_value_mismatch")
        self.assertEqual(parity.diffs[0].field, "fee")

    def test_engine_parity_rejects_order_intent_mismatch(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
            MovingAverageCashStrategy(window=3),
        )
        intents = external_order_intents_from_result(result)
        intents[0] = ExternalEngineOrderIntent(
            date=intents[0].date,
            action=intents[0].action,
            target_exposure=0.0,
            current_exposure=intents[0].current_exposure,
            desired_shares=intents[0].desired_shares,
            estimated_price=intents[0].estimated_price,
        )

        parity = run_engine_parity_check(
            result,
            external_equity_from_result(result),
            external_trades_from_result(result),
            reference_order_intents=intents,
        )

        self.assertEqual(parity.verdict.verdict, "REJECT")
        self.assertFalse(parity.checks["order_intent_values"])
        self.assertEqual(parity.diffs[0].code, "order_intent_value_mismatch")
        self.assertEqual(parity.diffs[0].field, "target_exposure")

    def test_engine_parity_loads_external_csv_traces(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
            MovingAverageCashStrategy(window=3),
        )
        with _temporary_directory() as tmpdir:
            equity_path = Path(tmpdir) / "external_equity.csv"
            trade_path = Path(tmpdir) / "external_trades.csv"
            fill_path = Path(tmpdir) / "external_fills.csv"
            intent_path = Path(tmpdir) / "external_order_intents.csv"
            with equity_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "equity", "benchmark_equity"])
                writer.writeheader()
                for point in result.equity_curve:
                    writer.writerow(
                        {
                            "date": point.date,
                            "equity": point.equity,
                            "benchmark_equity": point.benchmark_equity,
                        }
                    )
            with trade_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "action", "price", "shares", "gross_value"])
                writer.writeheader()
                for trade in result.trades:
                    writer.writerow(
                        {
                            "date": trade.date,
                            "action": trade.action,
                            "price": trade.price,
                            "shares": trade.shares,
                            "gross_value": trade.gross_value,
                        }
                    )
            with fill_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["date", "action", "price", "shares", "gross_value", "fee", "pnl", "target_exposure"],
                )
                writer.writeheader()
                for trade in result.trades:
                    writer.writerow(
                        {
                            "date": trade.date,
                            "action": trade.action,
                            "price": trade.price,
                            "shares": trade.shares,
                            "gross_value": trade.gross_value,
                            "fee": trade.fee,
                            "pnl": trade.pnl,
                            "target_exposure": trade.target_exposure,
                        }
                    )
            with intent_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "date",
                        "action",
                        "target_exposure",
                        "current_exposure",
                        "desired_shares",
                        "estimated_price",
                    ],
                )
                writer.writeheader()
                for intent in result.order_intents:
                    writer.writerow(
                        {
                            "date": intent.date,
                            "action": intent.action,
                            "target_exposure": intent.target_exposure,
                            "current_exposure": intent.current_exposure,
                            "desired_shares": intent.desired_shares,
                            "estimated_price": intent.estimated_price,
                        }
                    )

            parity = run_engine_parity_check(
                result,
                load_engine_equity_csv(equity_path),
                load_engine_trades_csv(trade_path),
                reference_fills=load_engine_fills_csv(fill_path),
                reference_order_intents=load_engine_order_intents_csv(intent_path),
                engine_name="csv_reference",
            )

        self.assertEqual(parity.verdict.verdict, "KEEP")
        self.assertEqual(parity.engine_name, "csv_reference")
        self.assertEqual(parity.metrics["reference_fill_count"], len(result.trades))
        self.assertEqual(parity.metrics["reference_order_intent_count"], len(result.order_intents))

    def test_engine_parity_report_writer_creates_summary_and_diff_csv(self):
        result = run_backtest(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90]),
            MovingAverageCashStrategy(window=3),
        )
        reference = external_equity_from_result(result)
        reference[-1] = ExternalEngineEquityPoint(
            date=reference[-1].date,
            equity=reference[-1].equity + 25.0,
            benchmark_equity=reference[-1].benchmark_equity,
        )
        parity = run_engine_parity_check(result, reference, external_trades_from_result(result), engine_name="unit_reference")

        with _temporary_directory() as tmpdir:
            paths = write_engine_parity_report(parity, tmpdir)
            summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
            with Path(paths["diffs"]).open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(summary["engine_name"], "unit_reference")
        self.assertEqual(summary["diffs"][0]["code"], "equity_value_mismatch")
        self.assertEqual(rows[0]["code"], "equity_value_mismatch")
        self.assertEqual(rows[0]["field"], "equity")

    def test_multi_asset_benchmark_keeps_diversified_downside_pack(self):
        result = run_multi_asset_benchmark(
            [
                MultiAssetBenchmarkCase(
                    name="crash_asset",
                    bars=make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
                    tags={"regime": "crash", "asset_class": "synthetic"},
                ),
                MultiAssetBenchmarkCase(
                    name="whipsaw_asset",
                    bars=make_bars([100, 103, 99, 104, 98, 105, 97, 106]),
                    tags={"regime": "whipsaw", "asset_class": "synthetic"},
                ),
            ],
            lambda: MovingAverageCashStrategy(window=3),
            config=BacktestConfig(max_allowed_drawdown=0.20),
            min_pass_rate=1.0,
        )

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["case_count"], 2)
        self.assertEqual(result.metrics["pass_rate"], 1.0)
        self.assertEqual(result.metrics["failed_cases"], [])
        self.assertEqual(result.metrics["group_metrics"]["asset_class:synthetic"]["pass_rate"], 1.0)
        self.assertEqual(result.metrics["group_metrics"]["regime:crash"]["case_count"], 1)
        self.assertLess(result.metrics["worst_max_drawdown"], 0.20)

    def test_multi_asset_benchmark_rejects_bad_asset_data(self):
        bad_bars = [
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-01", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        ]

        result = run_multi_asset_benchmark(
            [
                MultiAssetBenchmarkCase(
                    name="clean_asset",
                    bars=make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
                ),
                MultiAssetBenchmarkCase(name="bad_asset", bars=bad_bars),
            ],
            lambda: MovingAverageCashStrategy(window=3),
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertEqual(result.metrics["data_quality_reject_count"], 1)
        self.assertIn("bad_asset", result.metrics["failed_cases"])
        self.assertTrue(any("multi_asset_data_quality_rejections" in reason for reason in result.verdict.reasons))

    def test_multi_asset_benchmark_rejects_low_pack_pass_rate(self):
        result = run_multi_asset_benchmark(
            [
                MultiAssetBenchmarkCase(
                    name="crash_asset",
                    bars=make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
                    tags={"regime": "crash"},
                ),
                MultiAssetBenchmarkCase(
                    name="steady_up_asset",
                    bars=make_bars([100, 101, 102, 103, 104, 105, 106]),
                    tags={"regime": "steady_up"},
                ),
            ],
            lambda: MovingAverageCashStrategy(window=3),
            config=BacktestConfig(max_allowed_drawdown=0.20),
            min_pass_rate=0.75,
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertEqual(result.metrics["pass_rate"], 0.50)
        self.assertIn("steady_up_asset", result.metrics["failed_cases"])
        self.assertEqual(result.metrics["group_metrics"]["regime:steady_up"]["pass_rate"], 0.0)
        self.assertTrue(any("multi_asset_pass_rate_low" in reason for reason in result.verdict.reasons))

    def test_multi_asset_report_writer_creates_summary_case_and_group_csvs(self):
        result = run_multi_asset_benchmark(
            [
                MultiAssetBenchmarkCase(
                    name="crash_asset",
                    bars=make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
                    tags={"regime": "crash", "asset_class": "synthetic"},
                ),
                MultiAssetBenchmarkCase(
                    name="steady_up_asset",
                    bars=make_bars([100, 101, 102, 103, 104, 105, 106]),
                    tags={"regime": "steady_up", "asset_class": "synthetic"},
                ),
            ],
            lambda: MovingAverageCashStrategy(window=3),
            config=BacktestConfig(max_allowed_drawdown=0.20),
            min_pass_rate=0.50,
        )

        with _temporary_directory() as tmpdir:
            paths = write_multi_asset_benchmark_report(result, tmpdir)
            summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
            with Path(paths["cases"]).open(newline="", encoding="utf-8") as handle:
                case_rows = list(csv.DictReader(handle))
            with Path(paths["groups"]).open(newline="", encoding="utf-8") as handle:
                group_rows = list(csv.DictReader(handle))
            with Path(paths["case_manifest"]).open(newline="", encoding="utf-8") as handle:
                artifact_rows = list(csv.DictReader(handle))
            crash_artifact = next(row for row in artifact_rows if row["name"] == "crash_asset")
            crash_summary = json.loads(Path(crash_artifact["case_summary"]).read_text(encoding="utf-8"))
            case_artifacts_exists = Path(paths["case_artifacts"]).exists()
            crash_artifact_paths_exist = {
                "bars": Path(crash_artifact["bars"]).exists(),
                "data_quality": Path(crash_artifact["data_quality"]).exists(),
                "data_quality_issues": Path(crash_artifact["data_quality_issues"]).exists(),
                "backtest_equity_curve": Path(crash_artifact["backtest_equity_curve"]).exists(),
                "backtest_trades": Path(crash_artifact["backtest_trades"]).exists(),
                "backtest_order_intents": Path(crash_artifact["backtest_order_intents"]).exists(),
            }

        self.assertEqual(summary["strategy_name"], "ma_cash_3")
        self.assertEqual(summary["metrics"]["case_count"], 2)
        self.assertTrue(case_artifacts_exists)
        self.assertEqual([row["name"] for row in case_rows], ["crash_asset", "steady_up_asset"])
        self.assertEqual(case_rows[0]["data_quality_verdict"], "KEEP")
        self.assertIn("backtest_verdict", case_rows[0])
        groups = {row["group"]: row for row in group_rows}
        self.assertEqual(groups["asset_class:synthetic"]["case_count"], "2")
        self.assertEqual(groups["regime:steady_up"]["pass_rate"], "0.0")
        self.assertEqual({row["name"] for row in artifact_rows}, {"crash_asset", "steady_up_asset"})
        self.assertEqual(crash_summary["name"], "crash_asset")
        self.assertEqual(crash_summary["data"]["bar_count"], 11)
        self.assertTrue(all(crash_artifact_paths_exist.values()))

    def test_multi_asset_case_artifact_writer_can_run_standalone(self):
        result = run_multi_asset_benchmark(
            [
                MultiAssetBenchmarkCase(
                    name="Crash Asset / A",
                    bars=make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
                    tags={"regime": "crash"},
                ),
            ],
            lambda: MovingAverageCashStrategy(window=3),
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        with _temporary_directory() as tmpdir:
            paths = write_multi_asset_case_artifacts(result, tmpdir)
            with Path(paths["case_manifest"]).open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            row = rows[0]
            with Path(row["bars"]).open(newline="", encoding="utf-8") as handle:
                bar_rows = list(csv.DictReader(handle))
            summary = json.loads(Path(row["case_summary"]).read_text(encoding="utf-8"))

        self.assertEqual(len(rows), 1)
        self.assertIn("crash_asset_a", row["artifact_dir"])
        self.assertEqual(len(bar_rows), 11)
        self.assertEqual(summary["backtest"]["verdict"]["verdict"], "KEEP")

    def test_multi_asset_csv_directory_loader_builds_tagged_cases(self):
        with _temporary_directory() as tmpdir:
            root = Path(tmpdir)
            for name, prices in {
                "crash_asset": [100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75],
                "whipsaw_asset": [100, 103, 99, 104, 98, 105, 97, 106],
            }.items():
                path = root / f"{name}.csv"
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["date", "open", "high", "low", "close", "volume"])
                    writer.writeheader()
                    for idx, price in enumerate(prices, start=1):
                        writer.writerow(
                            {
                                "date": f"2020-01-{idx:02d}",
                                "open": price,
                                "high": price,
                                "low": price,
                                "close": price,
                                "volume": 1000,
                            }
                        )

            cases = load_multi_asset_csv_directory(root, tags={"asset_class": "synthetic"})
            result = run_multi_asset_benchmark(
                cases,
                lambda: MovingAverageCashStrategy(window=3),
                config=BacktestConfig(max_allowed_drawdown=0.20),
            )

        self.assertEqual({case.name for case in cases}, {"crash_asset", "whipsaw_asset"})
        self.assertTrue(all(case.tags["source"] == "csv_directory" for case in cases))
        self.assertTrue(all(case.tags["asset_class"] == "synthetic" for case in cases))
        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["group_metrics"]["asset_class:synthetic"]["case_count"], 2)

    def test_fees_and_slippage_reduce_performance_when_trades_occur(self):
        bars = make_bars([100, 101, 102, 103, 104, 105])
        strategy = MovingAverageCashStrategy(window=3)
        clean = run_backtest(bars, strategy, BacktestConfig(fee_bps=0.0, slippage_bps=0.0))
        costly = run_backtest(bars, strategy, BacktestConfig(fee_bps=10.0, slippage_bps=10.0))

        self.assertGreater(len(clean.trades), 0)
        self.assertGreater(clean.metrics["total_return"], costly.metrics["total_return"])

    def test_bear_cash_filter_reduces_drawdown_on_synthetic_crash(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75])
        result = run_backtest(bars, MovingAverageCashStrategy(window=3))

        self.assertLess(result.metrics["max_drawdown"], result.benchmark_metrics["max_drawdown"])
        self.assertLess(result.metrics["max_drawdown"], 0.20)

    def test_verdict_rejects_when_max_drawdown_exceeds_limit(self):
        result = run_backtest(
            make_bars([100, 120, 80, 70]),
            AlwaysLongStrategy(),
            BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertTrue(any("max_drawdown_breach" in reason for reason in result.verdict.reasons))

    def test_verdict_keeps_when_ma_filter_protects_downside(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75])
        result = run_backtest(bars, MovingAverageCashStrategy(window=3), BacktestConfig(max_allowed_drawdown=0.20))

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertIn("max_drawdown_better_than_benchmark", result.verdict.reasons)

    def test_report_writer_creates_json_and_csv_artifacts(self):
        result = run_backtest(make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90]), MovingAverageCashStrategy(window=3))
        with _temporary_directory() as tmpdir:
            paths = write_stock_report(result, tmpdir)

            self.assertTrue(Path(paths["metrics"]).exists())
            self.assertTrue(Path(paths["equity_curve"]).exists())
            self.assertTrue(Path(paths["trades"]).exists())
            self.assertTrue(Path(paths["order_intents"]).exists())
            payload = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))

        self.assertTrue(payload["research_only"])
        self.assertEqual(payload["strategy_name"], "ma_cash_3")
        self.assertIn("verdict", payload)

    def test_public_exports_are_available_from_angelos_os(self):
        from angelos_os import Bar as PublicBar
        from angelos_os import DataQualityResult as PublicDataQualityResult
        from angelos_os import EngineParityDiff as PublicEngineParityDiff
        from angelos_os import EngineParityResult as PublicEngineParityResult
        from angelos_os import ExternalEngineFill as PublicExternalEngineFill
        from angelos_os import ExternalEngineOrderIntent as PublicExternalEngineOrderIntent
        from angelos_os import MarketCalendarProfile as PublicMarketCalendarProfile
        from angelos_os import MultiAssetBenchmarkResult as PublicMultiAssetBenchmarkResult
        from angelos_os import OrderIntent as PublicOrderIntent
        from angelos_os import StressMatrixResult as PublicStressMatrixResult
        from angelos_os import audit_no_lookahead as public_audit_no_lookahead
        from angelos_os import create_experiment_manifest as public_create_experiment_manifest
        from angelos_os import load_engine_equity_csv as public_load_engine_equity_csv
        from angelos_os import load_engine_fills_csv as public_load_engine_fills_csv
        from angelos_os import load_engine_order_intents_csv as public_load_engine_order_intents_csv
        from angelos_os import load_engine_trades_csv as public_load_engine_trades_csv
        from angelos_os import load_market_calendar_csv as public_load_market_calendar_csv
        from angelos_os import load_multi_asset_csv_directory as public_load_multi_asset_csv_directory
        from angelos_os import run_cost_stress as public_run_cost_stress
        from angelos_os import run_data_quality_gate as public_run_data_quality_gate
        from angelos_os import run_engine_parity_check as public_run_engine_parity_check
        from angelos_os import run_ma_parameter_sweep as public_run_ma_parameter_sweep
        from angelos_os import run_multi_asset_benchmark as public_run_multi_asset_benchmark
        from angelos_os import run_regime_stress as public_run_regime_stress
        from angelos_os import run_backtest as public_run_backtest
        from angelos_os import run_stress_matrix as public_run_stress_matrix
        from angelos_os import run_walk_forward as public_run_walk_forward
        from angelos_os import write_engine_parity_report as public_write_engine_parity_report
        from angelos_os import write_multi_asset_case_artifacts as public_write_multi_asset_case_artifacts
        from angelos_os import write_multi_asset_benchmark_report as public_write_multi_asset_benchmark_report

        self.assertIs(PublicBar, Bar)
        self.assertEqual(PublicDataQualityResult.__name__, "DataQualityResult")
        self.assertEqual(PublicEngineParityDiff.__name__, "EngineParityDiff")
        self.assertEqual(PublicEngineParityResult.__name__, "EngineParityResult")
        self.assertIs(PublicExternalEngineFill, ExternalEngineFill)
        self.assertIs(PublicExternalEngineOrderIntent, ExternalEngineOrderIntent)
        self.assertIs(PublicMarketCalendarProfile, MarketCalendarProfile)
        self.assertEqual(PublicMultiAssetBenchmarkResult.__name__, "MultiAssetBenchmarkResult")
        self.assertEqual(PublicOrderIntent.__name__, "OrderIntent")
        self.assertEqual(PublicStressMatrixResult.__name__, "StressMatrixResult")
        self.assertIs(public_audit_no_lookahead, audit_no_lookahead)
        self.assertIs(public_create_experiment_manifest, create_experiment_manifest)
        self.assertIs(public_load_engine_equity_csv, load_engine_equity_csv)
        self.assertIs(public_load_engine_fills_csv, load_engine_fills_csv)
        self.assertIs(public_load_engine_order_intents_csv, load_engine_order_intents_csv)
        self.assertIs(public_load_engine_trades_csv, load_engine_trades_csv)
        self.assertIs(public_load_market_calendar_csv, load_market_calendar_csv)
        self.assertIs(public_load_multi_asset_csv_directory, load_multi_asset_csv_directory)
        self.assertIs(public_run_cost_stress, run_cost_stress)
        self.assertIs(public_run_data_quality_gate, run_data_quality_gate)
        self.assertIs(public_run_engine_parity_check, run_engine_parity_check)
        self.assertIs(public_run_ma_parameter_sweep, run_ma_parameter_sweep)
        self.assertIs(public_run_multi_asset_benchmark, run_multi_asset_benchmark)
        self.assertIs(public_run_regime_stress, run_regime_stress)
        self.assertIs(public_run_stress_matrix, run_stress_matrix)
        self.assertIs(public_run_walk_forward, run_walk_forward)
        self.assertIs(public_write_engine_parity_report, write_engine_parity_report)
        self.assertIs(public_write_multi_asset_case_artifacts, write_multi_asset_case_artifacts)
        self.assertIs(public_write_multi_asset_benchmark_report, write_multi_asset_benchmark_report)
        result = public_run_backtest(make_bars([100, 101, 102, 103]), MovingAverageCashStrategy(window=2))
        self.assertEqual(result.strategy_name, "ma_cash_2")

    def test_lookahead_audit_passes_history_only_strategy(self):
        audit = audit_no_lookahead(lambda: MovingAverageCashStrategy(window=3), make_bars([100, 101, 102, 103, 104]))

        self.assertTrue(audit.passed)
        self.assertEqual(audit.changed_decisions, 0)
        self.assertEqual(audit.checked_decisions, 5)

    def test_lookahead_audit_detects_future_peeking_strategy(self):
        audit = audit_no_lookahead(
            lambda bars: FuturePeekStrategy(bars),
            make_bars([100, 101, 102, 103, 104]),
            future_price_multiplier=0.01,
        )

        self.assertFalse(audit.passed)
        self.assertGreater(audit.changed_decisions, 0)
        self.assertTrue(any("future_mutation_changed" in reason for reason in audit.reasons))

    def test_walk_forward_keeps_repeated_crash_protection(self):
        prices = [
            100,
            105,
            110,
            115,
            120,
            119,
            118,
            117,
            90,
            80,
            75,
            100,
            105,
            110,
            115,
            120,
            119,
            118,
            117,
            90,
            80,
            75,
        ]
        result = run_walk_forward(
            make_bars(prices),
            lambda: MovingAverageCashStrategy(window=3),
            train_size=3,
            test_size=8,
            step_size=11,
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["fold_count"], 2)
        self.assertEqual(result.metrics["downside_pass_rate"], 1.0)
        self.assertLess(result.metrics["mean_max_drawdown"], result.metrics["mean_benchmark_max_drawdown"])

    def test_walk_forward_rejects_unprotected_always_long(self):
        result = run_walk_forward(
            make_bars([100, 120, 80, 70, 60, 55, 50, 48]),
            lambda: AlwaysLongStrategy(),
            train_size=2,
            test_size=3,
            step_size=3,
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertGreater(result.metrics["max_drawdown_breach_count"], 0)
        self.assertTrue(any("walk_forward_drawdown_breach" in reason for reason in result.verdict.reasons))

    def test_walk_forward_iterates_when_no_folds_exist(self):
        result = run_walk_forward(
            make_bars([100, 101, 102, 103]),
            lambda: MovingAverageCashStrategy(window=3),
            train_size=3,
            test_size=3,
        )

        self.assertEqual(result.verdict.verdict, "ITERATE")
        self.assertEqual(result.metrics["fold_count"], 0)

    def test_default_regime_stress_suite_matches_expected_verdicts(self):
        result = run_regime_stress(lambda: MovingAverageCashStrategy(window=3))

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["case_count"], len(default_regime_stress_cases()))
        self.assertEqual(result.metrics["pass_rate"], 1.0)
        actual = {case.name: case.actual_verdict for case in result.cases}
        self.assertEqual(actual["steady_up_reject"], "REJECT")
        self.assertEqual(actual["crash_keep"], "KEEP")
        self.assertEqual(actual["flat_then_spike_reject"], "REJECT")

    def test_regime_stress_rejects_when_expected_verdict_mismatches(self):
        cases = default_regime_stress_cases()
        bad_case = [type(cases[0])(name=cases[0].name, bars=cases[0].bars, expected_verdict="KEEP")]
        result = run_regime_stress(lambda: MovingAverageCashStrategy(window=3), bad_case)

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertEqual(result.metrics["failed_count"], 1)
        self.assertFalse(result.cases[0].passed)

    def test_experiment_manifest_records_reproducible_lineage(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75])
        config = BacktestConfig(max_allowed_drawdown=0.20)
        data_quality = run_data_quality_gate(bars)
        backtest = run_backtest(bars, MovingAverageCashStrategy(window=3), config)
        engine_parity = run_engine_parity_check(
            backtest,
            external_equity_from_result(backtest),
            external_trades_from_result(backtest),
            engine_name="unit_reference",
        )
        audit = audit_no_lookahead(lambda: MovingAverageCashStrategy(window=3), bars)
        walk_forward = run_walk_forward(
            bars + bars,
            lambda: MovingAverageCashStrategy(window=3),
            train_size=3,
            test_size=8,
            step_size=11,
            config=config,
        )
        stress = run_regime_stress(lambda: MovingAverageCashStrategy(window=3), config=config)
        sweep = run_ma_parameter_sweep(
            bars + bars,
            [2, 3, 4],
            train_size=3,
            test_size=8,
            step_size=11,
            config=config,
        )
        cost_stress = run_cost_stress(
            bars + bars,
            lambda: MovingAverageCashStrategy(window=3),
            config=config,
        )
        stress_matrix = run_stress_matrix(
            make_bars([100, 105, 110, 115, 120, 119, 118, 117, 116, 115, 100, 90, 80] * 2),
            lambda: MovingAverageCashStrategy(window=3),
            config=config,
        )
        multi_asset_benchmark = run_multi_asset_benchmark(
            [
                MultiAssetBenchmarkCase(name="crash_asset", bars=bars, tags={"regime": "crash"}),
                MultiAssetBenchmarkCase(
                    name="whipsaw_asset",
                    bars=make_bars([100, 103, 99, 104, 98, 105, 97, 106]),
                    tags={"regime": "whipsaw"},
                ),
            ],
            lambda: MovingAverageCashStrategy(window=3),
            config=config,
        )

        manifest = create_experiment_manifest(
            strategy_name="ma_cash_3",
            bars=bars,
            config=config,
            data_quality=data_quality,
            engine_parity=engine_parity,
            backtest=backtest,
            lookahead_audit=audit,
            walk_forward=walk_forward,
            regime_stress=stress,
            parameter_sweep=sweep,
            cost_stress=cost_stress,
            stress_matrix=stress_matrix,
            multi_asset_benchmark=multi_asset_benchmark,
        )

        self.assertEqual(manifest["schema"], "angelos_stock_experiment_manifest_v1")
        self.assertTrue(manifest["research_only"])
        self.assertEqual(manifest["data"]["bar_count"], len(bars))
        self.assertEqual(len(manifest["data"]["fingerprint"]), 64)
        self.assertEqual(manifest["artifacts"]["data_quality"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(manifest["artifacts"]["engine_parity"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(manifest["artifacts"]["backtest"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(manifest["artifacts"]["lookahead_audit"]["passed"], True)
        self.assertEqual(manifest["artifacts"]["regime_stress"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(manifest["artifacts"]["parameter_sweep"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(manifest["artifacts"]["cost_stress"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(manifest["artifacts"]["stress_matrix"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(manifest["artifacts"]["multi_asset_benchmark"]["verdict"]["verdict"], "KEEP")

    def test_parameter_sweep_keeps_stable_neighbor_windows(self):
        bars = make_bars(
            [
                100,
                105,
                110,
                115,
                120,
                119,
                118,
                117,
                90,
                80,
                75,
                100,
                105,
                110,
                115,
                120,
                119,
                118,
                117,
                90,
                80,
                75,
            ]
        )

        result = run_ma_parameter_sweep(
            bars,
            [2, 3, 4],
            train_size=3,
            test_size=8,
            step_size=11,
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["pass_rate"], 1.0)
        self.assertEqual(result.metrics["stable_pass_cluster"], 3)
        self.assertIn(result.best_window, {2, 3, 4})

    def test_parameter_sweep_rejects_single_lucky_window(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75] * 2)

        result = run_ma_parameter_sweep(
            bars,
            [3],
            train_size=3,
            test_size=8,
            step_size=11,
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertTrue(any("no_stable_neighbor_cluster" in reason for reason in result.verdict.reasons))

    def test_parameter_sweep_rejects_sparse_overfit_surface(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75] * 2)

        result = run_ma_parameter_sweep(
            bars,
            [2, 5, 8],
            train_size=3,
            test_size=8,
            step_size=11,
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertLess(result.metrics["pass_rate"], 0.60)
        self.assertTrue(any("parameter_pass_rate_low" in reason for reason in result.verdict.reasons))

    def test_cost_stress_keeps_downside_filter_under_default_costs(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75] * 2)

        result = run_cost_stress(
            bars,
            lambda: MovingAverageCashStrategy(window=3),
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["case_count"], len(default_cost_stress_cases()))
        self.assertTrue(result.metrics["all_costs_keep"])
        self.assertLessEqual(result.metrics["return_decay"], 0.50)
        self.assertLess(result.metrics["worst_max_drawdown"], 0.20)

    def test_cost_stress_rejects_punitive_cost_decay(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75] * 2)

        result = run_cost_stress(
            bars,
            lambda: MovingAverageCashStrategy(window=3),
            [
                CostStressCase(name="zero_cost", fee_bps=0.0, slippage_bps=0.0),
                CostStressCase(name="punitive_cost", fee_bps=1000.0, slippage_bps=1000.0),
            ],
            config=BacktestConfig(max_allowed_drawdown=0.20),
            max_return_decay=0.10,
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertTrue(
            any("cost_return_decay_high" in reason or "cost_case_rejected" in reason for reason in result.verdict.reasons)
        )

    def test_stress_matrix_keeps_default_execution_and_gap_pack(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 116, 115, 100, 90, 80] * 2)

        result = run_stress_matrix(
            bars,
            lambda: MovingAverageCashStrategy(window=3),
            config=BacktestConfig(max_allowed_drawdown=0.20),
        )

        self.assertEqual(result.verdict.verdict, "KEEP")
        self.assertEqual(result.metrics["case_count"], len(default_stress_matrix_cases()))
        self.assertTrue(result.metrics["all_stress_cases_keep"])
        self.assertGreaterEqual(result.metrics["max_execution_delay_bars"], 1)
        self.assertGreater(result.metrics["max_adverse_open_gap_bps"], 0.0)
        self.assertGreater(result.metrics["max_liquidity_participation_rate"], 0.0)
        self.assertGreaterEqual(result.metrics["liquidity_capped_case_count"], 1)
        self.assertGreater(result.metrics["max_market_impact_bps_per_100pct_participation"], 0.0)
        self.assertGreater(result.metrics["max_observed_market_impact_bps"], 0.0)
        self.assertLess(result.metrics["worst_max_drawdown"], 0.20)

    def test_stress_matrix_applies_liquidity_participation_cap(self):
        bars = [
            Bar(
                date=f"2020-01-{idx:02d}",
                open=float(price),
                high=float(price),
                low=float(price),
                close=float(price),
                volume=10.0,
            )
            for idx, price in enumerate([100, 101, 102, 103, 104, 105], start=1)
        ]

        result = run_stress_matrix(
            bars,
            lambda: AlwaysLongStrategy(),
            [
                StressMatrixCase(name="baseline", fee_bps=0.0, slippage_bps=0.0),
                StressMatrixCase(name="thin_volume", fee_bps=0.0, slippage_bps=0.0, max_participation_rate=0.05),
            ],
            config=BacktestConfig(max_allowed_drawdown=1.0),
            max_return_decay=10.0,
        )
        capped = next(case for case in result.cases if case.name == "thin_volume")

        self.assertEqual(result.metrics["liquidity_capped_case_count"], 1)
        self.assertEqual(result.metrics["max_liquidity_participation_rate"], 0.05)
        self.assertGreater(result.metrics["max_participation_cap_hit_count"], 0)
        self.assertGreater(capped.result.metrics["liquidity_cap_hit_count"], 0)
        self.assertGreater(capped.result.metrics["liquidity_unfilled_shares"], 0.0)
        self.assertTrue(all(trade.shares <= 0.5 + 1e-12 for trade in capped.result.trades))
        self.assertLess(capped.result.metrics["max_volume_participation"], 0.051)

    def test_stress_matrix_applies_market_impact_curve(self):
        bars = [
            Bar(
                date=f"2020-01-{idx:02d}",
                open=float(price),
                high=float(price),
                low=float(price),
                close=float(price),
                volume=1000.0,
            )
            for idx, price in enumerate([100, 101, 102, 103], start=1)
        ]

        result = run_stress_matrix(
            bars,
            lambda: AlwaysLongStrategy(),
            [
                StressMatrixCase(name="baseline", fee_bps=0.0, slippage_bps=0.0),
                StressMatrixCase(
                    name="impact_curve",
                    fee_bps=0.0,
                    slippage_bps=0.0,
                    market_impact_bps_per_100pct_participation=1000.0,
                ),
            ],
            config=BacktestConfig(max_allowed_drawdown=1.0),
            max_return_decay=10.0,
        )
        baseline = next(case for case in result.cases if case.name == "baseline")
        impact = next(case for case in result.cases if case.name == "impact_curve")

        self.assertGreater(impact.result.trades[0].price, baseline.result.trades[0].price)
        self.assertGreater(impact.result.metrics["market_impact_cost"], 0.0)
        self.assertGreater(impact.result.metrics["max_market_impact_bps"], 0.0)
        self.assertGreater(result.metrics["total_market_impact_cost"], 0.0)
        self.assertEqual(result.metrics["max_market_impact_bps_per_100pct_participation"], 1000.0)
        self.assertLess(impact.result.metrics["total_return"], baseline.result.metrics["total_return"])

    def test_stress_matrix_rejects_punitive_gap_and_delay(self):
        bars = make_bars([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75] * 2)

        result = run_stress_matrix(
            bars,
            lambda: MovingAverageCashStrategy(window=3),
            [
                StressMatrixCase(name="baseline", fee_bps=0.0, slippage_bps=0.0),
                StressMatrixCase(
                    name="punitive_gap_delay",
                    fee_bps=10.0,
                    slippage_bps=25.0,
                    adverse_open_gap_bps=2500.0,
                    execution_delay_bars=2,
                ),
            ],
            config=BacktestConfig(max_allowed_drawdown=0.20),
            max_return_decay=0.10,
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertTrue(
            any(
                "stress_case_rejected" in reason or "stress_return_decay_high" in reason
                for reason in result.verdict.reasons
            )
        )

    def test_stress_matrix_rejects_invalid_fill_assumption(self):
        result = run_stress_matrix(
            make_bars([100, 105, 110, 115]),
            lambda: MovingAverageCashStrategy(window=2),
            [StressMatrixCase(name="impossible_fill", slippage_bps=9000.0, adverse_open_gap_bps=1000.0)],
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertTrue(any("slippage plus adverse gap" in reason for reason in result.verdict.reasons))

    def test_stress_matrix_rejects_invalid_liquidity_cap(self):
        result = run_stress_matrix(
            make_bars([100, 105, 110, 115]),
            lambda: MovingAverageCashStrategy(window=2),
            [StressMatrixCase(name="bad_liquidity", max_participation_rate=0.0)],
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertTrue(any("max_participation_rate" in reason for reason in result.verdict.reasons))

    def test_stress_matrix_rejects_invalid_market_impact_curve(self):
        result = run_stress_matrix(
            make_bars([100, 105, 110, 115]),
            lambda: MovingAverageCashStrategy(window=2),
            [StressMatrixCase(name="bad_impact", market_impact_bps_per_100pct_participation=-1.0)],
        )

        self.assertEqual(result.verdict.verdict, "REJECT")
        self.assertTrue(any("impact" in reason for reason in result.verdict.reasons))

    def test_experiment_manifest_writer_creates_json_artifact(self):
        bars = make_bars([100, 105, 110, 115, 120])
        manifest = create_experiment_manifest(
            strategy_name="ma_cash_3",
            bars=bars,
            config=BacktestConfig(),
        )
        with _temporary_directory() as tmpdir:
            path = write_experiment_manifest(manifest, tmpdir)
            payload = json.loads(Path(path).read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "angelos_stock_experiment_manifest_v1")
        self.assertEqual(payload["strategy_name"], "ma_cash_3")

    def test_no_dependency_oracle_matches_harness_across_regimes(self):
        suite = run_benchmark_suite()

        self.assertTrue(suite["all_passed"])
        self.assertEqual({case["case"]["name"] for case in suite["cases"]}, {case.name for case in benchmark_cases()})
        for case in suite["cases"]:
            self.assertTrue(case["parity"]["passed"], case["case"]["name"])
            self.assertTrue(all(case["parity"]["checks"].values()), case["case"]["name"])

    def test_oracle_benchmark_preserves_expected_regime_verdicts(self):
        outcomes = {case.name: run_oracle_case(case) for case in benchmark_cases()}

        self.assertEqual(outcomes["steady_up"]["harness"]["verdict"], "REJECT")
        self.assertEqual(outcomes["crash"]["harness"]["verdict"], "KEEP")
        self.assertEqual(outcomes["whipsaw"]["harness"]["verdict"], "KEEP")
        self.assertEqual(outcomes["flat_then_spike"]["harness"]["verdict"], "REJECT")
        self.assertLess(
            outcomes["crash"]["harness"]["max_drawdown"],
            outcomes["crash"]["harness"]["benchmark_max_drawdown"],
        )

    def test_oracle_benchmark_cli_exits_success_and_emits_json(self):
        completed = subprocess.run(
            [sys.executable, "ops/benchmark_stock_harness.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["benchmark"], "stock_harness_no_dependency_oracle_v1")
        self.assertTrue(payload["all_passed"])
        self.assertEqual(payload["data_quality"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(payload["adjusted_ohlc_data_quality"]["verdict"]["verdict"], "KEEP")
        self.assertTrue(payload["adjusted_ohlc_data_quality"]["metrics"]["adjusted_ohlc_checks_applied"])
        self.assertEqual(payload["engine_parity"]["verdict"]["verdict"], "KEEP")
        self.assertTrue(payload["engine_parity"]["checks"]["fill_values"])
        self.assertEqual(payload["engine_parity"]["metrics"]["diff_count"], 0)
        self.assertEqual(payload["regime_stress"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(payload["parameter_sweep"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(payload["cost_stress"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(payload["stress_matrix"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(payload["multi_asset_benchmark"]["verdict"]["verdict"], "KEEP")
        self.assertEqual(payload["manifest"]["schema"], "angelos_stock_experiment_manifest_v1")

    def test_sota_evidence_comparison_supports_scoped_claim(self):
        report = run_comparison()

        self.assertEqual(report["claim"]["id"], "downside_verification_sota_grade_v0_1")
        self.assertEqual(report["claim"]["status"], "supported_for_included_benchmark_suite")
        self.assertIn("No financial advice.", report["claim"]["non_claims"])
        self.assertTrue(report["benchmark"]["all_passed"])
        self.assertEqual(report["benchmark"]["expected_diffs"], [])
        self.assertEqual(report["benchmark"]["claim_contract_diffs"], [])
        self.assertEqual(report["claim"]["contract_path"], "benchmarks/downside_verification_v1/claim_contract.json")
        self.assertEqual(report["tools"]["angelos_stock_harness"]["coverage_score"], 1.0)
        self.assertEqual(report["tools"]["angelos_stock_harness"]["missing_capabilities"], [])
        self.assertLess(
            report["tools"]["minimal_ma_backtest_baseline"]["coverage_score"],
            report["tools"]["angelos_stock_harness"]["coverage_score"],
        )

    def test_sota_evidence_comparison_cli_exits_success_and_emits_json(self):
        completed = subprocess.run(
            [sys.executable, "ops/compare_stock_harness_baselines.py", "--pretty"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["claim"]["status"], "supported_for_included_benchmark_suite")
        self.assertEqual(payload["benchmark"]["expected_diffs"], [])
        self.assertEqual(payload["benchmark"]["claim_contract_diffs"], [])
        self.assertEqual(payload["tools"]["angelos_stock_harness"]["covered_count"], 18)

    def test_sota_claim_docs_keep_scope_and_non_claims(self):
        required_paths = [
            Path("README.md"),
            Path("docs/FIRST_TIME_READER_GUIDE_KO.md"),
            Path("docs/CLAIMS.md"),
            Path("docs/BENCHMARK.md"),
            Path("docs/LIMITATIONS.md"),
            Path("docs/RELEASE_GATE.md"),
            Path("docs/THREAT_MODEL.md"),
            Path("benchmarks/downside_verification_v1/README.md"),
            Path("benchmarks/downside_verification_v1/expected_summary.json"),
            Path("benchmarks/downside_verification_v1/claim_contract.json"),
            Path("paper/SOTA_CLAIM_TECHNICAL_REPORT.md"),
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), str(path))
            self.assertGreater(len(path.read_text(encoding="utf-8")), 100, str(path))

        readme = Path("README.md").read_text(encoding="utf-8")
        first_time_guide = Path("docs/FIRST_TIME_READER_GUIDE_KO.md").read_text(encoding="utf-8")
        claims = Path("docs/CLAIMS.md").read_text(encoding="utf-8")
        limitations = Path("docs/LIMITATIONS.md").read_text(encoding="utf-8")
        release_gate = Path("docs/RELEASE_GATE.md").read_text(encoding="utf-8")
        paper = Path("paper/SOTA_CLAIM_TECHNICAL_REPORT.md").read_text(encoding="utf-8")
        expected_summary = json.loads(
            Path("benchmarks/downside_verification_v1/expected_summary.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("not financial advice", readme)
        self.assertIn("FIRST_TIME_READER_GUIDE_KO.md", readme)
        self.assertIn("This is a verification claim", readme)
        self.assertIn("run_stock_harness_release_gate.py", readme)
        self.assertIn("run_stock_harness_official_claim_gate.py", readme)
        self.assertIn("stock_harness_official_claim_packet", readme)
        self.assertNotIn("\x08", readme + first_time_guide + claims + limitations + release_gate + paper)
        self.assertIn("처음 보는 사람을 위한 안내서", first_time_guide)
        self.assertIn("주식 매매 프로그램이 아닙니다", first_time_guide)
        self.assertIn("downside_verification_sota_grade_v0_1", claims)
        self.assertIn("official_claim_ready: true", claims)
        self.assertIn("official_claim_publishable: true", claims)
        self.assertIn("official claim packet", claims.lower())
        self.assertIn("official_claim_publishable: true", release_gate)
        self.assertIn("stock_harness_official_claim_packet", release_gate)
        self.assertIn("release_bundle_passed", release_gate)
        self.assertIn("release_bundle_scope_enforced", release_gate)
        self.assertIn("release_audit_passed", release_gate)
        self.assertIn("evidence_packet_passed", release_gate)
        self.assertIn("evidence_packet_verified", release_gate)
        self.assertIn("release_candidate_passed", release_gate)
        self.assertIn("release_candidate_verified", release_gate)
        self.assertIn("release_candidate_replayed", release_gate)
        self.assertIn("claim_contract_required_assertions_present", release_gate)
        self.assertIn("not an industry certification", limitations)
        self.assertIn("technical report draft for private review", paper)
        self.assertIn("review patent and licensing strategy before publication", paper)
        self.assertIn("This is a verification-coverage claim", paper)
        self.assertIn("The current materials do not establish peer-reviewed novelty", paper)
        self.assertIn("stock harness unit suite", paper)
        self.assertIn("scoped stock harness release gate", paper)
        self.assertIn("official publication gate", paper)
        self.assertIn("official_claim_publishable: true", paper)
        self.assertIn("official claim packet", paper)
        self.assertIn("CI runs py_compile", paper)
        self.assertIn("rebuilds official evidence", paper)
        self.assertIn("Rust v0 Validation", paper)
        self.assertIn("7 Rust tests OK", paper)
        self.assertIn("The Python implementation remains the complete reference", paper)
        claim_contract = json.loads(Path("benchmarks/downside_verification_v1/claim_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(expected_summary["claim_id"], "downside_verification_sota_grade_v0_1")
        self.assertEqual(claim_contract["claim_id"], expected_summary["claim_id"])
        self.assertIn("release_bundle_scope_enforced", claim_contract["required_release_gate_assertions"])
        self.assertIn("evidence_packet_passed", claim_contract["required_release_gate_assertions"])
        self.assertIn("evidence_packet_verified", claim_contract["required_release_gate_assertions"])
        self.assertIn("release_candidate_passed", claim_contract["required_release_gate_assertions"])
        self.assertIn("release_candidate_verified", claim_contract["required_release_gate_assertions"])
        self.assertIn("release_candidate_replayed", claim_contract["required_release_gate_assertions"])
        self.assertIn("full_release_gate_official_ready", claim_contract["required_publication_gate_assertions"])
        self.assertIn("release_candidate_replayed_for_publication", claim_contract["required_publication_gate_assertions"])
        self.assertIn("official_gate_publishable", claim_contract["required_official_claim_packet_checks"])

    def test_release_bundle_file_list_is_scoped(self):
        errors = _validate_release_files()
        self.assertEqual(errors, [])
        normalized = [path.replace("\\", "/") for path in RELEASE_FILES]
        self.assertIn("angelos_os/stock_harness.py", normalized)
        self.assertIn("angelos_os/engine.py", normalized)
        self.assertIn("angelos_os/profiles.py", normalized)
        self.assertIn("angelos_os/providers.py", normalized)
        self.assertIn("angelos_os/safety.py", normalized)
        self.assertIn("angelos_os/schemas.py", normalized)
        self.assertIn("angelos_os/score_core.py", normalized)
        self.assertIn("angelos_os/validation.py", normalized)
        self.assertIn("angelos_os/version.py", normalized)
        self.assertIn("ops/run_stock_harness_release_gate.py", normalized)
        self.assertIn("ops/run_stock_harness_official_claim_gate.py", normalized)
        self.assertIn("ops/build_stock_harness_official_claim_packet.py", normalized)
        self.assertIn("ops/verify_stock_harness_official_claim_packet.py", normalized)
        self.assertIn("ops/build_stock_harness_evidence_packet.py", normalized)
        self.assertIn("ops/verify_stock_harness_evidence_packet.py", normalized)
        self.assertIn("ops/build_stock_harness_release_candidate.py", normalized)
        self.assertIn("ops/verify_stock_harness_release_candidate.py", normalized)
        self.assertIn("ops/replay_stock_harness_release_candidate.py", normalized)
        self.assertIn("ops/audit_stock_harness_release.py", normalized)
        self.assertIn("rust_stock_harness/src/lib.rs", normalized)
        self.assertIn("benchmarks/downside_verification_v1/claim_contract.json", normalized)
        self.assertFalse(any(path.startswith("external_models/") for path in normalized))
        self.assertFalse(any(path.startswith("rust_stock_harness/target/") for path in normalized))

    def test_release_gate_module_documents_scope(self):
        result = {
            "stdout": json.dumps(
                {
                    "all_passed": True,
                    "claim": {"status": "supported_for_included_benchmark_suite"},
                    "tools": {"angelos_stock_harness": {"coverage_score": 1.0}},
                }
            )
        }
        self.assertEqual(_parse_json_stdout(result)["all_passed"], True)

        assertions = _build_assertions(
            [
                {"name": "py_compile", "passed": True},
                {"name": "unit_tests", "passed": True},
                {"name": "benchmark", "passed": True, "stdout": json.dumps({"all_passed": True})},
                {
                    "name": "claim_comparison",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "claim": {
                                "status": "supported_for_included_benchmark_suite",
                                "non_claims": ["No universal external-framework dominance claim."],
                            },
                            "tools": {"angelos_stock_harness": {"coverage_score": 1.0}},
                        }
                    ),
                },
                {
                    "name": "release_audit",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "schema": "stock_harness_release_audit_v1",
                            "status": "passed",
                        }
                    ),
                },
                {
                    "name": "release_bundle",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "schema": "stock_harness_release_bundle_v1",
                            "status": "passed",
                            "file_count": 24,
                            "claim_scope": {
                                "benchmark_suite": "downside_verification_v1",
                                "claim_limit": "SOTA-grade deterministic verification coverage only",
                                "non_claims": [
                                    "No universal external-framework dominance claim."
                                ],
                            },
                        }
                    ),
                },
                {
                    "name": "evidence_packet",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "schema": "stock_harness_evidence_packet_v1",
                            "status": "passed",
                            "file_count": 7,
                            "checks": {
                                "benchmark_all_passed": True,
                                "claim_status_supported": True,
                                "release_bundle_passed": True,
                                "release_audit_passed": True,
                            },
                        }
                    ),
                },
                {
                    "name": "evidence_packet_verification",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "schema": "stock_harness_evidence_packet_verification_v1",
                            "status": "passed",
                            "checks": {
                                "hashes": {"passed": True},
                                "json_payloads": {"passed": True},
                            },
                        }
                    ),
                },
                {
                    "name": "release_candidate",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "schema": "stock_harness_release_candidate_v1",
                            "status": "passed",
                            "component_count": 2,
                        }
                    ),
                },
                {
                    "name": "release_candidate_verification",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "schema": "stock_harness_release_candidate_verification_v1",
                            "status": "passed",
                            "checks": {
                                "components": {"passed": True},
                                "zip_payloads": {"passed": True},
                            },
                        }
                    ),
                },
                {
                    "name": "release_candidate_replay",
                    "passed": True,
                    "stdout": json.dumps(
                        {
                            "schema": "stock_harness_release_candidate_replay_v1",
                            "status": "passed",
                            "assertions": [
                                {"id": "extracted_py_compile_passed", "passed": True},
                                {"id": "extracted_unit_tests_passed", "passed": True},
                                {"id": "extracted_benchmark_passed", "passed": True},
                                {"id": "extracted_claim_supported", "passed": True},
                                {"id": "extracted_release_audit_passed", "passed": True},
                                {
                                    "id": "candidate_verifier_from_extracted_source_passed",
                                    "passed": True,
                                },
                            ],
                        }
                    ),
                },
            ],
            rust_required=False,
        )
        self.assertTrue(all(item["passed"] for item in assertions))


    def test_official_claim_gate_requires_publication_ready_artifacts(self):
        commands = [
            {"name": "full_release_gate", "passed": True},
            {"name": "evidence_packet", "passed": True},
            {"name": "evidence_packet_verification", "passed": True},
            {"name": "release_candidate", "passed": True},
            {"name": "release_candidate_verification", "passed": True},
            {"name": "release_candidate_replay", "passed": True},
        ]
        release_gate = {
            "schema": "stock_harness_release_gate_v1",
            "official_claim_ready": True,
            "overall_status": "passed",
            "rust_status": "required",
            "python_gate_passed": True,
            "claim": {"status": "supported_for_included_benchmark_suite"},
            "claim_scope": {
                "benchmark_suite": "downside_verification_v1",
                "non_claims_enforced": [
                    "No investment-performance or alpha-generation claim.",
                    "No universal external-framework dominance claim.",
                ],
            },
            "assertions": [
                {"id": "rust_unit_tests_passed", "passed": True},
                {"id": "rust_benchmark_cli_passed", "passed": True},
                {"id": "release_candidate_replayed", "passed": True},
            ],
        }
        evidence_verification = {
            "schema": "stock_harness_evidence_packet_verification_v1",
            "status": "passed",
            "require_release_gate_json": True,
            "require_official_claim_ready": True,
            "checks": {
                "json_payloads": {
                    "checks": {"release_gate_official_ready": True},
                },
            },
        }
        candidate = {
            "schema": "stock_harness_release_candidate_v1",
            "status": "passed",
            "component_count": 2,
        }
        candidate_verification = {
            "schema": "stock_harness_release_candidate_verification_v1",
            "status": "passed",
            "require_release_gate_json": True,
            "require_official_claim_ready": True,
            "checks": {
                "zip_payloads": {
                    "checks": {"release_gate_official_ready": True},
                },
            },
        }
        replay = {
            "schema": "stock_harness_release_candidate_replay_v1",
            "status": "passed",
            "require_release_gate_json": True,
            "require_official_claim_ready": True,
            "skip_rust": False,
            "assertions": [
                {"id": "extracted_py_compile_passed", "passed": True},
                {"id": "extracted_unit_tests_passed", "passed": True},
                {"id": "extracted_benchmark_passed", "passed": True},
                {"id": "extracted_claim_supported", "passed": True},
                {"id": "extracted_release_audit_passed", "passed": True},
                {"id": "candidate_verifier_from_extracted_source_passed", "passed": True},
                {"id": "extracted_rust_unit_tests_passed", "passed": True},
                {"id": "extracted_rust_benchmark_cli_passed", "passed": True},
            ],
        }

        assertions = _build_official_claim_assertions(
            commands,
            release_gate,
            evidence_verification,
            candidate,
            candidate_verification,
            replay,
        )

        self.assertTrue(all(assertion["passed"] for assertion in assertions))
        assertion_ids = {assertion["id"] for assertion in assertions}
        self.assertIn("full_release_gate_official_ready", assertion_ids)
        self.assertIn("release_candidate_replayed_for_publication", assertion_ids)

    def test_official_claim_packet_materializes_and_detects_tampering(self):
        def write_json(path, payload):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        claim_scope = {
            "claim_id": "downside_verification_sota_grade_v0_1",
            "benchmark_suite": "downside_verification_v1",
        }
        with _temporary_directory() as tmpdir:
            root = Path(tmpdir)
            official_gate_path = root / "official_claim_gate.json"
            release_gate_path = root / "official_release_gate.json"
            replay_path = root / "official_release_candidate_replay.json"
            release_manifest_path = root / "release_manifest.json"
            evidence_manifest_path = root / "evidence_manifest.json"
            candidate_manifest_path = root / "release_candidate_manifest.json"
            packet_dir = root / "stock_harness_official_claim_packet"

            write_json(
                official_gate_path,
                {
                    "schema": "stock_harness_official_claim_gate_v1",
                    "status": "passed",
                    "official_claim_publishable": True,
                    "assertions": [
                        {"id": "full_release_gate_official_ready", "passed": True},
                        {"id": "evidence_packet_verified_for_publication", "passed": True},
                        {"id": "release_candidate_built_for_publication", "passed": True},
                        {"id": "release_candidate_verified_for_publication", "passed": True},
                        {"id": "release_candidate_replayed_for_publication", "passed": True},
                        {"id": "scoped_non_claims_preserved", "passed": True},
                        {"id": "official_commands_completed", "passed": True},
                    ],
                },
            )
            write_json(
                release_gate_path,
                {
                    "schema": "stock_harness_release_gate_v1",
                    "overall_status": "passed",
                    "official_claim_ready": True,
                    "rust_status": "required",
                    "claim": {"status": "supported_for_included_benchmark_suite"},
                    "claim_scope": {"benchmark_suite": "downside_verification_v1"},
                    "assertions": [
                        {"id": "rust_unit_tests_passed", "passed": True},
                        {"id": "rust_benchmark_cli_passed", "passed": True},
                        {"id": "release_candidate_replayed", "passed": True},
                    ],
                },
            )
            write_json(
                replay_path,
                {
                    "schema": "stock_harness_release_candidate_replay_v1",
                    "status": "passed",
                    "require_release_gate_json": True,
                    "require_official_claim_ready": True,
                    "skip_rust": False,
                    "assertions": [
                        {"id": "extracted_py_compile_passed", "passed": True},
                        {"id": "extracted_unit_tests_passed", "passed": True},
                        {"id": "extracted_benchmark_passed", "passed": True},
                        {"id": "extracted_claim_supported", "passed": True},
                        {"id": "extracted_release_audit_passed", "passed": True},
                        {"id": "candidate_verifier_from_extracted_source_passed", "passed": True},
                        {"id": "extracted_rust_unit_tests_passed", "passed": True},
                        {"id": "extracted_rust_benchmark_cli_passed", "passed": True},
                    ],
                },
            )
            write_json(
                release_manifest_path,
                {"schema": "stock_harness_release_bundle_v1", "status": "passed", "claim_scope": claim_scope},
            )
            write_json(
                evidence_manifest_path,
                {"schema": "stock_harness_evidence_packet_v1", "status": "passed", "claim_scope": claim_scope},
            )
            write_json(
                candidate_manifest_path,
                {"schema": "stock_harness_release_candidate_v1", "status": "passed", "claim_scope": claim_scope},
            )

            packet = build_official_claim_packet(
                packet_dir,
                official_claim_gate_json=official_gate_path,
                official_release_gate_json=release_gate_path,
                official_replay_json=replay_path,
                release_manifest=release_manifest_path,
                evidence_manifest=evidence_manifest_path,
                candidate_manifest=candidate_manifest_path,
                claim_contract=Path(AUDIT_CLAIM_CONTRACT_PATH),
            )
            verification = verify_official_claim_packet(packet_dir)

            tampered_dir = root / "tampered_official_claim_packet"
            shutil.copytree(str(packet_dir), str(tampered_dir))
            tampered = tampered_dir / "official_claim_gate.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            tampered_verification = verify_official_claim_packet(tampered_dir)

        self.assertEqual(packet["schema"], "stock_harness_official_claim_packet_v1")
        self.assertEqual(packet["status"], "passed")
        self.assertTrue(packet["checks"]["official_claim_gate"]["passed"])
        self.assertTrue(packet["checks"]["claim_contract"]["checks"]["official_claim_packet_checks_present"])
        paths = {entry["path"] for entry in packet["files"]}
        self.assertIn("official_claim_gate.json", paths)
        self.assertIn("official_release_gate.json", paths)
        self.assertIn("official_release_candidate_replay.json", paths)
        self.assertEqual(verification["schema"], "stock_harness_official_claim_packet_verification_v1")
        self.assertEqual(verification["status"], "passed")
        self.assertTrue(verification["checks"]["hashes"]["passed"])
        self.assertTrue(verification["checks"]["json_payloads"]["checks"]["claim_contract_packet_checks"])
        self.assertEqual(tampered_verification["status"], "failed")
        self.assertFalse(tampered_verification["checks"]["hashes"]["passed"])

    def test_release_audit_checks_claim_surface(self):
        contract = json.loads(Path(AUDIT_CLAIM_CONTRACT_PATH).read_text(encoding="utf-8"))

        self.assertTrue(_claim_contract_check(contract)["passed"])
        self.assertTrue(_release_file_check()["passed"])
        self.assertTrue(_docs_check(contract)["passed"])
        self.assertTrue(_ci_check()["passed"])
        self.assertTrue(_expected_summary_check(contract)["passed"])
        self.assertTrue(_broad_claim_phrase_check()["passed"])
        self.assertIn("release_audit_passed", contract["required_release_gate_assertions"])
        self.assertIn("evidence_packet_passed", contract["required_release_gate_assertions"])
        self.assertIn("evidence_packet_verified", contract["required_release_gate_assertions"])
        self.assertIn("release_candidate_passed", contract["required_release_gate_assertions"])
        self.assertIn("release_candidate_verified", contract["required_release_gate_assertions"])
        self.assertIn("release_candidate_replayed", contract["required_release_gate_assertions"])
        self.assertIn("full_release_gate_official_ready", contract["required_publication_gate_assertions"])
        self.assertIn("release_candidate_replayed_for_publication", contract["required_publication_gate_assertions"])
        self.assertIn("official_gate_publishable", contract["required_official_claim_packet_checks"])

    def test_release_audit_passes_after_clean_bundle_build(self):
        bundle = build_release_bundle(DEFAULT_OUTPUT_DIR, clean=True)
        self.assertEqual(bundle["status"], "passed")
        audit = run_audit(DEFAULT_OUTPUT_DIR / "RELEASE_MANIFEST.json")
        self.assertEqual(audit["status"], "passed")
        self.assertTrue(audit["checks"]["manifest"]["checks"]["file_set_exact"])
        self.assertTrue(audit["checks"]["manifest"]["checks"]["file_hashes_match"])
        self.assertEqual(audit["checks"]["manifest"]["hash_errors"], [])

    def test_evidence_packet_materializes_claim_review_files(self):
        with _temporary_directory() as tmpdir:
            release_gate_json = Path(tmpdir) / "release_gate.json"
            release_gate_json.write_text(
                json.dumps(
                    {
                        "schema": "stock_harness_release_gate_v1",
                        "claim": {"status": "supported_for_included_benchmark_suite"},
                        "python_gate_passed": True,
                    }
                ),
                encoding="utf-8",
            )
            packet = build_evidence_packet(
                EVIDENCE_PACKET_OUTPUT_DIR,
                clean=True,
                release_gate_json=release_gate_json,
            )

        self.assertEqual(packet["schema"], "stock_harness_evidence_packet_v1")
        self.assertEqual(packet["status"], "passed")
        self.assertEqual(packet["claim_scope"]["benchmark_suite"], "downside_verification_v1")
        self.assertTrue(packet["release_gate_json"]["provided"])
        self.assertTrue(packet["release_gate_json"]["passed"])
        self.assertTrue(packet["checks"]["benchmark_all_passed"])
        self.assertTrue(packet["checks"]["claim_status_supported"])
        self.assertTrue(packet["checks"]["release_bundle_passed"])
        self.assertTrue(packet["checks"]["release_audit_passed"])
        paths = {entry["path"] for entry in packet["files"]}
        self.assertIn("benchmark_stock_harness.json", paths)
        self.assertIn("claim_comparison.json", paths)
        self.assertIn("release_bundle_manifest.json", paths)
        self.assertIn("release_audit.json", paths)
        self.assertIn("claim_contract.json", paths)
        self.assertIn("release_gate.json", paths)
        self.assertTrue((EVIDENCE_PACKET_OUTPUT_DIR / "EVIDENCE_MANIFEST.json").is_file())
        verification = verify_evidence_packet(
            EVIDENCE_PACKET_OUTPUT_DIR,
            require_release_gate_json=True,
        )
        self.assertEqual(verification["schema"], "stock_harness_evidence_packet_verification_v1")
        self.assertEqual(verification["status"], "passed")
        self.assertTrue(verification["checks"]["hashes"]["passed"])
        self.assertTrue(verification["checks"]["json_payloads"]["passed"])

    def test_evidence_packet_verifier_detects_tampered_payload(self):
        build_evidence_packet(EVIDENCE_PACKET_OUTPUT_DIR, clean=True)
        with _temporary_directory() as tmpdir:
            packet_copy = Path(tmpdir) / "packet"
            shutil.copytree(str(EVIDENCE_PACKET_OUTPUT_DIR), str(packet_copy))
            tampered = packet_copy / "claim_comparison.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            verification = verify_evidence_packet(packet_copy)

        self.assertEqual(verification["status"], "failed")
        self.assertFalse(verification["checks"]["hashes"]["passed"])
        errors = verification["checks"]["hashes"]["errors"]
        self.assertTrue(any(error["path"] == "claim_comparison.json" for error in errors))

    def test_evidence_packet_verifier_detects_missing_required_file(self):
        build_evidence_packet(EVIDENCE_PACKET_OUTPUT_DIR, clean=True)
        with _temporary_directory() as tmpdir:
            packet_copy = Path(tmpdir) / "packet"
            shutil.copytree(str(EVIDENCE_PACKET_OUTPUT_DIR), str(packet_copy))
            (packet_copy / "expected_summary.json").unlink()

            verification = verify_evidence_packet(packet_copy)

        self.assertEqual(verification["status"], "failed")
        self.assertFalse(verification["checks"]["hashes"]["passed"])
        self.assertFalse(verification["checks"]["json_payloads"]["passed"])

    def test_release_bundle_manifest_check_detects_tampered_bundle_file(self):
        with _temporary_directory() as tmpdir:
            bundle_dir = Path(tmpdir) / "stock_harness_release"
            bundle = build_release_bundle(bundle_dir)
            self.assertEqual(bundle["status"], "passed")
            readme = bundle_dir / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            contract = json.loads(Path(AUDIT_CLAIM_CONTRACT_PATH).read_text(encoding="utf-8"))

            check = _manifest_check(bundle_dir / "RELEASE_MANIFEST.json", contract)

        self.assertFalse(check["passed"])
        self.assertFalse(check["checks"]["file_hashes_match"])
        self.assertTrue(any(error["path"] == "README.md" for error in check["hash_errors"]))

    def test_release_candidate_materializes_and_verifies_archives(self):
        with _temporary_directory() as tmpdir:
            release_gate_json = Path(tmpdir) / "release_gate.json"
            release_gate_json.write_text(
                json.dumps(
                    {
                        "schema": "stock_harness_release_gate_v1",
                        "claim": {"status": "supported_for_included_benchmark_suite"},
                        "python_gate_passed": True,
                    }
                ),
                encoding="utf-8",
            )
            build_evidence_packet(
                EVIDENCE_PACKET_OUTPUT_DIR,
                clean=True,
                release_gate_json=release_gate_json,
            )
            candidate = build_release_candidate(RELEASE_CANDIDATE_OUTPUT_DIR, clean=True)

        self.assertEqual(candidate["schema"], "stock_harness_release_candidate_v1")
        self.assertEqual(candidate["status"], "passed")
        self.assertEqual(candidate["component_count"], 2)
        paths = {component["path"] for component in candidate["components"]}
        self.assertIn("stock_harness_release.zip", paths)
        self.assertIn("stock_harness_evidence_packet.zip", paths)
        verification = verify_release_candidate(
            RELEASE_CANDIDATE_OUTPUT_DIR,
            require_release_gate_json=True,
        )
        self.assertEqual(verification["schema"], "stock_harness_release_candidate_verification_v1")
        self.assertEqual(verification["status"], "passed")
        self.assertTrue(verification["checks"]["components"]["checks"]["component_hashes_match"])
        self.assertTrue(verification["checks"]["zip_payloads"]["checks"]["release_manifest_passed"])
        self.assertTrue(verification["checks"]["zip_payloads"]["checks"]["evidence_manifest_passed"])

    def test_release_candidate_replay_verifies_packaged_source_zip(self):
        if os.environ.get("STOCK_HARNESS_REPLAY_MODE") == "1":
            self.skipTest("skip nested release candidate replay while replaying packaged source")

        with _temporary_directory() as tmpdir:
            release_gate_json = Path(tmpdir) / "release_gate.json"
            release_gate_json.write_text(
                json.dumps(
                    {
                        "schema": "stock_harness_release_gate_v1",
                        "claim": {"status": "supported_for_included_benchmark_suite"},
                        "python_gate_passed": True,
                    }
                ),
                encoding="utf-8",
            )
            build_evidence_packet(
                EVIDENCE_PACKET_OUTPUT_DIR,
                clean=True,
                release_gate_json=release_gate_json,
            )
            build_release_candidate(RELEASE_CANDIDATE_OUTPUT_DIR, clean=True)

        replay = replay_release_candidate(
            RELEASE_CANDIDATE_OUTPUT_DIR,
            clean=True,
            skip_rust=True,
            require_release_gate_json=True,
        )
        self.assertEqual(replay["schema"], "stock_harness_release_candidate_replay_v1")
        self.assertEqual(replay["status"], "passed")
        assertion_ids = {assertion["id"] for assertion in replay["assertions"]}
        self.assertIn("extracted_py_compile_passed", assertion_ids)
        self.assertIn("extracted_unit_tests_passed", assertion_ids)
        self.assertIn("extracted_benchmark_passed", assertion_ids)
        self.assertIn("extracted_claim_supported", assertion_ids)
        self.assertIn("extracted_release_audit_passed", assertion_ids)
        self.assertIn("candidate_verifier_from_extracted_source_passed", assertion_ids)

    def test_release_candidate_verifier_detects_tampered_component_zip(self):
        build_evidence_packet(EVIDENCE_PACKET_OUTPUT_DIR, clean=True)
        build_release_candidate(RELEASE_CANDIDATE_OUTPUT_DIR, clean=True)
        with _temporary_directory() as tmpdir:
            candidate_copy = Path(tmpdir) / "candidate"
            shutil.copytree(str(RELEASE_CANDIDATE_OUTPUT_DIR), str(candidate_copy))
            zip_path = candidate_copy / "stock_harness_release.zip"
            with zip_path.open("ab") as handle:
                handle.write(b"tamper")

            verification = verify_release_candidate(candidate_copy)

        self.assertEqual(verification["status"], "failed")
        self.assertFalse(verification["checks"]["components"]["checks"]["component_hashes_match"])
        self.assertTrue(
            any(error["path"] == "stock_harness_release.zip" for error in verification["checks"]["components"]["errors"])
        )

    def test_release_candidate_official_requirement_fails_without_official_gate(self):
        build_evidence_packet(EVIDENCE_PACKET_OUTPUT_DIR, clean=True)
        build_release_candidate(RELEASE_CANDIDATE_OUTPUT_DIR, clean=True)

        verification = verify_release_candidate(
            RELEASE_CANDIDATE_OUTPUT_DIR,
            require_release_gate_json=True,
            require_official_claim_ready=True,
        )

        self.assertEqual(verification["status"], "failed")
        self.assertFalse(verification["checks"]["zip_payloads"]["passed"])

    def test_rust_stock_harness_port_is_std_only_and_scoped(self):
        required_paths = [
            Path("rust_stock_harness/Cargo.toml"),
            Path("rust_stock_harness/README.md"),
            Path("rust_stock_harness/src/lib.rs"),
            Path("rust_stock_harness/src/main.rs"),
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), str(path))

        cargo = Path("rust_stock_harness/Cargo.toml").read_text(encoding="utf-8")
        readme = Path("rust_stock_harness/README.md").read_text(encoding="utf-8")
        lib = Path("rust_stock_harness/src/lib.rs").read_text(encoding="utf-8")
        main = Path("rust_stock_harness/src/main.rs").read_text(encoding="utf-8")

        self.assertNotIn("[dependencies]", cargo)
        self.assertIn("not financial advice", readme)
        self.assertIn("No external crates are required", readme)
        self.assertIn("pub fn load_ohlcv_csv", lib)
        self.assertIn("pub fn run_data_quality_gate", lib)
        self.assertIn("pub fn run_backtest", lib)
        self.assertIn("pub fn run_benchmark_suite", lib)
        self.assertIn("stock-harness-benchmark", cargo)
        self.assertIn("run_benchmark_suite", main)

    def test_global_framework_contract_requires_named_external_evidence(self):
        report = run_global_comparison(run_external_adapters=False)

        self.assertEqual(report["schema"], "stock_harness_global_framework_comparison_v1")
        self.assertEqual(report["claim"]["benchmark_suite"], "global_verification_v1")
        self.assertEqual(report["claim"]["status"], "not_supported_missing_external_evidence")
        self.assertEqual(report["tools"]["angelos_stock_harness"]["coverage_score"], 1.0)
        self.assertEqual(report["tools"]["angelos_stock_harness"]["covered_count"], 18)
        self.assertEqual(
            set(report["publication_requirements"]["missing_external_frameworks"]),
            set(EXTERNAL_FRAMEWORK_PROFILES.keys()),
        )
        self.assertFalse(report["publication_requirements"]["checks"]["all_required_external_adapters_executed"])
        self.assertFalse(report["publication_requirements"]["checks"]["profile_only_frameworks_excluded_from_supported_claim"])

    def test_global_publication_requirements_pass_only_with_complete_direct_external_evidence(self):
        contract = _load_global_claim_contract()
        report = run_global_comparison(run_external_adapters=False)
        tools = report["tools"]
        for framework_id in EXTERNAL_FRAMEWORK_PROFILES:
            tools[framework_id]["direct_adapter"] = {
                "status": "passed",
                "direct_execution": True,
                "version": "test-version",
                "import_name": framework_id,
                "case_count": 4,
                "cases_passed": 4,
                "error": "",
            }

        publication = _evaluate_publication_requirements(tools, contract)

        self.assertTrue(publication["passed"])
        self.assertEqual(publication["named_external_adapters_executed_count"], len(EXTERNAL_FRAMEWORK_PROFILES))
        self.assertEqual(publication["missing_external_frameworks"], [])
        self.assertTrue(publication["checks"]["stock_harness_ranked_first_by_coverage_score"])
        self.assertTrue(publication["checks"]["stock_harness_score_strictly_exceeds_each_external_framework"])

    def test_global_claim_contract_preserves_non_claims(self):
        contract = _load_global_claim_contract()

        self.assertEqual(contract["schema"], "stock_harness_global_claim_contract_v1")
        self.assertEqual(contract["claim_id"], "global_downside_verification_sota_grade_v0_1")
        self.assertIn("No investment-performance or alpha-generation claim.", contract["non_claims"])
        self.assertIn("No speed, latency, or throughput dominance claim.", contract["non_claims"])
        self.assertIn(
            "No claim for frameworks that are profile-only or missing from the direct adapter evidence.",
            contract["non_claims"],
        )


if __name__ == "__main__":
    unittest.main()

