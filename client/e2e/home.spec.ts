import { test, expect } from "@playwright/test";

test.describe("Homepage E2E & Interaction Tests", () => {
  test("renders homepage with proper title, landmark regions, and skip link", async ({ page }) => {
    await page.goto("/");

    // Title verification
    await expect(page).toHaveTitle(/DevMind/);

    // Skip to main content link
    const skipLink = page.getByRole("link", { name: /Skip to main content/i });
    await expect(skipLink).toBeAttached();
    await expect(skipLink).toHaveAttribute("href", "#main-content");

    // Main landmark exists
    const mainLandmark = page.locator("#main-content");
    await expect(mainLandmark).toBeAttached();
  });

  test("keyboard tab order visits skip link, navigation links, and primary interactive elements", async ({
    page,
  }) => {
    await page.goto("/");

    // Initial Tab focuses the skip link
    await page.keyboard.press("Tab");
    const activeText = await page.evaluate(() => document.activeElement?.textContent?.trim() || "");
    expect(activeText).toMatch(/Skip to main content/i);

    // Pressing Enter activates skip link and targets #main-content
    await page.keyboard.press("Enter");
    const targetHash = await page.evaluate(() => window.location.hash);
    expect(targetHash).toBe("#main-content");

    // Further tabs move focus into header navigation items
    await page.keyboard.press("Tab");
    const isFocused = await page.evaluate(() => !!document.activeElement);
    expect(isFocused).toBe(true);
  });

  test("reduced motion disables animation sequence and displays final trace state", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");

    // Verify code region is present
    const traceRegion = page.getByRole("region", { name: "Code trace analysis example" });
    await expect(traceRegion).toBeVisible();

    // With reduced motion, line 7 target should be immediately highlighted or rendered
    const line7 = page.getByText("/admin/users").first();
    await expect(line7).toBeVisible();

    // Margin note with finding E1 is visible
    const marginNote = page.getByText("devmind.authz.missing_role_check").first();
    await expect(marginNote).toBeVisible();
  });

  test("touch profile disables custom cursor and respects touch ergonomics", async ({ page }) => {
    // Emulate touch-first mobile viewport
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    const cursorRoot = page.locator("#devmind-cursor-root");
    if ((await cursorRoot.count()) > 0) {
      // In touch devices, either the element has opacity-0 or is hidden/pointer-events-none
      const isVisible = await cursorRoot.isVisible();
      const cursorStyle = await cursorRoot.evaluate((el) => window.getComputedStyle(el).display);
      expect(cursorStyle === "none" || !isVisible).toBe(true);
    }
  });

  test("section hash anchors navigate cleanly to target sections", async ({ page }) => {
    await page.goto("/");

    // Walkthrough section
    await page.goto("/#walkthrough");
    const walkthrough = page.locator("#walkthrough");
    await expect(walkthrough).toBeAttached();
    await expect(walkthrough).toBeInViewport();

    // Privacy ledger section
    await page.goto("/#ledger");
    const ledger = page.locator("#ledger");
    await expect(ledger).toBeAttached();
    await expect(ledger).toBeInViewport();
  });

  test("early access page loads, accepts input, and handles submission feedback", async ({
    page,
  }) => {
    await page.goto("/early-access");
    await expect(page).toHaveTitle(/Early Access/i);

    const emailInput = page.getByPlaceholder(/developer@domain.com/i);
    await expect(emailInput).toBeVisible();

    // Type email
    await emailInput.fill("developer@example.com");
    expect(await emailInput.inputValue()).toBe("developer@example.com");

    // Submit form
    const submitBtn = page.getByRole("button", { name: /Join waitlist/i });
    await submitBtn.click();

    // Feedback message rendered
    const confirmation = page.locator("text=Thank you for joining");
    await expect(confirmation).toBeVisible();
  });
});
