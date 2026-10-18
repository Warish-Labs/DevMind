import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { ProjectSettingsClient } from "@/components/settings/ProjectSettingsClient";

interface ProjectSettingsPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Project Settings & Privacy Controls · DevMind",
  description:
    "Synchronization modes, retention windows, privacy policies, and data purge controls (Screen S-10)",
};

export default async function ProjectSettingsPage({ params }: ProjectSettingsPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
        <ProjectSettingsClient projectId={projectId} />
      </div>
    </AppShell>
  );
}
