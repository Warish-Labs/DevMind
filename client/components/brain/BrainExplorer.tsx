"use client";

import React, { useState, useMemo } from "react";
import { BrainHeader } from "./BrainHeader";
import { FileTreePane } from "./FileTreePane";
import { CodeSymbolPane } from "./CodeSymbolPane";
import { RelationshipsPane } from "./RelationshipsPane";
import type {
  BrainFileNode,
  BrainFileContent,
  BrainSnapshotSummary,
  ProjectBrainMode,
  BrainSymbolDetail,
} from "./types";
import { SAMPLE_SNAPSHOTS, SAMPLE_FILE_TREE, SAMPLE_FILE_CONTENTS } from "./types";

export interface BrainExplorerProps {
  projectId: string;
  initialMode?: ProjectBrainMode;
  initialFilePath?: string;
  initialSnapshots?: BrainSnapshotSummary[];
  initialFileTree?: BrainFileNode[];
  initialFileContents?: Record<string, BrainFileContent>;
  className?: string;
}

export function BrainExplorer({
  projectId,
  initialMode = "indexed",
  initialFilePath = "server/app/domain/auth/permissions.py",
  initialSnapshots = SAMPLE_SNAPSHOTS,
  initialFileTree = SAMPLE_FILE_TREE,
  initialFileContents = SAMPLE_FILE_CONTENTS,
  className = "",
}: BrainExplorerProps) {
  const [projectMode, setProjectMode] = useState<ProjectBrainMode>(initialMode);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>(
    initialSnapshots[0]?.id || "snap-001"
  );
  const [selectedFilePath, setSelectedFilePath] = useState<string>(initialFilePath);
  const [selectedSymbolId, setSelectedSymbolId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [mobileTab, setMobileTab] = useState<"files" | "code" | "relationships">("code");

  const currentFileContent = useMemo<BrainFileContent | null>(() => {
    if (!selectedFilePath) return null;
    return (
      initialFileContents[selectedFilePath] || {
        id: `file-${selectedFilePath}`,
        path: selectedFilePath,
        lineCount: 42,
        contentHash: "e4f5a6b7c8d9e0f1",
        languageTier: "tier1",
        content: `// Source preview for ${selectedFilePath}\n// Loading AST symbols and dependencies...`,
        symbols: [],
        relationships: [],
        findings: [],
      }
    );
  }, [selectedFilePath, initialFileContents]);

  const selectedSymbol = useMemo<BrainSymbolDetail | undefined>(() => {
    if (!currentFileContent || !selectedSymbolId) return undefined;
    return currentFileContent.symbols.find((s) => s.id === selectedSymbolId);
  }, [currentFileContent, selectedSymbolId]);

  const handleSelectFile = (path: string) => {
    setSelectedFilePath(path);
    setSelectedSymbolId(null);
    setMobileTab("code");
  };

  const handleSelectSymbol = (symbol: BrainSymbolDetail) => {
    setSelectedSymbolId(symbol.id);
  };

  const handleToggleMode = () => {
    setProjectMode((prev) => (prev === "indexed" ? "metadata_only" : "indexed"));
  };

  return (
    <div className={`flex flex-col h-full bg-[var(--bg-0)] ${className}`}>
      {/* Top Header: Snapshot selector, mode indicator, and search */}
      <BrainHeader
        projectId={projectId}
        snapshots={initialSnapshots}
        selectedSnapshotId={selectedSnapshotId}
        onSelectSnapshot={setSelectedSnapshotId}
        projectMode={projectMode}
        onToggleMode={handleToggleMode}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {/* Mobile Panes Tabs Bar (< 1024px) */}
      <div className="flex lg:hidden border-b border-[var(--line-1)] bg-[var(--bg-1)] font-mono text-xs select-none shrink-0">
        <button
          type="button"
          onClick={() => setMobileTab("files")}
          className={`flex-1 py-2 text-center border-b-2 font-semibold transition-colors ${
            mobileTab === "files"
              ? "border-[var(--ref)] text-[var(--fg-0)] bg-[var(--bg-0)]"
              : "border-transparent text-[var(--fg-3)]"
          }`}
        >
          Files
        </button>

        <button
          type="button"
          onClick={() => setMobileTab("code")}
          className={`flex-1 py-2 text-center border-b-2 font-semibold transition-colors ${
            mobileTab === "code"
              ? "border-[var(--ref)] text-[var(--fg-0)] bg-[var(--bg-0)]"
              : "border-transparent text-[var(--fg-3)]"
          }`}
        >
          Code & Symbols
        </button>

        <button
          type="button"
          onClick={() => setMobileTab("relationships")}
          className={`flex-1 py-2 text-center border-b-2 font-semibold transition-colors ${
            mobileTab === "relationships"
              ? "border-[var(--ref)] text-[var(--fg-0)] bg-[var(--bg-0)]"
              : "border-transparent text-[var(--fg-3)]"
          }`}
        >
          Graph & Findings
        </button>
      </div>

      {/* Main 3-Pane Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane: File Tree */}
        <div
          className={`w-full lg:w-72 shrink-0 ${
            mobileTab === "files" ? "block" : "hidden lg:block"
          }`}
        >
          <FileTreePane
            tree={initialFileTree}
            selectedFilePath={selectedFilePath}
            onSelectFile={handleSelectFile}
            searchFilter={searchQuery}
          />
        </div>

        {/* Center Pane: Code & Symbol Detail */}
        <div
          className={`flex-1 min-w-0 flex flex-col ${
            mobileTab === "code" ? "block" : "hidden lg:flex"
          }`}
        >
          <CodeSymbolPane
            projectId={projectId}
            fileContent={currentFileContent}
            projectMode={projectMode}
            selectedSymbolId={selectedSymbolId}
            onSelectSymbol={handleSelectSymbol}
          />
        </div>

        {/* Right Pane: Relationships & Findings */}
        <div
          className={`w-full lg:w-84 shrink-0 ${
            mobileTab === "relationships" ? "block" : "hidden lg:block"
          }`}
        >
          <RelationshipsPane
            projectId={projectId}
            relationships={currentFileContent?.relationships || []}
            findings={currentFileContent?.findings || []}
            selectedSymbolName={selectedSymbol?.name}
            onExpandGraph={() => {
              // Could trigger expanded modal or graph explorer
            }}
          />
        </div>
      </div>
    </div>
  );
}
