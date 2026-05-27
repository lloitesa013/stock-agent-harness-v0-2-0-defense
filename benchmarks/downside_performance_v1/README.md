# downside_performance_v1

This benchmark is a deterministic, local, no-network performance suite for Stock Agent Harness.

The supported claim is deliberately scoped: SOTA-grade downside-adjusted hypothetical backtested performance under this included benchmark only. It is not a live trading claim, an alpha claim, a realized investor return claim, or a claim of dominance outside the included benchmark.

The suite compares `agentic_candidate_v1` against cash, buy-and-hold synthetic SPY, equal weight, SMA crossover, simple momentum, mean reversion, volatility targeting, and the Stock Harness MA-to-cash baseline. The gate requires top total return, top CAGR, top Calmar ratio, drawdown control, walk-forward pass, cost stress survival, lookahead audit pass, data-quality pass, negative-control detection, and deterministic replay stability.
