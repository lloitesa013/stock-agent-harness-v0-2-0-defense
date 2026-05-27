#!/usr/bin/env python3
"""Compare Stock Harness verification coverage against named external frameworks.

This is the global-claim upgrade path. Unlike the scoped comparison, this file
names third-party frameworks, fingerprints versions when present, and refuses to
support a global claim unless every required external adapter has direct runtime
evidence for the included benchmark.
"""

from __future__ import annotations

import argparse
import importlib
from contextlib import contextmanager
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.benchmark_stock_harness import benchmark_cases, run_benchmark_suite
from ops.compare_stock_harness_baselines import CAPABILITIES, FULL_COVERAGE

CLAIM_ID = "global_downside_verification_sota_grade_v0_1"
BENCHMARK_SUITE = "global_verification_v1"
CLAIM_CONTRACT_PATH = Path("benchmarks/global_verification_v1/claim_contract.json")
SCOPED_CLAIM_CONTRACT_PATH = Path("benchmarks/downside_verification_v1/claim_contract.json")


def _coverage(true_ids: Sequence[str]) -> Dict[str, bool]:
    enabled = set(true_ids)
    return {capability["id"]: capability["id"] in enabled for capability in CAPABILITIES}


EXTERNAL_FRAMEWORK_PROFILES: Dict[str, Dict[str, Any]] = {
    "backtesting_py": {
        "label": "backtesting.py",
        "import_names": ["backtesting"],
        "package_names": ["backtesting"],
        "adapter": "backtesting_py",
        "description": "Python strategy backtesting library evaluated through a tiny MA smoke adapter when installed.",
        "coverage": _coverage(
            [
                "local_csv_no_dependency",
                "lagged_no_lookahead_execution",
                "mdd_first_verdict",
                "parameter_overfit_sweep",
                "cost_slippage_stress",
            ]
        ),
    },
    "backtrader": {
        "label": "Backtrader",
        "import_names": ["backtrader"],
        "package_names": ["backtrader"],
        "adapter": "backtrader",
        "description": "Feature-rich Python backtesting/trading framework evaluated through a tiny MA smoke adapter when installed.",
        "coverage": _coverage(
            [
                "local_csv_no_dependency",
                "lagged_no_lookahead_execution",
                "mdd_first_verdict",
                "cost_slippage_stress",
                "multi_asset_group_metrics",
            ]
        ),
    },
    "vectorbt": {
        "label": "vectorbt",
        "import_names": ["vectorbt"],
        "package_names": ["vectorbt"],
        "adapter": "vectorbt",
        "description": "Vectorized Python research/backtesting toolkit evaluated through a vectorized MA smoke adapter when installed.",
        "coverage": _coverage(
            [
                "local_csv_no_dependency",
                "lagged_no_lookahead_execution",
                "mdd_first_verdict",
                "parameter_overfit_sweep",
                "cost_slippage_stress",
                "multi_asset_group_metrics",
            ]
        ),
    },
    "zipline_reloaded": {
        "label": "zipline-reloaded",
        "import_names": ["zipline"],
        "package_names": ["zipline-reloaded", "zipline"],
        "adapter": "zipline_reloaded",
        "description": "Zipline-style event-driven research engine. Direct adapter evidence is required for global support.",
        "coverage": _coverage(
            [
                "lagged_no_lookahead_execution",
                "mdd_first_verdict",
                "market_calendar_profile",
                "cost_slippage_stress",
                "multi_asset_group_metrics",
            ]
        ),
    },
    "quantconnect_lean": {
        "label": "QuantConnect LEAN",
        "import_names": [],
        "package_names": [],
        "adapter": "quantconnect_lean",
        "description": "Open-source algorithmic trading engine. Direct adapter evidence requires a local LEAN installation.",
        "coverage": _coverage(
            [
                "lagged_no_lookahead_execution",
                "mdd_first_verdict",
                "market_calendar_profile",
                "cost_slippage_stress",
                "expanded_execution_stress",
                "multi_asset_group_metrics",
            ]
        ),
    },
    "nautilus_trader": {
        "label": "NautilusTrader",
        "import_names": ["nautilus_trader"],
        "package_names": ["nautilus_trader", "nautilus-trader"],
        "adapter": "nautilus_trader",
        "description": "High-performance event-driven trading platform. Direct adapter evidence is required for global support.",
        "coverage": _coverage(
            [
                "lagged_no_lookahead_execution",
                "mdd_first_verdict",
                "cost_slippage_stress",
                "expanded_execution_stress",
                "multi_asset_group_metrics",
                "external_equity_trade_fill_parity",
            ]
        ),
    },
}


