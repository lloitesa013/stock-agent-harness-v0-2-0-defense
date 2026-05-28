# Five-Minute Pitch Script

## 1. Problem

Financial AI agents can produce convincing strategy narratives and backtest results very quickly. But the hard question is not whether an agent can produce a return chart. The hard question is whether the claim is reproducible, robust, cost-aware, and not overstated.

## 2. Solution

This project is Financial Agent Evidence OS.

This is not a trading bot. This is a claim-governed verification and evidence system for financial AI agents.

## 3. Difference from Existing Tools

Backtest engines such as QuantConnect, vectorbt, Backtrader, and LEAN execute strategies. They are important, but execution is not the same as claim governance.

Financial Agent Evidence OS sits downstream. It asks whether a claim survived data-quality gates, strategy freeze checks, cost stress, walk-forward validation, bootstrap confidence intervals, negative controls, and replayable evidence packaging.

## 4. Architecture

The architecture is:

```text
Market Data -> Strategy / Agent -> Backtest Engine -> Verification Harness -> Claim Governance -> Managing Agent -> Evidence Packet -> Dashboard
```

The backtest engine can be internal today and external later. The key layer is the evidence and claim-governance layer.

## 5. UI Demo

The dashboard starts with claim status: PASS, FAIL, or PENDING. It shows strategy freeze, data integrity, overfitting risk, cost stress, forward validation, and evidence packet export readiness.

The UI is not a trading cockpit. It is an executive evidence viewer.

## 6. Managing Agent

The managing agent is a verification manager. It does not trade. It plans verification work, finds missing evidence, reviews whether claims are too broad, suggests baselines, and drafts reports.

## 7. Roadmap

`v0.3-real-market-data-defense` adds real ETF market data evidence. Later versions add stronger overfitting analysis, external backtest-engine adapters, managing-agent reports, and team review workflows.

## 8. Close

The goal is not to build an AI that claims it beats the market. The goal is to build the system that verifies any AI making that kind of claim.

