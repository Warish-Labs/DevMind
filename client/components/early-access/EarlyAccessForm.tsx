"use client";

import React, { useState } from "react";

export function EarlyAccessForm() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setSubmitted(true);
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
    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-lg">
      <label htmlFor="email-input" className="sr-only">
        Email address
      </label>
      <input
        id="email-input"
        type="email"
        name="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="developer@domain.com"
        className="flex-1 px-4 py-2.5 rounded-control bg-[var(--bg-2)] border border-[var(--line-2)] text-sm text-[var(--fg-0)] placeholder:text-[var(--fg-2)] focus:border-[var(--ref)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
      />
      <button
        type="submit"
        className="px-6 py-2.5 rounded-control text-sm font-medium bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity whitespace-nowrap cursor-pointer"
      >
        Join Waitlist
      </button>
    </form>
  );
}
