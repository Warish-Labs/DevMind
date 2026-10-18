import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { FindingDetailPageClient } from "@/components/findings/FindingDetailPageClient";

interface FindingDetailPageProps {
  params: Promise<{
    projectId: string;
    findingId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Finding Detail · DevMind",
  description:
    "Evidence-first finding hierarchy with code excerpt, machine-checkable evidence, and suggested remediation (Screen S-08)",
};

export default async function FindingDetailPage({ params }: FindingDetailPageProps) {
  const { projectId, findingId } = await params;

  return (
    <AppShell>
      <FindingDetailPageClient projectId={projectId} findingId={findingId} />
    </AppShell>
  );
}