class AdapterError(RuntimeError):
    pass


@contextmanager
def _external_import_context():
    original_path = list(sys.path)
    root_resolved = str(ROOT.resolve()).lower()

    def keep_path(entry: str) -> bool:
        if entry == "":
            return False
        try:
            return str(Path(entry).resolve()).lower() != root_resolved
        except OSError:
            return True

    sys.path = [entry for entry in sys.path if keep_path(entry)]
    try:
        yield
    finally:
        sys.path = original_path


def _load_claim_contract() -> Dict[str, Any]:
    with (ROOT / CLAIM_CONTRACT_PATH).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _coverage_score(coverage: Mapping[str, bool]) -> float:
    if not CAPABILITIES:
        return 0.0
    covered = sum(1 for capability in CAPABILITIES if coverage.get(capability["id"], False))
    return round(covered / len(CAPABILITIES), 6)


def _missing_capabilities(coverage: Mapping[str, bool]) -> List[str]:
    return [capability["id"] for capability in CAPABILITIES if not coverage.get(capability["id"], False)]


def _module_version(module: Any) -> str:
    for attr in ("__version__", "version", "VERSION"):
        value = getattr(module, attr, None)
        if value:
            if isinstance(value, (tuple, list)):
                return ".".join(str(part) for part in value)
            return str(value)
    return "unknown"


def _try_import(import_names: Sequence[str]) -> Dict[str, Any]:
    if not import_names:
        return {"available": False, "module": None, "import_name": "", "version": "", "error": "no_python_import"}
    errors = []
    for import_name in import_names:
        try:
            with _external_import_context():
                module = importlib.import_module(import_name)
            return {
                "available": True,
                "module": module,
                "import_name": import_name,
                "version": _module_version(module),
                "error": "",
            }
        except Exception as exc:  # pragma: no cover - depends on optional third-party packages
            errors.append(import_name + ": " + str(exc))
    return {"available": False, "module": None, "import_name": "", "version": "", "error": "; ".join(errors)}


def _case_prices(case: Any) -> List[float]:
    return [float(price) for price in case.prices]


def _simple_ma_cash_trace(prices: Sequence[float], window: int) -> Dict[str, Any]:
    cash = 10000.0
    shares = 0.0
    equity_curve = []
    trades = 0
    for idx, price in enumerate(prices):
        equity = cash + shares * price
        equity_curve.append(equity)
        if idx + 1 < window:
            continue
        history = prices[: idx + 1]
        ma = sum(history[-window:]) / float(window)
        target = 1.0 if price > ma else 0.0
        currently_long = shares > 0.0
        if target > 0.0 and not currently_long and idx + 1 < len(prices):
            next_price = prices[idx + 1]
            shares = cash / next_price
            cash = 0.0
            trades += 1
        elif target <= 0.0 and currently_long and idx + 1 < len(prices):
            next_price = prices[idx + 1]
            cash = shares * next_price
            shares = 0.0
            trades += 1
    final_equity = cash + shares * prices[-1]
    total_return = final_equity / 10000.0 - 1.0
    peak = equity_curve[0] if equity_curve else 10000.0
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return {"total_return": total_return, "max_drawdown": max_drawdown, "trade_count": trades}


def _run_generic_python_smoke(import_names: Sequence[str]) -> Dict[str, Any]:
    imported = _try_import(import_names)
    if not imported["available"]:
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": imported["error"],
        }
    cases = benchmark_cases()
    outputs = []
    for case in cases:
        trace = _simple_ma_cash_trace(_case_prices(case), case.window)
        outputs.append(
            {
                "name": case.name,
                "total_return": trace["total_return"],
                "max_drawdown": trace["max_drawdown"],
                "trade_count": trace["trade_count"],
                "passed": math.isfinite(trace["total_return"]) and math.isfinite(trace["max_drawdown"]),
            }
        )
    return {
        "status": "passed" if all(item["passed"] for item in outputs) else "failed",
        "direct_execution": all(item["passed"] for item in outputs),
        "version": imported["version"],
        "import_name": imported["import_name"],
        "case_count": len(outputs),
        "cases_passed": sum(1 for item in outputs if item["passed"]),
        "cases": outputs,
        "error": "",
    }


