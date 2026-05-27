# Performance Claims

`downside_performance_v1` adds a separate performance layer on top of the existing verification claims.

Supported wording:

> Stock Agent Harness demonstrates SOTA-grade downside-adjusted hypothetical backtested performance under the included deterministic `downside_performance_v1` benchmark suite.

Required qualifiers:

- The result is hypothetical backtested performance.
- The benchmark uses a deterministic included synthetic OHLCV universe.
- The claim is limited to the included benchmark and included baselines.
- The claim requires `performance_claim_publishable: true` from `ops/run_downside_performance_claim_gate.py`.

Do not use this result as a live trading, future return, realized investor return, broker routing, or universal market dominance claim.
