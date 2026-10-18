import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { UsageDashboard } from "@/components/usage";

interface ProjectUsagePageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Usage & Quotas · DevMind",
  description:
    "Workspace inference token metering, quota thresholds, and connected extension devices (Screen S-12)",
};

export default async function ProjectUsagePage({ params }: ProjectUsagePageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
        <UsageDashboard projectId={projectId} />
      </div>
    </AppShell>
  );
}
