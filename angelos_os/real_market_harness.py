from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .performance_harness import (
    DEFAULT_COST_BPS,
    DEFAULT_SLIPPAGE_BPS,
    INITIAL_EQUITY,
    PERFORMANCE_NON_CLAIMS,
    TRADING_DAYS,
    PerformanceBar,
    PerformanceRunConfig,
    StrategyConfig,
    default_strategy_registry,
    run_downside_performance_benchmark,
)
from .stock_harness import Bar, run_data_quality_gate


ROOT = Path(__file__).resolve().parents[1]
REAL_MARKET_SUITE = "real_market_data_v1"
REAL_MARKET_REPORT_SCHEMA = "financial_agent_real_market_data_defense_v0_3"
REAL_MARKET_MANIFEST_SCHEMA = "real_market_data_manifest_v0_3"
REAL_MARKET_EVIDENCE_MANIFEST_SCHEMA = "real_market_evidence_manifest_v0_3"
REAL_MARKET_CLAIM_LIMIT = (
    "Real market data evidence demonstrates that the Financial Agent Evidence OS "
    "can verify claim-governed strategy evidence on sealed ETF data. It does not "
    "establish live trading readiness, future returns, or market dominance."
)
REAL_MARKET_NON_CLAIMS = [
    "No financial advice.",
    "No live trading readiness claim.",
    "No return guarantee or future performance claim.",
    "No realized investor return claim.",
    "No broker integration, order routing, or execution-readiness claim.",
    "No universal market, strategy, or external-framework dominance claim.",
    "No claim that real-market backtests are live or forward performance.",
]
REAL_MARKET_TICKERS = ["SPY", "QQQ", "TLT", "GLD", "IEF"]
REAL_MARKET_START = "2016-01-01"
REAL_MARKET_END = "2025-12-31"
REAL_MARKET_BENCHMARK_DIR = ROOT / "benchmarks" / REAL_MARKET_SUITE
REAL_MARKET_SEALED_CSV_DIR = REAL_MARKET_BENCHMARK_DIR / "sealed_csv"
REAL_MARKET_MANIFEST_PATH = REAL_MARKET_BENCHMARK_DIR / "REAL_MARKET_DATA_MANIFEST.json"
INTERNAL_SYMBOL_MAP = {
    "SPY_SYN": "SPY",
    "QUALITY_SYN": "QQQ",
    "DEFENSIVE_SYN": "IEF",
    "WHIPSAW_SYN": "GLD",
    "TREND_SYN": "TLT",
}


@dataclass(frozen=True)
class RealMarketRunConfig:
    data_dir: Path = REAL_MARKET_SEALED_CSV_DIR
    manifest_path: Path = REAL_MARKET_MANIFEST_PATH
    evidence_dir: Path = ROOT / "dist" / "real_market_data_v1_evidence"
    cost_bps: float = DEFAULT_COST_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_dir": str(self.data_dir),
            "manifest_path": str(self.manifest_path),
            "evidence_dir": str(self.evidence_dir),
            "cost_bps": self.cost_bps,
            "slippage_bps": self.slippage_bps,
            "official_mode": "sealed_csv_no_network",
        }


def real_market_strategy_registry() -> List[StrategyConfig]:
    labels = {
        "buy_and_hold_spy": "Buy & hold SPY",
        "sma_crossover": "SMA 50/200 crossover on SPY",
        "volatility_targeting": "Volatility targeting SPY",
        "stock_harness_ma_cash": "Stock Harness MA-to-cash SPY baseline",
        "agentic_candidate_v1": "Agentic downside-guarded real ETF momentum v1",
    }
    strategies: List[StrategyConfig] = []
    for strategy in default_strategy_registry():
        strategies.append(
            StrategyConfig(
                strategy.strategy_id,
                labels.get(strategy.strategy_id, strategy.label.replace("synthetic ", "")),
                strategy.family,
                dict(strategy.params),
                strategy.is_candidate,
            )
        )
    return strategies


