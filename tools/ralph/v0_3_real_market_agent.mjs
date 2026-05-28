#!/usr/bin/env node

import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import process from 'node:process';

const USAGE = `Ralph v0.3 real-market implementation helper

Usage:
  node tools/ralph/v0_3_real_market_agent.mjs <repo-root> [prompt]

Example:
  node .\\v0_3_real_market_agent.mjs "..\\.." "Review v0.3 readiness and finish with DONE."

This tool is advisory only. It does not edit files, download data, run trades,
or create official evidence.
`;

function printHelp() {
  console.log(USAGE);
}

function readIfExists(path) {
  if (!existsSync(path)) {
    return `[missing] ${path}`;
  }
  return readFileSync(path, 'utf8').slice(0, 4000);
}

function buildContext(repoRoot) {
  const files = [
    'README.md',
    'docs/ROADMAP.md',
    'docs/ARCHITECTURE.md',
    'docs/RISK_DISCLOSURE.md',
    'benchmarks/downside_performance_v1/README.md',
    'dashboard/app.py',
  ];
  return files
    .map((file) => `--- ${file} ---\n${readIfExists(resolve(repoRoot, file))}`)
    .join('\n\n');
}

async function main() {
  const [, , firstArg, ...rest] = process.argv;
  if (!firstArg || firstArg === '--help' || firstArg === '-h') {
    printHelp();
    return 0;
  }

  if (!process.env.OPENAI_API_KEY) {
    console.error(
      'Ralph advisory agent not started: set OPENAI_API_KEY first. Official gates do not require Ralph or any API key.',
    );
    return 2;
  }

  const repoRoot = resolve(process.cwd(), firstArg);
  const prompt =
    rest.join(' ') ||
    'Review v0.3 real-market-data-defense readiness. Produce a concise checklist and finish with DONE.';
  const context = buildContext(repoRoot);

  const { RalphLoopAgent, iterationCountIs } = await import('ralph-loop-agent');
  const agent = new RalphLoopAgent({
    model: process.env.RALPH_MODEL ?? 'openai/gpt-4o-mini',
    instructions:
      'You are an advisory implementation helper for Financial Agent Evidence OS. ' +
      'You must not suggest live trading claims, guaranteed returns, or broker execution. ' +
      'Focus on v0.3 real-market-data-defense evidence gaps. Finish with DONE when complete.',
    stopWhen: iterationCountIs(3),
    verifyCompletion: async ({ result }) => ({
      complete: result.text.includes('DONE'),
      reason: result.text.includes('DONE') ? 'Completed.' : 'Missing DONE marker.',
    }),
  });

  const result = await agent.loop({
    prompt: `${prompt}\n\nRepository context:\n${context}`,
  });
  console.log(result.text);
  return 0;
}

const exitCode = await main();
process.exitCode = exitCode;
