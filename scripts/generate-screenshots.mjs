#!/usr/bin/env node

/**
 * scripts/generate-screenshots.mjs
 * Captures the 8 deterministic screenshots required by Slice B8 (S1-19).
 * Output: docs/assets/screenshots/home-*.png
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { chromium } from "../client/node_modules/@playwright/test/index.mjs";

const ROOT = process.cwd();
const OUTPUT_DIR = path.join(ROOT, "docs/assets/screenshots");
const PORT = 3000;
const BASE_URL = `http://127.0.0.1:${PORT}`;

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

async function isServerRunning() {
  try {
    const res = await globalThis.fetch(BASE_URL);
    return res.status === 200;
  } catch {
    return false;
  }
}

async function startServer() {
  console.log("  ⏳ Starting Next.js production server for screenshots...");
  const server = spawn("pnpm", ["--filter", "client", "start", "-p", String(PORT)], {
    cwd: ROOT,
    env: {
      ...process.env,
      PATH: `/home/md-warish-ansari/.local/share/pnpm/bin:${process.env.PATH}`,
    },
    stdio: "ignore",
  });

  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    if (await isServerRunning()) {
      console.log("  ✓ Next.js server ready on port 3000.");
      return server;
    }
  }
  throw new Error("Failed to start Next.js production server within 30s.");
}

async function main() {
  console.log("\n==========================================================");
  console.log("DevMind Homepage Screenshot Generator (S1-19)");
  console.log("Destination: docs/assets/screenshots/");
  console.log("==========================================================\n");

  let serverProcess = null;
  const running = await isServerRunning();
  if (!running) {
    serverProcess = await startServer();
  }

  const browser = await chromium.launch({
    executablePath: "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--disable-gpu", "--headless=new"],
  });

  try {
    // 1. Desktop Hero (1440 x 900)
    console.log("  📸 1/8 Capturing home-hero-desktop.png (1440x900)...");
    const pageDesktop = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    await pageDesktop.goto(BASE_URL, { waitUntil: "networkidle" });
    await pageDesktop.waitForTimeout(500);
    await pageDesktop.screenshot({
      path: path.join(OUTPUT_DIR, "home-hero-desktop.png"),
      clip: { x: 0, y: 0, width: 1440, height: 900 },
    });

    // 2. Mid-Sequence Hero Trace (1440 x 900)
    console.log("  📸 2/8 Capturing home-hero-mid-sequence.png...");
    // Click step 3 button or wait for line 7 to be active
    const step3Btn = pageDesktop.locator("button:has-text('3. Security Check')");
    if ((await step3Btn.count()) > 0) {
      await step3Btn.click();
      await pageDesktop.waitForTimeout(400);
    }
    const heroSection = pageDesktop.locator("#section-01");
    if ((await heroSection.count()) > 0) {
      await heroSection.screenshot({
        path: path.join(OUTPUT_DIR, "home-hero-mid-sequence.png"),
      });
    } else {
      await pageDesktop.screenshot({
        path: path.join(OUTPUT_DIR, "home-hero-mid-sequence.png"),
        clip: { x: 0, y: 0, width: 1440, height: 900 },
      });
    }

    // 3. Project Brain Selected Stratum (Section 03)
    console.log("  📸 3/8 Capturing home-brain-selected.png...");
    const brainSection = pageDesktop.locator("#section-03");
    await brainSection.scrollIntoViewIfNeeded();
    // Select Stratum 3: Security Policy & Guard Resolution
    const stratum3Btn = pageDesktop.locator("button:has-text('Security Policy')");
    if ((await stratum3Btn.count()) > 0) {
      await stratum3Btn.click();
      await pageDesktop.waitForTimeout(300);
    }
    await brainSection.screenshot({
      path: path.join(OUTPUT_DIR, "home-brain-selected.png"),
    });

    // 4. 14-Step Walkthrough (Section 05)
    console.log("  📸 4/8 Capturing home-walkthrough-step.png...");
    const walkthroughSection = pageDesktop.locator("#section-05");
    await walkthroughSection.scrollIntoViewIfNeeded();
    // Click step 3 in walkthrough
    const walkStep3 = walkthroughSection.locator("button:has-text('AuthCheck')").first();
    if ((await walkStep3.count()) > 0) {
      await walkStep3.click();
      await pageDesktop.waitForTimeout(300);
    }
    await walkthroughSection.screenshot({
      path: path.join(OUTPUT_DIR, "home-walkthrough-step.png"),
    });

    // 5. Privacy Ledger (Section 07)
    console.log("  📸 5/8 Capturing home-privacy-ledger.png...");
    const ledgerSection = pageDesktop.locator("#section-07");
    await ledgerSection.scrollIntoViewIfNeeded();
    await pageDesktop.waitForTimeout(200);
    await ledgerSection.screenshot({
      path: path.join(OUTPUT_DIR, "home-privacy-ledger.png"),
    });

    // 6. Conversion CTA with Preferences (Section 08)
    console.log("  📸 6/8 Capturing home-cursor-cta.png...");
    const ctaSection = pageDesktop.locator("#section-08");
    await ctaSection.scrollIntoViewIfNeeded();
    await pageDesktop.waitForTimeout(200);
    await ctaSection.screenshot({
      path: path.join(OUTPUT_DIR, "home-cursor-cta.png"),
    });
    await pageDesktop.close();

    // 7. Tablet Viewport (768 x 1024)
    console.log("  📸 7/8 Capturing home-tablet.png (768x1024)...");
    const pageTablet = await browser.newPage({
      viewport: { width: 768, height: 1024 },
      deviceScaleFactor: 1,
    });
    await pageTablet.goto(BASE_URL, { waitUntil: "networkidle" });
    await pageTablet.waitForTimeout(400);
    await pageTablet.screenshot({
      path: path.join(OUTPUT_DIR, "home-tablet.png"),
      clip: { x: 0, y: 0, width: 768, height: 1024 },
    });
    await pageTablet.close();

    // 8. Mobile Viewport (390 x 844)
    console.log("  📸 8/8 Capturing home-mobile.png (390x844)...");
    const pageMobile = await browser.newPage({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 1,
      isMobile: true,
      hasTouch: true,
    });
    await pageMobile.goto(BASE_URL, { waitUntil: "networkidle" });
    await pageMobile.waitForTimeout(400);
    await pageMobile.screenshot({
      path: path.join(OUTPUT_DIR, "home-mobile.png"),
      clip: { x: 0, y: 0, width: 390, height: 844 },
    });
    await pageMobile.close();

    console.log("\n✓ All 8 screenshots captured successfully in docs/assets/screenshots/!");
  } finally {
    await browser.close();
    if (serverProcess) {
      serverProcess.kill();
    }
  }
}

main().catch((err) => {
  console.error("Screenshot generation failed:", err);
  process.exit(1);
});
