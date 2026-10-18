import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { BrainExplorer } from "@/components/brain/BrainExplorer";

interface BrainPageProps {
  params: Promise<{
    projectId: string;
  }>;
  searchParams: Promise<{
    file?: string;
  }>;
}

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Project Brain Explorer · DevMind",
  description:
    "Explore repository AST symbols, snapshots, dependency graphs, and code metrics (Screen S-05)",
};

export default async function BrainPage({ params, searchParams }: BrainPageProps) {
  const { projectId } = await params;
  const { file } = await searchParams;

  return (
    <AppShell>
      <div className="h-full">
        <BrainExplorer projectId={projectId} initialFilePath={file} />
      </div>
    </AppShell>
  );
}
