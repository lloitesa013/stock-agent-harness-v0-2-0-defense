# Performance Defense Layer

`v0.2.0-defense` adds a reviewer-facing defense packet for the scoped
`downside_performance_v1` claim.

It does not expand the claim beyond:

> SOTA-grade downside-adjusted hypothetical backtested performance under the
> included deterministic `downside_performance_v1` benchmark suite.

The defense packet answers the most likely review attacks:

- Strategy freeze: records the exact `agentic_candidate_v1` config, strategy
  registry fingerprint, train/validation/test partition, and final-test freeze
  statement.
- Data lineage and bias: discloses that the benchmark uses deterministic
  synthetic OHLCV, records the fixed universe, and marks real-market delisting,
  ticker-change, split, and dividend handling as out of scope for this
  performance benchmark.
- Baseline fairness: confirms that all included baselines use the same universe,
  dates, initial equity, cost/slippage model, portfolio accounting, and metric
  engine.
- Statistical confidence: writes deterministic moving-block bootstrap confidence
  intervals for total return, CAGR, max drawdown, Sharpe, Sortino, and Calmar,
  plus rolling stability and walk-forward references.
- Forward paper-trading protocol: initializes a paper-signal logging protocol
  with frozen parameters and 1/3/6 month checkpoints before any live-performance
  claim is considered.

Build and verify:

```bash
python3 ops/build_downside_performance_defense_packet.py --clean --pretty --forward-start-date 2026-05-27
python3 ops/verify_downside_performance_defense_packet.py --pretty
```

The generated packet is written to:

```text
dist/downside_performance_v1_defense_packet
```

The expected high-level checks are:

```text
strategy_freeze_verified: true
data_bias_defense_passed: true
baseline_fairness_verified: true
statistical_confidence_report_present: true
bootstrap_confidence_intervals_present: true
paper_trading_protocol_initialized: true
performance_claim_boundary_preserved: true
non_claims_preserved: true
```

This is a defense layer for a hypothetical backtest. It is not financial advice,
not live trading evidence, not an investor-return record, and not a universal
market-dominance claim.
