import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { WorkspaceMembersManager } from "@/components/workspaces/WorkspaceMembersManager";

interface WorkspaceSettingsPageProps {
  params: Promise<{
    workspaceId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Workspace Members & Invitations · DevMind",
  description:
    "Team members, role-based access control, and Resend email invitations (FR-PLT-05, ADR-014)",
};

export default async function WorkspaceSettingsPage({ params }: WorkspaceSettingsPageProps) {
  const { workspaceId } = await params;

  return (
    <AppShell>
      <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
        <WorkspaceMembersManager workspaceId={workspaceId} />
      </div>
    </AppShell>
  );
}
