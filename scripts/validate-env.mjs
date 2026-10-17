#!/usr/bin/env node

/**
 * DevMind Secret-Safe Environment Validation Script
 *
 * Audits environment configuration for client, server, and extension.
 * Guarantees:
 * - NEVER prints or logs credential values, tokens, or secrets.
 * - Reports status by variable name only: [OK], [MISSING], [DEFERRED], [INVALID_FORMAT].
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const REQUIRED_SERVER_VARS = [
  "DEVMIND_DATABASE_URL",
  "DEVMIND_REDIS_URL",
  "CLERK_SECRET_KEY",
  "CLERK_WEBHOOK_SECRET",
  "DEVMIND_ENCRYPTION_KEYS",
  "DEVMIND_TURNSTILE_SECRET_KEY",
];

const OPTIONAL_SERVER_VARS = [
  "DEVMIND_DATABASE_URL_DIRECT",
  "DEVMIND_EXT_TOKEN_PEPPER",
  "DEVMIND_GITHUB_CLIENT_ID",
  "DEVMIND_GITHUB_CLIENT_SECRET",
  "DEVMIND_GITHUB_WEBHOOK_SECRET",
  "DEVMIND_LLM_PROVIDER",
  "DEVMIND_LLM_API_KEY",
  "DEVMIND_EMBED_PROVIDER",
  "DEVMIND_EMBED_API_KEY",
  "DEVMIND_RESEND_API_KEY",
];

const DEFERRED_SERVER_VARS = [
  "DEVMIND_R2_ACCOUNT_ID",
  "DEVMIND_R2_ACCESS_KEY_ID",
  "DEVMIND_R2_SECRET_ACCESS_KEY",
  "DEVMIND_R2_BUCKET",
];

const REQUIRED_CLIENT_VARS = [
  "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
  "NEXT_PUBLIC_TURNSTILE_SITE_KEY",
];

const OPTIONAL_CLIENT_VARS = [
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_SITE_URL",
  "NEXT_PUBLIC_FIXTURE_MODE",
];

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const content = fs.readFileSync(filePath, "utf-8");
  const vars = {};
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx > 0) {
      const key = trimmed.slice(0, eqIdx).trim();
      const rawVal = trimmed.slice(eqIdx + 1).trim();
      const val = rawVal.replace(/^["']|["']$/g, "").trim();
      vars[key] = val;
    }
  }
  return vars;
}

function auditScope(scopeName, envVars, requiredList, optionalList, deferredList = []) {
  console.log(`\n=== Auditing ${scopeName} Environment ===`);
  let hasMissing = false;

  console.log("\nRequired Variables:");
  for (const key of requiredList) {
    const val = envVars[key] || process.env[key];
    if (val) {
      // Special validation checks
      if (
        key === "DEVMIND_REDIS_URL" &&
        (val.startsWith("http://") || val.startsWith("https://"))
      ) {
        console.log(
          `  ❌ ${key}: [INVALID_FORMAT] Must use redis:// or rediss:// protocol, not HTTP/REST`
        );
        hasMissing = true;
      } else {
        console.log(`  ✓ ${key}: [CONFIGURED]`);
      }
    } else {
      if (
        key === "DEVMIND_REDIS_URL" &&
        (envVars["UPSTASH_REDIS_REST_URL"] || process.env["UPSTASH_REDIS_REST_URL"])
      ) {
        console.log(
          `  ❌ ${key}: [MISSING] Found UPSTASH_REDIS_REST_URL, but DevMind requires Redis protocol URI ('rediss://default:<password>@<host>.upstash.io:6379') for Celery and redis-py`
        );
      } else {
        console.log(`  ❌ ${key}: [MISSING]`);
      }
      hasMissing = true;
    }
  }

  console.log("\nOptional / Integration Variables:");
  for (const key of optionalList) {
    const val = envVars[key] || process.env[key];
    if (val) {
      console.log(`  ✓ ${key}: [CONFIGURED]`);
    } else {
      console.log(`  - ${key}: [NOT_SET] (optional)`);
    }
  }

  if (deferredList.length > 0) {
    console.log("\nDeferred / Future Architecture Variables (Not needed for MVP):");
    for (const key of deferredList) {
      const val = envVars[key] || process.env[key];
      if (val) {
        console.log(`  ! ${key}: [CONFIGURED_BUT_DEFERRED] (R2 is deferred in MVP)`);
      } else {
        console.log(`  ✓ ${key}: [DEFERRED] (Not required for MVP)`);
      }
    }
  }

  return !hasMissing;
}

function main() {
  const serverEnv = parseEnvFile(path.resolve("server", ".env.production"));
  const clientEnv = parseEnvFile(path.resolve("client", ".env.production"));
  const extEnv = parseEnvFile(path.resolve("extension", ".env.production"));

  const serverOk = auditScope(
    "Server (FastAPI / Render)",
    serverEnv,
    REQUIRED_SERVER_VARS,
    OPTIONAL_SERVER_VARS,
    DEFERRED_SERVER_VARS
  );
  const clientOk = auditScope(
    "Client (Next.js / Vercel)",
    clientEnv,
    REQUIRED_CLIENT_VARS,
    OPTIONAL_CLIENT_VARS
  );
  const extOk = auditScope(
    "Extension (VS Code)",
    extEnv,
    [],
    ["DEVMIND_API_BASE_URL", "DEVMIND_FIXTURE_MODE_DEFAULT"]
  );

  console.log("\n==========================================");
  console.log("Validation Summary (Names only, no secrets exposed):");
  console.log(`  Server:    ${serverOk ? "✓ PASS" : "⚠️ MISSING REQUIRED"}`);
  console.log(`  Client:    ${clientOk ? "✓ PASS" : "⚠️ MISSING REQUIRED"}`);
  console.log(`  Extension: ${extOk ? "✓ PASS" : "⚠️ MISSING REQUIRED"}`);
  console.log("==========================================\n");

  if (!serverOk || !clientOk) {
    process.exit(1);
  }
}

main();
