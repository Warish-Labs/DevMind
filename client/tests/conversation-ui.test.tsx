import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { ChatMessageItem } from "../components/chat/ChatMessageItem";
import { CitationsPanel } from "../components/chat/CitationsPanel";
import { ChatComposer } from "../components/chat/ChatComposer";
import { ConversationView } from "../components/chat/ConversationView";
import {
  SAMPLE_CONVERSATION_MESSAGES,
  SAMPLE_CITATIONS,
  STARTER_PROMPTS,
} from "../components/chat/types";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/chat",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M8-07: AI Project Conversation UI (Screen S-06 per docs/08 §11)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("ChatMessageItem component", () => {
    it("renders user messages with right-aligned layout and timestamp", () => {
      const userMessage = SAMPLE_CONVERSATION_MESSAGES[0];
      const html = renderToString(
        <ChatMessageItem message={userMessage} onSelectCitation={vi.fn()} />
      );

      expect(html).toContain("How does DevMind prevent unauthorized users");
      expect(html).not.toContain("DevMind Avatar");
    });

    it("renders assistant messages with agent execution trace above answer", () => {
      const assistantMessage = SAMPLE_CONVERSATION_MESSAGES[1];
      const html = renderToString(
        <ChatMessageItem
          message={assistantMessage}
          onSelectCitation={vi.fn()}
          onOpenCitationsPanel={vi.fn()}
        />
      );

      // DevMind avatar & execution trace
      expect(html).toContain("DM");
      expect(html).toContain("Agent Execution Trace");
      expect(html).toContain("Searched Project Brain for");
      expect(html).toContain("Verified 3 citations against repository AST snapshot");

      // Numbered inline citation pills
      expect(html).toContain("[1]");
      expect(html).toContain("[2]");
      expect(html).toContain("[3]");

      // Footer actions
      expect(html).toContain("Copy markdown");
      expect(html).toContain("Citations (3)");
    });

    it("renders insufficient evidence messages with distinct alert style and suggested next steps", () => {
      const insufficientMessage = SAMPLE_CONVERSATION_MESSAGES[3];
      const html = renderToString(
        <ChatMessageItem message={insufficientMessage} onSelectCitation={vi.fn()} />
      );

      expect(html).toContain("Insufficient Evidence for Grounded Answer");
      expect(html).toContain("The query asks for zero-knowledge proof cryptographic primitives");
      expect(html).toContain("Suggested Next Steps:");
      expect(html).toContain("Review `docs/07-auth-and-redaction.md` for DevMind");
      expect(html).toContain("Check `docs/12-decisions/` to confirm");
    });
  });

  describe("CitationsPanel component", () => {
    it("renders empty state message when no citations exist", () => {
      const html = renderToString(
        <CitationsPanel
          projectId={projectId}
          citations={[]}
          selectedCitationId={null}
          onSelectCitation={vi.fn()}
          onClose={vi.fn()}
        />
      );

      expect(html).toContain("No citations referenced in selected response");
    });

    it("renders citation items with AST verification tag, line ranges, code snippets, and Brain Explorer links", () => {
      const html = renderToString(
        <CitationsPanel
          projectId={projectId}
          citations={SAMPLE_CITATIONS}
          selectedCitationId="cit-01"
          onSelectCitation={vi.fn()}
          onClose={vi.fn()}
        />
      );

      expect(html).toContain("Referenced Citations (3)");
      expect(html).toContain("AST Verified");

      // Citations items
      expect(html).toContain("server/app/domain/auth/permissions.py");
      expect(html).toContain("L28-L45");
      expect(html).toContain("require_permission");
      expect(html).toContain("FastAPI dependency factory enforcing AuthContext");

      expect(html).toContain("server/app/api/findings.py");
      expect(html).toContain("L98-L118");
      expect(html).toContain("transition_finding_status");

      expect(html).toContain("server/app/domain/brain/repository.py");
      expect(html).toContain("L54-L72");
      expect(html).toContain("resolve_project_context");

      // Actions
      expect(html).toContain("Copy reference");
      expect(html).toContain("Brain Explorer");
    });
  });

  describe("ChatComposer component", () => {
    it("renders textarea, starter queries, and Ask Project button", () => {
      const html = renderToString(<ChatComposer onSendMessage={vi.fn()} showStarters={true} />);

      expect(html).toContain("Ask Project Brain anything about code architecture");
      expect(html).toContain("Suggested starter queries:");
      expect(html).toContain(STARTER_PROMPTS[0]);
      expect(html).toContain(STARTER_PROMPTS[1]);
      expect(html).toContain("AST Grounded");
      expect(html).toContain("Ask Project");
    });

    it("renders Stop generation button when isStreaming is true", () => {
      const html = renderToString(
        <ChatComposer onSendMessage={vi.fn()} onStopGeneration={vi.fn()} isStreaming={true} />
      );

      expect(html).toContain("Stop");
      expect(html).not.toContain(">Ask Project<");
    });
  });

  describe("ConversationView component (Screen S-06 integration)", () => {
    it("renders conversation header, messages column, and citations panel", () => {
      const html = renderToString(
        <ConversationView projectId={projectId} initialMessages={SAMPLE_CONVERSATION_MESSAGES} />
      );

      // Header
      expect(html).toContain("AI Project Conversation");
      expect(html).toContain("Screen S-06");
      expect(html).toContain("Export");
      expect(html).toContain("Clear");
      expect(html).toContain("Citations");

      // Messages
      expect(html).toContain(
        "How does DevMind prevent unauthorized users from triaging or dismissing security findings?"
      );
      expect(html).toContain(
        "DevMind enforces role-based authorization using a two-tier permission guard"
      );
      expect(html).toContain("Insufficient Evidence for Grounded Answer");

      // Citations panel
      expect(html).toContain("Referenced Citations (3)");
    });
  });
});