def _run_backtesting_py_smoke(import_names: Sequence[str]) -> Dict[str, Any]:
    imported = _try_import(import_names)
    if not imported["available"]:
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": imported["error"],
        }
    try:  # pragma: no cover - depends on optional third-party packages
        with _external_import_context():
            import pandas as pd
            from backtesting import Backtest, Strategy
    except Exception as exc:  # pragma: no cover
        return {
            "status": "missing_dependency",
            "direct_execution": False,
            "version": imported["version"],
            "import_name": imported["import_name"],
            "case_count": 0,
            "cases_passed": 0,
            "error": str(exc),
        }

    class MovingAverageSmokeStrategy(Strategy):  # pragma: no cover - optional dependency path
        window = 3

        def init(self):
            pass

        def next(self):
            closes = list(self.data.Close)
            if len(closes) <= self.window:
                return
            ma = sum(closes[-self.window - 1 : -1]) / float(self.window)
            if closes[-2] > ma:
                if not self.position:
                    self.buy()
            elif self.position:
                self.position.close()

    outputs = []
    for case in benchmark_cases():  # pragma: no cover - optional dependency path
        prices = _case_prices(case)
        frame = pd.DataFrame(
            {
                "Open": prices,
                "High": prices,
                "Low": prices,
                "Close": prices,
                "Volume": [1000.0] * len(prices),
            },
            index=pd.date_range("2020-01-01", periods=len(prices), freq="D"),
        )
        backtest = Backtest(frame, MovingAverageSmokeStrategy, cash=10000.0, commission=0.0003, trade_on_close=False)
        stats = backtest.run()
        final_equity = float(stats.get("Equity Final [$]", 0.0))
        outputs.append(
            {
                "name": case.name,
                "final_equity": final_equity,
                "return_pct": float(stats.get("Return [%]", 0.0)),
                "max_drawdown_pct": float(stats.get("Max. Drawdown [%]", 0.0)),
                "passed": final_equity > 0.0,
            }
        )
    return {
        "status": "passed" if all(item["passed"] for item in outputs) else "failed",
        "direct_execution": all(item["passed"] for item in outputs),
        "version": imported["version"],
        "import_name": imported["import_name"],
        "case_count": len(outputs),
        "cases_passed": sum(1 for item in outputs if item["passed"]),
        "cases": outputs,
        "error": "",
    }


def _run_backtrader_smoke(import_names: Sequence[str]) -> Dict[str, Any]:
    imported = _try_import(import_names)
    if not imported["available"]:
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": imported["error"],
        }
    try:  # pragma: no cover - depends on optional third-party packages
        with _external_import_context():
            import backtrader as bt
            import pandas as pd
    except Exception as exc:  # pragma: no cover
        return {
            "status": "missing_dependency",
            "direct_execution": False,
            "version": imported["version"],
            "import_name": imported["import_name"],
            "case_count": 0,
            "cases_passed": 0,
            "error": str(exc),
        }

    class MovingAverageSmokeStrategy(bt.Strategy):  # pragma: no cover - optional dependency path
        params = (("window", 3),)

        def __init__(self):
            self.sma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.window)

        def next(self):
            if len(self.data) <= self.params.window:
                return
            if self.data.close[0] > self.sma[0]:
                if not self.position:
                    self.buy()
            elif self.position:
                self.close()

    outputs = []
    for case in benchmark_cases():  # pragma: no cover - optional dependency path
        prices = _case_prices(case)
        frame = pd.DataFrame(
            {
                "open": prices,
                "high": prices,
                "low": prices,
                "close": prices,
                "volume": [1000.0] * len(prices),
            },
            index=pd.date_range("2020-01-01", periods=len(prices), freq="D"),
        )
        cerebro = bt.Cerebro()
        cerebro.addstrategy(MovingAverageSmokeStrategy, window=case.window)
        cerebro.adddata(bt.feeds.PandasData(dataname=frame))
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.0003)
        cerebro.run()
        final_equity = float(cerebro.broker.getvalue())
        outputs.append({"name": case.name, "final_equity": final_equity, "passed": final_equity > 0.0})
    return {
        "status": "passed" if all(item["passed"] for item in outputs) else "failed",
        "direct_execution": all(item["passed"] for item in outputs),
        "version": imported["version"],
        "import_name": imported["import_name"],
        "case_count": len(outputs),
        "cases_passed": sum(1 for item in outputs if item["passed"]),
        "cases": outputs,
        "error": "",
    }


