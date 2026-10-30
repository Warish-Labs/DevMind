import { Suspense } from "react";
import { Metadata } from "next";
import { AcceptInvitationClient } from "@/components/invitations/AcceptInvitationClient";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Accept Workspace Invitation · DevMind",
  description:
    "Accept workspace membership invitation and access codebase intelligence (FR-PLT-05, ADR-014)",
};

export default function AcceptInvitationPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[75vh] flex items-center justify-center font-mono text-xs text-[var(--fg-2)]">
          Loading invitation...
        </div>
      }
    >
      <AcceptInvitationClient />
    </Suspense>
  );
}
