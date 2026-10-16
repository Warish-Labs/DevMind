import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("Automated Accessibility Audit (axe-core)", () => {
  test("homepage has no serious or critical accessibility violations", async ({ page }) => {
    await page.goto("/");

    // Wait for the page to stabilize
    await page.waitForLoadState("domcontentloaded");

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    // Filter serious and critical issues
    const severeViolations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );

    if (severeViolations.length > 0) {
      console.error(
        "Severe a11y violations found on /:",
        JSON.stringify(severeViolations, null, 2)
      );
    }

    expect(severeViolations).toEqual([]);
  });

  test("early access page has no serious or critical accessibility violations", async ({
    page,
  }) => {
    await page.goto("/early-access");

    await page.waitForLoadState("domcontentloaded");

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const severeViolations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );

    if (severeViolations.length > 0) {
      console.error(
        "Severe a11y violations found on /early-access:",
        JSON.stringify(severeViolations, null, 2)
      );
    }

    expect(severeViolations).toEqual([]);
  });
});
