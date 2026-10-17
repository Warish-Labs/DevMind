"use client";

import React, { useState } from "react";
import { TurnstileWidget } from "../turnstile/TurnstileWidget";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000");

export function EarlyAccessForm() {
  const [email, setEmail] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email) {
      setError("Please enter a valid developer email.");
      return;
    }

    if (!turnstileToken) {
      setError("Please complete the Cloudflare security verification challenge.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/public/waitlist`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          turnstile_token: turnstileToken,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        const detail = errorData?.detail || `Submission failed with status ${res.status}`;
        setError(detail);
        setSubmitting(false);
        return;
      }

      setSubmitted(true);
    } catch {
      setError(
        "Network error: Unable to contact DevMind API server. Please check your connection."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="p-4 rounded-control bg-[var(--signal)]/10 border border-[var(--signal)]/30 font-mono text-sm text-[var(--signal)]"
      >
        ✓ Thank you for joining the early access waitlist. We will notify you when developer preview
        builds are ready.
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
      <div className="flex flex-col sm:flex-row gap-3">
        <label htmlFor="email-input" className="sr-only">
          Email address
        </label>
        <input
          id="email-input"
          type="email"
          name="email"
          required
          disabled={submitting}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="developer@domain.com"
          className="flex-1 px-4 py-2.5 rounded-control bg-[var(--bg-2)] border border-[var(--line-2)] text-sm text-[var(--fg-0)] placeholder:text-[var(--fg-2)] focus:border-[var(--ref)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={submitting || !turnstileToken}
          title={!turnstileToken ? "Please verify the security challenge below" : undefined}
          className="px-6 py-2.5 rounded-control text-sm font-medium bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity whitespace-nowrap cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? "Submitting..." : !turnstileToken ? "Verify to Join" : "Join Waitlist"}
        </button>
      </div>

      {/* Cloudflare Turnstile challenge */}
      <TurnstileWidget
        onVerify={(token) => {
          setTurnstileToken(token);
          setError(null);
        }}
        onExpire={() => setTurnstileToken("")}
        onError={() => setError("Turnstile verification error. Please retry.")}
      />

      {error && (
        <div
          role="alert"
          className="p-3 rounded-control bg-red-950/40 border border-red-500/30 text-xs font-mono text-red-400"
        >
          {error}
        </div>
      )}
    </form>
  );
}
