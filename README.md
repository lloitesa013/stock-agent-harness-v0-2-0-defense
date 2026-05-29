# Financial Agent Evidence OS

[![Stock Harness Verification CI](https://github.com/lloitesa013/stock-agent-harness-v0-2-0-defense/actions/workflows/stock-harness-ci.yml/badge.svg)](https://github.com/lloitesa013/stock-agent-harness-v0-2-0-defense/actions/workflows/stock-harness-ci.yml)

Financial Agent Evidence OS is a claim-governed verification and evidence
system for financial AI agents.

It is **not** a trading bot, financial advice, live trading software, order
routing, broker integration, or a future-return guarantee. Its purpose is to
test whether financial-agent claims are scoped, reproducible, cost-aware, and
sealed as reviewable evidence.

![v0.3.1 presentation dashboard](docs/assets/v0_3_1_presentation_dashboard.png)

## What It Verifies

- Whether a claim has an explicit benchmark scope.
- Whether evidence artifacts can be reproduced and reviewed.
- Whether non-claims are preserved next to performance language.
- Whether weak or unfavorable evidence remains part of the record.
- Whether release gates, manifests, and seals match the public claim boundary.

## Evidence Surface

- One-page summary: [release_evidence/v0.2.0-defense-final/ONE_PAGE_SUMMARY.md](release_evidence/v0.2.0-defense-final/ONE_PAGE_SUMMARY.md)
- Release seal: [release_evidence/v0.2.0-defense-final/RELEASE_SEAL_MANIFEST.json](release_evidence/v0.2.0-defense-final/RELEASE_SEAL_MANIFEST.json)
- Technical paper: [release_evidence/v0.2.0-defense-final/paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.pdf](release_evidence/v0.2.0-defense-final/paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.pdf)
- Forward protocol: [release_evidence/v0.2.0-defense-final/forward/FORWARD_PAPER_TRADING_START.md](release_evidence/v0.2.0-defense-final/forward/FORWARD_PAPER_TRADING_START.md)
- Release note: [RELEASE_V0_2_0_DEFENSE.md](RELEASE_V0_2_0_DEFENSE.md)
- Three-minute demo script: [docs/DEMO_SCRIPT_3_MIN.md](docs/DEMO_SCRIPT_3_MIN.md)

## Current Layers

- `v0.3.1-presentation-ui`: read-only executive dashboard and short demo package
  for the v0.3 evidence release.
- `v0.3-real-market-data-defense`: sealed ETF evidence for `SPY`, `QQQ`, `TLT`,
  `GLD`, and `IEF`; no live trading or future-return claim.
- `v0.2.0-defense`: performance-defense packet with strategy freeze, evidence
  manifests, and forward paper-trading protocol.
- `downside_verification_v1`: deterministic verification coverage suite for
  local, no-dependency, downside-aware stock backtest research.

## Claim Boundary

This repository contains scoped benchmark claim language, including
SOTA-grade phrasing inside specific included benchmark suites. Such language is
not a universal market, trading, or investment claim.

The supported claims must be read with these boundaries:

- no financial advice
- no live trading readiness
- no broker integration or order routing
- no future-return guarantee
- no realized investor return claim
- no universal market dominance
- no external-framework dominance outside the documented comparison scope

See [docs/CLAIMS.md](docs/CLAIMS.md), [docs/PERFORMANCE_CLAIMS.md](docs/PERFORMANCE_CLAIMS.md),
[docs/PERFORMANCE_NON_CLAIMS.md](docs/PERFORMANCE_NON_CLAIMS.md), and
[docs/RISK_DISCLOSURE.md](docs/RISK_DISCLOSURE.md).

## Quick Reproduction

Run the stock harness unit suite:

```bash
python3 -m unittest tests/test_stock_harness.py
```

Run the deterministic benchmark:

```bash
python3 ops/benchmark_stock_harness.py --pretty
```

Run the public-claim evidence comparison:

```bash
python3 ops/compare_stock_harness_baselines.py --pretty
```

Run the performance claim gate:

```bash
python3 ops/run_downside_performance_claim_gate.py --pretty --output reports/downside_performance_claim_gate_latest.json --evidence-dir dist/downside_performance_v1_claim_gate_evidence
```

Build the v0.2 performance-defense packet:

```bash
python3 ops/build_downside_performance_defense_packet.py --clean --pretty --forward-start-date 2026-05-27
python3 ops/verify_downside_performance_defense_packet.py --pretty
```

Run the read-only Streamlit evidence viewer:

```bash
pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

## Real-Market Data Defense

`v0.3-real-market-data-defense` extends the Evidence OS from deterministic
benchmark evidence to sealed real-market ETF evidence for `SPY`, `QQQ`, `TLT`,
`GLD`, and `IEF` from `2016-01-01` through `2025-12-31`.

The real-market layer verifies that the Evidence OS works on sealed ETF OHLCV
data. It does not expand the project into live trading software and does not
create a future-return claim.

The public repository includes the real-market manifest, claim contract, and a
tiny synthetic schema sample. Full provider-derived ETF CSV snapshots are not
redistributed in the public repo because redistribution rights are unclear; keep
them as local/private sealed artifacts or release assets with appropriate
rights.

Run the sealed no-network gate when local/private sealed CSV artifacts are
present:

```bash
python3 ops/run_real_market_data_defense.py --clean --pretty --output reports/real_market_data_defense_latest.json
```

Optional data refresh adapters are available, but refreshed data must be
explicitly sealed before official use:

```bash
python3 ops/download_real_market_data.py --provider yahoo_chart --pretty
python3 ops/download_real_market_data.py --provider stooq --pretty
python3 ops/download_real_market_data.py --provider yfinance --pretty
```

The local sealed snapshot manifest records `yahoo_chart` as its provider. The
Stooq adapter is retained as a stdlib downloader, but the public Stooq endpoint
may require an API key depending on access policy. Official gates do not call
any downloader. The candidate strategy showed weak real-market performance, and
that result is intentionally preserved as evidence rather than converted into a
promotional claim.

## Productization Layer

The `v0.2.1-productization` work repositions the project as Financial Agent
Evidence OS:

- Product vision: [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- UI spec: [docs/UI_SPEC.md](docs/UI_SPEC.md)
- Managing agent: [docs/MANAGING_AGENT.md](docs/MANAGING_AGENT.md)
- Comparison: [docs/COMPARISON.md](docs/COMPARISON.md)
- Pitch script: [docs/PITCH_SCRIPT.md](docs/PITCH_SCRIPT.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Risk disclosure: [docs/RISK_DISCLOSURE.md](docs/RISK_DISCLOSURE.md)

Ralph advisory tooling is available under [tools/ralph](tools/ralph/README.md).
Ralph is optional, local-only, and not part of official evidence or CI.

## Release Gate

For official claim evidence, run:

```bash
python3 ops/run_stock_harness_official_claim_gate.py --pretty --output reports/stock_harness_official_claim_gate_latest.json
```

The official publication gate requires Python plus Cargo. It runs the full
release gate, embeds that gate JSON into the evidence packet, verifies the
packet and release candidate with `official_claim_ready: true`, replays the
packaged source zip, and reports `official_claim_publishable: true` only when
every scoped assertion passes.

The repository includes an MIT license. Before publishing any release, keep the
public claim scoped, preserve benchmark artifacts for the release tag, and avoid
universal trading-system or external-framework dominance claims.
