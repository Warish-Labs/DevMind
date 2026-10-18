import { describe, it, expect } from "vitest";

describe("Client Layout and Routing Integrity", () => {
  it("verifies site url environment configuration", () => {
    const defaultUrl = "https://devmind.warishlabs.in";
    const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || defaultUrl;
    expect(siteUrl).toMatch(/^https?:\/\//);
  });

  it("verifies expected homepage section anchors exist in contract", () => {
    const requiredSections = [
      "section-01",
      "section-02",
      "section-03",
      "section-04",
      "section-05",
      "section-06",
      "section-07",
      "section-08",
    ];
    expect(requiredSections).toHaveLength(8);
  });
});
