# Performance Benchmark Method

`downside_performance_v1` runs a deterministic multi-asset synthetic OHLCV benchmark with no network access and no external API requirement.

The benchmark executes these strategies:

- `cash`
- `buy_and_hold_spy`
- `equal_weight`
- `sma_crossover`
- `simple_momentum`
- `mean_reversion`
- `volatility_targeting`
- `stock_harness_ma_cash`
- `agentic_candidate_v1`

The report measures total return, return multiple, CAGR, annualized return, max drawdown, volatility, downside deviation, Sharpe, Sortino, Calmar, worst month, worst year, turnover, exposure, and final equity.

Robustness checks include walk-forward slices, cost and slippage stress, parameter sensitivity, lookahead mutation audit, data-quality gates, and negative controls for lookahead leakage and overfit traps.

The evidence packet contains JSON metrics, baseline comparison, robustness report, performance gate JSON, equity curves CSV, rebalance trace CSV, claim contract JSON, and `PERFORMANCE_MANIFEST.json` with SHA-256 hashes.
