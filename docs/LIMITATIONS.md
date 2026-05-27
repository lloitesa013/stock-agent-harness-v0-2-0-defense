# Limitations

This project is research verification infrastructure. It is deliberately conservative about public claims.

## Out Of Scope

- Financial advice.
- Live trading.
- Broker connectivity.
- Order routing.
- Real-time market data.
- Prediction or alpha claims.
- Portfolio optimization guarantees.
- Tax, legal, or suitability analysis.
- Vendor-data correctness.

## Data Limitations

The harness can detect many structural problems, including duplicate dates, nonmonotonic dates, missing business sessions, invalid OHLCV rows, adjusted-price inconsistencies, zero volume, and split-like jumps. It cannot prove that an input CSV is complete, licensed, survivorship-bias free, corporate-action perfect, or vendor-correct.

## Execution Limitations

The backtest core uses deterministic research execution assumptions. Stress layers model costs, slippage, delays, gaps, cash yield, liquidity limits, and market impact, but they are still verification scenarios, not broker-grade market simulators.

## Benchmark Limitations

`downside_verification_v1` is a local deterministic benchmark suite. It is useful for reproducibility and claim discipline, but it is not an industry certification, a peer-reviewed benchmark, or proof of economic value.

## Release Limitations

The repository includes an MIT license and a clean release bundle builder. A public release should publish the release-gate evidence JSON, benchmark outputs, and `dist/stock_harness_release/RELEASE_MANIFEST.json` for the exact release tag.

