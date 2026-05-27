# downside_verification_v1

`downside_verification_v1` is the benchmark suite behind the public SOTA-grade verification claim.

It is intentionally local and deterministic:

- No network.
- No external Python dependencies.
- No broker connection.
- No order routing.
- Synthetic fixtures only.

## Run

```bash
python3 ops/benchmark_stock_harness.py
python3 ops/compare_stock_harness_baselines.py --pretty
```

## Expected Summary

The benchmark is expected to satisfy the subset in `expected_summary.json`:

- All benchmark checks pass.
- Four oracle cases pass.
- External-engine parity has zero diffs.
- Two order intents are compared.
- Market-calendar data-quality case checks three expected sessions.
- Adjusted OHLC checks are applied.
- Two multi-asset case artifact bundles are written.
- Five expanded stress-matrix cases run.

## Claim Use

This benchmark supports a verification-coverage claim only. It should not be used to claim investment performance, live trading readiness, or universal superiority over every external backtesting framework.

## Claim Contract

claim_contract.json is the machine-readable source for the scoped public claim, non-claims, required capabilities, and release-gate assertions for this benchmark suite.
