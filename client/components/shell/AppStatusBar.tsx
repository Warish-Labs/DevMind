"use client";

import React from "react";
import { useApp } from "@/context/AppContext";
import { Badge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";

export function AppStatusBar() {
  const { syncMode, scanStatus, activeJobCount } = useApp();

  return (
    <footer
      aria-label="Application Status Bar"
      className="fixed bottom-0 left-0 right-0 h-7 z-30 lg:pl-14 border-t border-[var(--line-1)] bg-[var(--bg-1)] px-4 flex items-center justify-between font-mono text-[11px] text-[var(--fg-2)] select-none"
    >
      {/* Left: Scan Status & Sync Mode */}
      <div className="flex items-center gap-4">
        {/* Local Scan Status */}
        <div className="flex items-center gap-1.5 truncate max-w-xs sm:max-w-md">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
          <span className="truncate text-[var(--fg-1)]">{scanStatus}</span>
        </div>

        <span className="text-[var(--line-2)] hidden sm:inline">|</span>

        {/* Sync Mode Indicator */}
        <Tooltip
          content={
            syncMode === "indexed"
              ? "Indexed mode: AST, symbols, embeddings & citations active"
              : "Metadata-only mode: only structural symbols stored; source code never leaves your machine"
          }
          position="top"
        >
          <div className="flex items-center gap-1.5">
            <span className="hidden sm:inline text-[10px] text-[var(--fg-2)]">Sync:</span>
            <Badge
              variant={syncMode === "indexed" ? "signal" : "warn"}
              size="sm"
              className="text-[9px] px-1 py-0 cursor-default"
            >
              {syncMode}
            </Badge>
          </div>
        </Tooltip>
      </div>

      {/* Right: Extension link & Worker queue & Cloud health */}
      <div className="flex items-center gap-4">
        <div className="hidden md:flex items-center gap-1.5">
          <span className="text-[10px]">Queue:</span>
          <span className="text-[var(--fg-1)]">
            {activeJobCount === 0 ? "0 jobs" : `${activeJobCount} active`}
          </span>
        </div>

        <span className="text-[var(--line-2)] hidden md:inline">|</span>

        <Tooltip content="VS Code extension companion status" position="top">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
            <span className="hidden sm:inline text-[var(--fg-1)]">VS Code</span>
            <span className="text-[var(--fg-2)]">connected</span>
          </div>
        </Tooltip>

        <span className="text-[var(--line-2)] hidden sm:inline">|</span>

        <div className="flex items-center gap-1.5 text-[var(--fg-2)]">
          <span>v0.1.0</span>
          <span className="hidden lg:inline text-[10px] text-[var(--line-3)]">(Free tier)</span>
        </div>
      </div>
    </footer>
  );
}
