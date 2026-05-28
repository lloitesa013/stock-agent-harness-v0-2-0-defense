# Financial Agent Evidence OS

Financial Agent Evidence OS is a claim-governed verification and evidence system for financial AI agents.

It is not a trading bot. It does not predict stocks, place orders, route broker instructions, or guarantee returns. It tests whether financial-agent strategy claims survive reproducibility, risk, overfitting, cost, and evidence-governance checks.

## Product Thesis

Financial AI agents can produce persuasive research, backtests, and performance narratives. The missing layer is not another backtest engine; it is an evidence OS that asks:

- What exactly is the agent claiming?
- What evidence is required for that claim?
- What must the agent explicitly not claim?
- Was the strategy frozen before evaluation?
- Did the result survive data-quality, cost, walk-forward, bootstrap, and overfitting checks?
- Can an external reviewer replay the evidence packet?

## Positioning

Backtest engines execute strategy logic. Financial Agent Evidence OS governs the claim made from those results.

QuantConnect, vectorbt, Backtrader, LEAN, or internal engines can be treated as upstream execution systems. This project sits downstream as the evidence and claim-governance layer.

## Current Release

The current public release is `v0.2.0-defense`, with productization work continuing on `v0.2.1-productization`.

Allowed scoped claim:

> SOTA-grade downside-adjusted hypothetical backtested performance under the included deterministic `downside_performance_v1` benchmark suite.

This claim is limited to the included benchmark suite and remains hypothetical backtested performance.

## Next Product Step

`v0.3-real-market-data-defense` moves the Evidence OS from synthetic benchmark evidence into sealed ETF evidence for SPY, QQQ, TLT, GLD, and IEF. The purpose is not to claim real-world profitability. The purpose is to show that claim governance, data integrity, baseline comparison, cost stress, walk-forward review, bootstrap confidence, and strategy freeze checks operate on real market data.

The longer-term target is a reference architecture and open evidence protocol for financial AI agent verification:

> An open evidence protocol for financial AI agents.

## Non-Claims

- No financial advice.
- No live trading readiness claim.
- No guaranteed return or future-performance claim.
- No broker integration, order routing, or execution-readiness claim.
- No universal market, strategy, or external-framework dominance claim.
- No claim outside the included benchmark suites.
