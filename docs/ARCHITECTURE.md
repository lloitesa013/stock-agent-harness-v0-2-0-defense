# Architecture

Financial Agent Evidence OS is an evidence layer around financial-agent claims.

```text
Market Data
  -> Strategy / Agent
  -> Backtest Engine
  -> Verification Harness
  -> Claim Governance
  -> Managing Agent
  -> Evidence Packet
  -> Dashboard
```

## Layers

| Layer | Responsibility |
| --- | --- |
| Market Data | OHLCV, ETF data, benchmark data, costs, calendars, and data-quality metadata. |
| Strategy / Agent | Rule-based strategies, ML strategies, LLM agents, or external strategy proposals. |
| Backtest Engine | Internal engine today; future adapters may read vectorbt, Backtrader, LEAN, or QuantConnect outputs. |
| Verification Harness | Data-quality gates, cost stress, walk-forward validation, bootstrap confidence intervals, lookahead audits, and overfitting controls. |
| Claim Governance | Claim registry, non-claims, strategy freeze, release gates, evidence requirements, and publication readiness. |
| Managing Agent | Verification planning, gap finding, claim-scope review, failure exploration, and report drafting. |
| Evidence Packet | JSON, Markdown, PDF, release manifests, hashes, reproducible snapshots, and official claim packets. |
| Dashboard | Executive evidence viewer for claim status, risk state, freeze state, and export readiness. |

## Data Flow

1. A strategy or financial agent proposes a claim.
2. The strategy configuration and allowed claim are recorded.
3. The verification harness evaluates downside, cost, stability, overfit, and reproducibility evidence.
4. Claim governance checks whether the claim is publishable under explicit non-claims.
5. The managing agent summarizes gaps, objections, and next evidence needs.
6. The evidence packet seals JSON, PDF, Markdown, hashes, and replay metadata.
7. The dashboard displays PASS, FAIL, or PENDING status without running trading code.

## v0.3 Real Market Evidence Flow

```text
Optional Downloader
  -> Candidate ETF CSVs
  -> Explicit Seal Step
  -> Local/Private Sealed CSV + Public Hash Manifest
  -> No-Network Real Market Gate
  -> Real Market Evidence Packet
  -> Dashboard Real Market Evidence tab
```

Official v0.3 evaluation reads only sealed CSV snapshots and `REAL_MARKET_DATA_MANIFEST.json`. The public repository carries the manifest and a tiny synthetic schema sample, while full provider-derived ETF CSV snapshots remain local/private artifacts unless redistribution rights are explicitly cleared. The downloader adapters are convenience tools and are not used by official gates.

## Current Boundary

The dashboard and product documents are presentation and evidence-viewer layers. They do not change the sealed `v0.2.0-defense` evidence, and they do not add live-trading capability.
