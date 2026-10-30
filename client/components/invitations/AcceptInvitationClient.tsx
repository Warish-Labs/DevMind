"use client";

import React, { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { UsersIcon, CheckIcon } from "@/components/shell/icons";
import type { VerifyInvitationResponse } from "@devmind/common/api";

export function AcceptInvitationClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [isLoading, setIsLoading] = useState(Boolean(token));
  const [invitation, setInvitation] = useState<VerifyInvitationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(
    token ? null : "No invitation token provided in URL."
  );

  const [isAccepting, setIsAccepting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    let active = true;
    apiClient
      .verifyInvitationToken(token)
      .then((preview) => {
        if (active) {
          setInvitation(preview);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          const msg = err instanceof Error ? err.message : "Invalid or expired invitation token.";
          setErrorMessage(msg);
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [token]);

  const handleAccept = async () => {
    if (!token) return;

    setIsAccepting(true);
    setAcceptError(null);

    try {
      await apiClient.acceptInvitation({ token });
      setIsSuccess(true);
      setTimeout(() => {
        router.push("/projects");
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to accept workspace invitation.";
      setAcceptError(msg);
      setIsAccepting(false);
    }
  };

  return (
    <div className="min-h-[75vh] flex flex-col items-center justify-center px-4 py-12 font-sans">
      <div className="w-full max-w-md">
        {/* Brand header */}
        <div className="flex flex-col items-center gap-2 mb-6 text-center">
          <Link
            href="/"
            className="flex items-center gap-2 font-mono text-sm tracking-wider uppercase text-[var(--fg-0)] hover:text-[var(--accent)] transition-colors"
          >
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent)]" aria-hidden="true" />
            <span>DevMind</span>
          </Link>
          <h1 className="text-xl font-semibold text-[var(--fg-0)] tracking-tight">
            Workspace Invitation
          </h1>
          <p className="text-xs text-[var(--fg-2)]">
            Evidence-grounded code intelligence &amp; review checklist platform
          </p>
        </div>

        <Card className="border-[var(--line-1)] bg-[var(--bg-0)] shadow-xl">
          {isLoading ? (
            <CardContent className="py-12 text-center text-xs font-mono text-[var(--fg-2)] space-y-3">
              <div className="w-6 h-6 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto" />
              <p>Verifying invitation token...</p>
            </CardContent>
          ) : errorMessage ? (
            <CardContent className="py-8 space-y-4 text-center">
              <div className="p-3 bg-red-950/30 border border-red-800/40 rounded-card text-xs text-red-300">
                {errorMessage}
              </div>
              <p className="text-xs text-[var(--fg-2)]">
                The invitation link may have expired or already been accepted.
              </p>
              <Button
                variant="secondary"
                className="w-full text-xs"
                onClick={() => router.push("/")}
              >
                Return to Home
              </Button>
            </CardContent>
          ) : isSuccess ? (
            <CardContent className="py-8 space-y-4 text-center">
              <div className="w-10 h-10 rounded-full bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center mx-auto">
                <CheckIcon size={24} />
              </div>
              <h2 className="text-base font-semibold text-[var(--fg-0)]">Invitation Accepted!</h2>
              <p className="text-xs text-[var(--fg-2)]">
                You have successfully joined <strong>{invitation?.workspace_name}</strong>.
                Redirecting you to your projects...
              </p>
            </CardContent>
          ) : invitation ? (
            <>
              <CardHeader className="border-b border-[var(--line-1)] pb-4">
                <div className="flex items-center gap-2">
                  <UsersIcon size={18} className="text-[var(--accent)]" />
                  <CardTitle className="text-base text-[var(--fg-0)]">Join Workspace</CardTitle>
                </div>
                <CardDescription className="text-xs text-[var(--fg-2)]">
                  <strong>{invitation.inviter_name}</strong> has invited you to join their team.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-4 space-y-5">
                <div className="p-3.5 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-card space-y-2 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-[var(--fg-2)]">Workspace</span>
                    <span className="font-semibold text-[var(--fg-0)]">
                      {invitation.workspace_name}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[var(--fg-2)]">Assigned Role</span>
                    <Badge variant="signal" size="sm">
                      {invitation.role}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[var(--fg-2)]">Invitee Email</span>
                    <span className="font-mono text-[var(--fg-1)]">{invitation.email}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[var(--fg-2)]">Expires</span>
                    <span className="font-mono text-[var(--fg-3)]">
                      {new Date(invitation.expires_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {acceptError && (
                  <div className="p-3 bg-red-950/30 border border-red-800/40 rounded-card text-xs text-red-300">
                    {acceptError}
                  </div>
                )}

                <Button
                  variant="primary"
                  className="w-full text-xs font-semibold py-2.5"
                  disabled={isAccepting}
                  onClick={handleAccept}
                >
                  {isAccepting
                    ? "Joining Workspace..."
                    : `Accept & Join ${invitation.workspace_name}`}
                </Button>

                <p className="text-[11px] text-center text-[var(--fg-3)]">
                  By joining, you will have access to codebase repositories and intelligence reports
                  within this workspace.
                </p>
              </CardContent>
            </>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
