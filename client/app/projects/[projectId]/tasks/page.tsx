import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { MentorPageClient } from "@/components/mentor";

interface MentorTasksPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Project Mentor & Health · DevMind",
  description:
    "Task backlog, topological dependency DAG visualizer, AI next-task guidance, and multidimensional release-readiness health scorecards (Screen S-17)",
};

export default async function MentorTasksPage({ params }: MentorTasksPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <MentorPageClient projectId={projectId} />
    </AppShell>
  );
}
