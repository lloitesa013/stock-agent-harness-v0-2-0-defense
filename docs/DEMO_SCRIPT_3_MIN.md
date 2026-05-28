# Three-Minute Demo Script

## 0:00 - Problem

Financial AI agents can produce polished strategy claims very quickly. The hard question is whether the claim is reproducible, cost-aware, scoped, and preserved even when the result is weak.

## 0:30 - Product

This is Financial Agent Evidence OS. It is not a trading bot. It is a claim-governed verification and evidence system for financial AI agents.

## 1:00 - v0.3 Proof

The v0.3 release extends the system from deterministic benchmark evidence to sealed ETF evidence for SPY, QQQ, TLT, GLD, and IEF over the fixed 2016-01-01 to 2025-12-31 period.

The full provider-derived CSV snapshots stay local or private because redistribution rights are unclear. The public repo carries the manifest, hash policy, claim contract, sample schema, and verifier code.

## 1:40 - Dashboard Walkthrough

Open the Main Dashboard. The first row answers the executive question: claim status, real-market evidence, data mode, and candidate result.

Point out that the candidate result is weak and preserved. That is the product philosophy: the OS does not manufacture winning claims; it verifies, scopes, and seals what the evidence actually says.

## 2:20 - Boundary

The real-market layer does not claim live trading readiness, future-return prediction, return guarantees, broker execution readiness, or market dominance.

It only shows that the evidence pipeline can validate sealed market data, preserve the claim boundary, and produce a reviewable evidence packet.

## 2:50 - Close

QuantConnect, vectorbt, Backtrader, and LEAN execute or model strategies. Financial Agent Evidence OS sits downstream as the evidence and claim-governance layer.

The goal is not to build an AI that claims it beats the market. The goal is to build the system that verifies any AI making that kind of claim.