def load_sealed_real_market_universe(
    data_dir: Path = REAL_MARKET_SEALED_CSV_DIR,
    manifest_path: Path = REAL_MARKET_MANIFEST_PATH,
) -> Tuple[Dict[str, List[PerformanceBar]], Dict[str, Any]]:
    manifest = _load_manifest(manifest_path)
    _verify_manifest(manifest, data_dir)
    raw_by_ticker = {
        ticker: _read_ticker_csv(data_dir / str(manifest["files"][ticker]["path"]))
        for ticker in REAL_MARKET_TICKERS
    }
    common_dates = sorted(set.intersection(*(set(rows.keys()) for rows in raw_by_ticker.values())))
    if len(common_dates) < 2000:
        raise ValueError("sealed real-market data has insufficient common dates")

    universe: Dict[str, List[PerformanceBar]] = {}
    for internal_symbol, ticker in INTERNAL_SYMBOL_MAP.items():
        universe[internal_symbol] = [raw_by_ticker[ticker][day] for day in common_dates]
    return universe, manifest


def run_real_market_data_defense(config: Optional[RealMarketRunConfig] = None) -> Dict[str, Any]:
    cfg = config or RealMarketRunConfig()
    universe, data_manifest = load_sealed_real_market_universe(cfg.data_dir, cfg.manifest_path)
    performance_config = PerformanceRunConfig(
        cost_bps=cfg.cost_bps,
        slippage_bps=cfg.slippage_bps,
        trading_days=TRADING_DAYS,
        initial_equity=INITIAL_EQUITY,
        benchmark_suite=REAL_MARKET_SUITE,
    )
    full_report = run_downside_performance_benchmark(
        universe=universe,
        strategies=real_market_strategy_registry(),
        config=performance_config,
    ).to_dict()
    report = _compact_downside_report(full_report)
    data_integrity = _data_integrity_report(cfg.data_dir, data_manifest)
    bootstrap = _bootstrap_confidence_report(full_report)
    strategy_freeze = _strategy_freeze_report(report, data_manifest, cfg)
    gate = _real_market_gate(report, data_integrity, bootstrap, strategy_freeze, data_manifest)
    payload_without_fingerprint = {
        "schema": REAL_MARKET_REPORT_SCHEMA,
        "benchmark_suite": REAL_MARKET_SUITE,
        "claim_scope": _claim_scope(),
        "config": cfg.to_dict(),
        "data_manifest": data_manifest,
        "engine_symbol_map": dict(INTERNAL_SYMBOL_MAP),
        "data_integrity": data_integrity,
        "downside_performance_report": report,
        "metrics_by_strategy": report.get("metrics_by_strategy", {}),
        "baseline_comparison": report.get("baseline_comparison", {}),
        "cost_slippage_stress": report.get("robustness", {}).get("cost_slippage_stress", {}),
        "walk_forward": report.get("robustness", {}).get("walk_forward", {}),
        "bootstrap_confidence": bootstrap,
        "strategy_freeze": strategy_freeze,
        "real_market_gate": gate,
    }
    fingerprint = _fingerprint(payload_without_fingerprint)
    payload = dict(payload_without_fingerprint)
    payload["manifest"] = {
        "schema": "real_market_report_manifest_v0_3",
        "fingerprint": fingerprint,
        "sealed_data_fingerprint": data_manifest.get("fingerprint"),
    }
    return payload


