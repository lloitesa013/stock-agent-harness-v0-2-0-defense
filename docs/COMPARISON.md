# Comparison

Financial Agent Evidence OS is not positioned as a replacement for backtest engines or enterprise AI platforms. It is an evidence and claim-governance layer for financial AI outputs.

| System | Primary Role | Relationship to this Project |
| --- | --- | --- |
| QuantConnect / LEAN | Multi-asset backtesting, research, and deployment platform. | Upstream engine whose outputs could be verified and sealed. |
| vectorbt | Fast vectorized backtesting and parameter sweeps. | Upstream research engine whose results could be audited for claim scope and robustness. |
| Backtrader | Python event-driven backtesting framework. | Upstream strategy execution engine. |
| FinRL | Financial reinforcement-learning research framework. | Upstream ML strategy generator requiring evidence governance before performance claims. |
| Palantir | Enterprise data and decision platform. | Broader operational platform; this project is narrower and finance-claim specific. |
| SIONIC AI | Enterprise RAG and agent platform. | Potential agent platform; this project governs financial-agent claims and evidence. |
| Financial Agent Evidence OS | Claim, risk, overfit, and reproducibility evidence layer. | Downstream verifier and evidence packet system. |

## Core Differentiator

This project does not try to be the backtest engine. It verifies whether results from internal or external engines support the claim being made.

Key sentence:

> We are not replacing QuantConnect, vectorbt, or Backtrader. We are building the evidence layer that checks whether results from those systems are reproducible, robust, and claim-safe.

