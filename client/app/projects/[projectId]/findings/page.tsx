import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { FindingsPageClient } from "@/components/findings/FindingsPageClient";

interface FindingsPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Findings · DevMind",
  description:
    "Dense findings table with status, severity, category, and evidence level filters (Screen S-07)",
};

export default async function FindingsPage({ params }: FindingsPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <FindingsPageClient projectId={projectId} />
    </AppShell>
  );
}
