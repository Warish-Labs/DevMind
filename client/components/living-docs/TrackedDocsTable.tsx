"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { DocRecordResponse } from "./types";

interface TrackedDocsTableProps {
  docs: DocRecordResponse[];
  onInspectDoc: (docId: string) => void;
}

export function TrackedDocsTable({ docs, onInspectDoc }: TrackedDocsTableProps) {
  if (docs.length === 0) {
    return (
      <div className="border border-[var(--line-1)] bg-[var(--bg-0)] rounded-panel p-8 text-center font-mono">
        <p className="text-sm font-semibold text-[var(--fg-1)]">
          No documentation files registered
        </p>
        <p className="text-xs text-[var(--fg-2)] mt-1">
          Click &quot;Register Document&quot; above to track Markdown files and extract route/code
          symbols.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-[var(--line-1)] bg-[var(--bg-0)] rounded-panel overflow-hidden font-mono">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-[var(--line-1)] bg-[var(--bg-1)] text-[var(--fg-2)] text-[11px] uppercase tracking-wider font-semibold">
              <th className="py-2.5 px-3">Path &amp; Title</th>
              <th className="py-2.5 px-3">Kind</th>
              <th className="py-2.5 px-3">Content Hash</th>
              <th className="py-2.5 px-3 text-center">Status</th>
              <th className="py-2.5 px-3">Last Parsed</th>
              <th className="py-2.5 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--line-1)]">
            {docs.map((doc) => (
              <tr key={doc.id} className="hover:bg-[var(--bg-1)] transition-colors">
                <td className="py-3 px-3 max-w-[300px]">
                  <div className="font-semibold text-[var(--fg-0)] truncate">{doc.title}</div>
                  <code className="text-[11px] text-[var(--ref)] font-mono truncate block mt-0.5">
                    {doc.path}
                  </code>
                </td>

                <td className="py-3 px-3 whitespace-nowrap">
                  <Badge variant="neutral" className="uppercase text-[10px]">
                    {doc.kind}
                  </Badge>
                </td>

                <td className="py-3 px-3 font-mono text-[11px] text-[var(--fg-2)]">
                  <code>{doc.current_version_hash.slice(0, 16)}...</code>
                </td>

                <td className="py-3 px-3 text-center whitespace-nowrap">
                  <Badge variant="signal" className="text-[10px]">
                    TRACKED
                  </Badge>
                </td>

                <td className="py-3 px-3 text-[11px] text-[var(--fg-2)] whitespace-nowrap">
                  {new Date(doc.last_parsed_at || doc.updated_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </td>

                <td className="py-3 px-3 text-right whitespace-nowrap">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => onInspectDoc(doc.id)}
                    className="text-[11px] py-1 h-7"
                  >
                    Inspect
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
