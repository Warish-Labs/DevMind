"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { UsersIcon, MailIcon, PlusIcon, CheckIcon } from "@/components/shell/icons";
import type { WorkspaceMemberResponse, WorkspaceInvitationItem } from "@devmind/common/api";

interface WorkspaceMembersManagerProps {
  workspaceId: string;
  isWorkspaceAdmin?: boolean;
}

export function WorkspaceMembersManager({
  workspaceId,
  isWorkspaceAdmin = true,
}: WorkspaceMembersManagerProps) {
  const [members, setMembers] = useState<WorkspaceMemberResponse[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitationItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Invite modal state
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member" | "viewer">("member");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [inviteSuccessLink, setInviteSuccessLink] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  // Revoke state
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const refreshData = useCallback(async () => {
    try {
      const [membersData, invitesData] = await Promise.all([
        apiClient.listWorkspaceMembers(workspaceId),
        apiClient.listWorkspaceInvitations(workspaceId),
      ]);
      setMembers(membersData);
      setInvitations(invitesData);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load workspace members and invitations";
      setErrorMessage(msg);
    }
  }, [workspaceId]);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiClient.listWorkspaceMembers(workspaceId),
      apiClient.listWorkspaceInvitations(workspaceId),
    ])
      .then(([membersData, invitesData]) => {
        if (active) {
          setMembers(membersData);
          setInvitations(invitesData);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          const msg =
            err instanceof Error ? err.message : "Failed to load workspace members and invitations";
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
  }, [workspaceId]);

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);
    setInviteSuccessLink(null);

    try {
      const res = await apiClient.createWorkspaceInvitation(workspaceId, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      setInviteSuccessLink(res.accept_url);
      setInviteEmail("");
      await refreshData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to issue workspace invitation";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRevokeInvitation = async (invitationId: string) => {
    setRevokingId(invitationId);
    setErrorMessage(null);
    try {
      await apiClient.revokeWorkspaceInvitation(workspaceId, invitationId);
      setInvitations((prev) => prev.filter((i) => i.id !== invitationId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to revoke invitation";
      setErrorMessage(msg);
    } finally {
      setRevokingId(null);
    }
  };

  const handleCopyLink = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2500);
    } catch {
      // Fallback
    }
  };

  const getRoleBadgeVariant = (role: string): "signal" | "ref" | "neutral" => {
    if (role === "owner" || role === "admin") return "signal";
    if (role === "member") return "ref";
    return "neutral";
  };

  return (
    <div className="space-y-8 font-sans">
      {/* Top Banner and Invite Trigger */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold text-[var(--fg-0)] tracking-tight">
              Workspace Members &amp; Access Control
            </h2>
            <Badge variant="signal" size="sm" mono>
              FR-PLT-05
            </Badge>
            <Badge variant="neutral" size="sm" mono>
              ADR-014
            </Badge>
          </div>
          <p className="text-sm text-[var(--fg-2)] mt-1">
            Manage multi-user workspace memberships and issue transactional email invitations via
            Resend.
          </p>
        </div>

        {isWorkspaceAdmin && (
          <Button
            variant="primary"
            onClick={() => {
              setInviteSuccessLink(null);
              setIsInviteDialogOpen(true);
            }}
            className="flex items-center gap-2 shrink-0"
          >
            <PlusIcon size={16} />
            <span>Invite Member</span>
          </Button>
        )}
      </div>

      {errorMessage && (
        <div className="p-3 bg-red-950/30 border border-red-800/40 rounded-card text-xs text-red-300">
          {errorMessage}
        </div>
      )}

      {/* Active Members Table */}
      <Card>
        <CardHeader className="border-b border-[var(--line-1)] pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <UsersIcon size={18} className="text-[var(--accent)]" />
              <CardTitle className="text-base text-[var(--fg-0)]">
                Active Members ({members.length})
              </CardTitle>
            </div>
            <span className="text-xs font-mono text-[var(--fg-3)]">Role-Based Access Control</span>
          </div>
          <CardDescription className="text-xs text-[var(--fg-2)]">
            Users who currently hold access to this workspace and its constituent projects.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          {isLoading ? (
            <div className="py-6 text-center text-xs font-mono text-[var(--fg-3)]">
              Loading workspace members...
            </div>
          ) : members.length === 0 ? (
            <div className="py-6 text-center text-xs text-[var(--fg-2)]">
              No members found in this workspace.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--line-1)] text-[var(--fg-2)] font-mono text-[11px]">
                    <th className="pb-2.5 font-medium">User Identifier</th>
                    <th className="pb-2.5 font-medium">Assigned Role</th>
                    <th className="pb-2.5 font-medium">Joined Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--line-1)]">
                  {members.map((m) => (
                    <tr key={m.user_id} className="hover:bg-[var(--bg-1)]/50 transition-colors">
                      <td className="py-3 font-mono text-[var(--fg-0)] flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-[var(--bg-2)] border border-[var(--line-2)] flex items-center justify-center text-[10px] text-[var(--accent)] font-semibold">
                          {m.role[0].toUpperCase()}
                        </span>
                        <span className="truncate max-w-[240px]">{m.user_id}</span>
                      </td>
                      <td className="py-3">
                        <Badge variant={getRoleBadgeVariant(m.role)} size="sm">
                          {m.role}
                        </Badge>
                      </td>
                      <td className="py-3 font-mono text-[var(--fg-2)]">
                        {new Date(m.created_at).toLocaleDateString(undefined, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending Invitations Table */}
      <Card>
        <CardHeader className="border-b border-[var(--line-1)] pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MailIcon size={18} className="text-[var(--accent)]" />
              <CardTitle className="text-base text-[var(--fg-0)]">
                Pending Invitations ({invitations.length})
              </CardTitle>
            </div>
            <span className="text-xs font-mono text-[var(--fg-3)]">Resend Transactional</span>
          </div>
          <CardDescription className="text-xs text-[var(--fg-2)]">
            Pending email invitations valid for 7 days with SHA-256 token verification.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          {isLoading ? (
            <div className="py-6 text-center text-xs font-mono text-[var(--fg-3)]">
              Loading invitations...
            </div>
          ) : invitations.length === 0 ? (
            <div className="py-6 text-center text-xs text-[var(--fg-2)]">
              No pending invitations. Use &quot;Invite Member&quot; above to invite colleagues.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--line-1)] text-[var(--fg-2)] font-mono text-[11px]">
                    <th className="pb-2.5 font-medium">Invited Email</th>
                    <th className="pb-2.5 font-medium">Role</th>
                    <th className="pb-2.5 font-medium">Expires At</th>
                    <th className="pb-2.5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--line-1)]">
                  {invitations.map((inv) => (
                    <tr key={inv.id} className="hover:bg-[var(--bg-1)]/50 transition-colors">
                      <td className="py-3 font-medium text-[var(--fg-0)]">{inv.email}</td>
                      <td className="py-3">
                        <Badge variant={getRoleBadgeVariant(inv.role)} size="sm">
                          {inv.role}
                        </Badge>
                      </td>
                      <td className="py-3 font-mono text-[var(--fg-2)]">
                        {new Date(inv.expires_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="py-3 text-right">
                        {isWorkspaceAdmin && (
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={revokingId === inv.id}
                            onClick={() => handleRevokeInvitation(inv.id)}
                            className="text-xs px-2 py-1"
                          >
                            {revokingId === inv.id ? "Revoking..." : "Revoke"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Invite Member Dialog */}
      <Dialog
        isOpen={isInviteDialogOpen}
        onClose={() => {
          setIsInviteDialogOpen(false);
          setInviteSuccessLink(null);
        }}
        title="Invite New Workspace Member"
        description="Send a transactional invitation email via Resend with role assignment."
      >
        {inviteSuccessLink ? (
          <div className="space-y-4 py-2">
            <div className="p-3 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-card space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-[var(--accent)] font-medium">
                <CheckIcon size={16} />
                <span>Invitation email dispatched successfully!</span>
              </div>
              <p className="text-xs text-[var(--fg-2)]">
                You can also share this invitation link directly:
              </p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={inviteSuccessLink}
                  className="w-full bg-[var(--bg-0)] border border-[var(--line-2)] rounded px-2.5 py-1.5 text-xs font-mono text-[var(--fg-1)] select-all"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleCopyLink(inviteSuccessLink)}
                  className="shrink-0 text-xs"
                >
                  {copiedLink ? "Copied!" : "Copy"}
                </Button>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                onClick={() => {
                  setIsInviteDialogOpen(false);
                  setInviteSuccessLink(null);
                }}
              >
                Done
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSendInvite} className="space-y-4 py-2">
            <div>
              <label
                htmlFor="invite-email"
                className="block text-xs font-medium text-[var(--fg-1)] mb-1"
              >
                Recipient Email Address
              </label>
              <Input
                id="invite-email"
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@example.com"
                className="w-full text-xs font-mono"
              />
            </div>

            <div>
              <label
                htmlFor="invite-role"
                className="block text-xs font-medium text-[var(--fg-1)] mb-1"
              >
                Workspace Role
              </label>
              <select
                id="invite-role"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as "admin" | "member" | "viewer")}
                className="w-full bg-[var(--bg-1)] border border-[var(--line-2)] rounded px-3 py-2 text-xs text-[var(--fg-0)] focus:border-[var(--accent)] focus:outline-none"
              >
                <option value="member">Member — Read & write projects and jobs</option>
                <option value="admin">Admin — Manage members, settings, and integrations</option>
                <option value="viewer">Viewer — Read-only access to projects and findings</option>
              </select>
            </div>

            <p className="text-[11px] text-[var(--fg-3)]">
              An email invitation with a secure 7-day token link will be dispatched from{" "}
              <code>invitations@warishlabs.in</code>.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="tertiary" type="button" onClick={() => setIsInviteDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                type="submit"
                disabled={isSubmitting || !inviteEmail.trim()}
              >
                {isSubmitting ? "Dispatching..." : "Send Invitation"}
              </Button>
            </div>
          </form>
        )}
      </Dialog>
    </div>
  );
}
