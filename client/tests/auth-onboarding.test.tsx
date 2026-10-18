import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { devmindClerkAppearance } from "../components/auth/clerk-theme";
import SignInPage from "../app/sign-in/[[...sign-in]]/page";
import SignUpPage from "../app/sign-up/[[...sign-up]]/page";
import OnboardingPage from "../app/onboarding/page";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// Mock @clerk/nextjs components
vi.mock("@clerk/nextjs", () => ({
  SignIn: () => <div data-testid="mock-clerk-signin">Clerk SignIn Component</div>,
  SignUp: () => <div data-testid="mock-clerk-signup">Clerk SignUp Component</div>,
  ClerkProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe("Authentication and Onboarding (Screen S-02, docs/08 §11, M8-02)", () => {
  describe("Clerk Theme Integration (clerk-theme.ts)", () => {
    it("defines variables matching DevMind design tokens strictly", () => {
      const vars = devmindClerkAppearance.variables;
      expect(vars.colorPrimary).toBe("var(--signal)");
      expect(vars.colorBackground).toBe("var(--bg-1)");
      expect(vars.colorText).toBe("var(--fg-0)");
      expect(vars.colorInputBackground).toBe("var(--bg-2)");
      expect(vars.borderRadius).toBe("var(--radius-control)");
    });
  });

  describe("Sign In Page (/sign-in)", () => {
    it("renders branding and fallback developer sign-in when Clerk key is unconfigured", () => {
      const html = renderToString(<SignInPage />);
      expect(html).toContain("DevMind");
      expect(html).toContain("Sign in to your Project Brain");
      expect(html).toContain("Developer Access");
      expect(html).toContain('id="email"');
      expect(html).toContain('id="password"');
      expect(html).toContain("Continue to Onboarding");
      expect(html).toContain('href="/sign-up"');
    });
  });

  describe("Sign Up Page (/sign-up)", () => {
    it("renders branding and registration form with name, email, and password inputs", () => {
      const html = renderToString(<SignUpPage />);
      expect(html).toContain("DevMind");
      expect(html).toContain("Create your DevMind account");
      expect(html).toContain("Developer Registration");
      expect(html).toContain('id="name"');
      expect(html).toContain('id="email"');
      expect(html).toContain('id="password"');
      expect(html).toContain("Create Account &amp; Onboard");
      expect(html).toContain('href="/sign-in"');
    });
  });

  describe("Onboarding Page (/onboarding)", () => {
    it("renders 3-step progress rail matching Screen S-02", () => {
      const html = renderToString(<OnboardingPage />);
      expect(html).toContain("STEP 1 OF 3 · S-02 ONBOARDING");
      expect(html).toContain("Workspace");
      expect(html).toContain("Project Source");
      expect(html).toContain("Sync &amp; Consent");
      expect(html).toContain("Connect your codebase to DevMind");
    });

    it("renders Step 1 Workspace form with tenant isolation disclosure", () => {
      const html = renderToString(<OnboardingPage />);
      expect(html).toContain("1. Create or Choose Workspace");
      expect(html).toContain('id="workspaceName"');
      expect(html).toContain("Tenant Guarantee");
      expect(html).toContain("Continue to Project Source");
    });
  });
});