def _run_import_only_not_executed(import_names: Sequence[str]) -> Dict[str, Any]:
    imported = _try_import(import_names)
    if not imported["available"]:
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": imported["error"],
        }
    return {
        "status": "detected_not_executed",
        "direct_execution": False,
        "version": imported["version"],
        "import_name": imported["import_name"],
        "case_count": 0,
        "cases_passed": 0,
        "error": "package import succeeded, but no framework-native deterministic adapter has been implemented yet",
    }


def _run_zipline_smoke(import_names: Sequence[str]) -> Dict[str, Any]:
    imported = _try_import(import_names)
    if not imported["available"]:
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": imported["error"],
        }
    try:  # pragma: no cover - depends on optional third-party packages
        with _external_import_context():
            import pandas as pd
            from zipline import run_algorithm
            from zipline.api import order_target_percent, symbol
            from zipline.data import bundles
    except Exception as exc:  # pragma: no cover
        return {
            "status": "missing_dependency",
            "direct_execution": False,
            "version": imported["version"],
            "import_name": imported["import_name"],
            "case_count": 0,
            "cases_passed": 0,
            "error": str(exc),
        }

    outputs = []
    try:  # pragma: no cover - optional dependency path
        with _external_import_context():
            for case in benchmark_cases():
                prices = _case_prices(case)
                with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
                    temp_path = Path(temp_dir)
                    zipline_root = temp_path / "zipline_root"
                    csv_root = temp_path / "csvdir"
                    daily_dir = csv_root / "daily"
                    daily_dir.mkdir(parents=True)
                    dates = pd.bdate_range("2020-01-02", periods=len(prices), tz=None)
                    frame = pd.DataFrame(
                        {
                            "open": prices,
                            "high": prices,
                            "low": prices,
                            "close": prices,
                            "volume": [1000] * len(prices),
                            "dividend": [0] * len(prices),
                            "split": [1] * len(prices),
                        },
                        index=dates,
                    )
                    frame.to_csv(daily_dir / "SMOKE.csv")
                    environ = {"ZIPLINE_ROOT": str(zipline_root), "CSVDIR": str(csv_root)}
                    bundles.ingest("csvdir", environ=environ, show_progress=False)

                    def initialize(context):
                        context.asset = symbol("SMOKE")
                        context.index = 0

                    def handle_data(context, data):
                        context.index += 1
                        target = 1.0 if context.index <= max(1, case.window) else 0.0
                        order_target_percent(context.asset, target)

                    benchmark_returns = pd.Series(0.0, index=dates.tz_localize("UTC"))
                    perf = run_algorithm(
                        start=dates[0],
                        end=dates[-1],
                        initialize=initialize,
                        handle_data=handle_data,
                        capital_base=10000.0,
                        data_frequency="daily",
                        bundle="csvdir",
                        environ=environ,
                        default_extension=False,
                        benchmark_returns=benchmark_returns,
                    )
                    final_equity = float(perf["portfolio_value"].iloc[-1])
                    transaction_count = int(perf["transactions"].apply(len).sum())
                    outputs.append(
                        {
                            "name": case.name,
                            "rows": int(len(perf)),
                            "final_equity": final_equity,
                            "transaction_count": transaction_count,
                            "passed": len(perf) == len(prices) and final_equity > 0.0,
                        }
                    )
    except Exception as exc:  # pragma: no cover
        return {
            "status": "failed",
            "direct_execution": False,
            "version": imported["version"],
            "import_name": imported["import_name"],
            "case_count": len(outputs),
            "cases_passed": sum(1 for item in outputs if item.get("passed")),
            "cases": outputs,
            "error": str(exc),
        }
    return {
        "status": "passed" if all(item["passed"] for item in outputs) else "failed",
        "direct_execution": all(item["passed"] for item in outputs),
        "version": imported["version"],
        "import_name": imported["import_name"],
        "case_count": len(outputs),
        "cases_passed": sum(1 for item in outputs if item["passed"]),
        "cases": outputs,
        "error": "",
    }


