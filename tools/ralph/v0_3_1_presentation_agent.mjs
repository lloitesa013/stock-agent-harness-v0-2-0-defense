#!/usr/bin/env node

import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import process from 'node:process';

const USAGE = `Ralph v0.3.1 presentation UI helper

Usage:
  node tools/ralph/v0_3_1_presentation_agent.mjs <repo-root> [prompt]

Example:
  node .\\v0_3_1_presentation_agent.mjs "..\\.." "Review presentation readiness and finish with DONE."

This tool is advisory only. It does not edit files, run gates, place trades,
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
    'dashboard/app.py',
    'docs/UI_SPEC.md',
    'docs/DEMO_SCRIPT_3_MIN.md',
    'RELEASE_NOTES_V0_3_1_PRESENTATION_UI.md',
    'RELEASE_NOTES_V0_3_REAL_MARKET_DATA_DEFENSE.md',
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
      'Ralph presentation helper not started: set OPENAI_API_KEY first. Official gates do not require Ralph or any API key.',
    );
    return 2;
  }

  const repoRoot = resolve(process.cwd(), firstArg);
  const prompt =
    rest.join(' ') ||
    'Review v0.3.1 presentation UI readiness. Produce a concise checklist and finish with DONE.';
  const context = buildContext(repoRoot);

  const { RalphLoopAgent, iterationCountIs } = await import('ralph-loop-agent');
  const agent = new RalphLoopAgent({
    model: process.env.RALPH_MODEL ?? 'openai/gpt-4o-mini',
    instructions:
      'You are an advisory presentation-readiness helper for Financial Agent Evidence OS. ' +
      'You must not suggest live trading claims, future-return prediction, return guarantees, or broker execution. ' +
      'Focus on README clarity, dashboard reviewability, demo flow, and claim boundaries. Finish with DONE when complete.',
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
