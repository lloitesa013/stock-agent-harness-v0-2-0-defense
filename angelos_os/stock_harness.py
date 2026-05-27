from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date as Date
from pathlib import Path
from typing import Any, Dict, List, Sequence


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjusted_close: float | None = None
    adjusted_open: float | None = None
    adjusted_high: float | None = None
    adjusted_low: float | None = None


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    trading_days: int = 252
    max_allowed_drawdown: float = 0.20


@dataclass
class Trade:
    date: str
    action: str
    price: float
    shares: float
    gross_value: float
    fee: float
    pnl: float
    target_exposure: float


@dataclass
class OrderIntent:
    date: str
    action: str
    target_exposure: float
    current_exposure: float
    desired_shares: float
    estimated_price: float


@dataclass
class EquityPoint:
    date: str
    equity: float
    cash: float
    shares: float
    close: float
    exposure: float
    benchmark_equity: float
    drawdown: float
    benchmark_drawdown: float


@dataclass
class HarnessVerdict:
    verdict: str
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarketCalendarProfile:
    name: str = "weekday"
    expected_sessions: Sequence[str] = field(default_factory=tuple)
    holidays: Sequence[str] = field(default_factory=tuple)
    half_days: Sequence[str] = field(default_factory=tuple)
    weekend_days: Sequence[int] = (5, 6)


@dataclass
class DataQualityConfig:
    min_bars: int = 2
    max_zero_volume_ratio: float = 0.0
    max_missing_business_days_per_gap: int = 2
    max_open_gap_ratio: float = 0.30
    max_close_jump_ratio: float = 0.45
    min_adjustment_ratio: float = 0.01
    max_adjustment_ratio: float = 100.0
    max_adjustment_ratio_change: float = 0.20
    max_adjusted_ohlc_ratio_spread: float = 0.001
    market_calendar: MarketCalendarProfile | None = None
    max_missing_calendar_sessions_per_gap: int = 0


@dataclass(frozen=True)
class DataQualityIssue:
    severity: str
    code: str
    index: int | None = None
    date: str | None = None
    message: str = ""


@dataclass
class DataQualityResult:
    config: DataQualityConfig
    bar_count: int
    metrics: Dict[str, Any]
    issues: List[DataQualityIssue]
    verdict: HarnessVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": asdict(self.config),
            "bar_count": self.bar_count,
            "metrics": self.metrics,
            "issues": [asdict(issue) for issue in self.issues],
            "verdict": asdict(self.verdict),
        }


@dataclass
class EngineParityTolerance:
    equity_abs_tolerance: float = 1e-6
    equity_rel_tolerance: float = 1e-9
    trade_abs_tolerance: float = 1e-6
    trade_rel_tolerance: float = 1e-9


@dataclass(frozen=True)
class ExternalEngineEquityPoint:
    date: str
    equity: float
    benchmark_equity: float | None = None


@dataclass(frozen=True)
class ExternalEngineTrade:
    date: str
    action: str
    price: float | None = None
    shares: float | None = None
    gross_value: float | None = None


@dataclass(frozen=True)
class ExternalEngineFill:
    date: str
    action: str
    price: float | None = None
    shares: float | None = None
    gross_value: float | None = None
    fee: float | None = None
    pnl: float | None = None
    target_exposure: float | None = None


@dataclass(frozen=True)
class ExternalEngineOrderIntent:
    date: str
    action: str
    target_exposure: float | None = None
    current_exposure: float | None = None
    desired_shares: float | None = None
    estimated_price: float | None = None


@dataclass(frozen=True)
class EngineParityDiff:
    section: str
    code: str
    index: int | None = None
    date: str | None = None
    field: str | None = None
    harness_value: Any = None
    reference_value: Any = None
    abs_error: float | None = None
    rel_error: float | None = None
    message: str = ""


@dataclass
class EngineParityResult:
    engine_name: str
    tolerance: EngineParityTolerance
    metrics: Dict[str, Any]
    checks: Dict[str, bool]
    verdict: HarnessVerdict
    diffs: List[EngineParityDiff] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_name": self.engine_name,
            "tolerance": asdict(self.tolerance),
            "metrics": self.metrics,
            "checks": self.checks,
            "verdict": asdict(self.verdict),
            "diffs": [asdict(diff) for diff in self.diffs],
        }


@dataclass
class BacktestResult:
    strategy_name: str
    config: BacktestConfig
    metrics: Dict[str, Any]
    benchmark_metrics: Dict[str, Any]
    trades: List[Trade]
    equity_curve: List[EquityPoint]
    verdict: HarnessVerdict
    order_intents: List[OrderIntent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "research_only": True,
            "config": asdict(self.config),
            "metrics": self.metrics,
            "benchmark_metrics": self.benchmark_metrics,
            "trades": [asdict(trade) for trade in self.trades],
            "order_intents": [asdict(intent) for intent in self.order_intents],
            "equity_curve": [asdict(point) for point in self.equity_curve],
            "verdict": asdict(self.verdict),
        }


@dataclass
class LookaheadAuditResult:
    passed: bool
    checked_decisions: int
    changed_decisions: int
    reasons: List[str] = field(default_factory=list)


@dataclass
class WalkForwardFold:
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    result: BacktestResult


@dataclass
class WalkForwardResult:
    strategy_name: str
    train_size: int
    test_size: int
    step_size: int
    folds: List[WalkForwardFold]
    metrics: Dict[str, Any]
    verdict: HarnessVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "train_size": self.train_size,
            "test_size": self.test_size,
            "step_size": self.step_size,
            "metrics": self.metrics,
            "verdict": asdict(self.verdict),
            "folds": [
                {
                    "fold_index": fold.fold_index,
                    "train_start": fold.train_start,
                    "train_end": fold.train_end,
                    "test_start": fold.test_start,
                    "test_end": fold.test_end,
                    "result": fold.result.to_dict(),
                }
                for fold in self.folds
            ],
        }


@dataclass(frozen=True)
class RegimeStressCase:
    name: str
    bars: Sequence[Bar]
    expected_verdict: str
    description: str = ""


@dataclass
class RegimeStressCaseResult:
    name: str
    expected_verdict: str
    actual_verdict: str
    passed: bool
    reasons: List[str]
    result: BacktestResult


@dataclass
class RegimeStressResult:
    strategy_name: str
    cases: List[RegimeStressCaseResult]
    metrics: Dict[str, Any]
    verdict: HarnessVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "metrics": self.metrics,
            "verdict": asdict(self.verdict),
            "cases": [
                {
                    "name": case.name,
                    "expected_verdict": case.expected_verdict,
                    "actual_verdict": case.actual_verdict,
                    "passed": case.passed,
                    "reasons": case.reasons,
                    "result": case.result.to_dict(),
                }
                for case in self.cases
            ],
        }


@dataclass
class ParameterSweepCase:
    window: int
    backtest: BacktestResult
    walk_forward: WalkForwardResult
    regime_stress: RegimeStressResult
    passed: bool
    score: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class ParameterSweepResult:
    strategy_family: str
    windows: List[int]
    cases: List[ParameterSweepCase]
    best_window: int | None
    metrics: Dict[str, Any]
    verdict: HarnessVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_family": self.strategy_family,
            "windows": self.windows,
            "best_window": self.best_window,
            "metrics": self.metrics,
            "verdict": asdict(self.verdict),
            "cases": [
                {
                    "window": case.window,
                    "passed": case.passed,
                    "score": case.score,
                    "reasons": case.reasons,
                    "backtest": _result_summary(case.backtest),
                    "walk_forward": {
                        "verdict": asdict(case.walk_forward.verdict),
                        "metrics": case.walk_forward.metrics,
                    },
                    "regime_stress": {
                        "verdict": asdict(case.regime_stress.verdict),
                        "metrics": case.regime_stress.metrics,
                    },
                }
                for case in self.cases
            ],
        }


@dataclass(frozen=True)
class CostStressCase:
    fee_bps: float
    slippage_bps: float
    name: str = ""


@dataclass
class CostStressCaseResult:
    name: str
    fee_bps: float
    slippage_bps: float
    result: BacktestResult
    passed: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class CostStressResult:
    strategy_name: str
    cases: List[CostStressCaseResult]
    metrics: Dict[str, Any]
    verdict: HarnessVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "metrics": self.metrics,
            "verdict": asdict(self.verdict),
            "cases": [
                {
                    "name": case.name,
                    "fee_bps": case.fee_bps,
                    "slippage_bps": case.slippage_bps,
                    "passed": case.passed,
                    "reasons": case.reasons,
                    "result": _result_summary(case.result),
                }
                for case in self.cases
            ],
        }


@dataclass(frozen=True)
class StressMatrixCase:
    name: str
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    execution_delay_bars: int = 0
    adverse_open_gap_bps: float = 0.0
    cash_yield_annual: float = 0.0
    max_participation_rate: float | None = None
    market_impact_bps_per_100pct_participation: float = 0.0


@dataclass
class StressMatrixCaseResult:
    name: str
    case: StressMatrixCase
    result: BacktestResult
    passed: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class StressMatrixResult:
    strategy_name: str
    cases: List[StressMatrixCaseResult]
    metrics: Dict[str, Any]
    verdict: HarnessVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "metrics": self.metrics,
            "verdict": asdict(self.verdict),
            "cases": [
                {
                    "name": case.name,
                    "case": asdict(case.case),
                    "passed": case.passed,
                    "reasons": case.reasons,
                    "result": _result_summary(case.result),
                }
                for case in self.cases
            ],
        }


@dataclass(frozen=True)
class MultiAssetBenchmarkCase:
    name: str
    bars: Sequence[Bar]
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MultiAssetBenchmarkCaseResult:
    name: str
    description: str
    tags: Dict[str, str]
    passed: bool
    reasons: List[str]
    data_quality: DataQualityResult
    backtest: BacktestResult
    bars: Sequence[Bar] = field(default_factory=tuple)


@dataclass
class MultiAssetBenchmarkResult:
    strategy_name: str
    cases: List[MultiAssetBenchmarkCaseResult]
    metrics: Dict[str, Any]
    verdict: HarnessVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "metrics": self.metrics,
            "verdict": asdict(self.verdict),
            "cases": [
                {
                    "name": case.name,
                    "description": case.description,
                    "tags": case.tags,
                    "passed": case.passed,
                    "reasons": case.reasons,
                    "data": _data_summary(case.bars),
                    "data_quality": case.data_quality.to_dict(),
                    "backtest": _result_summary(case.backtest),
                }
                for case in self.cases
            ],
        }


@dataclass(frozen=True)
class MovingAverageCashStrategy:
    window: int = 200

    def __post_init__(self) -> None:
        if self.window <= 0:
            raise ValueError("window must be positive")

    @property
    def name(self) -> str:
        return f"ma_cash_{self.window}"

    @property
    def min_history(self) -> int:
        return self.window

    def target_exposure(self, history: Sequence[Bar]) -> float:
        if len(history) < self.window:
            return 0.0
        closes = [bar.close for bar in history[-self.window :]]
        moving_average = sum(closes) / float(self.window)
        return 1.0 if history[-1].close > moving_average else 0.0


def load_ohlcv_csv(path: str | Path) -> List[Bar]:
    csv_path = Path(path)
    required = {"date", "open", "high", "low", "close", "volume"}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV must include a header row")
        missing = sorted(required.difference(reader.fieldnames))
        if missing:
            raise ValueError(f"CSV missing required fields: {', '.join(missing)}")

        bars: List[Bar] = []
        for row_number, row in enumerate(reader, start=2):
            bars.append(_bar_from_row(row, row_number=row_number))

    if not bars:
        raise ValueError("CSV must contain at least one OHLCV row")
    return bars


def load_market_calendar_csv(path: str | Path, *, name: str | None = None) -> MarketCalendarProfile:
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError("CSV must include a header row")
        if "date" not in fieldnames:
            raise ValueError("CSV missing required fields: date")
        if "status" not in fieldnames and "is_open" not in fieldnames:
            raise ValueError("market calendar CSV must include status or is_open")

        expected_sessions: List[str] = []
        holidays: List[str] = []
        half_days: List[str] = []
        seen_dates: Dict[str, int] = {}
        for row_number, row in enumerate(reader, start=2):
            session_date = str(row.get("date", "")).strip()
            if not session_date:
                raise ValueError(f"row {row_number}: date is required")
            if _parse_iso_date(session_date) is None:
                raise ValueError(f"row {row_number}: date must be ISO YYYY-MM-DD")
            if session_date in seen_dates:
                raise ValueError(f"row {row_number}: duplicate calendar date {session_date}")
            seen_dates[session_date] = row_number
            status = _calendar_status_from_row(row, row_number)
            if status == "open":
                expected_sessions.append(session_date)
            elif status == "half_day":
                expected_sessions.append(session_date)
                half_days.append(session_date)
            else:
                holidays.append(session_date)

    if not seen_dates:
        raise ValueError("market calendar CSV must contain at least one row")
    return MarketCalendarProfile(
        name=(name or csv_path.stem),
        expected_sessions=tuple(expected_sessions),
        holidays=tuple(holidays),
        half_days=tuple(half_days),
    )


