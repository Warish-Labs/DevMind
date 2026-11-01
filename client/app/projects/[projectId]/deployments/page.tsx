import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { DeploymentPageClient } from "@/components/deployment";

interface DeploymentPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Deployment Diagnosis & Doctor · DevMind",
  description:
    "Automated deployment log sanitization, root cause hypothesis ranking, environment variable checker, and incident ledger (Screen S-18, CAP-07)",
};

export default async function DeploymentPage({ params }: DeploymentPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <DeploymentPageClient projectId={projectId} />
    </AppShell>
  );
}
