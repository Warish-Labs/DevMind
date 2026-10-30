import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { PullRequestDetailClient } from "@/components/pull-requests/PullRequestDetailClient";

interface PullRequestDetailPageProps {
  params: Promise<{
    projectId: string;
    prId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "PR Intelligence & Impact · DevMind",
  description:
    "PRAgent change-impact graph, multi-perspective summary, and ReviewBuddy checklist triage",
};

export default async function PullRequestDetailPage({ params }: PullRequestDetailPageProps) {
  const { projectId, prId } = await params;

  return (
    <AppShell>
      <PullRequestDetailClient projectId={projectId} prId={prId} />
    </AppShell>
  );
}