def load_multi_asset_csv_directory(
    directory: str | Path,
    *,
    pattern: str = "*.csv",
    recursive: bool = False,
    tags: Dict[str, str] | None = None,
) -> List[MultiAssetBenchmarkCase]:
    root = Path(directory)
    if not root.exists():
        raise ValueError(f"multi-asset CSV directory does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"multi-asset CSV path must be a directory: {root}")
    paths = sorted(root.rglob(pattern) if recursive else root.glob(pattern))
    cases: List[MultiAssetBenchmarkCase] = []
    for path in paths:
        if not path.is_file():
            continue
        case_tags = dict(tags or {})
        case_tags.setdefault("source", "csv_directory")
        case_tags.setdefault("file", path.name)
        cases.append(
            MultiAssetBenchmarkCase(
                name=path.stem,
                bars=load_ohlcv_csv(path),
                description=str(path),
                tags=case_tags,
            )
        )
    if not cases:
        raise ValueError(f"no CSV files matched pattern {pattern!r} under {root}")
    return cases


def load_engine_equity_csv(path: str | Path) -> List[ExternalEngineEquityPoint]:
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_csv_fields(reader.fieldnames, {"date", "equity"})
        points: List[ExternalEngineEquityPoint] = []
        for row_number, row in enumerate(reader, start=2):
            date = str(row.get("date", "")).strip()
            if not date:
                raise ValueError(f"row {row_number}: date is required")
            points.append(
                ExternalEngineEquityPoint(
                    date=date,
                    equity=_required_csv_float(row, "equity", row_number),
                    benchmark_equity=_optional_csv_float(row, "benchmark_equity", row_number),
                )
            )
    if not points:
        raise ValueError("engine equity CSV must contain at least one row")
    return points


def load_engine_trades_csv(path: str | Path) -> List[ExternalEngineTrade]:
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_csv_fields(reader.fieldnames, {"date", "action"})
        trades: List[ExternalEngineTrade] = []
        for row_number, row in enumerate(reader, start=2):
            date = str(row.get("date", "")).strip()
            action = str(row.get("action", "")).strip().lower()
            if not date:
                raise ValueError(f"row {row_number}: date is required")
            if action not in {"buy", "sell"}:
                raise ValueError(f"row {row_number}: action must be buy or sell")
            trades.append(
                ExternalEngineTrade(
                    date=date,
                    action=action,
                    price=_optional_csv_float(row, "price", row_number),
                    shares=_optional_csv_float(row, "shares", row_number),
                    gross_value=_optional_csv_float(row, "gross_value", row_number),
                )
            )
    return trades


def load_engine_fills_csv(path: str | Path) -> List[ExternalEngineFill]:
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_csv_fields(reader.fieldnames, {"date", "action"})
        fills: List[ExternalEngineFill] = []
        for row_number, row in enumerate(reader, start=2):
            date = str(row.get("date", "")).strip()
            action = str(row.get("action", "")).strip().lower()
            if not date:
                raise ValueError(f"row {row_number}: date is required")
            if action not in {"buy", "sell"}:
                raise ValueError(f"row {row_number}: action must be buy or sell")
            fills.append(
                ExternalEngineFill(
                    date=date,
                    action=action,
                    price=_optional_csv_float(row, "price", row_number),
                    shares=_optional_csv_float(row, "shares", row_number),
                    gross_value=_optional_csv_float(row, "gross_value", row_number),
                    fee=_optional_csv_float(row, "fee", row_number),
                    pnl=_optional_csv_float(row, "pnl", row_number),
                    target_exposure=_optional_csv_float(row, "target_exposure", row_number),
                )
            )
    return fills


def load_engine_order_intents_csv(path: str | Path) -> List[ExternalEngineOrderIntent]:
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_csv_fields(reader.fieldnames, {"date", "action"})
        intents: List[ExternalEngineOrderIntent] = []
        for row_number, row in enumerate(reader, start=2):
            date = str(row.get("date", "")).strip()
            action = str(row.get("action", "")).strip().lower()
            if not date:
                raise ValueError(f"row {row_number}: date is required")
            if action not in {"buy", "sell"}:
                raise ValueError(f"row {row_number}: action must be buy or sell")
            intents.append(
                ExternalEngineOrderIntent(
                    date=date,
                    action=action,
                    target_exposure=_optional_csv_float(row, "target_exposure", row_number),
                    current_exposure=_optional_csv_float(row, "current_exposure", row_number),
                    desired_shares=_optional_csv_float(row, "desired_shares", row_number),
                    estimated_price=_optional_csv_float(row, "estimated_price", row_number),
                )
            )
    return intents


def run_data_quality_gate(
    bars: Sequence[Bar],
    config: DataQualityConfig | None = None,
) -> DataQualityResult:
    cfg = config or DataQualityConfig()
    issues: List[DataQualityIssue] = []
    metrics = _empty_data_quality_metrics()
    metrics["bar_count"] = len(bars)

    config_errors = _validate_data_quality_config(cfg)
    for error in config_errors:
        issues.append(DataQualityIssue(severity="ERROR", code="config_invalid", message=error))
    if config_errors:
        return _data_quality_result(cfg, bars, metrics, issues)

    if len(bars) < cfg.min_bars:
        issues.append(
            DataQualityIssue(
                severity="ERROR",
                code="insufficient_bars",
                message=f"need at least {cfg.min_bars} bars",
            )
        )

    seen_dates: Dict[str, int] = {}
    parsed_dates: List[Date | None] = []
    zero_volume_count = 0
    adjusted_close_count = 0
    adjusted_ohlc_count = 0
    adjusted_ohlc_side_field_seen = False
    open_gap_ratios: List[float] = []
    close_jump_ratios: List[float] = []
    adjustment_ratios: List[float] = []
    adjustment_ratio_changes: List[float] = []
    adjusted_ohlc_presence_counts: List[int] = []
    adjusted_ohlc_ratio_spreads: List[float] = []
    missing_business_days = 0
    missing_calendar_sessions = 0
    calendar_expected_sessions = 0
    calendar_unexpected_sessions = 0
    calendar_half_day_count = 0

    for idx, bar in enumerate(bars):
        try:
            _validate_bar(bar, label=f"bar {idx}")
        except ValueError as exc:
            issues.append(
                DataQualityIssue(
                    severity="ERROR",
                    code="invalid_ohlcv",
                    index=idx,
                    date=bar.date,
                    message=str(exc),
                )
            )

        if bar.volume == 0.0:
            zero_volume_count += 1

        if bar.adjusted_close is not None:
            adjusted_close_count += 1
            if bar.close > 0.0 and bar.adjusted_close > 0.0 and math.isfinite(bar.adjusted_close):
                adjustment_ratio = bar.adjusted_close / bar.close
                adjustment_ratios.append(adjustment_ratio)
                if adjustment_ratio < cfg.min_adjustment_ratio or adjustment_ratio > cfg.max_adjustment_ratio:
                    issues.append(
                        DataQualityIssue(
                            severity="ERROR",
                            code="invalid_adjustment_ratio",
                            index=idx,
                            date=bar.date,
                            message=(
                                f"adjusted_close/close ratio {adjustment_ratio:.6f} outside "
                                f"[{cfg.min_adjustment_ratio:.6f}, {cfg.max_adjustment_ratio:.6f}]"
                            ),
                        )
                    )
                if idx > 0:
                    previous = bars[idx - 1]
                    if (
                        previous.adjusted_close is not None
                        and previous.close > 0.0
                        and previous.adjusted_close > 0.0
                        and math.isfinite(previous.adjusted_close)
                    ):
                        previous_ratio = previous.adjusted_close / previous.close
                        if previous_ratio > 0.0 and math.isfinite(previous_ratio):
                            ratio_change = abs(adjustment_ratio / previous_ratio - 1.0)
                            adjustment_ratio_changes.append(ratio_change)
                            if ratio_change > cfg.max_adjustment_ratio_change:
                                issues.append(
                                    DataQualityIssue(
                                        severity="ERROR",
                                        code="adjustment_ratio_jump",
                                        index=idx,
                                        date=bar.date,
                                        message=(
                                            f"adjustment ratio change {ratio_change:.6f} exceeds "
                                            f"{cfg.max_adjustment_ratio_change:.6f}"
                                        ),
                                    )
                                )
        adjusted_ohlc_values = (bar.adjusted_open, bar.adjusted_high, bar.adjusted_low, bar.adjusted_close)
        adjusted_ohlc_presence_count = sum(1 for value in adjusted_ohlc_values if value is not None)
        adjusted_ohlc_presence_counts.append(adjusted_ohlc_presence_count)
        if any(value is not None for value in (bar.adjusted_open, bar.adjusted_high, bar.adjusted_low)):
            adjusted_ohlc_side_field_seen = True
        if adjusted_ohlc_presence_count == 4:
            adjusted_ohlc_count += 1
            ratios = [
                bar.adjusted_open / bar.open,
                bar.adjusted_high / bar.high,
                bar.adjusted_low / bar.low,
                bar.adjusted_close / bar.close,
            ]
            if all(math.isfinite(ratio) and ratio > 0.0 for ratio in ratios):
                ratio_spread = max(ratios) - min(ratios)
                adjusted_ohlc_ratio_spreads.append(ratio_spread)
                if ratio_spread > cfg.max_adjusted_ohlc_ratio_spread:
                    issues.append(
                        DataQualityIssue(
                            severity="ERROR",
                            code="adjusted_ohlc_ratio_mismatch",
                            index=idx,
                            date=bar.date,
                            message=(
                                f"adjusted OHLC ratio spread {ratio_spread:.6f} exceeds "
                                f"{cfg.max_adjusted_ohlc_ratio_spread:.6f}"
                            ),
                        )
                    )

        previous_index = seen_dates.get(bar.date)
        if previous_index is not None:
            issues.append(
                DataQualityIssue(
                    severity="ERROR",
                    code="duplicate_date",
                    index=idx,
                    date=bar.date,
                    message=f"first seen at index {previous_index}",
                )
            )
        else:
            seen_dates[bar.date] = idx

        parsed_dates.append(_parse_iso_date(bar.date))

        if idx == 0:
            continue
        previous = bars[idx - 1]
        if previous.close > 0.0 and all(math.isfinite(value) for value in (previous.close, bar.open, bar.close)):
            open_gap = abs(bar.open / previous.close - 1.0)
            close_jump = abs(bar.close / previous.close - 1.0)
            open_gap_ratios.append(open_gap)
            close_jump_ratios.append(close_jump)
            if open_gap > cfg.max_open_gap_ratio:
                issues.append(
                    DataQualityIssue(
                        severity="ERROR",
                        code="suspicious_open_gap",
                        index=idx,
                        date=bar.date,
                        message=f"open gap {open_gap:.4f} exceeds {cfg.max_open_gap_ratio:.4f}",
                    )
                )
            if close_jump > cfg.max_close_jump_ratio:
                issues.append(
                    DataQualityIssue(
                        severity="ERROR",
                        code="split_like_close_jump",
                        index=idx,
                        date=bar.date,
                        message=f"close jump {close_jump:.4f} exceeds {cfg.max_close_jump_ratio:.4f}",
                    )
                )

    parsed_count = sum(1 for parsed in parsed_dates if parsed is not None)
    if parsed_count == len(bars):
        calendar_profile = cfg.market_calendar
        if calendar_profile is not None and parsed_dates:
            observed_dates = [parsed for parsed in parsed_dates if parsed is not None]
            calendar_expected = _calendar_expected_sessions(
                calendar_profile,
                min(observed_dates),
                max(observed_dates),
            )
            calendar_expected_sessions = len(calendar_expected)
            calendar_half_days = _market_calendar_date_set(calendar_profile.half_days)
            for idx, current_date in enumerate(parsed_dates):
                if current_date is None:
                    continue
                if current_date in calendar_half_days:
                    calendar_half_day_count += 1
                if not _calendar_is_expected_session(calendar_profile, current_date):
                    calendar_unexpected_sessions += 1
                    issues.append(
                        DataQualityIssue(
                            severity="ERROR",
                            code="non_trading_session",
                            index=idx,
                            date=bars[idx].date,
                            message=f"{current_date.isoformat()} is not an expected session in {calendar_profile.name}",
                        )
                    )
        for idx in range(1, len(parsed_dates)):
            previous_date = parsed_dates[idx - 1]
            current_date = parsed_dates[idx]
            if previous_date is None or current_date is None:
                continue
            if current_date <= previous_date:
                issues.append(
                    DataQualityIssue(
                        severity="ERROR",
                        code="non_monotonic_date",
                        index=idx,
                        date=bars[idx].date,
                        message=f"{current_date.isoformat()} is not after {previous_date.isoformat()}",
                    )
                )
                continue
            if calendar_profile is None:
                gap = _business_days_between(previous_date, current_date)
                missing_business_days += gap
                if gap > cfg.max_missing_business_days_per_gap:
                    issues.append(
                        DataQualityIssue(
                            severity="ERROR",
                            code="missing_business_dates",
                            index=idx,
                            date=bars[idx].date,
                            message=f"{gap} business days missing after {previous_date.isoformat()}",
                        )
                    )
                continue

            gap = _calendar_sessions_between(calendar_profile, previous_date, current_date)
            missing_business_days += gap
            missing_calendar_sessions += gap
            if gap > cfg.max_missing_calendar_sessions_per_gap:
                issues.append(
                    DataQualityIssue(
                        severity="ERROR",
                        code="missing_calendar_sessions",
                        index=idx,
                        date=bars[idx].date,
                        message=(
                            f"{gap} expected {calendar_profile.name} sessions missing "
                            f"after {previous_date.isoformat()}"
                        ),
                    )
                )
        metrics["date_checks_applied"] = True
    elif parsed_count > 0:
        issues.append(
            DataQualityIssue(
                severity="ERROR",
                code="mixed_date_formats",
                message="all dates must be ISO YYYY-MM-DD when any date is ISO parseable",
            )
        )
    elif bars:
        issues.append(
            DataQualityIssue(
                severity="WARN",
                code="date_sequence_checks_skipped",
                message="dates are not ISO YYYY-MM-DD; duplicate checks still applied",
            )
        )

    zero_volume_ratio = 0.0 if not bars else zero_volume_count / len(bars)
    if zero_volume_ratio > cfg.max_zero_volume_ratio:
        issues.append(
            DataQualityIssue(
                severity="ERROR",
                code="zero_volume",
                message=f"zero-volume ratio {zero_volume_ratio:.4f} exceeds {cfg.max_zero_volume_ratio:.4f}",
            )
        )

    if 0 < adjusted_close_count < len(bars):
        issues.append(
            DataQualityIssue(
                severity="ERROR",
                code="mixed_adjusted_close",
                message="adjusted close must be present for every bar when any adjusted close is present",
            )
        )
    partial_adjusted_ohlc_count = 0
    if adjusted_ohlc_side_field_seen:
        partial_adjusted_ohlc_count = sum(1 for count in adjusted_ohlc_presence_counts if count != 4)
        if partial_adjusted_ohlc_count > 0:
            issues.append(
                DataQualityIssue(
                    severity="ERROR",
                    code="mixed_adjusted_ohlc",
                    message=(
                        "adjusted open/high/low/close must be complete for every bar "
                        "when adjusted OHLC fields are present"
                    ),
                )
            )

    metrics.update(
        {
            "unique_dates": len(seen_dates),
            "duplicate_dates": len(bars) - len(seen_dates),
            "zero_volume_count": zero_volume_count,
            "zero_volume_ratio": zero_volume_ratio,
            "adjusted_close_count": adjusted_close_count,
            "adjusted_ohlc_count": adjusted_ohlc_count,
            "partial_adjusted_ohlc_count": partial_adjusted_ohlc_count,
            "adjustment_checks_applied": bool(bars) and adjusted_close_count == len(bars),
            "adjusted_ohlc_checks_applied": bool(bars) and adjusted_ohlc_count == len(bars),
            "min_adjustment_ratio": min(adjustment_ratios, default=0.0),
            "max_adjustment_ratio": max(adjustment_ratios, default=0.0),
            "max_adjustment_ratio_change": max(adjustment_ratio_changes, default=0.0),
            "max_adjusted_ohlc_ratio_spread": max(adjusted_ohlc_ratio_spreads, default=0.0),
            "calendar_profile_name": "" if cfg.market_calendar is None else cfg.market_calendar.name,
            "calendar_profile_applied": cfg.market_calendar is not None and parsed_count == len(bars),
            "calendar_expected_sessions": calendar_expected_sessions,
            "calendar_missing_sessions": missing_calendar_sessions,
            "calendar_unexpected_sessions": calendar_unexpected_sessions,
            "calendar_half_day_count": calendar_half_day_count,
            "missing_business_days": missing_business_days,
            "max_open_gap_ratio": max(open_gap_ratios, default=0.0),
            "max_close_jump_ratio": max(close_jump_ratios, default=0.0),
        }
    )
    return _data_quality_result(cfg, bars, metrics, issues)


def run_engine_parity_check(
    result: BacktestResult,
    reference_equity: Sequence[ExternalEngineEquityPoint],
    reference_trades: Sequence[ExternalEngineTrade] | None = None,
    *,
    reference_fills: Sequence[ExternalEngineFill] | None = None,
    reference_order_intents: Sequence[ExternalEngineOrderIntent] | None = None,
    engine_name: str = "external_engine",
    tolerance: EngineParityTolerance | None = None,
    max_diffs: int = 20,
) -> EngineParityResult:
    tol = tolerance or EngineParityTolerance()
    validation_errors = _validate_engine_parity_tolerance(tol)
    if max_diffs < 0:
        validation_errors.append("max_diffs must be non-negative")
    if validation_errors:
        return EngineParityResult(
            engine_name=engine_name,
            tolerance=tol,
            metrics=_empty_engine_parity_metrics(
                result,
                reference_equity,
                reference_trades,
                reference_fills,
                reference_order_intents,
            ),
            checks=_failed_engine_parity_checks(),
            verdict=HarnessVerdict(verdict="REJECT", reasons=validation_errors),
        )

    checks = {
        "equity_point_count": len(result.equity_curve) == len(reference_equity),
        "equity_dates": True,
        "equity_values": True,
        "benchmark_values": True,
        "trade_count": True,
        "trade_actions": True,
        "trade_values": True,
        "fill_count": True,
        "fill_actions": True,
        "fill_values": True,
        "order_intent_count": True,
        "order_intent_actions": True,
        "order_intent_values": True,
    }
    metrics = _empty_engine_parity_metrics(
        result,
        reference_equity,
        reference_trades,
        reference_fills,
        reference_order_intents,
    )
    metrics["max_recorded_diffs"] = max_diffs
    diffs: List[EngineParityDiff] = []

    if not checks["equity_point_count"]:
        _record_engine_parity_diff(
            diffs,
            metrics,
            max_diffs,
            EngineParityDiff(
                section="equity",
                code="equity_point_count_mismatch",
                harness_value=len(result.equity_curve),
                reference_value=len(reference_equity),
                message="equity point count differs",
            ),
        )

    if not reference_equity:
        checks["equity_point_count"] = False
        checks["equity_values"] = False
        _record_engine_parity_diff(
            diffs,
            metrics,
            max_diffs,
            EngineParityDiff(
                section="equity",
                code="reference_equity_empty",
                harness_value=len(result.equity_curve),
                reference_value=0,
                message="reference equity trace is empty",
            ),
        )

    compared_points = min(len(result.equity_curve), len(reference_equity))
    reference_benchmark_points = 0
    for idx in range(compared_points):
        harness_point = result.equity_curve[idx]
        reference_point = reference_equity[idx]
        if harness_point.date != reference_point.date:
            checks["equity_dates"] = False
            _record_engine_parity_diff(
                diffs,
                metrics,
                max_diffs,
                EngineParityDiff(
                    section="equity",
                    code="equity_date_mismatch",
                    index=idx,
                    date=harness_point.date,
                    field="date",
                    harness_value=harness_point.date,
                    reference_value=reference_point.date,
                    message="equity date differs",
                ),
            )
        equity_abs_error = abs(harness_point.equity - reference_point.equity)
        equity_rel_error = _relative_error(harness_point.equity, reference_point.equity)
        metrics["max_equity_abs_error"] = max(metrics["max_equity_abs_error"], equity_abs_error)
        metrics["max_equity_rel_error"] = max(metrics["max_equity_rel_error"], equity_rel_error)
        if not _within_parity_tolerance(
            harness_point.equity,
            reference_point.equity,
            abs_tolerance=tol.equity_abs_tolerance,
            rel_tolerance=tol.equity_rel_tolerance,
        ):
            checks["equity_values"] = False
            _record_engine_parity_diff(
                diffs,
                metrics,
                max_diffs,
                EngineParityDiff(
                    section="equity",
                    code="equity_value_mismatch",
                    index=idx,
                    date=harness_point.date,
                    field="equity",
                    harness_value=harness_point.equity,
                    reference_value=reference_point.equity,
                    abs_error=equity_abs_error,
                    rel_error=equity_rel_error,
                    message="equity value outside tolerance",
                ),
            )

        if reference_point.benchmark_equity is not None:
            reference_benchmark_points += 1
            benchmark_abs_error = abs(harness_point.benchmark_equity - reference_point.benchmark_equity)
            benchmark_rel_error = _relative_error(harness_point.benchmark_equity, reference_point.benchmark_equity)
            metrics["max_benchmark_abs_error"] = max(metrics["max_benchmark_abs_error"], benchmark_abs_error)
            metrics["max_benchmark_rel_error"] = max(metrics["max_benchmark_rel_error"], benchmark_rel_error)
            if not _within_parity_tolerance(
                harness_point.benchmark_equity,
                reference_point.benchmark_equity,
                abs_tolerance=tol.equity_abs_tolerance,
                rel_tolerance=tol.equity_rel_tolerance,
            ):
                checks["benchmark_values"] = False
                _record_engine_parity_diff(
                    diffs,
                    metrics,
                    max_diffs,
                    EngineParityDiff(
                        section="benchmark",
                        code="benchmark_value_mismatch",
                        index=idx,
                        date=harness_point.date,
                        field="benchmark_equity",
                        harness_value=harness_point.benchmark_equity,
                        reference_value=reference_point.benchmark_equity,
                        abs_error=benchmark_abs_error,
                        rel_error=benchmark_rel_error,
                        message="benchmark equity value outside tolerance",
                    ),
                )

    metrics["compared_equity_points"] = compared_points
    metrics["reference_benchmark_points"] = reference_benchmark_points

    if reference_trades is not None:
        checks["trade_count"] = len(result.trades) == len(reference_trades)
        if not checks["trade_count"]:
            _record_engine_parity_diff(
                diffs,
                metrics,
                max_diffs,
                EngineParityDiff(
                    section="trade",
                    code="trade_count_mismatch",
                    harness_value=len(result.trades),
                    reference_value=len(reference_trades),
                    message="trade count differs",
                ),
            )
        compared_trades = min(len(result.trades), len(reference_trades))
        for idx in range(compared_trades):
            harness_trade = result.trades[idx]
            reference_trade = reference_trades[idx]
            if harness_trade.date != reference_trade.date or harness_trade.action.lower() != reference_trade.action.lower():
                checks["trade_actions"] = False
                _record_engine_parity_diff(
                    diffs,
                    metrics,
                    max_diffs,
                    EngineParityDiff(
                        section="trade",
                        code="trade_action_mismatch",
                        index=idx,
                        date=harness_trade.date,
                        field="date_action",
                        harness_value=f"{harness_trade.date}:{harness_trade.action.lower()}",
                        reference_value=f"{reference_trade.date}:{reference_trade.action.lower()}",
                        message="trade date or action differs",
                    ),
                )
            for field_name in ("price", "shares", "gross_value"):
                reference_value = getattr(reference_trade, field_name)
                if reference_value is None:
                    continue
                harness_value = getattr(harness_trade, field_name)
                abs_error = abs(harness_value - reference_value)
                rel_error = _relative_error(harness_value, reference_value)
                metrics[f"max_trade_{field_name}_abs_error"] = max(
                    metrics[f"max_trade_{field_name}_abs_error"],
                    abs_error,
                )
                metrics[f"max_trade_{field_name}_rel_error"] = max(
                    metrics[f"max_trade_{field_name}_rel_error"],
                    rel_error,
                )
                if not _within_parity_tolerance(
                    harness_value,
                    reference_value,
                    abs_tolerance=tol.trade_abs_tolerance,
                    rel_tolerance=tol.trade_rel_tolerance,
                ):
                    checks["trade_values"] = False
                    _record_engine_parity_diff(
                        diffs,
                        metrics,
                        max_diffs,
                        EngineParityDiff(
                            section="trade",
                            code="trade_value_mismatch",
                            index=idx,
                            date=harness_trade.date,
                            field=field_name,
                            harness_value=harness_value,
                            reference_value=reference_value,
                            abs_error=abs_error,
                            rel_error=rel_error,
                            message="trade value outside tolerance",
                        ),
                    )
        metrics["compared_trades"] = compared_trades

    if reference_fills is not None:
        checks["fill_count"] = len(result.trades) == len(reference_fills)
        if not checks["fill_count"]:
            _record_engine_parity_diff(
                diffs,
                metrics,
                max_diffs,
                EngineParityDiff(
                    section="fill",
                    code="fill_count_mismatch",
                    harness_value=len(result.trades),
                    reference_value=len(reference_fills),
                    message="fill count differs",
                ),
            )
        compared_fills = min(len(result.trades), len(reference_fills))
        for idx in range(compared_fills):
            harness_fill = result.trades[idx]
            reference_fill = reference_fills[idx]
            if harness_fill.date != reference_fill.date or harness_fill.action.lower() != reference_fill.action.lower():
                checks["fill_actions"] = False
                _record_engine_parity_diff(
                    diffs,
                    metrics,
                    max_diffs,
                    EngineParityDiff(
                        section="fill",
                        code="fill_action_mismatch",
                        index=idx,
                        date=harness_fill.date,
                        field="date_action",
                        harness_value=f"{harness_fill.date}:{harness_fill.action.lower()}",
                        reference_value=f"{reference_fill.date}:{reference_fill.action.lower()}",
                        message="fill date or action differs",
                    ),
                )
            for field_name in ("price", "shares", "gross_value", "fee", "pnl", "target_exposure"):
                reference_value = getattr(reference_fill, field_name)
                if reference_value is None:
                    continue
                harness_value = getattr(harness_fill, field_name)
                abs_error = abs(harness_value - reference_value)
                rel_error = _relative_error(harness_value, reference_value)
                metrics[f"max_fill_{field_name}_abs_error"] = max(
                    metrics[f"max_fill_{field_name}_abs_error"],
                    abs_error,
                )
                metrics[f"max_fill_{field_name}_rel_error"] = max(
                    metrics[f"max_fill_{field_name}_rel_error"],
                    rel_error,
                )
                if not _within_parity_tolerance(
                    harness_value,
                    reference_value,
                    abs_tolerance=tol.trade_abs_tolerance,
                    rel_tolerance=tol.trade_rel_tolerance,
                ):
                    checks["fill_values"] = False
                    _record_engine_parity_diff(
                        diffs,
                        metrics,
                        max_diffs,
                        EngineParityDiff(
                            section="fill",
                            code="fill_value_mismatch",
                            index=idx,
                            date=harness_fill.date,
                            field=field_name,
                            harness_value=harness_value,
                            reference_value=reference_value,
                            abs_error=abs_error,
                            rel_error=rel_error,
                            message="fill value outside tolerance",
                        ),
                    )
        metrics["compared_fills"] = compared_fills

    if reference_order_intents is not None:
        checks["order_intent_count"] = len(result.order_intents) == len(reference_order_intents)
        if not checks["order_intent_count"]:
            _record_engine_parity_diff(
                diffs,
                metrics,
                max_diffs,
                EngineParityDiff(
                    section="order_intent",
                    code="order_intent_count_mismatch",
                    harness_value=len(result.order_intents),
                    reference_value=len(reference_order_intents),
                    message="order intent count differs",
                ),
            )
        compared_order_intents = min(len(result.order_intents), len(reference_order_intents))
        for idx in range(compared_order_intents):
            harness_intent = result.order_intents[idx]
            reference_intent = reference_order_intents[idx]
            if (
                harness_intent.date != reference_intent.date
                or harness_intent.action.lower() != reference_intent.action.lower()
            ):
                checks["order_intent_actions"] = False
                _record_engine_parity_diff(
                    diffs,
                    metrics,
                    max_diffs,
                    EngineParityDiff(
                        section="order_intent",
                        code="order_intent_action_mismatch",
                        index=idx,
                        date=harness_intent.date,
                        field="date_action",
                        harness_value=f"{harness_intent.date}:{harness_intent.action.lower()}",
                        reference_value=f"{reference_intent.date}:{reference_intent.action.lower()}",
                        message="order intent date or action differs",
                    ),
                )
            for field_name in ("target_exposure", "current_exposure", "desired_shares", "estimated_price"):
                reference_value = getattr(reference_intent, field_name)
                if reference_value is None:
                    continue
                harness_value = getattr(harness_intent, field_name)
                abs_error = abs(harness_value - reference_value)
                rel_error = _relative_error(harness_value, reference_value)
                metrics[f"max_order_intent_{field_name}_abs_error"] = max(
                    metrics[f"max_order_intent_{field_name}_abs_error"],
                    abs_error,
                )
                metrics[f"max_order_intent_{field_name}_rel_error"] = max(
                    metrics[f"max_order_intent_{field_name}_rel_error"],
                    rel_error,
                )
                if not _within_parity_tolerance(
                    harness_value,
                    reference_value,
                    abs_tolerance=tol.trade_abs_tolerance,
                    rel_tolerance=tol.trade_rel_tolerance,
                ):
                    checks["order_intent_values"] = False
                    _record_engine_parity_diff(
                        diffs,
                        metrics,
                        max_diffs,
                        EngineParityDiff(
                            section="order_intent",
                            code="order_intent_value_mismatch",
                            index=idx,
                            date=harness_intent.date,
                            field=field_name,
                            harness_value=harness_value,
                            reference_value=reference_value,
                            abs_error=abs_error,
                            rel_error=rel_error,
                            message="order intent value outside tolerance",
                        ),
                    )
        metrics["compared_order_intents"] = compared_order_intents

    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    if failed_checks:
        return EngineParityResult(
            engine_name=engine_name,
            tolerance=tol,
            metrics=metrics,
            checks=checks,
            verdict=HarnessVerdict(
                verdict="REJECT",
                reasons=["engine_parity_failed"] + [f"failed_check: {name}" for name in failed_checks],
            ),
            diffs=diffs,
        )
    return EngineParityResult(
        engine_name=engine_name,
        tolerance=tol,
        metrics=metrics,
        checks=checks,
        verdict=HarnessVerdict(verdict="KEEP", reasons=["engine_parity_passed"]),
        diffs=diffs,
    )


def run_backtest(
    bars: Sequence[Bar],
    strategy: Any,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    cfg = config or BacktestConfig()
    strategy_name = getattr(strategy, "name", strategy.__class__.__name__)
    validation_errors = _validate_backtest_inputs(bars, cfg)
    if validation_errors:
        return _empty_result(strategy_name, cfg, "REJECT", validation_errors)
    return _run_backtest_window(bars, strategy, cfg, start_index=0, end_index=len(bars), strategy_name=strategy_name)


def audit_no_lookahead(
    strategy_factory: Any,
    bars: Sequence[Bar],
    *,
    future_price_multiplier: float = 10.0,
) -> LookaheadAuditResult:
    reasons = _validate_backtest_inputs(bars, BacktestConfig())
    if reasons:
        return LookaheadAuditResult(
            passed=False,
            checked_decisions=0,
            changed_decisions=0,
            reasons=[f"data_invalid: {reason}" for reason in reasons],
        )
    if future_price_multiplier <= 0.0:
        return LookaheadAuditResult(
            passed=False,
            checked_decisions=0,
            changed_decisions=0,
            reasons=["future_price_multiplier must be positive"],
        )

    checked = 0
    changed = 0
    for idx in range(len(bars)):
        baseline_strategy = _make_strategy(strategy_factory, bars)
        baseline_signal = _target_exposure(baseline_strategy, bars[:idx])
        attacked_bars = _future_mutated_bars(bars, start_index=idx, multiplier=future_price_multiplier)
        attacked_strategy = _make_strategy(strategy_factory, attacked_bars)
        attacked_signal = _target_exposure(attacked_strategy, attacked_bars[:idx])
        checked += 1
        if abs(baseline_signal - attacked_signal) > 1e-12:
            changed += 1

    if changed:
        return LookaheadAuditResult(
            passed=False,
            checked_decisions=checked,
            changed_decisions=changed,
            reasons=[f"future_mutation_changed_{changed}_of_{checked}_signals"],
        )
    return LookaheadAuditResult(
        passed=True,
        checked_decisions=checked,
        changed_decisions=0,
        reasons=["signals_invariant_to_future_mutation"],
    )


def run_walk_forward(
    bars: Sequence[Bar],
    strategy_factory: Any,
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    config: BacktestConfig | None = None,
) -> WalkForwardResult:
    cfg = config or BacktestConfig()
    step = step_size or test_size
    strategy_name = getattr(_make_strategy(strategy_factory, bars), "name", "strategy")
    validation_errors = _validate_backtest_inputs(bars, cfg)
    validation_errors.extend(_validate_walk_forward_config(train_size, test_size, step))
    if validation_errors:
        return WalkForwardResult(
            strategy_name=strategy_name,
            train_size=train_size,
            test_size=test_size,
            step_size=step,
            folds=[],
            metrics=_empty_walk_forward_metrics(),
            verdict=HarnessVerdict(verdict="REJECT", reasons=validation_errors),
        )

    folds: List[WalkForwardFold] = []
    fold_index = 0
    train_start_idx = 0
    while train_start_idx + train_size + test_size <= len(bars):
        train_end_idx = train_start_idx + train_size
        test_start_idx = train_end_idx
        test_end_idx = test_start_idx + test_size
        strategy = _make_strategy(strategy_factory, bars)
        result = _run_backtest_window(
            bars,
            strategy,
            cfg,
            start_index=test_start_idx,
            end_index=test_end_idx,
            strategy_name=getattr(strategy, "name", strategy_name),
        )
        folds.append(
            WalkForwardFold(
                fold_index=fold_index,
                train_start=bars[train_start_idx].date,
                train_end=bars[train_end_idx - 1].date,
                test_start=bars[test_start_idx].date,
                test_end=bars[test_end_idx - 1].date,
                result=result,
            )
        )
        fold_index += 1
        train_start_idx += step

    if not folds:
        return WalkForwardResult(
            strategy_name=strategy_name,
            train_size=train_size,
            test_size=test_size,
            step_size=step,
            folds=[],
            metrics=_empty_walk_forward_metrics(),
            verdict=HarnessVerdict(verdict="ITERATE", reasons=["insufficient_bars_for_walk_forward_folds"]),
        )

    metrics = _walk_forward_metrics(folds, cfg)
    verdict = _judge_walk_forward(metrics, cfg)
    return WalkForwardResult(
        strategy_name=strategy_name,
        train_size=train_size,
        test_size=test_size,
        step_size=step,
        folds=folds,
        metrics=metrics,
        verdict=verdict,
    )


def default_regime_stress_cases() -> List[RegimeStressCase]:
    return [
        RegimeStressCase(
            name="steady_up_reject",
            bars=_bars_from_prices([100, 101, 102, 103, 104, 105, 106]),
            expected_verdict="REJECT",
            description="Pure rising market should not be promoted without downside advantage.",
        ),
        RegimeStressCase(
            name="crash_keep",
            bars=_bars_from_prices([100, 105, 110, 115, 120, 119, 118, 117, 90, 80, 75]),
            expected_verdict="KEEP",
            description="Moving-average cash filter should avoid a synthetic crash.",
        ),
        RegimeStressCase(
            name="whipsaw_keep",
            bars=_bars_from_prices([100, 103, 99, 104, 98, 105, 97, 106]),
            expected_verdict="KEEP",
            description="Whipsaw case records turnover stress while still requiring downside protection.",
        ),
        RegimeStressCase(
            name="flat_then_spike_reject",
            bars=_bars_from_prices([100, 100, 100, 200, 200]),
            expected_verdict="REJECT",
            description="Lagged strategy must not chase a one-day future spike into promotion.",
        ),
    ]


def run_regime_stress(
    strategy_factory: Any,
    cases: Sequence[RegimeStressCase] | None = None,
    *,
    config: BacktestConfig | None = None,
) -> RegimeStressResult:
    cfg = config or BacktestConfig()
    selected_cases = list(cases) if cases is not None else default_regime_stress_cases()
    strategy_name = getattr(_make_strategy(strategy_factory, []), "name", "strategy")
    case_results: List[RegimeStressCaseResult] = []
    for case in selected_cases:
        strategy = _make_strategy(strategy_factory, case.bars)
        result = run_backtest(case.bars, strategy, cfg)
        passed = result.verdict.verdict == case.expected_verdict
        reasons = [f"expected_{case.expected_verdict}_got_{result.verdict.verdict}"] if not passed else ["expected_verdict_matched"]
        case_results.append(
            RegimeStressCaseResult(
                name=case.name,
                expected_verdict=case.expected_verdict,
                actual_verdict=result.verdict.verdict,
                passed=passed,
                reasons=reasons,
                result=result,
            )
        )

    passed_count = sum(1 for case in case_results if case.passed)
    metrics = {
        "case_count": len(case_results),
        "passed_count": passed_count,
        "failed_count": len(case_results) - passed_count,
        "pass_rate": 0.0 if not case_results else passed_count / len(case_results),
        "worst_max_drawdown": max((case.result.metrics["max_drawdown"] for case in case_results), default=0.0),
        "max_turnover": max((case.result.metrics["turnover"] for case in case_results), default=0.0),
    }
    if metrics["failed_count"] > 0:
        verdict = HarnessVerdict(
            verdict="REJECT",
            reasons=[
                f"regime_stress_failed_cases: {metrics['failed_count']}",
                f"pass_rate={metrics['pass_rate']:.4f}",
            ],
        )
    else:
        verdict = HarnessVerdict(verdict="KEEP", reasons=["all_regime_stress_cases_matched_expected_verdicts"])
    return RegimeStressResult(
        strategy_name=strategy_name,
        cases=case_results,
        metrics=metrics,
        verdict=verdict,
    )


def run_ma_parameter_sweep(
    bars: Sequence[Bar],
    windows: Sequence[int],
    *,
    config: BacktestConfig | None = None,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    min_pass_rate: float = 0.60,
    max_best_score_gap: float = 0.75,
) -> ParameterSweepResult:
    cfg = config or BacktestConfig()
    unique_windows = sorted({int(window) for window in windows})
    validation_errors = _validate_parameter_sweep_inputs(unique_windows, min_pass_rate, max_best_score_gap)
    validation_errors.extend(_validate_backtest_inputs(bars, cfg))
    validation_errors.extend(_validate_walk_forward_config(train_size, test_size, step_size or test_size))
    if validation_errors:
        return ParameterSweepResult(
            strategy_family="ma_cash",
            windows=unique_windows,
            cases=[],
            best_window=None,
            metrics=_empty_parameter_sweep_metrics(),
            verdict=HarnessVerdict(verdict="REJECT", reasons=validation_errors),
        )

    cases: List[ParameterSweepCase] = []
    for window in unique_windows:
        strategy_factory = lambda window=window: MovingAverageCashStrategy(window=window)
        strategy = strategy_factory()
        backtest = run_backtest(bars, strategy, cfg)
        walk_forward = run_walk_forward(
            bars,
            strategy_factory,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            config=cfg,
        )
        regime_stress = run_regime_stress(strategy_factory, config=cfg)
        passed = (
            backtest.verdict.verdict == "KEEP"
            and walk_forward.verdict.verdict == "KEEP"
            and regime_stress.verdict.verdict == "KEEP"
        )
        reasons = _parameter_case_reasons(backtest, walk_forward, regime_stress)
        score = _parameter_case_score(backtest, walk_forward, regime_stress)
        cases.append(
            ParameterSweepCase(
                window=window,
                backtest=backtest,
                walk_forward=walk_forward,
                regime_stress=regime_stress,
                passed=passed,
                score=score,
                reasons=reasons,
            )
        )

    metrics = _parameter_sweep_metrics(cases)
    verdict = _judge_parameter_sweep(metrics, min_pass_rate=min_pass_rate, max_best_score_gap=max_best_score_gap)
    best_case = max(cases, key=lambda case: case.score) if cases else None
    return ParameterSweepResult(
        strategy_family="ma_cash",
        windows=unique_windows,
        cases=cases,
        best_window=None if best_case is None else best_case.window,
        metrics=metrics,
        verdict=verdict,
    )


def default_cost_stress_cases() -> List[CostStressCase]:
    return [
        CostStressCase(name="zero_cost", fee_bps=0.0, slippage_bps=0.0),
        CostStressCase(name="default_cost", fee_bps=1.0, slippage_bps=2.0),
        CostStressCase(name="elevated_cost", fee_bps=5.0, slippage_bps=10.0),
        CostStressCase(name="severe_cost", fee_bps=10.0, slippage_bps=25.0),
    ]


def run_cost_stress(
    bars: Sequence[Bar],
    strategy_factory: Any,
    cost_cases: Sequence[CostStressCase] | None = None,
    *,
    config: BacktestConfig | None = None,
    max_return_decay: float = 0.50,
) -> CostStressResult:
    cfg = config or BacktestConfig()
    selected_cases = list(cost_cases) if cost_cases is not None else default_cost_stress_cases()
    strategy_name = getattr(_make_strategy(strategy_factory, bars), "name", "strategy")
    validation_errors = _validate_backtest_inputs(bars, cfg)
    validation_errors.extend(_validate_cost_stress_inputs(selected_cases, max_return_decay))
    if validation_errors:
        return CostStressResult(
            strategy_name=strategy_name,
            cases=[],
            metrics=_empty_cost_stress_metrics(),
            verdict=HarnessVerdict(verdict="REJECT", reasons=validation_errors),
        )

    case_results: List[CostStressCaseResult] = []
    for idx, case in enumerate(selected_cases):
        case_config = BacktestConfig(
            initial_capital=cfg.initial_capital,
            fee_bps=case.fee_bps,
            slippage_bps=case.slippage_bps,
            trading_days=cfg.trading_days,
            max_allowed_drawdown=cfg.max_allowed_drawdown,
        )
        strategy = _make_strategy(strategy_factory, bars)
        result = run_backtest(bars, strategy, case_config)
        passed = result.verdict.verdict == "KEEP"
        case_results.append(
            CostStressCaseResult(
                name=case.name or f"cost_case_{idx}",
                fee_bps=case.fee_bps,
                slippage_bps=case.slippage_bps,
                result=result,
                passed=passed,
                reasons=["cost_case_keep"] if passed else [f"cost_case_{result.verdict.verdict.lower()}"],
            )
        )

    metrics = _cost_stress_metrics(case_results)
    verdict = _judge_cost_stress(metrics, case_results, max_return_decay=max_return_decay)
    return CostStressResult(
        strategy_name=strategy_name,
        cases=case_results,
        metrics=metrics,
        verdict=verdict,
    )


def default_stress_matrix_cases() -> List[StressMatrixCase]:
    return [
        StressMatrixCase(name="baseline_default", fee_bps=1.0, slippage_bps=2.0),
        StressMatrixCase(name="delayed_execution", fee_bps=1.0, slippage_bps=2.0, execution_delay_bars=1),
        StressMatrixCase(name="gap_risk", fee_bps=1.0, slippage_bps=2.0, adverse_open_gap_bps=10.0),
        StressMatrixCase(
            name="crisis_liquidity",
            fee_bps=5.0,
            slippage_bps=15.0,
            adverse_open_gap_bps=10.0,
            max_participation_rate=0.10,
            market_impact_bps_per_100pct_participation=25.0,
        ),
        StressMatrixCase(name="cash_yield", fee_bps=1.0, slippage_bps=2.0, cash_yield_annual=0.02),
    ]


def run_stress_matrix(
    bars: Sequence[Bar],
    strategy_factory: Any,
    stress_cases: Sequence[StressMatrixCase] | None = None,
    *,
    config: BacktestConfig | None = None,
    max_return_decay: float = 0.90,
) -> StressMatrixResult:
    cfg = config or BacktestConfig()
    selected_cases = list(stress_cases) if stress_cases is not None else default_stress_matrix_cases()
    strategy_name = getattr(_make_strategy(strategy_factory, bars), "name", "strategy")
    validation_errors = _validate_backtest_inputs(bars, cfg)
    validation_errors.extend(_validate_stress_matrix_inputs(selected_cases, max_return_decay))
    if validation_errors:
        return StressMatrixResult(
            strategy_name=strategy_name,
            cases=[],
            metrics=_empty_stress_matrix_metrics(),
            verdict=HarnessVerdict(verdict="REJECT", reasons=validation_errors),
        )

    case_results: List[StressMatrixCaseResult] = []
    for idx, case in enumerate(selected_cases):
        case_config = BacktestConfig(
            initial_capital=cfg.initial_capital,
            fee_bps=case.fee_bps,
            slippage_bps=case.slippage_bps,
            trading_days=cfg.trading_days,
            max_allowed_drawdown=cfg.max_allowed_drawdown,
        )
        strategy = _make_strategy(strategy_factory, bars)
        result = _run_backtest_window(
            bars,
            strategy,
            case_config,
            start_index=0,
            end_index=len(bars),
            strategy_name=getattr(strategy, "name", strategy_name),
            execution_delay_bars=case.execution_delay_bars,
            adverse_open_gap_bps=case.adverse_open_gap_bps,
            cash_yield_annual=case.cash_yield_annual,
            max_participation_rate=case.max_participation_rate,
            market_impact_bps_per_100pct_participation=case.market_impact_bps_per_100pct_participation,
        )
        passed = result.verdict.verdict == "KEEP"
        case_results.append(
            StressMatrixCaseResult(
                name=case.name or f"stress_case_{idx}",
                case=case,
                result=result,
                passed=passed,
                reasons=["stress_case_keep"] if passed else [f"stress_case_{result.verdict.verdict.lower()}"],
            )
        )

    metrics = _stress_matrix_metrics(case_results)
    verdict = _judge_stress_matrix(metrics, case_results, max_return_decay=max_return_decay)
    return StressMatrixResult(
        strategy_name=strategy_name,
        cases=case_results,
        metrics=metrics,
        verdict=verdict,
    )


def run_multi_asset_benchmark(
    cases: Sequence[MultiAssetBenchmarkCase],
    strategy_factory: Any,
    *,
    config: BacktestConfig | None = None,
    data_quality_config: DataQualityConfig | None = None,
    min_pass_rate: float = 1.0,
    require_all_data_quality: bool = True,
) -> MultiAssetBenchmarkResult:
    cfg = config or BacktestConfig()
    strategy_name = getattr(_make_strategy(strategy_factory, []), "name", "strategy")
    selected_cases = list(cases)
    validation_errors = _validate_multi_asset_inputs(selected_cases, min_pass_rate)
    if validation_errors:
        return MultiAssetBenchmarkResult(
            strategy_name=strategy_name,
            cases=[],
            metrics=_empty_multi_asset_metrics(),
            verdict=HarnessVerdict(verdict="REJECT", reasons=validation_errors),
        )
    if not selected_cases:
        return MultiAssetBenchmarkResult(
            strategy_name=strategy_name,
            cases=[],
            metrics=_empty_multi_asset_metrics(),
            verdict=HarnessVerdict(verdict="ITERATE", reasons=["no_multi_asset_cases_tested"]),
        )

    case_results: List[MultiAssetBenchmarkCaseResult] = []
    for case in selected_cases:
        data_quality = run_data_quality_gate(case.bars, data_quality_config)
        if data_quality.verdict.verdict != "KEEP":
            backtest = _empty_result(
                strategy_name,
                cfg,
                "REJECT",
                [f"data_quality_{data_quality.verdict.verdict.lower()}"] + data_quality.verdict.reasons,
            )
        else:
            strategy = _make_strategy(strategy_factory, case.bars)
            backtest = run_backtest(case.bars, strategy, cfg)
        passed = data_quality.verdict.verdict == "KEEP" and backtest.verdict.verdict == "KEEP"
        case_results.append(
            MultiAssetBenchmarkCaseResult(
                name=case.name,
                description=case.description,
                tags=dict(case.tags),
                passed=passed,
                reasons=_multi_asset_case_reasons(data_quality, backtest),
                data_quality=data_quality,
                backtest=backtest,
                bars=tuple(case.bars),
            )
        )

    metrics = _multi_asset_metrics(case_results)
    verdict = _judge_multi_asset_benchmark(
        metrics,
        min_pass_rate=min_pass_rate,
        require_all_data_quality=require_all_data_quality,
    )
    return MultiAssetBenchmarkResult(
        strategy_name=strategy_name,
        cases=case_results,
        metrics=metrics,
        verdict=verdict,
    )


def _run_backtest_window(
    bars: Sequence[Bar],
    strategy: Any,
    cfg: BacktestConfig,
    *,
    start_index: int,
    end_index: int,
    strategy_name: str,
    execution_delay_bars: int = 0,
    adverse_open_gap_bps: float = 0.0,
    cash_yield_annual: float = 0.0,
    max_participation_rate: float | None = None,
    market_impact_bps_per_100pct_participation: float = 0.0,
) -> BacktestResult:
    cash = cfg.initial_capital
    shares = 0.0
    entry_cost = 0.0
    trades: List[Trade] = []
    order_intents: List[OrderIntent] = []
    equity_curve: List[EquityPoint] = []
    gross_turnover = 0.0
    winning_exits = 0
    completed_exits = 0
    participation_cap_hit_count = 0
    liquidity_unfilled_shares = 0.0
    max_volume_participation = 0.0
    market_impact_cost = 0.0
    max_market_impact_bps = 0.0

    benchmark_start = bars[start_index].close
    equity_peak = cfg.initial_capital
    benchmark_peak = cfg.initial_capital
    fee_rate = cfg.fee_bps / 10000.0
    slippage_rate = cfg.slippage_bps / 10000.0
    adverse_gap_rate = adverse_open_gap_bps / 10000.0
    cash_yield_period = cash_yield_annual / cfg.trading_days

    for idx in range(start_index, end_index):
        bar = bars[idx]
        if cash != 0.0 and cash_yield_period != 0.0:
            cash *= 1.0 + cash_yield_period
        signal_end_idx = max(0, idx - execution_delay_bars)
        target_exposure = _target_exposure(strategy, bars[:signal_end_idx])
        max_fill_shares = math.inf if max_participation_rate is None else max(0.0, bar.volume * max_participation_rate)
        if target_exposure > 0.5 and cash > 1e-12:
            base_fill_price = bar.open * (1.0 + slippage_rate + adverse_gap_rate)
            desired_shares = cash / (base_fill_price * (1.0 + fee_rate))
            order_intents.append(
                OrderIntent(
                    date=bar.date,
                    action="buy",
                    target_exposure=target_exposure,
                    current_exposure=_portfolio_exposure(cash, shares, bar.close),
                    desired_shares=desired_shares,
                    estimated_price=base_fill_price,
                )
            )
            shares_to_buy = min(desired_shares, max_fill_shares)
            if max_participation_rate is not None and desired_shares > max_fill_shares + 1e-12:
                participation_cap_hit_count += 1
                liquidity_unfilled_shares += desired_shares - max_fill_shares
            if shares_to_buy <= 1e-12:
                equity = cash + shares * bar.close
                equity_peak = max(equity_peak, equity)
                drawdown = 0.0 if equity_peak <= 0.0 else 1.0 - equity / equity_peak
                benchmark_equity = cfg.initial_capital * (bar.close / benchmark_start)
                benchmark_peak = max(benchmark_peak, benchmark_equity)
                benchmark_drawdown = 0.0 if benchmark_peak <= 0.0 else 1.0 - benchmark_equity / benchmark_peak
                exposure = 0.0 if equity <= 0.0 else max(0.0, min(1.0, shares * bar.close / equity))
                equity_curve.append(
                    EquityPoint(
                        date=bar.date,
                        equity=equity,
                        cash=cash,
                        shares=shares,
                        close=bar.close,
                        exposure=exposure,
                        benchmark_equity=benchmark_equity,
                        drawdown=drawdown,
                        benchmark_drawdown=benchmark_drawdown,
                    )
                )
                continue
            impact_rate = _market_impact_rate(
                shares_to_buy,
                bar.volume,
                market_impact_bps_per_100pct_participation,
            )
            fill_price = bar.open * (1.0 + slippage_rate + adverse_gap_rate + impact_rate)
            shares_to_buy = min(shares_to_buy, cash / (fill_price * (1.0 + fee_rate)))
            impact_rate = _market_impact_rate(
                shares_to_buy,
                bar.volume,
                market_impact_bps_per_100pct_participation,
            )
            fill_price = bar.open * (1.0 + slippage_rate + adverse_gap_rate + impact_rate)
            base_fill_price = bar.open * (1.0 + slippage_rate + adverse_gap_rate)
            gross_value = shares_to_buy * fill_price
            fee = gross_value * fee_rate
            cash -= gross_value + fee
            shares += shares_to_buy
            entry_cost += gross_value + fee
            gross_turnover += gross_value
            impact_cost = max(0.0, fill_price - base_fill_price) * shares_to_buy
            market_impact_cost += impact_cost
            max_market_impact_bps = max(max_market_impact_bps, impact_rate * 10000.0)
            if bar.volume > 0.0:
                max_volume_participation = max(max_volume_participation, shares_to_buy / bar.volume)
            trades.append(
                Trade(
                    date=bar.date,
                    action="buy",
                    price=fill_price,
                    shares=shares_to_buy,
                    gross_value=gross_value,
                    fee=fee,
                    pnl=0.0,
                    target_exposure=1.0,
                )
            )
        elif target_exposure <= 0.5 and shares > 0.0:
            base_fill_price = bar.open * (1.0 - slippage_rate - adverse_gap_rate)
            desired_shares = shares
            order_intents.append(
                OrderIntent(
                    date=bar.date,
                    action="sell",
                    target_exposure=target_exposure,
                    current_exposure=_portfolio_exposure(cash, shares, bar.close),
                    desired_shares=desired_shares,
                    estimated_price=base_fill_price,
                )
            )
            shares_to_sell = min(desired_shares, max_fill_shares)
            if max_participation_rate is not None and desired_shares > max_fill_shares + 1e-12:
                participation_cap_hit_count += 1
                liquidity_unfilled_shares += desired_shares - max_fill_shares
            if shares_to_sell <= 1e-12:
                equity = cash + shares * bar.close
                equity_peak = max(equity_peak, equity)
                drawdown = 0.0 if equity_peak <= 0.0 else 1.0 - equity / equity_peak
                benchmark_equity = cfg.initial_capital * (bar.close / benchmark_start)
                benchmark_peak = max(benchmark_peak, benchmark_equity)
                benchmark_drawdown = 0.0 if benchmark_peak <= 0.0 else 1.0 - benchmark_equity / benchmark_peak
                exposure = 0.0 if equity <= 0.0 else max(0.0, min(1.0, shares * bar.close / equity))
                equity_curve.append(
                    EquityPoint(
                        date=bar.date,
                        equity=equity,
                        cash=cash,
                        shares=shares,
                        close=bar.close,
                        exposure=exposure,
                        benchmark_equity=benchmark_equity,
                        drawdown=drawdown,
                        benchmark_drawdown=benchmark_drawdown,
                    )
                )
                continue
            impact_rate = _market_impact_rate(
                shares_to_sell,
                bar.volume,
                market_impact_bps_per_100pct_participation,
            )
            fill_price = bar.open * (1.0 - slippage_rate - adverse_gap_rate - impact_rate)
            base_fill_price = bar.open * (1.0 - slippage_rate - adverse_gap_rate)
            shares_before_sell = shares
            gross_value = shares_to_sell * fill_price
            fee = gross_value * fee_rate
            proceeds = gross_value - fee
            cost_basis_sold = entry_cost * (shares_to_sell / shares_before_sell) if shares_before_sell > 0.0 else 0.0
            pnl = proceeds - cost_basis_sold
            cash += proceeds
            shares -= shares_to_sell
            entry_cost -= cost_basis_sold
            gross_turnover += gross_value
            completed_exits += 1
            if pnl > 0.0:
                winning_exits += 1
            impact_cost = max(0.0, base_fill_price - fill_price) * shares_to_sell
            market_impact_cost += impact_cost
            max_market_impact_bps = max(max_market_impact_bps, impact_rate * 10000.0)
            if bar.volume > 0.0:
                max_volume_participation = max(max_volume_participation, shares_to_sell / bar.volume)
            trades.append(
                Trade(
                    date=bar.date,
                    action="sell",
                    price=fill_price,
                    shares=shares_to_sell,
                    gross_value=gross_value,
                    fee=fee,
                    pnl=pnl,
                    target_exposure=0.0,
                )
            )
            if shares <= 1e-12:
                shares = 0.0
                entry_cost = 0.0

        equity = cash + shares * bar.close
        equity_peak = max(equity_peak, equity)
        drawdown = 0.0 if equity_peak <= 0.0 else 1.0 - equity / equity_peak
        benchmark_equity = cfg.initial_capital * (bar.close / benchmark_start)
        benchmark_peak = max(benchmark_peak, benchmark_equity)
        benchmark_drawdown = 0.0 if benchmark_peak <= 0.0 else 1.0 - benchmark_equity / benchmark_peak
        exposure = 0.0 if equity <= 0.0 else max(0.0, min(1.0, shares * bar.close / equity))
        equity_curve.append(
            EquityPoint(
                date=bar.date,
                equity=equity,
                cash=cash,
                shares=shares,
                close=bar.close,
                exposure=exposure,
                benchmark_equity=benchmark_equity,
                drawdown=drawdown,
                benchmark_drawdown=benchmark_drawdown,
            )
        )

    metrics = _metrics_from_curve(
        [point.equity for point in equity_curve],
        cfg,
        max_drawdown=max(point.drawdown for point in equity_curve),
        time_under_water=sum(1 for point in equity_curve if point.drawdown > 0.0),
    )
    metrics.update(
        {
            "exposure_ratio": sum(point.exposure for point in equity_curve) / len(equity_curve),
            "turnover": gross_turnover / cfg.initial_capital,
            "trade_count": len(trades),
            "order_intent_count": len(order_intents),
            "win_rate": 0.0 if completed_exits == 0 else winning_exits / completed_exits,
            "liquidity_participation_cap": max_participation_rate,
            "liquidity_cap_hit_count": participation_cap_hit_count,
            "liquidity_unfilled_shares": liquidity_unfilled_shares,
            "max_volume_participation": max_volume_participation,
            "market_impact_bps_per_100pct_participation": market_impact_bps_per_100pct_participation,
            "market_impact_cost": market_impact_cost,
            "market_impact_cost_ratio": market_impact_cost / cfg.initial_capital,
            "max_market_impact_bps": max_market_impact_bps,
        }
    )
    benchmark_metrics = _metrics_from_curve(
        [point.benchmark_equity for point in equity_curve],
        cfg,
        max_drawdown=max(point.benchmark_drawdown for point in equity_curve),
        time_under_water=sum(1 for point in equity_curve if point.benchmark_drawdown > 0.0),
    )
    benchmark_metrics.update(
        {
            "exposure_ratio": 1.0,
            "turnover": 1.0,
            "trade_count": 1,
            "win_rate": 0.0,
        }
    )

    verdict = _judge_result(bars[:end_index], strategy, cfg, metrics, benchmark_metrics)
    return BacktestResult(
        strategy_name=strategy_name,
        config=cfg,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        trades=trades,
        equity_curve=equity_curve,
        verdict=verdict,
        order_intents=order_intents,
    )


def write_stock_report(result: BacktestResult, output_dir: str | Path) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    metrics_path = out / "metrics.json"
    equity_path = out / "equity_curve.csv"
    trades_path = out / "trades.csv"
    order_intents_path = out / "order_intents.csv"

    metrics_payload = {
        "strategy_name": result.strategy_name,
        "research_only": True,
        "config": asdict(result.config),
        "metrics": result.metrics,
        "benchmark_metrics": result.benchmark_metrics,
        "verdict": asdict(result.verdict),
    }
    metrics_path.write_text(json.dumps(metrics_payload, indent=2, sort_keys=True), encoding="utf-8")

    _write_dataclass_csv(equity_path, result.equity_curve, EquityPoint)
    _write_dataclass_csv(trades_path, result.trades, Trade)
    _write_dataclass_csv(order_intents_path, result.order_intents, OrderIntent)
    return {
        "metrics": str(metrics_path),
        "equity_curve": str(equity_path),
        "trades": str(trades_path),
        "order_intents": str(order_intents_path),
    }


def write_engine_parity_report(result: EngineParityResult, output_dir: str | Path) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary_path = out / "engine_parity.json"
    diffs_path = out / "engine_parity_diffs.csv"

    summary_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    _write_dataclass_csv(diffs_path, result.diffs, EngineParityDiff)
    return {
        "summary": str(summary_path),
        "diffs": str(diffs_path),
    }


def write_multi_asset_benchmark_report(result: MultiAssetBenchmarkResult, output_dir: str | Path) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary_path = out / "multi_asset_benchmark.json"
    cases_path = out / "multi_asset_cases.csv"
    groups_path = out / "multi_asset_groups.csv"

    summary_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    _write_dict_csv(
        cases_path,
        _multi_asset_case_report_rows(result),
        [
            "name",
            "description",
            "tags",
            "passed",
            "reasons",
            "data_quality_verdict",
            "data_quality_error_count",
            "data_quality_warning_count",
            "backtest_verdict",
            "total_return",
            "benchmark_total_return",
            "max_drawdown",
            "benchmark_max_drawdown",
            "turnover",
            "trade_count",
        ],
    )
    _write_dict_csv(
        groups_path,
        _multi_asset_group_report_rows(result),
        [
            "group",
            "case_count",
            "passed_count",
            "failed_count",
            "pass_rate",
            "worst_max_drawdown",
            "failed_cases",
        ],
    )
    return {
        "summary": str(summary_path),
        "cases": str(cases_path),
        "groups": str(groups_path),
        **write_multi_asset_case_artifacts(result, out),
    }


def write_multi_asset_case_artifacts(result: MultiAssetBenchmarkResult, output_dir: str | Path) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    artifacts_root = out / "case_artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "multi_asset_case_artifacts.csv"
    manifest_rows: List[Dict[str, Any]] = []
    used_slugs: set[str] = set()

    for case in sorted(result.cases, key=lambda item: item.name):
        slug = _unique_artifact_slug(case.name, used_slugs)
        case_dir = artifacts_root / slug
        case_dir.mkdir(parents=True, exist_ok=True)

        case_summary_path = case_dir / "case.json"
        bars_path = case_dir / "bars.csv"
        data_quality_path = case_dir / "data_quality.json"
        data_quality_issues_path = case_dir / "data_quality_issues.csv"
        backtest_dir = case_dir / "backtest"

        case_summary_path.write_text(
            json.dumps(_multi_asset_case_artifact_summary(case), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _write_dataclass_csv(bars_path, case.bars, Bar)
        data_quality_path.write_text(
            json.dumps(case.data_quality.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _write_dataclass_csv(data_quality_issues_path, case.data_quality.issues, DataQualityIssue)
        stock_paths = write_stock_report(case.backtest, backtest_dir)

        manifest_rows.append(
            {
                "name": case.name,
                "artifact_dir": str(case_dir),
                "passed": case.passed,
                "reasons": json.dumps(case.reasons, sort_keys=True),
                "case_summary": str(case_summary_path),
                "bars": str(bars_path),
                "data_quality": str(data_quality_path),
                "data_quality_issues": str(data_quality_issues_path),
                "backtest_metrics": stock_paths["metrics"],
                "backtest_equity_curve": stock_paths["equity_curve"],
                "backtest_trades": stock_paths["trades"],
                "backtest_order_intents": stock_paths["order_intents"],
            }
        )

    _write_dict_csv(
        manifest_path,
        manifest_rows,
        [
            "name",
            "artifact_dir",
            "passed",
            "reasons",
            "case_summary",
            "bars",
            "data_quality",
            "data_quality_issues",
            "backtest_metrics",
            "backtest_equity_curve",
            "backtest_trades",
            "backtest_order_intents",
        ],
    )
    return {
        "case_artifacts": str(artifacts_root),
        "case_manifest": str(manifest_path),
    }


def create_experiment_manifest(
    *,
    strategy_name: str,
    bars: Sequence[Bar],
    config: BacktestConfig,
    data_quality: DataQualityResult | None = None,
    engine_parity: EngineParityResult | None = None,
    backtest: BacktestResult | None = None,
    lookahead_audit: LookaheadAuditResult | None = None,
    walk_forward: WalkForwardResult | None = None,
    regime_stress: RegimeStressResult | None = None,
    parameter_sweep: ParameterSweepResult | None = None,
    cost_stress: CostStressResult | None = None,
    stress_matrix: StressMatrixResult | None = None,
    multi_asset_benchmark: MultiAssetBenchmarkResult | None = None,
) -> Dict[str, Any]:
    return {
        "schema": "angelos_stock_experiment_manifest_v1",
        "research_only": True,
        "strategy_name": strategy_name,
        "config": asdict(config),
        "data": _data_summary(bars),
        "artifacts": {
            "data_quality": None if data_quality is None else data_quality.to_dict(),
            "engine_parity": None if engine_parity is None else engine_parity.to_dict(),
            "backtest": None if backtest is None else _result_summary(backtest),
            "lookahead_audit": None if lookahead_audit is None else asdict(lookahead_audit),
            "walk_forward": None
            if walk_forward is None
            else {
                "verdict": asdict(walk_forward.verdict),
                "metrics": walk_forward.metrics,
                "fold_count": len(walk_forward.folds),
            },
            "regime_stress": None
            if regime_stress is None
            else {
                "verdict": asdict(regime_stress.verdict),
                "metrics": regime_stress.metrics,
                "case_names": [case.name for case in regime_stress.cases],
            },
            "parameter_sweep": None
            if parameter_sweep is None
            else {
                "verdict": asdict(parameter_sweep.verdict),
                "metrics": parameter_sweep.metrics,
                "best_window": parameter_sweep.best_window,
                "windows": parameter_sweep.windows,
            },
            "cost_stress": None
            if cost_stress is None
            else {
                "verdict": asdict(cost_stress.verdict),
                "metrics": cost_stress.metrics,
                "case_names": [case.name for case in cost_stress.cases],
            },
            "stress_matrix": None
            if stress_matrix is None
            else {
                "verdict": asdict(stress_matrix.verdict),
                "metrics": stress_matrix.metrics,
                "case_names": [case.name for case in stress_matrix.cases],
            },
            "multi_asset_benchmark": None
            if multi_asset_benchmark is None
            else {
                "verdict": asdict(multi_asset_benchmark.verdict),
                "metrics": multi_asset_benchmark.metrics,
                "case_names": [case.name for case in multi_asset_benchmark.cases],
            },
        },
    }


def write_experiment_manifest(manifest: Dict[str, Any], output_dir: str | Path) -> str:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "experiment_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _bar_from_row(row: Dict[str, str], *, row_number: int) -> Bar:
    date = str(row.get("date", "")).strip()
    if not date:
        raise ValueError(f"row {row_number}: date is required")
    try:
        bar = Bar(
            date=date,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            adjusted_close=_optional_adjusted_close(row, row_number),
            adjusted_open=_optional_adjusted_value(row, row_number, {"adjusted_open", "adj_open"}),
            adjusted_high=_optional_adjusted_value(row, row_number, {"adjusted_high", "adj_high"}),
            adjusted_low=_optional_adjusted_value(row, row_number, {"adjusted_low", "adj_low"}),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: invalid numeric OHLCV value") from exc
    _validate_bar(bar, label=f"row {row_number}")
    return bar


def _require_csv_fields(fieldnames: Sequence[str] | None, required: set[str]) -> None:
    if fieldnames is None:
        raise ValueError("CSV must include a header row")
    missing = sorted(required.difference(fieldnames))
    if missing:
        raise ValueError(f"CSV missing required fields: {', '.join(missing)}")


def _optional_adjusted_close(row: Dict[str, str], row_number: int) -> float | None:
    return _optional_adjusted_value(row, row_number, {"adjusted_close", "adj_close"})


def _optional_adjusted_value(row: Dict[str, str], row_number: int, aliases: set[str]) -> float | None:
    for field_name in row:
        normalized = field_name.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in aliases:
            return _optional_csv_float(row, field_name, row_number)
    return None


def _required_csv_float(row: Dict[str, str], field_name: str, row_number: int) -> float:
    raw = str(row.get(field_name, "")).strip()
    if raw == "":
        raise ValueError(f"row {row_number}: {field_name} is required")
    return _csv_float(raw, field_name, row_number)


def _optional_csv_float(row: Dict[str, str], field_name: str, row_number: int) -> float | None:
    if field_name not in row:
        return None
    raw = str(row.get(field_name, "")).strip()
    if raw == "":
        return None
    return _csv_float(raw, field_name, row_number)


def _csv_float(raw: str, field_name: str, row_number: int) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field_name} must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"row {row_number}: {field_name} must be finite")
    return value


def _calendar_status_from_row(row: Dict[str, str], row_number: int) -> str:
    raw_status = str(row.get("status", "")).strip().lower().replace("-", "_").replace(" ", "_")
    if raw_status:
        if raw_status in {"open", "regular", "session", "trading", "full_day"}:
            return "open"
        if raw_status in {"half_day", "half", "early_close", "partial"}:
            return "half_day"
        if raw_status in {"closed", "holiday", "non_trading", "no_session"}:
            return "closed"
        raise ValueError(f"row {row_number}: unsupported calendar status {raw_status!r}")

    raw_open = str(row.get("is_open", "")).strip().lower()
    if raw_open in {"1", "true", "yes", "y", "open"}:
        return "open"
    if raw_open in {"0", "false", "no", "n", "closed"}:
        return "closed"
    raise ValueError(f"row {row_number}: status or is_open is required")


def _bars_from_prices(prices: Sequence[float]) -> List[Bar]:
    return [
        Bar(
            date=f"synthetic-{idx + 1:04d}",
            open=float(price),
            high=float(price),
            low=float(price),
            close=float(price),
            volume=1000.0,
        )
        for idx, price in enumerate(prices)
    ]


def _data_summary(bars: Sequence[Bar]) -> Dict[str, Any]:
    if not bars:
        return {
            "bar_count": 0,
            "start_date": None,
            "end_date": None,
            "first_close": None,
            "last_close": None,
            "fingerprint": _fingerprint_payload([]),
        }
    return {
        "bar_count": len(bars),
        "start_date": bars[0].date,
        "end_date": bars[-1].date,
        "first_close": bars[0].close,
        "last_close": bars[-1].close,
        "fingerprint": _fingerprint_payload([asdict(bar) for bar in bars]),
    }


def _result_summary(result: BacktestResult) -> Dict[str, Any]:
    return {
        "strategy_name": result.strategy_name,
        "verdict": asdict(result.verdict),
        "metrics": result.metrics,
        "benchmark_metrics": result.benchmark_metrics,
        "trade_count": len(result.trades),
        "order_intent_count": len(result.order_intents),
        "equity_points": len(result.equity_curve),
    }


def _fingerprint_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_bar(bar: Bar, *, label: str) -> None:
    values = [bar.open, bar.high, bar.low, bar.close, bar.volume]
    adjusted_values = [bar.adjusted_close, bar.adjusted_open, bar.adjusted_high, bar.adjusted_low]
    values.extend(value for value in adjusted_values if value is not None)
    if any(not math.isfinite(value) for value in values):
        raise ValueError(f"{label}: OHLCV values must be finite")
    if min(bar.open, bar.high, bar.low, bar.close) <= 0.0:
        raise ValueError(f"{label}: OHLC prices must be positive")
    if any(value is not None and value <= 0.0 for value in adjusted_values):
        raise ValueError(f"{label}: adjusted OHLC values must be positive")
    if bar.volume < 0.0:
        raise ValueError(f"{label}: volume must be non-negative")
    if bar.high < bar.low:
        raise ValueError(f"{label}: high must be >= low")
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        raise ValueError(f"{label}: high/low must contain open and close")
    if bar.adjusted_high is not None and bar.adjusted_low is not None and bar.adjusted_high < bar.adjusted_low:
        raise ValueError(f"{label}: adjusted_high must be >= adjusted_low")
    adjusted_contained_values = [
        value for value in (bar.adjusted_open, bar.adjusted_close) if value is not None
    ]
    if bar.adjusted_high is not None and adjusted_contained_values:
        if bar.adjusted_high < max(adjusted_contained_values):
            raise ValueError(f"{label}: adjusted_high must contain adjusted open and close")
    if bar.adjusted_low is not None and adjusted_contained_values:
        if bar.adjusted_low > min(adjusted_contained_values):
            raise ValueError(f"{label}: adjusted_low must contain adjusted open and close")


def _validate_data_quality_config(config: DataQualityConfig) -> List[str]:
    reasons: List[str] = []
    if config.min_bars <= 0:
        reasons.append("min_bars must be positive")
    if config.max_zero_volume_ratio < 0.0 or config.max_zero_volume_ratio > 1.0:
        reasons.append("max_zero_volume_ratio must be within [0, 1]")
    if config.max_missing_business_days_per_gap < 0:
        reasons.append("max_missing_business_days_per_gap must be non-negative")
    if config.max_missing_calendar_sessions_per_gap < 0:
        reasons.append("max_missing_calendar_sessions_per_gap must be non-negative")
    for name, value in (
        ("max_open_gap_ratio", config.max_open_gap_ratio),
        ("max_close_jump_ratio", config.max_close_jump_ratio),
        ("max_adjustment_ratio_change", config.max_adjustment_ratio_change),
        ("max_adjusted_ohlc_ratio_spread", config.max_adjusted_ohlc_ratio_spread),
    ):
        if value < 0.0 or not math.isfinite(value):
            reasons.append(f"{name} must be finite and non-negative")
    if config.min_adjustment_ratio <= 0.0 or not math.isfinite(config.min_adjustment_ratio):
        reasons.append("min_adjustment_ratio must be finite and positive")
    if config.max_adjustment_ratio < config.min_adjustment_ratio or not math.isfinite(config.max_adjustment_ratio):
        reasons.append("max_adjustment_ratio must be finite and >= min_adjustment_ratio")
    if config.market_calendar is not None:
        reasons.extend(_validate_market_calendar_profile(config.market_calendar))
    return reasons


def _validate_market_calendar_profile(profile: MarketCalendarProfile) -> List[str]:
    reasons: List[str] = []
    if not str(profile.name).strip():
        reasons.append("market_calendar.name must be non-empty")
    weekend_days = list(profile.weekend_days)
    if (
        len(set(weekend_days)) != len(weekend_days)
        or any(not isinstance(day, int) or day < 0 or day > 6 for day in weekend_days)
    ):
        reasons.append("market_calendar.weekend_days must be unique integers in [0, 6]")

    parsed_expected = _validate_market_calendar_dates(profile.expected_sessions, "expected_sessions", reasons)
    parsed_holidays = _validate_market_calendar_dates(profile.holidays, "holidays", reasons)
    parsed_half_days = _validate_market_calendar_dates(profile.half_days, "half_days", reasons)
    if parsed_expected.intersection(parsed_holidays):
        reasons.append("market_calendar expected_sessions and holidays must not overlap")
    if parsed_holidays.intersection(parsed_half_days):
        reasons.append("market_calendar holidays and half_days must not overlap")
    if parsed_expected and not parsed_half_days.issubset(parsed_expected):
        reasons.append("market_calendar half_days must be included in expected_sessions when expected_sessions is set")
    return reasons


def _validate_market_calendar_dates(
    values: Sequence[str],
    field_name: str,
    reasons: List[str],
) -> set[Date]:
    parsed_dates: set[Date] = set()
    seen: set[str] = set()
    for raw in values:
        date_text = str(raw).strip()
        if date_text in seen:
            reasons.append(f"market_calendar.{field_name} contains duplicate date {date_text}")
            continue
        seen.add(date_text)
        parsed = _parse_iso_date(date_text)
        if parsed is None:
            reasons.append(f"market_calendar.{field_name} contains non-ISO date {date_text!r}")
            continue
        parsed_dates.add(parsed)
    return parsed_dates


def _validate_engine_parity_tolerance(tolerance: EngineParityTolerance) -> List[str]:
    reasons: List[str] = []
    for name, value in (
        ("equity_abs_tolerance", tolerance.equity_abs_tolerance),
        ("equity_rel_tolerance", tolerance.equity_rel_tolerance),
        ("trade_abs_tolerance", tolerance.trade_abs_tolerance),
        ("trade_rel_tolerance", tolerance.trade_rel_tolerance),
    ):
        if value < 0.0 or not math.isfinite(value):
            reasons.append(f"config_invalid: {name} must be finite and non-negative")
    return reasons


def _validate_backtest_inputs(bars: Sequence[Bar], config: BacktestConfig) -> List[str]:
    reasons: List[str] = []
    if len(bars) < 2:
        reasons.append("data_invalid: need at least two bars")
    for idx, bar in enumerate(bars):
        try:
            _validate_bar(bar, label=f"bar {idx}")
        except ValueError as exc:
            reasons.append(f"data_invalid: {exc}")
            break
    if config.initial_capital <= 0.0:
        reasons.append("config_invalid: initial_capital must be positive")
    if config.fee_bps < 0.0 or config.slippage_bps < 0.0:
        reasons.append("config_invalid: fee_bps and slippage_bps must be non-negative")
    if config.trading_days <= 0:
        reasons.append("config_invalid: trading_days must be positive")
    if config.max_allowed_drawdown < 0.0:
        reasons.append("config_invalid: max_allowed_drawdown must be non-negative")
    return reasons


def _validate_walk_forward_config(train_size: int, test_size: int, step_size: int) -> List[str]:
    reasons: List[str] = []
    if train_size <= 0:
        reasons.append("config_invalid: train_size must be positive")
    if test_size <= 0:
        reasons.append("config_invalid: test_size must be positive")
    if step_size <= 0:
        reasons.append("config_invalid: step_size must be positive")
    return reasons


def _validate_parameter_sweep_inputs(
    windows: Sequence[int],
    min_pass_rate: float,
    max_best_score_gap: float,
) -> List[str]:
    reasons: List[str] = []
    if not windows:
        reasons.append("config_invalid: windows must not be empty")
    if any(window <= 0 for window in windows):
        reasons.append("config_invalid: all windows must be positive")
    if not (0.0 <= min_pass_rate <= 1.0):
        reasons.append("config_invalid: min_pass_rate must be within [0, 1]")
    if max_best_score_gap < 0.0:
        reasons.append("config_invalid: max_best_score_gap must be non-negative")
    return reasons


def _validate_cost_stress_inputs(
    cases: Sequence[CostStressCase],
    max_return_decay: float,
) -> List[str]:
    reasons: List[str] = []
    if not cases:
        reasons.append("config_invalid: cost_cases must not be empty")
    if max_return_decay < 0.0 or not math.isfinite(max_return_decay):
        reasons.append("config_invalid: max_return_decay must be finite and non-negative")
    for idx, case in enumerate(cases):
        if case.fee_bps < 0.0 or case.slippage_bps < 0.0:
            reasons.append(f"config_invalid: cost case {idx} fee/slippage must be non-negative")
            break
        if not math.isfinite(case.fee_bps) or not math.isfinite(case.slippage_bps):
            reasons.append(f"config_invalid: cost case {idx} fee/slippage must be finite")
            break
    return reasons


def _validate_stress_matrix_inputs(
    cases: Sequence[StressMatrixCase],
    max_return_decay: float,
) -> List[str]:
    reasons: List[str] = []
    if not cases:
        reasons.append("config_invalid: stress_cases must not be empty")
    if max_return_decay < 0.0 or not math.isfinite(max_return_decay):
        reasons.append("config_invalid: max_return_decay must be finite and non-negative")
    for idx, case in enumerate(cases):
        if case.execution_delay_bars < 0:
            reasons.append(f"config_invalid: stress case {idx} execution_delay_bars must be non-negative")
            break
        numeric_values = (
            ("fee_bps", case.fee_bps),
            ("slippage_bps", case.slippage_bps),
            ("adverse_open_gap_bps", case.adverse_open_gap_bps),
            ("cash_yield_annual", case.cash_yield_annual),
            ("market_impact_bps_per_100pct_participation", case.market_impact_bps_per_100pct_participation),
        )
        for name, value in numeric_values:
            if not math.isfinite(value):
                reasons.append(f"config_invalid: stress case {idx} {name} must be finite")
                return reasons
        if (
            case.fee_bps < 0.0
            or case.slippage_bps < 0.0
            or case.adverse_open_gap_bps < 0.0
            or case.market_impact_bps_per_100pct_participation < 0.0
        ):
            reasons.append(f"config_invalid: stress case {idx} fee/slippage/gap/impact must be non-negative")
            break
        if case.slippage_bps + case.adverse_open_gap_bps >= 10000.0:
            reasons.append(f"config_invalid: stress case {idx} slippage plus adverse gap must be < 10000 bps")
            break
        if (
            case.slippage_bps
            + case.adverse_open_gap_bps
            + case.market_impact_bps_per_100pct_participation
            >= 10000.0
        ):
            reasons.append(
                f"config_invalid: stress case {idx} slippage plus adverse gap plus market impact must be < 10000 bps"
            )
            break
        if case.cash_yield_annual <= -1.0:
            reasons.append(f"config_invalid: stress case {idx} cash_yield_annual must be greater than -1.0")
            break
        if case.max_participation_rate is not None:
            if not math.isfinite(case.max_participation_rate):
                reasons.append(f"config_invalid: stress case {idx} max_participation_rate must be finite")
                break
            if case.max_participation_rate <= 0.0 or case.max_participation_rate > 1.0:
                reasons.append(f"config_invalid: stress case {idx} max_participation_rate must be within (0, 1]")
                break
    return reasons


def _validate_multi_asset_inputs(
    cases: Sequence[MultiAssetBenchmarkCase],
    min_pass_rate: float,
) -> List[str]:
    reasons: List[str] = []
    if min_pass_rate < 0.0 or min_pass_rate > 1.0 or not math.isfinite(min_pass_rate):
        reasons.append("config_invalid: min_pass_rate must be finite and within [0, 1]")
    names = [case.name for case in cases]
    if any(not str(name).strip() for name in names):
        reasons.append("config_invalid: multi-asset case names must be non-empty")
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if duplicate_names:
        reasons.append(f"config_invalid: duplicate multi-asset case names: {', '.join(duplicate_names)}")
    for case in cases:
        for key, value in case.tags.items():
            if not str(key).strip() or not str(value).strip():
                reasons.append(f"config_invalid: multi-asset case {case.name} tags must have non-empty keys and values")
                return reasons
    return reasons


def _target_exposure(strategy: Any, history: Sequence[Bar]) -> float:
    raw = float(strategy.target_exposure(history))
    return max(0.0, min(1.0, raw))


def _portfolio_exposure(cash: float, shares: float, close: float) -> float:
    equity = cash + shares * close
    if equity <= 0.0:
        return 0.0
    return max(0.0, min(1.0, shares * close / equity))


def _make_strategy(strategy_factory: Any, bars: Sequence[Bar]) -> Any:
    if hasattr(strategy_factory, "target_exposure"):
        return strategy_factory
    try:
        return strategy_factory(bars)
    except TypeError:
        return strategy_factory()


def _future_mutated_bars(bars: Sequence[Bar], *, start_index: int, multiplier: float) -> List[Bar]:
    mutated: List[Bar] = []
    for idx, bar in enumerate(bars):
        if idx < start_index:
            mutated.append(bar)
            continue
        mutated.append(
            Bar(
                date=bar.date,
                open=bar.open * multiplier,
                high=bar.high * multiplier,
                low=bar.low * multiplier,
                close=bar.close * multiplier,
                volume=bar.volume,
                adjusted_close=None if bar.adjusted_close is None else bar.adjusted_close * multiplier,
                adjusted_open=None if bar.adjusted_open is None else bar.adjusted_open * multiplier,
                adjusted_high=None if bar.adjusted_high is None else bar.adjusted_high * multiplier,
                adjusted_low=None if bar.adjusted_low is None else bar.adjusted_low * multiplier,
            )
        )
    return mutated


def _empty_engine_parity_metrics(
    result: BacktestResult,
    reference_equity: Sequence[ExternalEngineEquityPoint],
    reference_trades: Sequence[ExternalEngineTrade] | None,
    reference_fills: Sequence[ExternalEngineFill] | None,
    reference_order_intents: Sequence[ExternalEngineOrderIntent] | None,
) -> Dict[str, Any]:
    return {
        "harness_equity_points": len(result.equity_curve),
        "reference_equity_points": len(reference_equity),
        "compared_equity_points": 0,
        "reference_benchmark_points": 0,
        "max_equity_abs_error": 0.0,
        "max_equity_rel_error": 0.0,
        "max_benchmark_abs_error": 0.0,
        "max_benchmark_rel_error": 0.0,
        "harness_trade_count": len(result.trades),
        "reference_trade_count": None if reference_trades is None else len(reference_trades),
        "compared_trades": 0,
        "max_trade_price_abs_error": 0.0,
        "max_trade_price_rel_error": 0.0,
        "max_trade_shares_abs_error": 0.0,
        "max_trade_shares_rel_error": 0.0,
        "max_trade_gross_value_abs_error": 0.0,
        "max_trade_gross_value_rel_error": 0.0,
        "harness_fill_count": len(result.trades),
        "reference_fill_count": None if reference_fills is None else len(reference_fills),
        "compared_fills": 0,
        "max_fill_price_abs_error": 0.0,
        "max_fill_price_rel_error": 0.0,
        "max_fill_shares_abs_error": 0.0,
        "max_fill_shares_rel_error": 0.0,
        "max_fill_gross_value_abs_error": 0.0,
        "max_fill_gross_value_rel_error": 0.0,
        "max_fill_fee_abs_error": 0.0,
        "max_fill_fee_rel_error": 0.0,
        "max_fill_pnl_abs_error": 0.0,
        "max_fill_pnl_rel_error": 0.0,
        "max_fill_target_exposure_abs_error": 0.0,
        "max_fill_target_exposure_rel_error": 0.0,
        "harness_order_intent_count": len(result.order_intents),
        "reference_order_intent_count": None if reference_order_intents is None else len(reference_order_intents),
        "compared_order_intents": 0,
        "max_order_intent_target_exposure_abs_error": 0.0,
        "max_order_intent_target_exposure_rel_error": 0.0,
        "max_order_intent_current_exposure_abs_error": 0.0,
        "max_order_intent_current_exposure_rel_error": 0.0,
        "max_order_intent_desired_shares_abs_error": 0.0,
        "max_order_intent_desired_shares_rel_error": 0.0,
        "max_order_intent_estimated_price_abs_error": 0.0,
        "max_order_intent_estimated_price_rel_error": 0.0,
        "diff_count": 0,
        "diffs_truncated": False,
        "max_recorded_diffs": 0,
    }


def _failed_engine_parity_checks() -> Dict[str, bool]:
    return {
        "equity_point_count": False,
        "equity_dates": False,
        "equity_values": False,
        "benchmark_values": False,
        "trade_count": False,
        "trade_actions": False,
        "trade_values": False,
        "fill_count": False,
        "fill_actions": False,
        "fill_values": False,
        "order_intent_count": False,
        "order_intent_actions": False,
        "order_intent_values": False,
    }


def _record_engine_parity_diff(
    diffs: List[EngineParityDiff],
    metrics: Dict[str, Any],
    max_diffs: int,
    diff: EngineParityDiff,
) -> None:
    metrics["diff_count"] += 1
    if max_diffs > 0 and len(diffs) < max_diffs:
        diffs.append(diff)
        return
    metrics["diffs_truncated"] = True


def _market_impact_rate(
    shares: float,
    volume: float,
    market_impact_bps_per_100pct_participation: float,
) -> float:
    if shares <= 0.0 or volume <= 0.0 or market_impact_bps_per_100pct_participation <= 0.0:
        return 0.0
    participation = min(1.0, shares / volume)
    return (market_impact_bps_per_100pct_participation / 10000.0) * participation


def _relative_error(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0)


def _within_parity_tolerance(
    left: float,
    right: float,
    *,
    abs_tolerance: float,
    rel_tolerance: float,
) -> bool:
    return abs(left - right) <= abs_tolerance or _relative_error(left, right) <= rel_tolerance


def _empty_data_quality_metrics() -> Dict[str, Any]:
    return {
        "bar_count": 0,
        "unique_dates": 0,
        "duplicate_dates": 0,
        "zero_volume_count": 0,
        "zero_volume_ratio": 0.0,
        "adjusted_close_count": 0,
        "adjusted_ohlc_count": 0,
        "partial_adjusted_ohlc_count": 0,
        "adjustment_checks_applied": False,
        "adjusted_ohlc_checks_applied": False,
        "min_adjustment_ratio": 0.0,
        "max_adjustment_ratio": 0.0,
        "max_adjustment_ratio_change": 0.0,
        "max_adjusted_ohlc_ratio_spread": 0.0,
        "date_checks_applied": False,
        "calendar_profile_name": "",
        "calendar_profile_applied": False,
        "calendar_expected_sessions": 0,
        "calendar_missing_sessions": 0,
        "calendar_unexpected_sessions": 0,
        "calendar_half_day_count": 0,
        "missing_business_days": 0,
        "max_open_gap_ratio": 0.0,
        "max_close_jump_ratio": 0.0,
        "error_count": 0,
        "warning_count": 0,
    }


def _data_quality_result(
    config: DataQualityConfig,
    bars: Sequence[Bar],
    metrics: Dict[str, Any],
    issues: Sequence[DataQualityIssue],
) -> DataQualityResult:
    error_count = sum(1 for issue in issues if issue.severity == "ERROR")
    warning_count = sum(1 for issue in issues if issue.severity == "WARN")
    metrics["error_count"] = error_count
    metrics["warning_count"] = warning_count
    if error_count:
        verdict = HarnessVerdict(
            verdict="REJECT",
            reasons=[f"data_quality_errors: {error_count}"] + _issue_codes(issues, severity="ERROR"),
        )
    elif warning_count:
        verdict = HarnessVerdict(
            verdict="KEEP",
            reasons=[f"data_quality_warnings: {warning_count}"] + _issue_codes(issues, severity="WARN"),
        )
    else:
        verdict = HarnessVerdict(verdict="KEEP", reasons=["data_quality_clean"])
    return DataQualityResult(
        config=config,
        bar_count=len(bars),
        metrics=metrics,
        issues=list(issues),
        verdict=verdict,
    )


def _issue_codes(issues: Sequence[DataQualityIssue], *, severity: str) -> List[str]:
    codes = sorted({issue.code for issue in issues if issue.severity == severity})
    return [f"{severity.lower()}: {code}" for code in codes]


def _parse_iso_date(raw: str) -> Date | None:
    try:
        return Date.fromisoformat(raw)
    except ValueError:
        return None


def _market_calendar_date_set(dates: Sequence[str]) -> set[Date]:
    parsed_dates: set[Date] = set()
    for raw in dates:
        parsed = _parse_iso_date(str(raw))
        if parsed is not None:
            parsed_dates.add(parsed)
    return parsed_dates


def _calendar_is_expected_session(profile: MarketCalendarProfile, day: Date) -> bool:
    expected_sessions = _market_calendar_date_set(profile.expected_sessions)
    if expected_sessions:
        return day in expected_sessions
    if day in _market_calendar_date_set(profile.holidays):
        return False
    if day in _market_calendar_date_set(profile.half_days):
        return True
    return day.weekday() not in set(profile.weekend_days)


def _calendar_expected_sessions(profile: MarketCalendarProfile, start: Date, end: Date) -> set[Date]:
    if end < start:
        return set()
    expected_sessions = _market_calendar_date_set(profile.expected_sessions)
    if expected_sessions:
        return {day for day in expected_sessions if start <= day <= end}
    expected: set[Date] = set()
    current = start.toordinal()
    while current <= end.toordinal():
        day = Date.fromordinal(current)
        if _calendar_is_expected_session(profile, day):
            expected.add(day)
        current += 1
    return expected


def _calendar_sessions_between(profile: MarketCalendarProfile, start: Date, end: Date) -> int:
    if end <= start:
        return 0
    return sum(1 for day in _calendar_expected_sessions(profile, start, end) if start < day < end)


def _business_days_between(start: Date, end: Date) -> int:
    missing = 0
    current = start.toordinal() + 1
    while current < end.toordinal():
        day = Date.fromordinal(current)
        if day.weekday() < 5:
            missing += 1
        current += 1
    return missing


def _empty_result(
    strategy_name: str,
    config: BacktestConfig,
    verdict: str,
    reasons: List[str],
) -> BacktestResult:
    zero_metrics = {
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "time_under_water": 0,
        "exposure_ratio": 0.0,
        "turnover": 0.0,
        "trade_count": 0,
        "order_intent_count": 0,
        "win_rate": 0.0,
        "liquidity_participation_cap": None,
        "liquidity_cap_hit_count": 0,
        "liquidity_unfilled_shares": 0.0,
        "max_volume_participation": 0.0,
        "market_impact_bps_per_100pct_participation": 0.0,
        "market_impact_cost": 0.0,
        "market_impact_cost_ratio": 0.0,
        "max_market_impact_bps": 0.0,
    }
    return BacktestResult(
        strategy_name=strategy_name,
        config=config,
        metrics=dict(zero_metrics),
        benchmark_metrics=dict(zero_metrics),
        trades=[],
        equity_curve=[],
        verdict=HarnessVerdict(verdict=verdict, reasons=reasons),
    )


def _empty_walk_forward_metrics() -> Dict[str, Any]:
    return {
        "fold_count": 0,
        "keep_count": 0,
        "reject_count": 0,
        "iterate_count": 0,
        "mean_total_return": 0.0,
        "mean_benchmark_total_return": 0.0,
        "mean_max_drawdown": 0.0,
        "mean_benchmark_max_drawdown": 0.0,
        "worst_max_drawdown": 0.0,
        "downside_pass_rate": 0.0,
        "max_drawdown_breach_count": 0,
    }


def _empty_parameter_sweep_metrics() -> Dict[str, Any]:
    return {
        "window_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "pass_rate": 0.0,
        "best_score": 0.0,
        "median_score": 0.0,
        "best_score_gap": 0.0,
        "stable_pass_cluster": 0,
    }


def _empty_cost_stress_metrics() -> Dict[str, Any]:
    return {
        "case_count": 0,
        "keep_count": 0,
        "reject_count": 0,
        "iterate_count": 0,
        "baseline_total_return": 0.0,
        "min_total_return": 0.0,
        "worst_max_drawdown": 0.0,
        "return_decay": 0.0,
        "all_costs_keep": False,
    }


def _empty_stress_matrix_metrics() -> Dict[str, Any]:
    return {
        "case_count": 0,
        "keep_count": 0,
        "reject_count": 0,
        "iterate_count": 0,
        "baseline_case": None,
        "baseline_total_return": 0.0,
        "min_total_return": 0.0,
        "worst_max_drawdown": 0.0,
        "return_decay": 0.0,
        "all_stress_cases_keep": False,
        "max_execution_delay_bars": 0,
        "max_adverse_open_gap_bps": 0.0,
        "max_cash_yield_annual": 0.0,
        "min_cash_yield_annual": 0.0,
        "max_liquidity_participation_rate": 0.0,
        "liquidity_capped_case_count": 0,
        "max_participation_cap_hit_count": 0,
        "max_volume_participation": 0.0,
        "total_liquidity_unfilled_shares": 0.0,
        "max_market_impact_bps_per_100pct_participation": 0.0,
        "max_observed_market_impact_bps": 0.0,
        "total_market_impact_cost": 0.0,
        "max_market_impact_cost_ratio": 0.0,
    }


def _empty_multi_asset_metrics() -> Dict[str, Any]:
    return {
        "case_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "pass_rate": 0.0,
        "keep_count": 0,
        "reject_count": 0,
        "iterate_count": 0,
        "data_quality_keep_count": 0,
        "data_quality_reject_count": 0,
        "mean_total_return": 0.0,
        "mean_benchmark_total_return": 0.0,
        "worst_max_drawdown": 0.0,
        "worst_benchmark_max_drawdown": 0.0,
        "max_turnover": 0.0,
        "worst_drawdown_case": None,
        "failed_cases": [],
        "group_metrics": {},
    }


def _multi_asset_case_reasons(
    data_quality: DataQualityResult,
    backtest: BacktestResult,
) -> List[str]:
    reasons: List[str] = []
    if data_quality.verdict.verdict != "KEEP":
        reasons.append(f"data_quality_{data_quality.verdict.verdict.lower()}")
    if backtest.verdict.verdict != "KEEP":
        reasons.append(f"backtest_{backtest.verdict.verdict.lower()}")
    return reasons or ["asset_passed_all_gates"]


def _multi_asset_metrics(cases: Sequence[MultiAssetBenchmarkCaseResult]) -> Dict[str, Any]:
    if not cases:
        return _empty_multi_asset_metrics()
    case_count = len(cases)
    passed_count = sum(1 for case in cases if case.passed)
    keep_count = sum(1 for case in cases if case.backtest.verdict.verdict == "KEEP")
    reject_count = sum(1 for case in cases if case.backtest.verdict.verdict == "REJECT")
    iterate_count = sum(1 for case in cases if case.backtest.verdict.verdict == "ITERATE")
    data_quality_keep_count = sum(1 for case in cases if case.data_quality.verdict.verdict == "KEEP")
    data_quality_reject_count = sum(1 for case in cases if case.data_quality.verdict.verdict == "REJECT")
    total_returns = [case.backtest.metrics["total_return"] for case in cases]
    benchmark_returns = [case.backtest.benchmark_metrics["total_return"] for case in cases]
    worst_case = max(cases, key=lambda case: case.backtest.metrics["max_drawdown"])
    return {
        "case_count": case_count,
        "passed_count": passed_count,
        "failed_count": case_count - passed_count,
        "pass_rate": passed_count / case_count,
        "keep_count": keep_count,
        "reject_count": reject_count,
        "iterate_count": iterate_count,
        "data_quality_keep_count": data_quality_keep_count,
        "data_quality_reject_count": data_quality_reject_count,
        "mean_total_return": sum(total_returns) / case_count,
        "mean_benchmark_total_return": sum(benchmark_returns) / case_count,
        "worst_max_drawdown": max(case.backtest.metrics["max_drawdown"] for case in cases),
        "worst_benchmark_max_drawdown": max(case.backtest.benchmark_metrics["max_drawdown"] for case in cases),
        "max_turnover": max(case.backtest.metrics["turnover"] for case in cases),
        "worst_drawdown_case": worst_case.name,
        "failed_cases": [case.name for case in cases if not case.passed],
        "group_metrics": _multi_asset_group_metrics(cases),
    }


def _multi_asset_group_metrics(cases: Sequence[MultiAssetBenchmarkCaseResult]) -> Dict[str, Any]:
    grouped: Dict[str, List[MultiAssetBenchmarkCaseResult]] = {}
    for case in cases:
        for tag_key, tag_value in sorted(case.tags.items()):
            group_name = f"{tag_key}:{tag_value}"
            grouped.setdefault(group_name, []).append(case)
    metrics: Dict[str, Any] = {}
    for group_name, group_cases in sorted(grouped.items()):
        case_count = len(group_cases)
        passed_count = sum(1 for case in group_cases if case.passed)
        metrics[group_name] = {
            "case_count": case_count,
            "passed_count": passed_count,
            "failed_count": case_count - passed_count,
            "pass_rate": passed_count / case_count,
            "failed_cases": [case.name for case in group_cases if not case.passed],
            "worst_max_drawdown": max(case.backtest.metrics["max_drawdown"] for case in group_cases),
        }
    return metrics


def _judge_multi_asset_benchmark(
    metrics: Dict[str, Any],
    *,
    min_pass_rate: float,
    require_all_data_quality: bool,
) -> HarnessVerdict:
    if metrics["case_count"] <= 0:
        return HarnessVerdict(verdict="ITERATE", reasons=["no_multi_asset_cases_tested"])
    reasons: List[str] = []
    if metrics["pass_rate"] < min_pass_rate:
        reasons.append(f"multi_asset_pass_rate_low: {metrics['pass_rate']:.4f} < {min_pass_rate:.4f}")
    if require_all_data_quality and metrics["data_quality_reject_count"] > 0:
        reasons.append(f"multi_asset_data_quality_rejections: {metrics['data_quality_reject_count']}")
    if metrics["iterate_count"] > 0:
        reasons.append(f"multi_asset_iterate_cases: {metrics['iterate_count']}")
    if reasons:
        return HarnessVerdict(verdict="REJECT", reasons=reasons)
    return HarnessVerdict(
        verdict="KEEP",
        reasons=[
            "multi_asset_pass_rate_ok",
            "multi_asset_data_quality_ok",
        ],
    )


def _multi_asset_case_report_rows(result: MultiAssetBenchmarkResult) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for case in sorted(result.cases, key=lambda item: item.name):
        rows.append(
            {
                "name": case.name,
                "description": case.description,
                "tags": json.dumps(case.tags, sort_keys=True),
                "passed": case.passed,
                "reasons": json.dumps(case.reasons, sort_keys=True),
                "data_quality_verdict": case.data_quality.verdict.verdict,
                "data_quality_error_count": case.data_quality.metrics.get("error_count", 0),
                "data_quality_warning_count": case.data_quality.metrics.get("warning_count", 0),
                "backtest_verdict": case.backtest.verdict.verdict,
                "total_return": case.backtest.metrics.get("total_return", 0.0),
                "benchmark_total_return": case.backtest.benchmark_metrics.get("total_return", 0.0),
                "max_drawdown": case.backtest.metrics.get("max_drawdown", 0.0),
                "benchmark_max_drawdown": case.backtest.benchmark_metrics.get("max_drawdown", 0.0),
                "turnover": case.backtest.metrics.get("turnover", 0.0),
                "trade_count": case.backtest.metrics.get("trade_count", len(case.backtest.trades)),
            }
        )
    return rows


def _multi_asset_case_artifact_summary(case: MultiAssetBenchmarkCaseResult) -> Dict[str, Any]:
    return {
        "name": case.name,
        "description": case.description,
        "tags": case.tags,
        "passed": case.passed,
        "reasons": case.reasons,
        "data": _data_summary(case.bars),
        "data_quality": case.data_quality.to_dict(),
        "backtest": _result_summary(case.backtest),
    }


def _unique_artifact_slug(name: str, used_slugs: set[str]) -> str:
    base_slug = _artifact_slug(name)
    slug = base_slug
    suffix = 2
    while slug in used_slugs:
        slug = f"{base_slug}_{suffix}"
        suffix += 1
    used_slugs.add(slug)
    return slug


def _artifact_slug(name: str) -> str:
    chars: List[str] = []
    previous_separator = False
    for char in str(name).strip().lower():
        if char.isascii() and char.isalnum():
            chars.append(char)
            previous_separator = False
        elif char in {"-", "_", "."}:
            chars.append(char)
            previous_separator = False
        elif not previous_separator:
            chars.append("_")
            previous_separator = True
    slug = "".join(chars).strip("._-")
    return slug or "case"


def _multi_asset_group_report_rows(result: MultiAssetBenchmarkResult) -> List[Dict[str, Any]]:
    group_metrics = result.metrics.get("group_metrics", {})
    rows: List[Dict[str, Any]] = []
    for group_name, metrics in sorted(group_metrics.items()):
        rows.append(
            {
                "group": group_name,
                "case_count": metrics.get("case_count", 0),
                "passed_count": metrics.get("passed_count", 0),
                "failed_count": metrics.get("failed_count", 0),
                "pass_rate": metrics.get("pass_rate", 0.0),
                "worst_max_drawdown": metrics.get("worst_max_drawdown", 0.0),
                "failed_cases": json.dumps(metrics.get("failed_cases", []), sort_keys=True),
            }
        )
    return rows


def _walk_forward_metrics(folds: Sequence[WalkForwardFold], config: BacktestConfig) -> Dict[str, Any]:
    fold_count = len(folds)
    keep_count = sum(1 for fold in folds if fold.result.verdict.verdict == "KEEP")
    reject_count = sum(1 for fold in folds if fold.result.verdict.verdict == "REJECT")
    iterate_count = sum(1 for fold in folds if fold.result.verdict.verdict == "ITERATE")
    total_returns = [fold.result.metrics["total_return"] for fold in folds]
    benchmark_total_returns = [fold.result.benchmark_metrics["total_return"] for fold in folds]
    drawdowns = [fold.result.metrics["max_drawdown"] for fold in folds]
    benchmark_drawdowns = [fold.result.benchmark_metrics["max_drawdown"] for fold in folds]
    downside_passes = [
        fold.result.metrics["max_drawdown"] < fold.result.benchmark_metrics["max_drawdown"]
        for fold in folds
    ]
    return {
        "fold_count": fold_count,
        "keep_count": keep_count,
        "reject_count": reject_count,
        "iterate_count": iterate_count,
        "mean_total_return": sum(total_returns) / fold_count,
        "mean_benchmark_total_return": sum(benchmark_total_returns) / fold_count,
        "mean_max_drawdown": sum(drawdowns) / fold_count,
        "mean_benchmark_max_drawdown": sum(benchmark_drawdowns) / fold_count,
        "worst_max_drawdown": max(drawdowns),
        "downside_pass_rate": sum(1 for passed in downside_passes if passed) / fold_count,
        "max_drawdown_breach_count": sum(1 for drawdown in drawdowns if drawdown > config.max_allowed_drawdown),
    }


def _parameter_case_reasons(
    backtest: BacktestResult,
    walk_forward: WalkForwardResult,
    regime_stress: RegimeStressResult,
) -> List[str]:
    reasons: List[str] = []
    if backtest.verdict.verdict != "KEEP":
        reasons.append(f"backtest_{backtest.verdict.verdict.lower()}")
    if walk_forward.verdict.verdict != "KEEP":
        reasons.append(f"walk_forward_{walk_forward.verdict.verdict.lower()}")
    if regime_stress.verdict.verdict != "KEEP":
        reasons.append(f"regime_stress_{regime_stress.verdict.verdict.lower()}")
    return reasons or ["all_gates_keep"]


def _parameter_case_score(
    backtest: BacktestResult,
    walk_forward: WalkForwardResult,
    regime_stress: RegimeStressResult,
) -> float:
    return (
        backtest.metrics["total_return"]
        + 0.5 * walk_forward.metrics["mean_total_return"]
        - 2.0 * backtest.metrics["max_drawdown"]
        - walk_forward.metrics["worst_max_drawdown"]
        + regime_stress.metrics["pass_rate"]
    )


def _parameter_sweep_metrics(cases: Sequence[ParameterSweepCase]) -> Dict[str, Any]:
    if not cases:
        return _empty_parameter_sweep_metrics()
    scores = sorted(case.score for case in cases)
    passed_count = sum(1 for case in cases if case.passed)
    median_score = scores[len(scores) // 2] if len(scores) % 2 else (scores[len(scores) // 2 - 1] + scores[len(scores) // 2]) / 2.0
    best_score = max(scores)
    return {
        "window_count": len(cases),
        "passed_count": passed_count,
        "failed_count": len(cases) - passed_count,
        "pass_rate": passed_count / len(cases),
        "best_score": best_score,
        "median_score": median_score,
        "best_score_gap": best_score - median_score,
        "stable_pass_cluster": _longest_pass_cluster(cases),
    }


def _longest_pass_cluster(cases: Sequence[ParameterSweepCase]) -> int:
    longest = 0
    current = 0
    for case in sorted(cases, key=lambda item: item.window):
        if case.passed:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _judge_parameter_sweep(
    metrics: Dict[str, Any],
    *,
    min_pass_rate: float,
    max_best_score_gap: float,
) -> HarnessVerdict:
    if metrics["window_count"] <= 0:
        return HarnessVerdict(verdict="ITERATE", reasons=["no_parameter_windows_tested"])
    reasons: List[str] = []
    if metrics["pass_rate"] < min_pass_rate:
        reasons.append(f"parameter_pass_rate_low: {metrics['pass_rate']:.4f} < {min_pass_rate:.4f}")
    if metrics["stable_pass_cluster"] < 2:
        reasons.append(f"no_stable_neighbor_cluster: {metrics['stable_pass_cluster']} < 2")
    if metrics["best_score_gap"] > max_best_score_gap:
        reasons.append(f"best_score_gap_high: {metrics['best_score_gap']:.4f} > {max_best_score_gap:.4f}")
    if reasons:
        return HarnessVerdict(verdict="REJECT", reasons=reasons)
    return HarnessVerdict(
        verdict="KEEP",
        reasons=[
            "parameter_pass_rate_ok",
            "stable_neighbor_cluster_present",
            "best_score_gap_within_limit",
        ],
    )


def _cost_stress_metrics(cases: Sequence[CostStressCaseResult]) -> Dict[str, Any]:
    if not cases:
        return _empty_cost_stress_metrics()
    keep_count = sum(1 for case in cases if case.result.verdict.verdict == "KEEP")
    reject_count = sum(1 for case in cases if case.result.verdict.verdict == "REJECT")
    iterate_count = sum(1 for case in cases if case.result.verdict.verdict == "ITERATE")
    baseline_case = min(cases, key=lambda case: (case.fee_bps + case.slippage_bps, case.fee_bps, case.slippage_bps))
    total_returns = [case.result.metrics["total_return"] for case in cases]
    baseline_return = baseline_case.result.metrics["total_return"]
    min_return = min(total_returns)
    if baseline_return > 0.0:
        return_decay = max(0.0, (baseline_return - min_return) / abs(baseline_return))
    else:
        return_decay = max(0.0, baseline_return - min_return)
    return {
        "case_count": len(cases),
        "keep_count": keep_count,
        "reject_count": reject_count,
        "iterate_count": iterate_count,
        "baseline_case": baseline_case.name,
        "baseline_total_return": baseline_return,
        "min_total_return": min_return,
        "worst_max_drawdown": max(case.result.metrics["max_drawdown"] for case in cases),
        "return_decay": return_decay,
        "all_costs_keep": keep_count == len(cases),
    }


def _stress_matrix_metrics(cases: Sequence[StressMatrixCaseResult]) -> Dict[str, Any]:
    if not cases:
        return _empty_stress_matrix_metrics()
    keep_count = sum(1 for case in cases if case.result.verdict.verdict == "KEEP")
    reject_count = sum(1 for case in cases if case.result.verdict.verdict == "REJECT")
    iterate_count = sum(1 for case in cases if case.result.verdict.verdict == "ITERATE")
    baseline_case = min(cases, key=lambda case: _stress_case_load(case.case))
    total_returns = [case.result.metrics["total_return"] for case in cases]
    baseline_return = baseline_case.result.metrics["total_return"]
    min_return = min(total_returns)
    if baseline_return > 0.0:
        return_decay = max(0.0, (baseline_return - min_return) / abs(baseline_return))
    else:
        return_decay = max(0.0, baseline_return - min_return)
    return {
        "case_count": len(cases),
        "keep_count": keep_count,
        "reject_count": reject_count,
        "iterate_count": iterate_count,
        "baseline_case": baseline_case.name,
        "baseline_total_return": baseline_return,
        "min_total_return": min_return,
        "worst_max_drawdown": max(case.result.metrics["max_drawdown"] for case in cases),
        "return_decay": return_decay,
        "all_stress_cases_keep": keep_count == len(cases),
        "max_execution_delay_bars": max(case.case.execution_delay_bars for case in cases),
        "max_adverse_open_gap_bps": max(case.case.adverse_open_gap_bps for case in cases),
        "max_cash_yield_annual": max(case.case.cash_yield_annual for case in cases),
        "min_cash_yield_annual": min(case.case.cash_yield_annual for case in cases),
        "max_liquidity_participation_rate": max((case.case.max_participation_rate or 0.0) for case in cases),
        "liquidity_capped_case_count": sum(1 for case in cases if case.case.max_participation_rate is not None),
        "max_participation_cap_hit_count": max(
            case.result.metrics.get("liquidity_cap_hit_count", 0) for case in cases
        ),
        "max_volume_participation": max(case.result.metrics.get("max_volume_participation", 0.0) for case in cases),
        "total_liquidity_unfilled_shares": sum(
            case.result.metrics.get("liquidity_unfilled_shares", 0.0) for case in cases
        ),
        "max_market_impact_bps_per_100pct_participation": max(
            case.case.market_impact_bps_per_100pct_participation for case in cases
        ),
        "max_observed_market_impact_bps": max(
            case.result.metrics.get("max_market_impact_bps", 0.0) for case in cases
        ),
        "total_market_impact_cost": sum(case.result.metrics.get("market_impact_cost", 0.0) for case in cases),
        "max_market_impact_cost_ratio": max(
            case.result.metrics.get("market_impact_cost_ratio", 0.0) for case in cases
        ),
    }


def _stress_case_load(case: StressMatrixCase) -> tuple[float, int, float, float, float, float, str]:
    participation_load = 0.0 if case.max_participation_rate is None else 1.0 / case.max_participation_rate
    return (
        case.fee_bps
        + case.slippage_bps
        + case.adverse_open_gap_bps
        + case.market_impact_bps_per_100pct_participation,
        case.execution_delay_bars,
        participation_load,
        abs(case.cash_yield_annual),
        case.fee_bps,
        case.name,
    )


def _judge_cost_stress(
    metrics: Dict[str, Any],
    cases: Sequence[CostStressCaseResult],
    *,
    max_return_decay: float,
) -> HarnessVerdict:
    if metrics["case_count"] <= 0:
        return HarnessVerdict(verdict="ITERATE", reasons=["no_cost_stress_cases_tested"])
    reasons: List[str] = []
    for case in cases:
        if case.result.verdict.verdict != "KEEP":
            reasons.append(f"cost_case_rejected: {case.name}={case.result.verdict.verdict}")
    if metrics["return_decay"] > max_return_decay:
        reasons.append(f"cost_return_decay_high: {metrics['return_decay']:.4f} > {max_return_decay:.4f}")
    if reasons:
        return HarnessVerdict(verdict="REJECT", reasons=reasons)
    return HarnessVerdict(
        verdict="KEEP",
        reasons=[
            "all_cost_cases_keep",
            "return_decay_within_limit",
        ],
    )


def _judge_stress_matrix(
    metrics: Dict[str, Any],
    cases: Sequence[StressMatrixCaseResult],
    *,
    max_return_decay: float,
) -> HarnessVerdict:
    if metrics["case_count"] <= 0:
        return HarnessVerdict(verdict="ITERATE", reasons=["no_stress_matrix_cases_tested"])
    reasons: List[str] = []
    for case in cases:
        if case.result.verdict.verdict != "KEEP":
            reasons.append(f"stress_case_rejected: {case.name}={case.result.verdict.verdict}")
    if metrics["return_decay"] > max_return_decay:
        reasons.append(f"stress_return_decay_high: {metrics['return_decay']:.4f} > {max_return_decay:.4f}")
    if reasons:
        return HarnessVerdict(verdict="REJECT", reasons=reasons)
    return HarnessVerdict(
        verdict="KEEP",
        reasons=[
            "all_stress_matrix_cases_keep",
            "stress_return_decay_within_limit",
        ],
    )


def _judge_walk_forward(metrics: Dict[str, Any], config: BacktestConfig) -> HarnessVerdict:
    if metrics["fold_count"] <= 0:
        return HarnessVerdict(verdict="ITERATE", reasons=["insufficient_bars_for_walk_forward_folds"])
    reasons: List[str] = []
    if metrics["worst_max_drawdown"] > config.max_allowed_drawdown:
        reasons.append(
            "walk_forward_drawdown_breach: "
            f"{metrics['worst_max_drawdown']:.4f} > {config.max_allowed_drawdown:.4f}"
        )
    if metrics["downside_pass_rate"] < 1.0:
        reasons.append(
            "walk_forward_downside_failed: "
            f"{metrics['downside_pass_rate']:.4f} < 1.0000"
        )
    if metrics["iterate_count"] > 0:
        reasons.append(f"walk_forward_iterate_folds: {metrics['iterate_count']}")
    if reasons:
        return HarnessVerdict(verdict="REJECT", reasons=reasons)
    return HarnessVerdict(
        verdict="KEEP",
        reasons=[
            "all_walk_forward_folds_protect_downside",
            "worst_drawdown_within_limit",
        ],
    )


def _metrics_from_curve(
    equity_values: Sequence[float],
    config: BacktestConfig,
    *,
    max_drawdown: float,
    time_under_water: int,
) -> Dict[str, Any]:
    final_equity = equity_values[-1]
    total_return = final_equity / config.initial_capital - 1.0
    periods = max(1, len(equity_values) - 1)
    cagr = (final_equity / config.initial_capital) ** (config.trading_days / periods) - 1.0
    returns = [
        equity_values[idx] / equity_values[idx - 1] - 1.0
        for idx in range(1, len(equity_values))
        if equity_values[idx - 1] > 0.0
    ]
    sharpe = _annualized_sharpe(returns, config.trading_days)
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "time_under_water": time_under_water,
    }


def _annualized_sharpe(returns: Sequence[float], trading_days: int) -> float:
    if len(returns) < 2:
        return 0.0
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / len(returns)
    volatility = math.sqrt(variance)
    if volatility <= 0.0:
        return 0.0
    return (mean_return / volatility) * math.sqrt(trading_days)


def _judge_result(
    bars: Sequence[Bar],
    strategy: Any,
    config: BacktestConfig,
    metrics: Dict[str, Any],
    benchmark_metrics: Dict[str, Any],
) -> HarnessVerdict:
    min_history = int(getattr(strategy, "min_history", 0))
    if len(bars) <= min_history:
        return HarnessVerdict(
            verdict="ITERATE",
            reasons=[f"insufficient_bars: need more than {min_history} bars for {getattr(strategy, 'name', 'strategy')}"],
        )
    reasons: List[str] = []
    if metrics["max_drawdown"] > config.max_allowed_drawdown:
        reasons.append(
            "max_drawdown_breach: "
            f"{metrics['max_drawdown']:.4f} > {config.max_allowed_drawdown:.4f}"
        )
    if metrics["max_drawdown"] >= benchmark_metrics["max_drawdown"]:
        reasons.append(
            "downside_protection_failed: "
            f"{metrics['max_drawdown']:.4f} >= benchmark {benchmark_metrics['max_drawdown']:.4f}"
        )
    if reasons:
        return HarnessVerdict(verdict="REJECT", reasons=reasons)
    return HarnessVerdict(
        verdict="KEEP",
        reasons=[
            "drawdown_within_limit",
            "max_drawdown_better_than_benchmark",
        ],
    )


def _write_dataclass_csv(path: Path, rows: Sequence[Any], row_type: type) -> None:
    field_names = list(row_type.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _write_dict_csv(path: Path, rows: Sequence[Dict[str, Any]], field_names: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(field_names))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
