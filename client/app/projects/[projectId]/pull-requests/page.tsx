import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { PullRequestsPageClient } from "@/components/pull-requests/PullRequestsPageClient";

interface PullRequestsPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Pull Requests & Impact · DevMind",
  description:
    "Mirrored GitHub pull requests, change-impact blast radius, and ReviewBuddy automated triage (Screen S-14)",
};

export default async function PullRequestsPage({ params }: PullRequestsPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <PullRequestsPageClient projectId={projectId} />
    </AppShell>
  );
}
