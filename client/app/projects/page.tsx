import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { ProjectIndex } from "@/components/projects/ProjectIndex";

export const metadata: Metadata = {
  title: "Projects · DevMind",
  description: "DevMind Workspace Project Selection and Index (Screen S-03)",
};

export default function ProjectsPage() {
  return (
    <AppShell>
      <ProjectIndex />
    </AppShell>
  );
}
