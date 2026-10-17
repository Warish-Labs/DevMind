import esbuild from "esbuild";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2);
const isWatch = args.includes("--watch");
const isProduction = args.includes("--production");

// Resolve configuration file based on target build mode
const envFileName = isProduction ? ".env.production" : ".env.local";
const candidateEnvFiles = [
  path.join(__dirname, envFileName),
  path.resolve(envFileName),
  path.resolve("extension", envFileName),
];

let defaultApiBaseUrl = isProduction
  ? "https://api.devmind.warishlabs.in/api/v1"
  : "http://localhost:8000/api/v1";
let defaultFixtureMode = isProduction ? "false" : "false";

for (const envFile of candidateEnvFiles) {
  if (fs.existsSync(envFile)) {
    try {
      const content = fs.readFileSync(envFile, "utf-8");
      for (const line of content.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) continue;
        const [k, ...v] = trimmed.split("=");
        const val = v
          .join("=")
          .replace(/^["']|["']$/g, "")
          .trim();
        if (k === "DEVMIND_API_BASE_URL" && val) defaultApiBaseUrl = val;
        if (k === "DEVMIND_FIXTURE_MODE_DEFAULT" && val) defaultFixtureMode = val;
      }
      break;
    } catch {
      // Ignore reading error
    }
  }
}

// Ambient environment variable overrides with production safety guard
if (process.env.DEVMIND_API_BASE_URL) {
  if (
    isProduction &&
    (process.env.DEVMIND_API_BASE_URL.includes("localhost") ||
      process.env.DEVMIND_API_BASE_URL.includes("127.0.0.1"))
  ) {
    console.warn(
      "[esbuild] WARNING: Ambient DEVMIND_API_BASE_URL points to localhost, but this is a --production build! Enforcing production URL: https://api.devmind.warishlabs.in/api/v1"
    );
    defaultApiBaseUrl = "https://api.devmind.warishlabs.in/api/v1";
  } else {
    defaultApiBaseUrl = process.env.DEVMIND_API_BASE_URL;
  }
}

if (process.env.DEVMIND_FIXTURE_MODE_DEFAULT) {
  if (isProduction && process.env.DEVMIND_FIXTURE_MODE_DEFAULT === "true") {
    console.warn(
      "[esbuild] WARNING: Ambient DEVMIND_FIXTURE_MODE_DEFAULT is true in a --production build! Enforcing false for production."
    );
    defaultFixtureMode = "false";
  } else {
    defaultFixtureMode = process.env.DEVMIND_FIXTURE_MODE_DEFAULT;
  }
}

// In production, enforce standard /api/v1 suffix
if (isProduction) {
  if (defaultApiBaseUrl.endsWith("/")) {
    defaultApiBaseUrl = defaultApiBaseUrl.slice(0, -1);
  }
  if (!defaultApiBaseUrl.endsWith("/api/v1")) {
    defaultApiBaseUrl = `${defaultApiBaseUrl}/api/v1`;
  }
  defaultFixtureMode = "false";
}

async function main() {
  const context = await esbuild.context({
    entryPoints: ["src/extension.ts"],
    bundle: true,
    format: "cjs",
    minify: isProduction,
    sourcemap: !isProduction,
    sourcesContent: false,
    platform: "node",
    outfile: "dist/extension.js",
    external: ["vscode"],
    logLevel: "info",
    define: {
      "process.env.DEVMIND_BUILD_MODE": JSON.stringify(isProduction ? "production" : "development"),
      "process.env.DEVMIND_DEFAULT_API_BASE_URL": JSON.stringify(defaultApiBaseUrl),
      "process.env.DEVMIND_DEFAULT_FIXTURE_MODE": JSON.stringify(defaultFixtureMode),
    },
  });

  if (isWatch) {
    console.log("[esbuild] Watching extension files for changes...");
    await context.watch();
  } else {
    await context.rebuild();
    await context.dispose();
    console.log("[esbuild] Build complete: dist/extension.js");
  }
}

main().catch((err) => {
  console.error("[esbuild] Build failed:", err);
  process.exit(1);
});
