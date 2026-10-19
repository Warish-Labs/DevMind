"use client";

import React from "react";
import { Dialog } from "@/components/ui/Dialog";
import { AuditLogViewer } from "./AuditLogViewer";

export interface AuditLogModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId?: string;
  projectId?: string;
  title?: string;
}

export function AuditLogModal({
  isOpen,
  onClose,
  workspaceId,
  projectId,
  title = "Audit Event Log",
}: AuditLogModalProps) {
  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      description="Immutable governance log recording sensitive workspace and project operations (docs/03 §3.5, docs/07 §16)."
      className="max-w-4xl w-full"
    >
      <div className="max-h-[70vh] overflow-y-auto pr-1">
        <AuditLogViewer workspaceId={workspaceId} projectId={projectId} showHeader={false} />
      </div>
    </Dialog>
  );
}
