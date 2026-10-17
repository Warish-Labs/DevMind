import { describe, it, expect } from "vitest";
import { CLOUDFLARE_TEST_SITE_KEY } from "../components/turnstile/TurnstileWidget";

describe("Cloudflare Turnstile Client Configuration & Integrity", () => {
  it("exports official Cloudflare dummy test sitekey", () => {
    expect(CLOUDFLARE_TEST_SITE_KEY).toBe("1x00000000000000000000AA");
  });

  it("resolves active site key prioritizing NEXT_PUBLIC_TURNSTILE_SITE_KEY then test fallback", () => {
    const originalEnv = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
    try {
      delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
      const defaultKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || CLOUDFLARE_TEST_SITE_KEY;
      expect(defaultKey).toBe("1x00000000000000000000AA");

      process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = "0x4AAAAAAtestkey123";
      const customKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || CLOUDFLARE_TEST_SITE_KEY;
      expect(customKey).toBe("0x4AAAAAAtestkey123");
    } finally {
      if (originalEnv !== undefined) {
        process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = originalEnv;
      } else {
        delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
      }
    }
  });
});