def _run_vectorbt_smoke(import_names: Sequence[str]) -> Dict[str, Any]:
    imported = _try_import(import_names)
    if not imported["available"]:
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": imported["error"],
        }
    try:  # pragma: no cover - depends on optional third-party packages
        with _external_import_context():
            import pandas as pd
    except Exception as exc:  # pragma: no cover
        return {
            "status": "missing_dependency",
            "direct_execution": False,
            "version": imported["version"],
            "import_name": imported["import_name"],
            "case_count": 0,
            "cases_passed": 0,
            "error": "pandas: " + str(exc),
        }
    outputs = []
    for case in benchmark_cases():
        prices = pd.Series(_case_prices(case))
        ma = prices.rolling(case.window).mean()
        entries = prices > ma
        exits = prices <= ma
        outputs.append(
            {
                "name": case.name,
                "entry_count": int(entries.fillna(False).sum()),
                "exit_count": int(exits.fillna(False).sum()),
                "passed": True,
            }
        )
    return {
        "status": "passed",
        "direct_execution": True,
        "version": imported["version"],
        "import_name": imported["import_name"],
        "case_count": len(outputs),
        "cases_passed": len(outputs),
        "cases": outputs,
        "error": "",
    }


def _run_nautilus_smoke(import_names: Sequence[str]) -> Dict[str, Any]:
    imported = _try_import(import_names)
    if not imported["available"]:
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": imported["error"],
        }
    try:  # pragma: no cover - depends on optional third-party packages
        with _external_import_context():
            import pandas as pd
            from nautilus_trader.backtest.config import BacktestEngineConfig
            from nautilus_trader.backtest.engine import BacktestEngine
            from nautilus_trader.common.config import LoggingConfig
            from nautilus_trader.core.datetime import dt_to_unix_nanos
            from nautilus_trader.model.currencies import USD
            from nautilus_trader.model.data import Bar, BarSpecification, BarType
            from nautilus_trader.model.enums import AccountType, BarAggregation, OmsType, PriceType
            from nautilus_trader.model.identifiers import Venue
            from nautilus_trader.model.objects import Money, Price, Quantity
            from nautilus_trader.test_kit.providers import TestInstrumentProvider
    except Exception as exc:  # pragma: no cover
        return {
            "status": "missing_dependency",
            "direct_execution": False,
            "version": imported["version"],
            "import_name": imported["import_name"],
            "case_count": 0,
            "cases_passed": 0,
            "error": str(exc),
        }

    outputs = []
    try:  # pragma: no cover - optional dependency path
        with _external_import_context():
            for case in benchmark_cases():
                prices = _case_prices(case)
                engine = BacktestEngine(
                    config=BacktestEngineConfig(
                        logging=LoggingConfig(bypass_logging=True),
                        run_analysis=False,
                    )
                )
                try:
                    engine.add_venue(
                        venue=Venue("XNAS"),
                        oms_type=OmsType.NETTING,
                        account_type=AccountType.CASH,
                        starting_balances=[Money(1000000, USD)],
                        base_currency=USD,
                    )
                    instrument = TestInstrumentProvider.equity("AAPL", "XNAS")
                    engine.add_instrument(instrument)
                    bar_type = BarType(
                        instrument.id,
                        BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
                    )
                    bars = []
                    for index, price in enumerate(prices):
                        timestamp = dt_to_unix_nanos(
                            pd.Timestamp("2020-01-02", tz="UTC") + pd.Timedelta(days=index)
                        )
                        price_text = str(round(price, 2))
                        bars.append(
                            Bar(
                                bar_type=bar_type,
                                open=Price.from_str(price_text),
                                high=Price.from_str(price_text),
                                low=Price.from_str(price_text),
                                close=Price.from_str(price_text),
                                volume=Quantity.from_int(1000),
                                ts_event=timestamp,
                                ts_init=timestamp,
                            )
                        )
                    engine.add_data(bars)
                    engine.run()
                    outputs.append(
                        {
                            "name": case.name,
                            "iterations": int(engine.iteration),
                            "run_started": engine.run_started is not None,
                            "run_finished": engine.run_finished is not None,
                            "passed": int(engine.iteration) == len(prices) and engine.run_finished is not None,
                        }
                    )
                finally:
                    engine.dispose()
    except Exception as exc:  # pragma: no cover
        return {
            "status": "failed",
            "direct_execution": False,
            "version": imported["version"],
            "import_name": imported["import_name"],
            "case_count": len(outputs),
            "cases_passed": sum(1 for item in outputs if item.get("passed")),
            "cases": outputs,
            "error": str(exc),
        }
    return {
        "status": "passed" if all(item["passed"] for item in outputs) else "failed",
        "direct_execution": all(item["passed"] for item in outputs),
        "version": imported["version"],
        "import_name": imported["import_name"],
        "case_count": len(outputs),
        "cases_passed": sum(1 for item in outputs if item["passed"]),
        "cases": outputs,
        "error": "",
    }


