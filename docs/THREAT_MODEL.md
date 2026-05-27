# Threat Model

The harness is designed to reduce common research-verification failure modes in stock backtests.

## Primary Threats

- Lookahead leakage from same-bar signals or mutated execution order.
- Silent data corruption in OHLCV CSV input.
- Missing sessions that change moving averages or drawdowns.
- Duplicate or nonmonotonic dates.
- Split-like discontinuities without adjusted-price handling.
- Inconsistent adjusted OHLC fields.
- Overfit parameter choices that only work in one narrow window.
- Fragile results under costs, slippage, delayed execution, gaps, cash yield assumptions, liquidity constraints, or market impact.
- External-engine integration drift in equity curves, trades, fills, or order intents.
- Missing reproducibility metadata.

## Controls

- Strict CSV parsing and data-quality reports.
- Lagged signal execution.
- No-dependency oracle benchmark.
- Lookahead mutation audit.
- External-engine style parity checks.
- Walk-forward and regime validation.
- Parameter overfit sweep.
- Expanded stress matrix.
- Multi-asset grouped metrics and artifact bundles.
- Experiment manifest hashing.

## Residual Risk

These controls make research results harder to fool, but they do not prove market edge, future performance, data-vendor correctness, or live-execution realism.
