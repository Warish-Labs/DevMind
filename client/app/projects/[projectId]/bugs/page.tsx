import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { BugsPageClient } from "@/components/bugs/BugsPageClient";

interface BugsPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Bug Memory & Resolutions · DevMind",
  description:
    "Historical recurring error lookup, deterministic stack fingerprinting, and resolution matching (Screen S-15)",
};

export default async function BugsPage({ params }: BugsPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <BugsPageClient projectId={projectId} />
    </AppShell>
  );
}
