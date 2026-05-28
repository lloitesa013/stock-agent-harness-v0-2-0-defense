# Managing Agent

The managing agent is a verification manager, not a trading agent.

It does not buy, sell, route orders, generate broker instructions, or claim future returns. Its job is to coordinate evidence.

## Responsibilities

- Build a verification plan for a proposed financial-agent claim.
- Identify missing evidence before publication.
- Detect overbroad or unsafe claim language.
- Search for failure cases and robustness gaps.
- Recommend additional baselines and negative controls.
- Draft evidence summaries for human review.
- Preserve non-claims and release-gate boundaries.

## Non-Roles

- No live trading.
- No portfolio management.
- No broker integration.
- No investment recommendation.
- No guarantee that a strategy will work in future markets.
- No replacement for human legal, compliance, or investment review.

## Workflow

1. Read the claim registry and evidence packet.
2. Check whether all required evidence exists.
3. Compare strategy claims with allowed claim scope.
4. Flag missing tests, weak baselines, or possible overfitting.
5. Draft a concise PASS / FAIL / PENDING explanation.
6. Recommend next evidence collection steps.

## Current Implementation Direction

In `v0.2.1-productization`, the managing-agent concept is documented and surfaced in the dashboard. Future versions may add deterministic managing-agent reports that read the evidence packet and produce structured review notes.