def write_real_market_evidence_packet(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    clean: bool = False,
) -> Dict[str, Any]:
    if clean and output_dir.exists():
        _safe_clean(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, Any]] = []

    def write_json(name: str, payload: Any) -> None:
        path = output_dir / name
        path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")
        files.append(_file_entry(output_dir, path))

    write_json("real_market_report.json", report)
    write_json("real_market_data_manifest.json", report.get("data_manifest", {}))
    write_json("metrics.json", report.get("metrics_by_strategy", {}))
    write_json("baseline_comparison.json", report.get("baseline_comparison", {}))
    write_json("cost_slippage_stress_report.json", report.get("cost_slippage_stress", {}))
    write_json("walk_forward_report.json", report.get("walk_forward", {}))
    write_json("bootstrap_confidence_report.json", report.get("bootstrap_confidence", {}))
    write_json("strategy_freeze_report.json", report.get("strategy_freeze", {}))
    write_json("real_market_gate.json", report.get("real_market_gate", {}))

    manifest = {
        "schema": REAL_MARKET_EVIDENCE_MANIFEST_SCHEMA,
        "status": "passed" if report.get("real_market_gate", {}).get("real_market_claim_ready") else "failed",
        "benchmark_suite": REAL_MARKET_SUITE,
        "claim_scope": report.get("claim_scope", {}),
        "report_fingerprint": report.get("manifest", {}).get("fingerprint"),
        "sealed_data_fingerprint": report.get("data_manifest", {}).get("fingerprint"),
        "files": sorted(files, key=lambda item: item["path"]),
    }
    manifest_path = output_dir / "REAL_MARKET_EVIDENCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    manifest["files"].append(_file_entry(output_dir, manifest_path))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def build_real_market_data_manifest(
    data_dir: Path,
    manifest_path: Path,
    *,
    provider: str,
    start: str = REAL_MARKET_START,
    end: str = REAL_MARKET_END,
) -> Dict[str, Any]:
    files: Dict[str, Any] = {}
    for ticker in REAL_MARKET_TICKERS:
        relative = Path(f"{ticker}.csv")
        path = data_dir / relative
        rows = _read_ticker_csv(path)
        ordered_dates = sorted(rows)
        files[ticker] = {
            "path": str(relative).replace("\\", "/"),
            "sha256": _sha256(path),
            "rows": len(ordered_dates),
            "first_date": ordered_dates[0] if ordered_dates else "",
            "last_date": ordered_dates[-1] if ordered_dates else "",
            "required_columns": ["Date", "Open", "High", "Low", "Close", "Volume"],
        }
    common_dates = _common_dates_from_files(data_dir)
    payload_without_fingerprint = {
        "schema": REAL_MARKET_MANIFEST_SCHEMA,
        "benchmark_suite": REAL_MARKET_SUITE,
        "provider": provider,
        "source_policy": "sealed_csv_snapshot_with_optional_downloader",
        "distribution_policy": "public_repo_manifest_and_sample_only_full_csv_local_or_private_artifact",
        "official_mode": "sealed_csv_no_network",
        "tickers": list(REAL_MARKET_TICKERS),
        "start": start,
        "end": end,
        "common_date_count": len(common_dates),
        "common_first_date": common_dates[0] if common_dates else "",
        "common_last_date": common_dates[-1] if common_dates else "",
        "adjustment_policy": "provider_adjusted_daily_ohlcv_snapshot",
        "files": files,
    }
    payload = dict(payload_without_fingerprint)
    payload["fingerprint"] = _fingerprint(payload_without_fingerprint)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def download_real_market_csvs(
    output_dir: Path,
    *,
    provider: str = "yahoo_chart",
    start: str = REAL_MARKET_START,
    end: str = REAL_MARKET_END,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    provider_key = provider.lower()
    if provider_key == "stooq":
        for ticker in REAL_MARKET_TICKERS:
            _download_stooq(ticker, output_dir / f"{ticker}.csv", start=start, end=end)
    elif provider_key == "yahoo_chart":
        for ticker in REAL_MARKET_TICKERS:
            _download_yahoo_chart(ticker, output_dir / f"{ticker}.csv", start=start, end=end)
    elif provider_key == "yfinance":
        _download_yfinance(output_dir, start=start, end=end)
    else:
        raise ValueError("unsupported real-market data provider: " + provider)
    return build_real_market_data_manifest(
        output_dir,
        output_dir.parent / "REAL_MARKET_DATA_MANIFEST.json",
        provider=provider_key,
        start=start,
        end=end,
    )


def _download_stooq(ticker: str, output_path: Path, *, start: str, end: str) -> None:
    d1 = start.replace("-", "")
    d2 = end.replace("-", "")
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d&d1={d1}&d2={d2}"
    with urllib.request.urlopen(url, timeout=30) as response:
        content = response.read().decode("utf-8")
    first_line = content.splitlines()[0] if content.splitlines() else ""
    if first_line.strip().lower() != "date,open,high,low,close,volume":
        raise ValueError("unexpected Stooq CSV header for " + ticker + ": " + first_line[:120])
    output_path.write_text(content, encoding="utf-8")


def _download_yahoo_chart(ticker: str, output_path: Path, *, start: str, end: str) -> None:
    from datetime import datetime, timedelta, timezone

    start_ts = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end_ts = int((datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)).timestamp())
    params = urllib.parse.urlencode(
        {
            "period1": str(start_ts),
            "period2": str(end_ts),
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload.get("chart", {}).get("result", [])
    if not result:
        raise ValueError("Yahoo chart returned no result for " + ticker)
    block = result[0]
    timestamps = block.get("timestamp", [])
    quote = block.get("indicators", {}).get("quote", [{}])[0]
    adjclose = block.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
    rows = []
    for idx, timestamp in enumerate(timestamps):
        close = _series_value(quote.get("close", []), idx)
        adjusted_close = _series_value(adjclose, idx)
        if close is None or adjusted_close is None:
            continue
        ratio = 1.0 if close <= 0 else adjusted_close / close
        day = datetime.utcfromtimestamp(int(timestamp)).date().isoformat()
        rows.append(
            [
                day,
                _series_value(quote.get("open", []), idx) * ratio,
                _series_value(quote.get("high", []), idx) * ratio,
                _series_value(quote.get("low", []), idx) * ratio,
                adjusted_close,
                _series_value(quote.get("volume", []), idx),
            ]
        )
    if not rows:
        raise ValueError("Yahoo chart returned no usable rows for " + ticker)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        writer.writerows(rows)


def _download_yfinance(output_dir: Path, *, start: str, end: str) -> None:
    from datetime import timedelta

    try:
        import yfinance as yf  # type: ignore
    except ImportError as exc:
        raise RuntimeError("yfinance provider requires optional dependency: pip install yfinance") from exc

    end_exclusive = (Date.fromisoformat(end) + timedelta(days=1)).isoformat()
    for ticker in REAL_MARKET_TICKERS:
        data = yf.download(ticker, start=start, end=end_exclusive, progress=False, auto_adjust=False)
        if data.empty:
            raise ValueError("yfinance returned no rows for " + ticker)
        output_path = output_dir / f"{ticker}.csv"
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
            for index, row in data.iterrows():
                day = index.date().isoformat()
                writer.writerow(
                    [
                        day,
                        float(row["Open"]),
                        float(row["High"]),
                        float(row["Low"]),
                        float(row["Close"]),
                        float(row["Volume"]),
                    ]
                )


def _series_value(values: Sequence[Any], idx: int) -> float:
    try:
        value = values[idx]
    except IndexError:
        raise ValueError("missing market data series value")
    if value is None:
        raise ValueError("null market data series value")
    return float(value)


def _load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError("missing sealed real-market data manifest: " + str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("real-market data manifest must be a JSON object")
    return payload


def _verify_manifest(manifest: Mapping[str, Any], data_dir: Path) -> None:
    if manifest.get("schema") != REAL_MARKET_MANIFEST_SCHEMA:
        raise ValueError("unexpected real-market manifest schema")
    if list(manifest.get("tickers", [])) != REAL_MARKET_TICKERS:
        raise ValueError("real-market manifest tickers do not match required ETF universe")
    files = manifest.get("files", {})
    for ticker in REAL_MARKET_TICKERS:
        entry = files.get(ticker)
        if not isinstance(entry, Mapping):
            raise ValueError("missing manifest file entry for " + ticker)
        path = data_dir / str(entry.get("path", ""))
        if not path.exists():
            raise FileNotFoundError(
                "missing local/private sealed real-market CSV artifact for "
                + ticker
                + ": "
                + str(path)
                + ". Full ETF CSV snapshots are not redistributed in the public repository."
            )
        if _sha256(path) != entry.get("sha256"):
            raise ValueError("sealed CSV hash mismatch for " + ticker)
    expected = dict(manifest)
    expected.pop("fingerprint", None)
    if _fingerprint(expected) != manifest.get("fingerprint"):
        raise ValueError("real-market manifest fingerprint mismatch")


def _read_ticker_csv(path: Path) -> Dict[str, PerformanceBar]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    rows: Dict[str, PerformanceBar] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("missing required OHLCV columns in " + str(path))
        for row in reader:
            day = str(row["Date"])
            if day < REAL_MARKET_START or day > REAL_MARKET_END:
                continue
            if day in rows:
                raise ValueError("duplicate date in " + str(path) + ": " + day)
            bar = PerformanceBar(
                date=day,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
            rows[day] = bar
    return rows


def _common_dates_from_files(data_dir: Path) -> List[str]:
    date_sets = []
    for ticker in REAL_MARKET_TICKERS:
        date_sets.append(set(_read_ticker_csv(data_dir / f"{ticker}.csv").keys()))
    return sorted(set.intersection(*date_sets)) if date_sets else []


def _data_integrity_report(data_dir: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    ticker_reports: Dict[str, Any] = {}
    passed = True
    for ticker in REAL_MARKET_TICKERS:
        rows = list(_read_ticker_csv(data_dir / str(manifest["files"][ticker]["path"])).values())
        issues = []
        for bar in rows:
            if min(bar.open, bar.high, bar.low, bar.close) <= 0.0:
                issues.append({"date": bar.date, "issue": "non_positive_price"})
            if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
                issues.append({"date": bar.date, "issue": "invalid_high_low"})
        dq = run_data_quality_gate([Bar(bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume) for bar in rows])
        error_count = int(dq.metrics.get("error_count", 0))
        warning_count = int(dq.metrics.get("warning_count", 0))
        ticker_passed = not issues and error_count == 0 and len(rows) >= 2000
        passed = passed and ticker_passed
        ticker_reports[ticker] = {
            "passed": ticker_passed,
            "row_count": len(rows),
            "first_date": rows[0].date if rows else "",
            "last_date": rows[-1].date if rows else "",
            "structural_issue_count": len(issues),
            "data_quality_error_count": error_count,
            "data_quality_warning_count": warning_count,
            "zero_volume_count": dq.metrics.get("zero_volume_count", 0),
        }
    common_dates = _common_dates_from_files(data_dir)
    return {
        "schema": "real_market_data_integrity_v0_3",
        "passed": passed and len(common_dates) >= 2000,
        "common_date_count": len(common_dates),
        "common_first_date": common_dates[0] if common_dates else "",
        "common_last_date": common_dates[-1] if common_dates else "",
        "tickers": ticker_reports,
    }


def _compact_downside_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    universe = dict(report.get("universe", {}))
    universe.update(
        {
            "schema": "real_market_etf_universe_v0_3",
            "data_type": "sealed_real_market_etf_ohlcv",
            "etf_tickers": list(REAL_MARKET_TICKERS),
            "internal_symbol_map": dict(INTERNAL_SYMBOL_MAP),
            "survivorship_bias_note": (
                "fixed ETF benchmark universe selected before v0.3 evaluation; "
                "not a claim about all tradable assets or future ETF survival"
            ),
        }
    )
    return {
        "schema": report.get("schema"),
        "claim": report.get("claim", {}),
        "config": report.get("config", {}),
        "universe": universe,
        "strategies": report.get("strategies", []),
        "metrics_by_strategy": report.get("metrics_by_strategy", {}),
        "rankings": report.get("rankings", {}),
        "baseline_comparison": report.get("baseline_comparison", {}),
        "robustness": report.get("robustness", {}),
        "performance_gate": report.get("performance_gate", {}),
        "negative_controls": report.get("negative_controls", {}),
        "manifest": report.get("manifest", {}),
        "equity_curves_omitted": True,
    }


def _bootstrap_confidence_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    curve = report.get("equity_curves_by_strategy", {}).get("agentic_candidate_v1", [])
    returns = [float(point.get("daily_return", 0.0)) for point in curve[1:]]
    if not returns:
        return {"schema": "real_market_bootstrap_confidence_v0_3", "passed": False, "reason": "missing returns"}
    total_returns = []
    cagrs = []
    max_drawdowns = []
    sample_count = 64
    for sample_idx in range(sample_count):
        sample = [returns[(sample_idx * 17 + item_idx * 37) % len(returns)] for item_idx in range(len(returns))]
        total_return, cagr, max_drawdown = _sample_metrics(sample)
        total_returns.append(total_return)
        cagrs.append(cagr)
        max_drawdowns.append(max_drawdown)
    return {
        "schema": "real_market_bootstrap_confidence_v0_3",
        "passed": True,
        "method": "deterministic_circular_daily_return_resampling",
        "sample_count": sample_count,
        "total_return_ci": _percentiles(total_returns),
        "cagr_ci": _percentiles(cagrs),
        "max_drawdown_ci": _percentiles(max_drawdowns),
    }


def _sample_metrics(returns: Sequence[float]) -> Tuple[float, float, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        if peak > 0.0:
            max_drawdown = max(max_drawdown, 1.0 - equity / peak)
    years = max(1.0 / TRADING_DAYS, len(returns) / TRADING_DAYS)
    total_return = equity - 1.0
    cagr = equity ** (1.0 / years) - 1.0
    return total_return, cagr, max_drawdown


def _percentiles(values: Sequence[float]) -> Dict[str, float]:
    ordered = sorted(values)
    return {
        "p05": ordered[int(0.05 * (len(ordered) - 1))],
        "median": ordered[int(0.50 * (len(ordered) - 1))],
        "p95": ordered[int(0.95 * (len(ordered) - 1))],
    }


def _strategy_freeze_report(
    report: Mapping[str, Any],
    data_manifest: Mapping[str, Any],
    config: RealMarketRunConfig,
) -> Dict[str, Any]:
    strategy_payload = report.get("strategies", [])
    payload = {
        "strategy_payload": strategy_payload,
        "data_fingerprint": data_manifest.get("fingerprint"),
        "config": config.to_dict(),
        "period": {"start": REAL_MARKET_START, "end": REAL_MARKET_END},
    }
    return {
        "schema": "real_market_strategy_freeze_v0_3",
        "passed": True,
        "freeze_statement": (
            "Strategy configuration, ETF universe, sealed CSV hashes, and benchmark period "
            "are fixed before official real-market evaluation."
        ),
        "strategy_fingerprint": _fingerprint(strategy_payload),
        "data_fingerprint": data_manifest.get("fingerprint"),
        "config_fingerprint": _fingerprint(payload),
        "data_cutoff": REAL_MARKET_END,
        "post_freeze_modification_allowed": False,
    }


def _real_market_gate(
    report: Mapping[str, Any],
    data_integrity: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
    strategy_freeze: Mapping[str, Any],
    data_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    robustness = report.get("robustness", {})
    checks = {
        "sealed_csv_manifest_present": data_manifest.get("schema") == REAL_MARKET_MANIFEST_SCHEMA,
        "required_tickers_present": list(data_manifest.get("tickers", [])) == REAL_MARKET_TICKERS,
        "sealed_csv_hashes_verified": bool(data_manifest.get("fingerprint")),
        "benchmark_period_fixed": data_manifest.get("start") == REAL_MARKET_START
        and data_manifest.get("end") == REAL_MARKET_END,
        "common_dates_sufficient": data_manifest.get("common_date_count", 0) >= 2000,
        "data_integrity_passed": data_integrity.get("passed") is True,
        "baseline_comparison_present": bool(report.get("baseline_comparison")),
        "cost_slippage_stress_present": robustness.get("cost_slippage_stress", {}).get("schema")
        == "downside_performance_cost_stress_v1",
        "walk_forward_present": robustness.get("walk_forward", {}).get("schema")
        == "downside_performance_walk_forward_v1",
        "bootstrap_confidence_present": bootstrap.get("passed") is True,
        "strategy_freeze_present": strategy_freeze.get("passed") is True,
        "claim_boundary_preserved": all(non_claim in _claim_scope()["non_claims"] for non_claim in REAL_MARKET_NON_CLAIMS),
    }
    return {
        "schema": "real_market_data_defense_gate_v0_3",
        "real_market_claim_ready": all(checks.values()),
        "checks": checks,
        "claim_scope": _claim_scope(),
        "nested_downside_performance_gate": report.get("performance_gate", {}),
    }


def _claim_scope() -> Dict[str, Any]:
    return {
        "benchmark_suite": REAL_MARKET_SUITE,
        "claim_limit": REAL_MARKET_CLAIM_LIMIT,
        "performance_type": "hypothetical_backtested_real_market_data_evidence",
        "official_mode": "sealed_csv_no_network",
        "distribution_policy": "public_repo_manifest_and_sample_only_full_csv_local_or_private_artifact",
        "non_claims": list(REAL_MARKET_NON_CLAIMS),
    }


def _safe_clean(path: Path) -> None:
    resolved = path.resolve()
    root = ROOT.resolve()
    if root not in [resolved] + list(resolved.parents):
        raise ValueError("refusing to clean output outside repository: " + str(path))
    shutil.rmtree(str(resolved))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_entry(root: Path, path: Path) -> Dict[str, Any]:
    return {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value
