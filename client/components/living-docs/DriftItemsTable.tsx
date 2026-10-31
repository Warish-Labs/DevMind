"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  type DocDriftItemResponse,
  getDriftStatusBadgeVariant,
  getDriftKindBadgeVariant,
} from "./types";

interface DriftItemsTableProps {
  items: DocDriftItemResponse[];
  onReviewProposal: (item: DocDriftItemResponse) => void;
}

export function DriftItemsTable({ items, onReviewProposal }: DriftItemsTableProps) {
  if (items.length === 0) {
    return (
      <div className="border border-[var(--line-1)] bg-[var(--bg-0)] rounded-panel p-8 text-center font-mono">
        <p className="text-sm font-semibold text-[var(--fg-1)]">No documentation drift detected</p>
        <p className="text-xs text-[var(--fg-2)] mt-1">
          All tracked routes and code symbols match the current documentation records.
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
              <th className="py-2.5 px-3">Discrepancy &amp; Target</th>
              <th className="py-2.5 px-3">Kind</th>
              <th className="py-2.5 px-3 text-center">Status</th>
              <th className="py-2.5 px-3 text-center">Gate</th>
              <th className="py-2.5 px-3">Detected</th>
              <th className="py-2.5 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--line-1)]">
            {items.map((item) => (
              <tr key={item.id} className="hover:bg-[var(--bg-1)] transition-colors">
                <td className="py-3 px-3 max-w-[320px]">
                  <div className="font-semibold text-[var(--fg-0)] truncate">
                    {item.target_route_path || item.target_symbol_key || "Code/Doc Discrepancy"}
                  </div>
                  <div
                    className="text-[11px] text-[var(--fg-2)] truncate mt-0.5"
                    title={item.explanation}
                  >
                    {item.explanation}
                  </div>
                </td>

                <td className="py-3 px-3 whitespace-nowrap">
                  <Badge variant={getDriftKindBadgeVariant(item.kind)}>
                    {item.kind.replace("_", " ").toUpperCase()}
                  </Badge>
                </td>

                <td className="py-3 px-3 text-center whitespace-nowrap">
                  <Badge variant={getDriftStatusBadgeVariant(item.status)}>
                    {item.status.toUpperCase()}
                  </Badge>
                </td>

                <td className="py-3 px-3 text-center whitespace-nowrap">
                  <span className="text-[10px] text-[var(--signal)] font-bold bg-[var(--bg-1)] px-1.5 py-0.5 rounded border border-[var(--line-1)]">
                    HUMAN GATE
                  </span>
                </td>

                <td className="py-3 px-3 text-[11px] text-[var(--fg-2)] whitespace-nowrap">
                  {new Date(item.created_at).toLocaleDateString(undefined, {
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
                    onClick={() => onReviewProposal(item)}
                    className="text-[11px] py-1 h-7 text-[var(--signal)] border-[var(--line-2)] hover:border-[var(--signal)]"
                  >
                    Review Proposal
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
