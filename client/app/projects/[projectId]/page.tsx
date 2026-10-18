import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { ProjectOverview } from "@/components/overview/ProjectOverview";

interface ProjectOverviewPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const metadata: Metadata = {
  title: "Project Overview · DevMind",
  description:
    "Continuous Project Brain overview answering the five core project questions (Screen S-04)",
};

export default async function ProjectOverviewPage({ params }: ProjectOverviewPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <ProjectOverview projectId={projectId} />
    </AppShell>
  );
}
