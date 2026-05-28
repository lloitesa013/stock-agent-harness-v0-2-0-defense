# Roadmap

## v0.2.1-productization

- Reposition the project as Financial Agent Evidence OS.
- Add product vision, architecture, UI spec, managing-agent spec, comparison, pitch script, roadmap, and risk disclosure.
- Add Streamlit evidence viewer over the sealed `v0.2.0-defense` evidence packet.

## v0.3-real-market-data-defense

- Add SPY, QQQ, TLT, GLD, and IEF historical ETF benchmark inputs.
- Add data-lineage disclosure for real market data.
- Run data-integrity gates, baseline comparison, cost stress, walk-forward validation, bootstrap confidence intervals, strategy freeze, and evidence packet generation.
- Maintain the claim boundary: real market data verifies harness behavior; it does not create a live-performance claim.

## v0.4-overfitting-defense

- Add stronger parameter sensitivity reports.
- Add probability of backtest overfitting style diagnostics where feasible.
- Add shuffled-return and random-strategy negative controls.
- Add clearer degradation reporting between train, validation, and test partitions.

## v0.5-multi-engine-evidence

- Add adapters for reading outputs from external engines such as vectorbt, Backtrader, LEAN, or QuantConnect exports.
- Compare output evidence under the same claim-governance contract.
- Keep engine execution separate from evidence governance.

## v0.6-managing-agent

- Add deterministic managing-agent reports.
- Generate structured verification plans and evidence-gap reports.
- Add claim-language linting and review summaries.

## v1.0-evidence-os

- Provide a stable claim registry.
- Provide stable evidence packet schemas.
- Provide dashboard-ready evidence outputs.
- Provide repeatable release gates and external-review workflows.

