#!/usr/bin/env node

/**
 * scripts/test-all.mjs
 * Master test and quality runner for DevMind monorepo.
 *
 * Usage:
 *   node scripts/test-all.mjs [--fast] [--full] [--only <area>] [--changed] [--ci] [--bail]
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const REPO_ROOT = process.cwd();
const args = process.argv.slice(2);

const IS_FULL = args.includes("--full");
const IS_CI = args.includes("--ci") || Boolean(process.env.CI);
const BAIL = args.includes("--bail");
const _CHANGED_ONLY = args.includes("--changed");

const onlyIdx = args.indexOf("--only");
const ONLY_AREA = onlyIdx !== -1 && args[onlyIdx + 1] ? args[onlyIdx + 1] : null;

const TIMESTAMP = new Date().toISOString().replace(/[:.]/g, "-");
const REPORT_DIR = path.join(REPO_ROOT, "reports", TIMESTAMP);

fs.mkdirSync(REPORT_DIR, { recursive: true });

function formatDuration(ms) {
  return `${(ms / 1000).toFixed(2)}s`;
}

function runStep(name, area, command, cmdArgs, condition = true, skipReason = "") {
  if (ONLY_AREA && ONLY_AREA !== area) {
    return { name, area, status: "SKIP", reason: `Filtered by --only ${ONLY_AREA}`, duration: 0 };
  }

  if (!condition) {
    return { name, area, status: "SKIP", reason: skipReason, duration: 0 };
  }

  const logFile = path.join(REPORT_DIR, `${name.replace(/[^a-zA-Z0-9_-]/g, "_")}.log`);
  const start = Date.now();

  if (!IS_CI) {
    process.stdout.write(`  ⏳ Running: ${name} ... `);
  }

  const result = spawnSync(command, cmdArgs, {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      PATH: `${process.env.HOME}/.local/bin:${process.env.HOME}/.local/share/pnpm/bin:${process.env.HOME}/.local/share/pnpm:${process.env.PATH}`,
    },
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });

  const duration = Date.now() - start;
  const combinedOutput = `=== STDOUT ===\n${result.stdout || ""}\n=== STDERR ===\n${result.stderr || ""}\n`;
  fs.writeFileSync(logFile, combinedOutput);

  if (result.status === 0) {
    if (!IS_CI) {
      console.log(`✓ PASS (${formatDuration(duration)})`);
    }
    return { name, area, status: "PASS", duration, logFile };
  } else {
    if (!IS_CI) {
      console.log(`✗ FAIL (${formatDuration(duration)})`);
      console.error(`     See log: ${path.relative(REPO_ROOT, logFile)}`);
    }
    return { name, area, status: "FAIL", duration, logFile, error: result.stderr || result.stdout };
  }
}

function main() {
  console.log(`\n==========================================================`);
  console.log(`DevMind Test-All Runner [${IS_FULL ? "FULL" : "FAST"}]`);
  console.log(`Logs: reports/${TIMESTAMP}/`);
  console.log(`==========================================================\n`);

  const results = [];

  // Step 1: Documentation link validation
  results.push(
    runStep(
      "docs:links",
      "docs",
      "node",
      ["scripts/docs-links.mjs"],
      fs.existsSync(path.join(REPO_ROOT, "scripts/docs-links.mjs")),
      "scripts/docs-links.mjs not found"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  // Step 2: Brand asset drift check
  results.push(
    runStep(
      "brand:check",
      "brand",
      "node",
      ["scripts/sync-brand.mjs", "--check"],
      fs.existsSync(path.join(REPO_ROOT, "scripts/sync-brand.mjs")),
      "scripts/sync-brand.mjs not found"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  // Step 3: TypeScript Typecheck (root & common)
  results.push(
    runStep(
      "typecheck:root",
      "common",
      "pnpm",
      ["typecheck"],
      fs.existsSync(path.join(REPO_ROOT, "tsconfig.json")),
      "tsconfig.json not found"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  // Step 4: Unit tests for @devmind/common
  const hasCommon = fs.existsSync(path.join(REPO_ROOT, "common/package.json"));
  results.push(
    runStep(
      "test:common",
      "common",
      "pnpm",
      ["--filter", "@devmind/common", "test"],
      hasCommon,
      "common package not created yet"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  // Step 5: Build @devmind/common
  results.push(
    runStep(
      "build:common",
      "common",
      "pnpm",
      ["--filter", "@devmind/common", "build"],
      hasCommon,
      "common package not created yet"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  // Step 6: Client (Next.js) steps
  const hasClient = fs.existsSync(path.join(REPO_ROOT, "client/package.json"));
  results.push(
    runStep(
      "typecheck:client",
      "client",
      "pnpm",
      ["--filter", "client", "exec", "tsc", "--noEmit"],
      hasClient,
      "client not scaffolded yet"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  results.push(
    runStep(
      "test:client",
      "client",
      "pnpm",
      ["--filter", "client", "test"],
      hasClient,
      "client not scaffolded yet"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  results.push(
    runStep(
      "test:e2e",
      "client",
      "pnpm",
      ["--filter", "client", "test:e2e"],
      hasClient && IS_FULL,
      "e2e tests skipped in fast mode (run with --full to include Playwright)"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  // Step 7: Extension steps (Phase S2)
  const hasExtension = fs.existsSync(path.join(REPO_ROOT, "extension/package.json"));
  results.push(
    runStep(
      "build:extension",
      "extension",
      "pnpm",
      ["--filter", "devmind-vscode", "build"],
      hasExtension,
      "extension not created yet (Phase S2)"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  results.push(
    runStep(
      "test:extension",
      "extension",
      "pnpm",
      ["--filter", "devmind-vscode", "test"],
      hasExtension,
      "extension not created yet (Phase S2)"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  results.push(
    runStep(
      "package:extension",
      "extension",
      "pnpm",
      ["--filter", "devmind-vscode", "package"],
      hasExtension,
      "extension not created yet (Phase S2)"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  // Step 8: Server steps (Milestone M1)
  const hasServer = fs.existsSync(path.join(REPO_ROOT, "server/pyproject.toml"));
  results.push(
    runStep(
      "lint:server",
      "server",
      "uv",
      ["run", "--directory", "server", "ruff", "check", "."],
      hasServer,
      "server not scaffolded yet (Milestone M1)"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  results.push(
    runStep(
      "boundaries:server",
      "server",
      "uv",
      ["run", "--directory", "server", "lint-imports", "--no-cache"],
      hasServer,
      "server not scaffolded yet (Milestone M1)"
    )
  );
  if (BAIL && results[results.length - 1].status === "FAIL") finish(results);

  results.push(
    runStep(
      "test:server",
      "server",
      "uv",
      ["run", "--directory", "server", "pytest"],
      hasServer,
      "server not scaffolded yet (Milestone M1)"
    )
  );

  finish(results);
}

function finish(results) {
  console.log(`\n==========================================================`);
  console.log(`Test-All Summary`);
  console.log(`==========================================================`);

  let passCount = 0;
  let failCount = 0;
  let skipCount = 0;

  for (const r of results) {
    const statusCol = r.status === "PASS" ? "✓ PASS" : r.status === "FAIL" ? "✗ FAIL" : "- SKIP";

    const reasonCol = r.reason ? ` (${r.reason})` : "";
    const timeCol = r.duration ? ` [${formatDuration(r.duration)}]` : "";

    console.log(`  ${statusCol.padEnd(8)} ${r.name.padEnd(20)} ${timeCol}${reasonCol}`);

    if (r.status === "PASS") passCount++;
    if (r.status === "FAIL") failCount++;
    if (r.status === "SKIP") skipCount++;
  }

  const summary = {
    timestamp: TIMESTAMP,
    passed: passCount,
    failed: failCount,
    skipped: skipCount,
    results,
  };

  fs.writeFileSync(path.join(REPORT_DIR, "summary.json"), JSON.stringify(summary, null, 2));

  console.log(`\nResults: ${passCount} passed, ${failCount} failed, ${skipCount} skipped.`);
  console.log(`Full summary written to: reports/${TIMESTAMP}/summary.json\n`);

  if (failCount > 0) {
    process.exit(1);
  }
  process.exit(0);
}

main();
