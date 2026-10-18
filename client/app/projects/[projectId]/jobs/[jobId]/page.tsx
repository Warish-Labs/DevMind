import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { JobDetailPageClient } from "@/components/jobs/JobDetailPageClient";

interface JobDetailPageProps {
  params: Promise<{
    projectId: string;
    jobId: string;
  }>;
}

export const metadata: Metadata = {
  title: "Job Details · DevMind",
  description:
    "Live milestone events, SSE streaming progress, and human approval prompts (Screen S-09)",
};

export default async function JobDetailPage({ params }: JobDetailPageProps) {
  const { projectId, jobId } = await params;

  return (
    <AppShell>
      <JobDetailPageClient projectId={projectId} jobId={jobId} />
    </AppShell>
  );
}
