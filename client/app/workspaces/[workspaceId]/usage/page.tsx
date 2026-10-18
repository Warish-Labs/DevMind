import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { UsageDashboard } from "@/components/usage";

interface WorkspaceUsagePageProps {
  params: Promise<{
    workspaceId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Workspace Usage & Quotas · DevMind",
  description:
    "Workspace inference token metering, quota thresholds, and connected extension devices (Screen S-12)",
};

export default async function WorkspaceUsagePage({ params }: WorkspaceUsagePageProps) {
  const { workspaceId } = await params;

  return (
    <AppShell>
      <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
        <UsageDashboard workspaceId={workspaceId} />
      </div>
    </AppShell>
  );
}
