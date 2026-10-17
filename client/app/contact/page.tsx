"use client";

import React, { useState } from "react";
import Link from "next/link";
import { TurnstileWidget } from "../../components/turnstile/TurnstileWidget";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000");

export default function ContactPage() {
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState("");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    subject: "inquiry",
    message: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.name.trim() || !formData.email.trim() || !formData.message.trim()) {
      setError("Please fill in all required fields.");
      return;
    }

    if (!turnstileToken) {
      setError("Please complete the Cloudflare security verification challenge.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/public/contact`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: formData.name.trim(),
          email: formData.email.trim(),
          subject: formData.subject,
          message: formData.message.trim(),
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

  return (
    <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24">
      {/* Eyebrow Label */}
      <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
        <span className="inline-block w-2 h-2 rounded-full bg-[var(--signal)]" />
        <span>COMMUNICATION CHANNELS</span>
      </div>

      <h1 className="text-4xl sm:text-6xl font-display text-[var(--fg-0)] mb-6 tracking-tight leading-[1.1]">
        Contact the DevMind Team
      </h1>

      <p className="text-lg text-[var(--fg-1)] mb-12 max-w-2xl leading-relaxed">
        Have questions about the Continuous Project Brain, local-first security boundaries, custom
        deployment profiles, or early access? Reach out directly.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start mb-16">
        {/* Direct Channels */}
        <div className="md:col-span-5 space-y-6">
          <div className="p-6 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)] font-mono text-xs space-y-4">
            <div className="text-[var(--signal)] font-semibold uppercase tracking-wider text-[11px]">
              Organization
            </div>
            <div className="text-sm font-display text-[var(--fg-0)]">WarishLabs</div>
            <p className="text-[var(--fg-1)] leading-relaxed">
              Open source engineering &amp; continuous developer tooling.
            </p>
            <div className="pt-3 border-t border-[var(--line-1)] space-y-2 text-[var(--fg-1)]">
              <div>
                <span className="text-[var(--fg-2)]">Web: </span>
                <a
                  href="https://warishlabs.in"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--ref)] hover:underline"
                >
                  warishlabs.in
                </a>
              </div>
              <div>
                <span className="text-[var(--fg-2)]">Extension: </span>
                <a
                  href="https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--ref)] hover:underline"
                >
                  VS Code Marketplace ↗
                </a>
              </div>
            </div>
          </div>

          <div className="p-6 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)] font-mono text-xs space-y-3">
            <div className="text-[var(--ref)] font-semibold uppercase tracking-wider text-[11px]">
              Response SLA
            </div>
            <p className="text-[var(--fg-1)] leading-relaxed">
              We respond to architecture inquiries and early access feedback within 24 business
              hours.
            </p>
          </div>
        </div>

        {/* Contact Form */}
        <div className="md:col-span-7 p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] shadow-xl font-mono text-xs">
          {submitted ? (
            <div className="text-center py-10 space-y-4">
              <div className="w-10 h-10 rounded-full bg-[var(--signal)]/10 text-[var(--signal)] border border-[var(--signal)]/30 mx-auto flex items-center justify-center text-lg">
                ✓
              </div>
              <h3 className="text-lg font-display text-[var(--fg-0)]">Message Received</h3>
              <p className="text-[var(--fg-1)] max-w-sm mx-auto text-xs leading-relaxed font-mono">
                Thank you for reaching out. A confirmation has been registered, and our team will
                get back to you shortly.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSubmitted(false);
                  setFormData({ name: "", email: "", subject: "inquiry", message: "" });
                  setTurnstileToken("");
                }}
                className="mt-4 px-4 py-2 rounded-control border border-[var(--line-2)] text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors cursor-pointer"
              >
                Send Another Message
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="name"
                  className="block text-[var(--fg-1)] mb-1.5 uppercase tracking-wider text-[10px]"
                >
                  Your Name
                </label>
                <input
                  id="name"
                  type="text"
                  required
                  disabled={submitting}
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Warish Ansari"
                  className="w-full px-3 py-2 rounded-control bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] placeholder:text-[var(--fg-2)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] text-xs font-mono disabled:opacity-50"
                />
              </div>

              <div>
                <label
                  htmlFor="email"
                  className="block text-[var(--fg-1)] mb-1.5 uppercase tracking-wider text-[10px]"
                >
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  disabled={submitting}
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="name@domain.com"
                  className="w-full px-3 py-2 rounded-control bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] placeholder:text-[var(--fg-2)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] text-xs font-mono disabled:opacity-50"
                />
              </div>

              <div>
                <label
                  htmlFor="subject"
                  className="block text-[var(--fg-1)] mb-1.5 uppercase tracking-wider text-[10px]"
                >
                  Topic
                </label>
                <select
                  id="subject"
                  disabled={submitting}
                  value={formData.subject}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                  className="w-full px-3 py-2 rounded-control bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] text-xs font-mono disabled:opacity-50"
                >
                  <option value="inquiry">General Architecture Inquiry</option>
                  <option value="early-access">Early Access Registration</option>
                  <option value="security">Security &amp; Threat Boundary Discussion</option>
                  <option value="partnership">Collaboration &amp; Integrations</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="message"
                  className="block text-[var(--fg-1)] mb-1.5 uppercase tracking-wider text-[10px]"
                >
                  Message
                </label>
                <textarea
                  id="message"
                  required
                  disabled={submitting}
                  rows={5}
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  placeholder="How can we help your team with Project Brain capabilities?"
                  className="w-full px-3 py-2 rounded-control bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] placeholder:text-[var(--fg-2)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] text-xs font-mono resize-none disabled:opacity-50"
                />
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

              <button
                type={turnstileToken ? "submit" : "button"}
                disabled={submitting || !turnstileToken}
                onClick={(e) => {
                  if (!turnstileToken) {
                    e.preventDefault();
                    setError(
                      "Please complete the Cloudflare security verification challenge above."
                    );
                  }
                }}
                title={!turnstileToken ? "Please verify the security challenge above" : undefined}
                className="w-full py-3 rounded-control bg-[var(--signal)] text-[var(--bg-0)] font-medium font-mono text-xs hover:opacity-90 transition-opacity cursor-pointer shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {submitting
                  ? "Sending..."
                  : !turnstileToken
                    ? "Verify Security Challenge to Send →"
                    : "Send Message →"}
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Navigation Footer */}
      <div className="flex items-center justify-between pt-8 border-t border-[var(--line-1)] text-sm font-mono">
        <Link href="/" className="text-[var(--ref)] hover:text-[var(--fg-0)] transition-colors">
          ← Back to Home
        </Link>
        <Link
          href="/privacy"
          className="text-[var(--fg-1)] hover:text-[var(--fg-0)] transition-colors"
        >
          Inspect Privacy Policy →
        </Link>
      </div>
    </div>
  );
}
