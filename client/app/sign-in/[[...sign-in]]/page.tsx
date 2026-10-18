"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SignIn } from "@clerk/nextjs";
import { devmindClerkAppearance } from "../../../components/auth/clerk-theme";
import {
  Button,
  Input,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "../../../components/ui";

export default function SignInPage() {
  const router = useRouter();
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const isClerkConfigured = Boolean(publishableKey && !publishableKey.includes("REPLACE_ME"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDevSignIn = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError("Email address is required.");
      return;
    }
    setIsLoading(true);
    setTimeout(() => {
      router.push("/onboarding");
    }, 400);
  };

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md flex flex-col items-center gap-6">
        {/* Brand header */}
        <div className="flex flex-col items-center gap-2 text-center">
          <Link
            href="/"
            className="flex items-center gap-2 font-mono text-sm tracking-wider uppercase text-[var(--fg-0)] hover:text-[var(--signal)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)]"
          >
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--signal)]" aria-hidden="true" />
            <span>DevMind</span>
          </Link>
          <h1 className="text-2xl font-semibold text-[var(--fg-0)] tracking-tight">
            Sign in to your Project Brain
          </h1>
          <p className="text-sm text-[var(--fg-2)] max-w-xs">
            Continuous mental model, deterministic findings, and agentic code intelligence.
          </p>
        </div>

        {/* Authentication Card */}
        {isClerkConfigured ? (
          <div className="w-full flex justify-center" data-testid="clerk-signin-wrapper">
            <SignIn
              path="/sign-in"
              routing="path"
              signUpUrl="/sign-up"
              fallbackRedirectUrl="/onboarding"
              appearance={devmindClerkAppearance}
            />
          </div>
        ) : (
          <Card variant="elevated" className="w-full" data-testid="dev-signin-card">
            <CardHeader>
              <CardTitle>Developer Access</CardTitle>
              <CardDescription>
                Clerk publishable key not detected in local environment. Use developer sign-in to
                proceed to onboarding.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleDevSignIn} className="flex flex-col gap-4">
                <Input
                  id="email"
                  type="email"
                  label="Email address"
                  placeholder="engineer@example.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError(null);
                  }}
                  error={error || undefined}
                  required
                />
                <Input
                  id="password"
                  type="password"
                  label="Password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <Button
                  type="submit"
                  variant="primary"
                  size="default"
                  isLoading={isLoading}
                  className="w-full mt-2"
                >
                  Continue to Onboarding
                </Button>

                <div className="flex items-center justify-between text-xs text-[var(--fg-2)] mt-2 pt-4 border-t border-[var(--line-1)]">
                  <span>Don&apos;t have an account?</span>
                  <Link
                    href="/sign-up"
                    className="text-[var(--signal)] hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ref)]"
                  >
                    Sign up
                  </Link>
                </div>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
