"use client";

import React, { useState } from "react";
import type { BrainFileNode } from "./types";

export interface FileTreePaneProps {
  tree: BrainFileNode[];
  selectedFilePath: string | null;
  onSelectFile: (filePath: string) => void;
  searchFilter?: string;
  className?: string;
}

export function FileTreePane({
  tree,
  selectedFilePath,
  onSelectFile,
  searchFilter = "",
  className = "",
}: FileTreePaneProps) {
  const [expandedDirs, setExpandedDirs] = useState<Record<string, boolean>>({
    server: true,
    "server/app": true,
    "server/app/api": true,
    "server/app/domain": true,
    "server/app/domain/auth": true,
    "server/app/domain/brain": true,
    client: true,
    "client/components": true,
    "client/components/chat": true,
  });

  const toggleDir = (dirPath: string) => {
    setExpandedDirs((prev) => ({
      ...prev,
      [dirPath]: !prev[dirPath],
    }));
  };

  const renderNode = (node: BrainFileNode, depth: number = 0) => {
    if (node.isDirectory) {
      const isExpanded = !!expandedDirs[node.path];
      const childMatches =
        searchFilter &&
        node.children?.some(
          (c) =>
            c.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
            c.path.toLowerCase().includes(searchFilter.toLowerCase())
        );

      return (
        <div key={node.id} className="space-y-0.5 select-none">
          <button
            type="button"
            onClick={() => toggleDir(node.path)}
            style={{ paddingLeft: `${depth * 14 + 10}px` }}
            className="w-full flex items-center justify-between py-1.5 pr-2 rounded text-left text-xs font-mono text-[var(--fg-1)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors group"
          >
            <div className="flex items-center gap-1.5 overflow-hidden">
              <span className="text-[10px] text-[var(--fg-3)] shrink-0 w-3">
                {isExpanded ? "▼" : "▶"}
              </span>
              <span className="font-semibold truncate">{node.name}</span>
            </div>
            {childMatches && <span className="w-1.5 h-1.5 rounded-full bg-[var(--ref)] shrink-0" />}
          </button>

          {isExpanded && node.children && (
            <div className="space-y-0.5">
              {node.children.map((child) => renderNode(child, depth + 1))}
            </div>
          )}
        </div>
      );
    }

    // File Leaf
    const isSelected = selectedFilePath === node.path;
    const matchesSearch =
      !searchFilter ||
      node.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      node.path.toLowerCase().includes(searchFilter.toLowerCase());

    if (!matchesSearch) return null;

    return (
      <button
        key={node.id}
        type="button"
        onClick={() => onSelectFile(node.path)}
        style={{ paddingLeft: `${depth * 14 + 18}px` }}
        className={`w-full flex items-center justify-between py-1.5 pr-2.5 rounded text-left text-xs font-mono transition-colors group ${
          isSelected
            ? "bg-[rgba(78,161,255,0.12)] text-[var(--ref)] font-semibold border-l-2 border-[var(--ref)]"
            : "text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)]"
        }`}
      >
        <div className="flex items-center gap-1.5 overflow-hidden">
          <span className="text-[11px] text-[var(--fg-3)]">📄</span>
          <span className="truncate">{node.name}</span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {node.languageTier && (
            <span className="text-[9px] px-1 py-0.2 rounded bg-[var(--bg-2)] text-[var(--fg-3)] font-mono uppercase">
              {node.languageTier}
            </span>
          )}

          {node.hasFindings && (
            <span
              className="text-[9px] px-1.5 py-0.2 rounded-full bg-[rgba(235,90,90,0.15)] text-[var(--danger)] border border-[rgba(235,90,90,0.3)] font-bold font-mono"
              title={`${node.findingsCount || 1} security finding(s) detected`}
            >
              {`!${node.findingsCount || 1}`}
            </span>
          )}

          {node.isStale && (
            <span
              className="text-[9px] px-1 py-0.2 rounded bg-[rgba(240,180,76,0.15)] text-[var(--warn)] font-mono"
              title="File modified since snapshot base"
            >
              stale
            </span>
          )}
        </div>
      </button>
    );
  };

  return (
    <aside
      className={`border-r border-[var(--line-1)] bg-[var(--bg-1)] flex flex-col h-full font-mono text-xs ${className}`}
    >
      <div className="px-4 py-2.5 border-b border-[var(--line-1)] flex items-center justify-between text-[11px] text-[var(--fg-3)] select-none">
        <span className="font-semibold uppercase tracking-wider text-[var(--fg-2)]">
          Repository Files
        </span>
        <span>Tree (S-05)</span>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {tree.map((rootNode) => renderNode(rootNode, 0))}
      </div>
    </aside>
  );
}
