import { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { ConversationView } from "@/components/chat/ConversationView";

interface ChatPageProps {
  params: Promise<{
    projectId: string;
  }>;
}

export const metadata: Metadata = {
  title: "AI Project Conversation · DevMind",
  description:
    "Ask Project Brain with grounded AST citations and insufficient evidence detection (Screen S-06)",
};

export default async function ChatPage({ params }: ChatPageProps) {
  const { projectId } = await params;

  return (
    <AppShell>
      <div className="h-full">
        <ConversationView projectId={projectId} />
      </div>
    </AppShell>
  );
}
