import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { JobsPageClient } from "@/components/jobs/JobsPageClient";

interface JobsPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Job Center · DevMind",
  description:
    "Background analysis jobs, agent workflows, and real-time SSE progress (Screen S-09)",
};

export default async function JobsPage({ params }: JobsPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <JobsPageClient projectId={projectId} />
    </AppShell>
  );
}
