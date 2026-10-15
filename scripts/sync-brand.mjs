#!/usr/bin/env node

/**
 * scripts/sync-brand.mjs
 * Syncs brand assets (tokens, favicons, logos, extension media) into client and extension.
 *
 * Usage:
 *   node scripts/sync-brand.mjs          # Syncs files
 *   node scripts/sync-brand.mjs --check  # Verifies files are in sync without writing
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const REPO_ROOT = process.cwd();
const CHECK_MODE = process.argv.includes("--check");

const SYNC_MAPPINGS = [
  // Tokens
  {
    src: "brand/tokens/devmind-tokens.css",
    dest: "client/app/tokens.css",
  },
  // Extension media
  {
    src: "brand/vscode/icon.png",
    dest: "extension/media/icon.png",
  },
  {
    src: "brand/vscode/icon@2x.png",
    dest: "extension/media/icon@2x.png",
  },
  {
    src: "brand/vscode/activitybar-icon.svg",
    dest: "extension/media/activitybar-icon.svg",
  },
  // Favicons and client public icons
  {
    src: "brand/favicon/favicon.ico",
    dest: "client/public/favicon.ico",
  },
  {
    src: "brand/favicon/favicon.svg",
    dest: "client/public/favicon.svg",
  },
  {
    src: "brand/favicon/apple-touch-icon.png",
    dest: "client/public/apple-touch-icon.png",
  },
  {
    src: "brand/favicon/site.webmanifest",
    dest: "client/public/site.webmanifest",
  },
  {
    src: "brand/social/og-image-1200x630.png",
    dest: "client/public/og-image-1200x630.png",
  },
];

function main() {
  let hasDrift = false;
  let syncedCount = 0;

  console.log(`\n========================================`);
  console.log(`DevMind Brand Assets Sync ${CHECK_MODE ? "(Check Mode)" : ""}`);
  console.log(`========================================\n`);

  for (const { src, dest } of SYNC_MAPPINGS) {
    const srcPath = path.resolve(REPO_ROOT, src);
    const destPath = path.resolve(REPO_ROOT, dest);

    if (!fs.existsSync(srcPath)) {
      console.warn(`[WARN] Source file missing: ${src}`);
      continue;
    }

    const srcContent = fs.readFileSync(srcPath);

    if (fs.existsSync(destPath)) {
      const destContent = fs.readFileSync(destPath);
      if (srcContent.equals(destContent)) {
        if (!CHECK_MODE) {
          console.log(`  ✓ Up to date: ${dest}`);
        }
        continue;
      }
    }

    if (CHECK_MODE) {
      console.error(`  ✗ Drift detected: ${dest} differs from ${src}`);
      hasDrift = true;
    } else {
      fs.mkdirSync(path.dirname(destPath), { recursive: true });
      fs.writeFileSync(destPath, srcContent);
      console.log(`  ➔ Synced: ${src} -> ${dest}`);
      syncedCount++;
    }
  }

  if (CHECK_MODE) {
    if (hasDrift) {
      console.error(
        `\n✗ Brand assets check failed: drift detected. Run "pnpm brand:sync" to update.\n`
      );
      process.exit(1);
    } else {
      console.log(`\n✓ All brand assets are in sync.\n`);
      process.exit(0);
    }
  } else {
    console.log(`\n✓ Brand assets sync complete (${syncedCount} file(s) updated).\n`);
    process.exit(0);
  }
}

main();
