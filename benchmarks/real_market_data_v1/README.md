# real_market_data_v1

`real_market_data_v1` is the v0.3 sealed ETF evidence benchmark for Financial Agent Evidence OS.

It uses sealed daily OHLCV CSV snapshots for:

- SPY
- QQQ
- TLT
- GLD
- IEF

Default benchmark period:

```text
2016-01-01 through 2025-12-31
```

Official mode is sealed CSV only and no-network. Optional downloader adapters may refresh candidate CSVs, but official evidence requires fixed hashes in `REAL_MARKET_DATA_MANIFEST.json`.

The public repository intentionally does not redistribute full provider-derived ETF CSV snapshots because redistribution rights are unclear. Keep full CSV files as local/private sealed artifacts under `sealed_csv/`, or distribute them only through a properly licensed release asset. The committed `sample_csv/SAMPLE_ETF.csv` file is a tiny synthetic schema sample and is not market data.

The claim is deliberately scoped:

> Real market data evidence demonstrates that the Financial Agent Evidence OS can verify claim-governed strategy evidence on sealed ETF data. It does not establish live trading readiness, future returns, or market dominance.

This benchmark is still hypothetical backtested evidence. It is not financial advice, live investor performance, broker routing, or a guaranteed-return claim.
