import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";

const systemChrome = "/usr/bin/google-chrome";
const hasSystemChrome = fs.existsSync(systemChrome);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000",
    trace: "on-first-retry",
    launchOptions: {
      executablePath: hasSystemChrome ? systemChrome : undefined,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
      ],
    },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
  webServer: {
    command: "pnpm exec next start -p 3000",
    cwd: __dirname,
    port: 3000,
    reuseExistingServer: true,
    timeout: 60000,
  },
});
