"use client";

/**
 * /settings/extension-token
 *
 * Displays the user's DevMind extension token so they can paste it into
 * the VS Code extension's "DevMind: Sign In" command.
 *
 * The token is fetched from POST /api/v1/ext/token (Clerk bearer → DevMind ext token).
 * A one-click "Open in VS Code" deep-link encodes projectId + token so the extension
 * can self-configure without manual copy-paste.
 */

import React, { Suspense, useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../../components/ui";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://api.devmind.warishlabs.in";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  registration_id: string;
  expires_in: number;
}

function ExtensionTokenContent() {
  const { getToken } = useAuth();
  const searchParams = useSearchParams();
  const projectId = searchParams?.get("projectId") || searchParams?.get("project");

  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function fetchToken() {
      try {
        const clerkToken = await getToken();
        if (!clerkToken) throw new Error("Not authenticated");
        const res = await fetch(`${API_BASE}/api/v1/ext/token`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${clerkToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ device_name: "web-portal" }),
        });
        if (!res.ok) {
          const body = await res.text();
          throw new Error(`Server error ${res.status}: ${body}`);
        }
        const data: TokenResponse = await res.json();
        if (!cancelled) setToken(data.access_token);
      } catch (err) {
        if (!cancelled) setError(String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchToken();
    return () => {
      cancelled = true;
    };
  }, [getToken]);

  const handleCopy = async () => {
    if (!token) return;
    await navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Build a vscode:// deep-link that opens the extension and auto-signs-in
  const queryParams = new URLSearchParams();
  if (token) queryParams.set("token", token);
  if (projectId) queryParams.set("projectId", projectId.trim());
  const queryString = queryParams.toString();

  const vsCodeDeepLink = token ? `vscode://WarishLabs.devmind-vscode/connect?${queryString}` : null;

  const cursorDeepLink = token ? `cursor://WarishLabs.devmind-vscode/connect?${queryString}` : null;

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg flex flex-col gap-6">
        {/* Back link */}
        <Link
          href={projectId ? `/projects/${projectId}` : "/projects"}
          className="text-xs font-mono text-[var(--fg-2)] hover:text-[var(--fg-0)] transition-colors"
        >
          ← Back to {projectId ? "Project Overview" : "Dashboard"}
        </Link>

        <Card variant="elevated">
          <CardHeader>
            <CardTitle>🔑 Extension Connection &amp; Token</CardTitle>
            <CardDescription>
              Connect your local editor companion to the DevMind Project Brain. Click
              <strong> Open in VS Code</strong> to authenticate and link automatically, or copy the
              token below for manual entry.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {projectId && (
              <div className="p-2.5 rounded-control bg-[var(--bg-2)] border border-[var(--line-1)] flex items-center justify-between font-mono text-xs">
                <span className="text-[var(--fg-2)]">Target Project:</span>
                <span className="text-[var(--signal)] font-bold truncate max-w-[240px]">
                  {projectId}
                </span>
              </div>
            )}

            {loading && (
              <div className="text-sm text-[var(--fg-2)] font-mono animate-pulse">
                Generating secure scoped extension token…
              </div>
            )}
            {error && (
              <div className="p-3 rounded-control border border-[var(--danger)] bg-[var(--bg-2)] text-sm text-[var(--danger)] font-mono">
                {error}
              </div>
            )}
            {token && !loading && (
              <>
                {/* Token display */}
                <div className="flex items-center gap-2">
                  <div className="flex-1 font-mono text-xs bg-[var(--bg-2)] border border-[var(--line-2)] rounded-control px-3 py-2 truncate text-[var(--fg-0)] select-all">
                    {token}
                  </div>
                  <button
                    onClick={handleCopy}
                    className="shrink-0 px-3 py-2 rounded-control text-xs font-mono font-medium bg-[var(--bg-1)] border border-[var(--line-2)] text-[var(--fg-1)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-0)] transition-colors cursor-pointer"
                  >
                    {copied ? "✓ Copied" : "Copy"}
                  </button>
                </div>

                {/* One-click deep links */}
                <div className="flex flex-col sm:flex-row gap-2 pt-1">
                  {vsCodeDeepLink && (
                    <a
                      href={vsCodeDeepLink}
                      className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-control text-xs sm:text-sm font-mono font-semibold bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity text-center cursor-pointer"
                    >
                      <span>⚡ Open in VS Code</span>
                    </a>
                  )}
                  {cursorDeepLink && (
                    <a
                      href={cursorDeepLink}
                      className="inline-flex items-center justify-center gap-2 px-3 py-2.5 rounded-control text-xs sm:text-sm font-mono font-medium border border-[var(--line-2)] bg-[var(--bg-1)] text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors text-center cursor-pointer"
                    >
                      <span>Open in Cursor</span>
                    </a>
                  )}
                </div>

                {/* Instructions */}
                <div className="p-3 rounded-control border border-[var(--line-1)] bg-[var(--bg-2)] text-xs text-[var(--fg-2)] leading-relaxed space-y-1 font-mono">
                  <p className="font-semibold text-[var(--fg-1)]">Manual steps (if required):</p>
                  <ol className="list-decimal list-inside space-y-1">
                    <li>Open VS Code with your project folder.</li>
                    <li>
                      Press{" "}
                      <kbd className="font-mono text-[10px] bg-[var(--bg-1)] px-1 py-0.5 rounded">
                        Ctrl+Shift+P
                      </kbd>{" "}
                      → <code>DevMind: Sign In</code>
                    </li>
                    <li>Paste the token above and press Enter.</li>
                    <li>
                      Run <code>DevMind: Link Workspace to Project</code> and paste your Project ID:
                      <code className="text-[var(--signal)] ml-1">
                        {projectId || "your-project-id"}
                      </code>
                    </li>
                    <li>
                      Run <code>DevMind: Trigger Sync Now</code> to sync local AST &amp; findings.
                    </li>
                  </ol>
                </div>

                <p className="text-[10px] font-mono text-[var(--fg-2)]">
                  Token is scoped to your account and stored encrypted in VS Code SecretStorage.
                  Revoke anytime from workspace settings.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function ExtensionTokenPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[80vh] flex items-center justify-center font-mono text-xs text-[var(--fg-2)]">
          Loading connection portal…
        </div>
      }
    >
      <ExtensionTokenContent />
    </Suspense>
  );
}