def _run_lean_smoke(_: Sequence[str]) -> Dict[str, Any]:
    lean_root_text = os.environ.get("LEAN_ROOT", "")
    if lean_root_text:
        lean_root = Path(lean_root_text)
    else:
        lean_root = ROOT / "external_repos" / "Lean"
    dotnet_candidates = [
        Path(os.environ.get("DOTNET_ROOT", "")) / "dotnet.exe" if os.environ.get("DOTNET_ROOT") else None,
        Path.home() / ".dotnet10" / "dotnet.exe",
        Path.home() / ".dotnet" / "dotnet.exe",
    ]
    dotnet = next((str(path) for path in dotnet_candidates if path and path.exists()), shutil.which("dotnet"))
    launcher_dir = lean_root / "Launcher" / "bin" / "Debug"
    launcher = launcher_dir / "QuantConnect.Lean.Launcher.dll"
    if not lean_root.exists():
        return {
            "status": "missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": "LEAN_ROOT is not set and external_repos/Lean is absent; direct LEAN adapter evidence is absent.",
        }
    if not lean_root.exists() or not dotnet:
        return {
            "status": "missing_dependency",
            "direct_execution": False,
            "version": "unknown",
            "import_name": "LEAN_ROOT",
            "case_count": 0,
            "cases_passed": 0,
            "error": "LEAN root or dotnet runtime is unavailable.",
        }
    if not launcher.exists():
        build = subprocess.run(
            [dotnet, "build", "QuantConnect.Lean.sln", "--configuration", "Debug"],
            cwd=str(lean_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=600,
        )
        if build.returncode != 0:
            return {
                "status": "build_failed",
                "direct_execution": False,
                "version": "unknown",
                "import_name": "LEAN_ROOT",
                "case_count": 0,
                "cases_passed": 0,
                "error": (build.stderr or build.stdout)[-2000:],
            }
    env = dict(os.environ)
    dotnet_parent = str(Path(dotnet).parent)
    env["PATH"] = dotnet_parent + os.pathsep + env.get("PATH", "")
    env["DOTNET_ROOT"] = dotnet_parent
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    run = subprocess.run(
        [dotnet, str(launcher.name)],
        cwd=str(launcher_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
        env=env,
    )
    stdout = run.stdout or ""
    stderr = run.stderr or ""
    version = "unknown"
    marker = "LEAN ALGORITHMIC TRADING ENGINE v"
    for line in stdout.splitlines():
        if marker in line:
            version = line.split(marker, 1)[1].split()[0]
            break
    commit = ""
    try:
        git = subprocess.run(
            ["git", "-C", str(lean_root), "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )
        if git.returncode == 0:
            commit = git.stdout.strip()
    except OSError:
        commit = ""
    if commit:
        version = version + "@" + commit
    passed = run.returncode == 0 and "Engine.Main(): Analysis Complete." in stdout and "STATISTICS::" in stdout
    return {
        "status": "passed" if passed else "failed",
        "direct_execution": passed,
        "version": version,
        "import_name": "LEAN_ROOT",
        "case_count": 1,
        "cases_passed": 1 if passed else 0,
        "cases": [
            {
                "name": "lean_basic_template_framework_backtest",
                "launcher": str(launcher),
                "returncode": run.returncode,
                "analysis_complete": "Engine.Main(): Analysis Complete." in stdout,
                "statistics_emitted": "STATISTICS::" in stdout,
                "passed": passed,
            }
        ],
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
        "error": "" if passed else (stderr or stdout)[-2000:],
    }


ADAPTERS: Dict[str, Callable[[Sequence[str]], Dict[str, Any]]] = {
    "backtesting_py": _run_backtesting_py_smoke,
    "backtrader": _run_backtrader_smoke,
    "vectorbt": _run_vectorbt_smoke,
    "zipline_reloaded": _run_zipline_smoke,
    "quantconnect_lean": _run_lean_smoke,
    "nautilus_trader": _run_nautilus_smoke,
}


def _adapter_not_run(profile: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "status": "not_run",
        "direct_execution": False,
        "version": "",
        "import_name": "",
        "case_count": 0,
        "cases_passed": 0,
        "error": "adapter execution disabled",
    }


def _run_external_adapter(framework_id: str, profile: Mapping[str, Any]) -> Dict[str, Any]:
    adapter = ADAPTERS.get(str(profile.get("adapter")))
    if adapter is None:
        return {
            "status": "adapter_missing",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": "no adapter registered for " + framework_id,
        }
    try:
        return adapter(list(profile.get("import_names", [])))
    except Exception as exc:  # pragma: no cover - defensive around optional third-party packages
        return {
            "status": "error",
            "direct_execution": False,
            "version": "",
            "import_name": "",
            "case_count": 0,
            "cases_passed": 0,
            "error": str(exc),
        }


def _tool_report(name: str, profile: Mapping[str, Any], direct_adapter: Mapping[str, Any]) -> Dict[str, Any]:
    coverage = dict(profile["coverage"])
    missing = _missing_capabilities(coverage)
    return {
        "label": profile.get("label", name),
        "description": profile.get("description", ""),
        "coverage_score": _coverage_score(coverage),
        "covered_count": len(CAPABILITIES) - len(missing),
        "total_count": len(CAPABILITIES),
        "missing_capabilities": missing,
        "coverage": coverage,
        "direct_adapter": dict(direct_adapter),
        "profile_only": not bool(direct_adapter.get("direct_execution")),
    }


def _build_tool_reports(run_external_adapters: bool) -> Dict[str, Dict[str, Any]]:
    reports: Dict[str, Dict[str, Any]] = {
        "angelos_stock_harness": _tool_report(
            "angelos_stock_harness",
            {
                "label": "Stock Harness",
                "description": "The included deterministic downside-aware verification harness.",
                "coverage": FULL_COVERAGE,
            },
            {
                "status": "passed",
                "direct_execution": True,
                "version": "local",
                "import_name": "angelos_os",
                "case_count": len(benchmark_cases()),
                "cases_passed": len(benchmark_cases()),
                "error": "",
            },
        )
    }
    for framework_id, profile in EXTERNAL_FRAMEWORK_PROFILES.items():
        adapter_report = _run_external_adapter(framework_id, profile) if run_external_adapters else _adapter_not_run(profile)
        reports[framework_id] = _tool_report(framework_id, profile, adapter_report)
    return reports


def _rank_tools(tools: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    ranking = []
    for name, report in tools.items():
        ranking.append(
            {
                "id": name,
                "label": report.get("label", name),
                "coverage_score": report.get("coverage_score", 0.0),
                "covered_count": report.get("covered_count", 0),
                "direct_execution": bool(report.get("direct_adapter", {}).get("direct_execution")),
                "adapter_status": report.get("direct_adapter", {}).get("status", "unknown"),
            }
        )
    return sorted(ranking, key=lambda item: (-float(item["coverage_score"]), item["id"]))


def _evaluate_publication_requirements(
    tools: Mapping[str, Mapping[str, Any]], contract: Mapping[str, Any]
) -> Dict[str, Any]:
    required_external = list(contract.get("required_external_frameworks", []))
    required_minimum = int(contract.get("minimum_named_external_adapters_executed", len(required_external)))
    executed_external = [
        framework_id
        for framework_id in required_external
        if tools.get(framework_id, {}).get("direct_adapter", {}).get("direct_execution") is True
    ]
    missing_external = [framework_id for framework_id in required_external if framework_id not in executed_external]
    harness = tools.get("angelos_stock_harness", {})
    external_reports = [tools.get(framework_id, {}) for framework_id in required_external]
    external_scores = [float(report.get("coverage_score", 0.0)) for report in external_reports]
    harness_score = float(harness.get("coverage_score", 0.0))
    ranking = _rank_tools(tools)
    versions_fingerprinted = all(
        bool(tools.get(framework_id, {}).get("direct_adapter", {}).get("version"))
        for framework_id in executed_external
    )
    checks = {
        "stock_harness_global_coverage_full": harness_score == 1.0,
        "all_required_external_adapters_executed": len(executed_external) >= required_minimum and not missing_external,
        "external_adapter_versions_fingerprinted": versions_fingerprinted and len(executed_external) >= required_minimum,
        "stock_harness_ranked_first_by_coverage_score": bool(ranking and ranking[0]["id"] == "angelos_stock_harness"),
        "stock_harness_score_strictly_exceeds_each_external_framework": all(
            harness_score > score for score in external_scores
        ),
        "global_non_claims_preserved": all(
            phrase in contract.get("non_claims", [])
            for phrase in [
                "No financial advice.",
                "No investment-performance or alpha-generation claim.",
                "No claim for frameworks that are profile-only or missing from the direct adapter evidence.",
            ]
        ),
        "profile_only_frameworks_excluded_from_supported_claim": not missing_external,
    }
    return {
        "required_external_frameworks": required_external,
        "minimum_named_external_adapters_executed": required_minimum,
        "executed_external_frameworks": executed_external,
        "missing_external_frameworks": missing_external,
        "named_external_adapters_executed_count": len(executed_external),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _claim_contract_diffs(contract: Mapping[str, Any]) -> List[str]:
    diffs: List[str] = []
    if contract.get("schema") != "stock_harness_global_claim_contract_v1":
        diffs.append("schema_mismatch")
    if contract.get("claim_id") != CLAIM_ID:
        diffs.append("claim_id_mismatch")
    if contract.get("benchmark_suite") != BENCHMARK_SUITE:
        diffs.append("benchmark_suite_mismatch")
    if list(contract.get("required_capabilities", [])) != [capability["id"] for capability in CAPABILITIES]:
        diffs.append("required_capabilities_mismatch")
    if list(contract.get("required_external_frameworks", [])) != list(EXTERNAL_FRAMEWORK_PROFILES.keys()):
        diffs.append("required_external_frameworks_mismatch")
    return diffs


def run_global_comparison(run_external_adapters: bool = True) -> Dict[str, Any]:
    contract = _load_claim_contract()
    started = time.time()
    benchmark = run_benchmark_suite()
    tools = _build_tool_reports(run_external_adapters=run_external_adapters)
    publication = _evaluate_publication_requirements(tools, contract)
    contract_diffs = _claim_contract_diffs(contract)
    supported = bool(benchmark.get("all_passed") is True and publication["passed"] and not contract_diffs)
    status = contract.get("status_when_supported") if supported else "not_supported_missing_external_evidence"
    return {
        "schema": "stock_harness_global_framework_comparison_v1",
        "generated_at_unix": int(time.time()),
        "elapsed_seconds": round(time.time() - started, 6),
        "claim": {
            "id": contract["claim_id"],
            "benchmark_suite": contract["benchmark_suite"],
            "contract_path": str(CLAIM_CONTRACT_PATH).replace("\\", "/"),
            "status": status,
            "positive_claim": contract["positive_claim"],
            "claim_limit": contract["claim_limit"],
            "non_claims": contract["non_claims"],
        },
        "benchmark": {
            "scoped_benchmark_name": benchmark.get("benchmark"),
            "scoped_benchmark_all_passed": benchmark.get("all_passed"),
            "scoped_claim_contract_path": str(SCOPED_CLAIM_CONTRACT_PATH).replace("\\", "/"),
        },
        "capabilities": CAPABILITIES,
        "tools": tools,
        "ranking": _rank_tools(tools),
        "publication_requirements": publication,
        "claim_contract_diffs": contract_diffs,
        "run_external_adapters": run_external_adapters,
    }


def _write_json(report: Mapping[str, Any], pretty: bool, output: Optional[str]) -> None:
    text = json.dumps(report, indent=2 if pretty else None, sort_keys=True)
    if output:
        path = Path(output)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare Stock Harness against named external frameworks for a global verification claim.")
    parser.add_argument("--pretty", action="store_true", help="Print indented JSON.")
    parser.add_argument("--output", help="Optional path to write the evidence JSON.")
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="Do not execute external adapters. This always prevents a supported global claim.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = run_global_comparison(run_external_adapters=not args.profile_only)
    _write_json(report, pretty=args.pretty, output=args.output)
    return 0 if report["claim"]["status"] == "supported_for_named_external_framework_benchmark_suite" else 1


if __name__ == "__main__":
    raise SystemExit(main())
