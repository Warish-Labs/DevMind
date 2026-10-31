import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { LivingDocsPageClient } from "@/components/living-docs/LivingDocsPageClient";

interface LivingDocsPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Living Documentation & Drift · DevMind",
  description:
    "Tracked Markdown documentation records, DocsAlive route drift detection, and human approval gates (Screen S-16)",
};

export default async function LivingDocsPage({ params }: LivingDocsPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <LivingDocsPageClient projectId={projectId} />
    </AppShell>
  );
}
