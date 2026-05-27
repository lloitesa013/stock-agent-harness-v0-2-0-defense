# Rust Stock Harness

Std-only Rust port of the Downside-Aware Stock Harness verification core.

This crate is research-only infrastructure. It is not financial advice, not live trading software, not order routing, and not a broker integration.

## Scope

Implemented in this v0 Rust port:

- OHLCV CSV loader.
- Structural data-quality gate.
- Lagged moving-average-to-cash backtest.
- MDD-first verdict.
- Deterministic benchmark suite.
- JSON benchmark CLI without external crates.

The Python implementation remains the current full SOTA-grade reference. This Rust crate is the deterministic systems-language foundation that can grow toward parity with the Python evidence package.

## Commands

When Rust is installed:

```bash
cargo test --manifest-path rust_stock_harness/Cargo.toml
cargo run --manifest-path rust_stock_harness/Cargo.toml --bin stock-harness-benchmark -- --pretty
```

No external crates are required.
