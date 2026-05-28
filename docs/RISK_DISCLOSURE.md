# Risk Disclosure

This project is research software for evidence governance around financial-agent claims.

## What It Is

- A deterministic verification harness.
- A claim-governance layer.
- An evidence packet generator.
- A dashboard-friendly evidence viewer.
- A framework for checking downside risk, overfitting, cost stress, reproducibility, and claim scope.

## What It Is Not

- Not financial advice.
- Not a trading bot.
- Not a stock prediction system.
- Not live trading software.
- Not a broker integration.
- Not an order-routing system.
- Not a guarantee of future returns.
- Not evidence of realized investor returns.
- Not a universal market, strategy, or external-framework dominance claim.

## Backtested Performance

Any performance values in the current evidence packet are hypothetical backtested values under the included benchmark suite. They do not imply future performance, live execution readiness, or investor returns.

## Real Market Data Evidence

The v0.3 real-market layer uses sealed ETF OHLCV snapshots to test the Evidence OS workflow on real data. This remains hypothetical backtested evidence. A failed or weak strategy result in real-market evidence does not invalidate the Evidence OS; it shows that the system can preserve unfavorable evidence instead of turning every benchmark into a promotional claim.

Official real-market gates are no-network and read sealed CSV hashes only. Optional downloader adapters are not official evidence until their outputs are sealed and hashed. Full provider-derived ETF CSV snapshots are not redistributed in the public repository because data redistribution rights are unclear; the public repo carries manifest lineage and a tiny synthetic schema sample instead.

## Data and Model Risk

The current release includes deterministic benchmark evidence. Future releases must separately document real data sources, survivorship risk, corporate action handling, universe selection, liquidity assumptions, and forward paper-trading results.

## Human Review

Evidence packets are designed to support human review. They do not replace legal, compliance, investment, risk, or operational review.
