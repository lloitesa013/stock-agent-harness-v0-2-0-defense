# Ralph helper

This directory contains optional local Ralph tooling for development only.

Ralph is not part of the official evidence packet, CI gate, performance claim, or release criteria. It is an advisory implementation helper for reviewing the `v0.3-real-market-data-defense` checklist.

## Setup

```powershell
cd tools\ralph
npm install
node .\v0_3_real_market_agent.mjs "..\.." "Review v0.3 readiness and finish with DONE."
```

If no `OPENAI_API_KEY` is configured, the agent exits with a setup message instead of producing a report.

## Boundaries

- Ralph does not place trades.
- Ralph does not download market data.
- Ralph does not mutate sealed evidence.
- Ralph output is not official claim evidence.
- Official v0.3 gates must remain deterministic, Python-based, sealed-data, and no-network.
