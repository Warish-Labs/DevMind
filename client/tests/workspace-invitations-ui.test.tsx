import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { WorkspaceMembersManager } from "../components/workspaces/WorkspaceMembersManager";
import { AcceptInvitationClient } from "../components/invitations/AcceptInvitationClient";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
  useSearchParams: () => ({
    get: (key: string) => (key === "token" ? "sample-valid-token-xyz" : null),
  }),
}));

// Mock @/lib/api
vi.mock("@/lib/api", () => ({
  apiClient: {
    listWorkspaceMembers: vi.fn().mockResolvedValue([
      {
        workspace_id: "ws-1",
        user_id: "user-1",
        role: "owner",
        created_at: "2026-10-01T00:00:00Z",
      },
      {
        workspace_id: "ws-1",
        user_id: "user-2",
        role: "member",
        created_at: "2026-10-15T00:00:00Z",
      },
    ]),
    listWorkspaceInvitations: vi.fn().mockResolvedValue([
      {
        id: "inv-1",
        workspace_id: "ws-1",
        email: "alice@example.com",
        role: "admin",
        expires_at: "2026-11-05T00:00:00Z",
        created_at: "2026-10-29T00:00:00Z",
      },
    ]),
    createWorkspaceInvitation: vi.fn().mockResolvedValue({
      invitation: {
        id: "inv-2",
        workspace_id: "ws-1",
        email: "bob@example.com",
        role: "member",
        expires_at: "2026-11-06T00:00:00Z",
        created_at: "2026-10-30T00:00:00Z",
      },
      accept_url: "https://devmind.warishlabs.in/invitations/accept?token=bob-token",
    }),
    revokeWorkspaceInvitation: vi.fn().mockResolvedValue(undefined),
    verifyInvitationToken: vi.fn().mockResolvedValue({
      invitation_id: "inv-1",
      workspace_id: "ws-1",
      workspace_name: "Acme Platform Engineering",
      email: "joiner@example.com",
      role: "member",
      inviter_name: "Sarah Lead",
      expires_at: "2026-11-05T00:00:00Z",
    }),
    acceptInvitation: vi.fn().mockResolvedValue({
      status: "accepted",
      workspace_id: "ws-1",
      workspace_name: "Acme Platform Engineering",
      role: "member",
      user_id: "user-new",
    }),
  },
}));

describe("M11-07: Workspace Invitations & Access Control UI (FR-PLT-05, ADR-014)", () => {
  describe("WorkspaceMembersManager Component", () => {
    it("renders workspace member manager headers, active members, and pending invitations sections", () => {
      const html = renderToString(
        <WorkspaceMembersManager workspaceId="ws-1" isWorkspaceAdmin={true} />
      );

      // Section titles and badges
      expect(html).toContain("Workspace Members &amp; Access Control");
      expect(html).toContain("FR-PLT-05");
      expect(html).toContain("ADR-014");
      expect(html).toContain("Active Members");
      expect(html).toContain("Pending Invitations");
      expect(html).toContain("Invite Member");
    });

    it("displays loading state initially during SSR", () => {
      const html = renderToString(
        <WorkspaceMembersManager workspaceId="ws-1" isWorkspaceAdmin={false} />
      );

      expect(html).toContain("Loading workspace members...");
      expect(html).toContain("Loading invitations...");
    });
  });

  describe("AcceptInvitationClient Component", () => {
    it("renders the accept invitation layout with brand title and loading indicator", () => {
      const html = renderToString(<AcceptInvitationClient />);

      expect(html).toContain("DevMind");
      expect(html).toContain("Workspace Invitation");
      expect(html).toContain("Verifying invitation token...");
    });
  });
});
