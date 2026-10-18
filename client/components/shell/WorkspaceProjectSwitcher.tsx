"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { CheckIcon, PlusIcon, ChevronDownIcon, FolderIcon } from "./icons";
import { Badge } from "@/components/ui/Badge";

interface SwitcherProps {
  onClose?: () => void;
  align?: "left" | "right";
  isGutterRail?: boolean;
}

export function WorkspaceProjectSwitcher({
  onClose,
  align = "left",
  isGutterRail = false,
}: SwitcherProps) {
  const {
    workspaces,
    currentWorkspace,
    setCurrentWorkspace,
    projects,
    currentProject,
    setCurrentProject,
  } = useApp();

  const [projectSearch, setProjectSearch] = useState("");
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose?.();
      }
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose?.();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose]);

  const filteredProjects = projects.filter((p) =>
    p.name.toLowerCase().includes(projectSearch.toLowerCase())
  );

  return (
    <div
      ref={popoverRef}
      role="dialog"
      aria-label="Workspace and Project Switcher"
      className={`absolute z-50 w-72 rounded-panel border border-[var(--line-2)] bg-[var(--bg-1)] p-2 shadow-2xl backdrop-blur-md text-xs font-mono animate-in fade-in zoom-in-95 duration-100 ${
        isGutterRail
          ? "left-14 top-2"
          : align === "right"
            ? "right-0 top-full mt-2"
            : "left-0 top-full mt-2"
      }`}
    >
      {/* Workspace Section */}
      <div className="px-2 py-1.5 text-[10px] uppercase tracking-wider text-[var(--fg-2)] font-semibold flex items-center justify-between">
        <span>Workspaces</span>
        <span className="text-[10px] text-[var(--line-3)]">E0 Isolated</span>
      </div>

      <div className="space-y-0.5 mb-2">
        {workspaces.map((ws) => {
          const isSelected = currentWorkspace?.id === ws.id;
          return (
            <button
              key={ws.id}
              type="button"
              onClick={() => {
                setCurrentWorkspace(ws);
              }}
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-control text-left transition-colors cursor-pointer ${
                isSelected
                  ? "bg-[var(--bg-2)] text-[var(--fg-0)] font-medium"
                  : "text-[var(--fg-1)] hover:bg-[var(--bg-2)]/60 hover:text-[var(--fg-0)]"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <span className="flex-shrink-0 w-4 h-4 rounded bg-[var(--line-1)] flex items-center justify-center text-[10px] font-bold text-[var(--signal)]">
                  {ws.name.charAt(0).toUpperCase()}
                </span>
                <span className="truncate">{ws.name}</span>
              </div>
              {isSelected && <CheckIcon size={14} className="text-[var(--signal)] flex-shrink-0" />}
            </button>
          );
        })}
      </div>

      <div className="my-1 border-t border-[var(--line-1)]" />

      {/* Projects Section */}
      <div className="px-2 py-1.5 text-[10px] uppercase tracking-wider text-[var(--fg-2)] font-semibold flex items-center justify-between">
        <span>Projects</span>
        <Link
          href="/projects"
          onClick={onClose}
          className="text-[10px] text-[var(--ref)] hover:underline"
        >
          View all
        </Link>
      </div>

      {projects.length > 3 && (
        <div className="px-1 mb-1.5">
          <input
            type="text"
            placeholder="Filter projects..."
            value={projectSearch}
            onChange={(e) => setProjectSearch(e.target.value)}
            className="w-full px-2 py-1 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] text-[11px] text-[var(--fg-0)] placeholder-[var(--fg-2)] focus:outline-none focus:border-[var(--line-3)]"
          />
        </div>
      )}

      <div className="max-h-48 overflow-y-auto space-y-0.5 mb-2">
        {filteredProjects.length === 0 ? (
          <div className="px-2 py-3 text-center text-[11px] text-[var(--fg-2)]">
            No projects found
          </div>
        ) : (
          filteredProjects.map((p) => {
            const isSelected = currentProject?.id === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setCurrentProject(p);
                  onClose?.();
                }}
                className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-control text-left transition-colors cursor-pointer ${
                  isSelected
                    ? "bg-[var(--bg-2)] text-[var(--fg-0)] font-medium"
                    : "text-[var(--fg-1)] hover:bg-[var(--bg-2)]/60 hover:text-[var(--fg-0)]"
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <FolderIcon size={14} className="text-[var(--fg-2)] flex-shrink-0" />
                  <span className="truncate">{p.name}</span>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <Badge
                    variant={p.sync_mode === "indexed" ? "signal" : "warn"}
                    size="sm"
                    className="text-[9px] px-1 py-0"
                  >
                    {p.sync_mode === "indexed" ? "idx" : "meta"}
                  </Badge>
                  {isSelected && <CheckIcon size={14} className="text-[var(--signal)]" />}
                </div>
              </button>
            );
          })
        )}
      </div>

      <div className="my-1 border-t border-[var(--line-1)]" />

      {/* Switcher Footer Actions */}
      <div className="pt-1 flex flex-col gap-0.5">
        <Link
          href="/projects?action=create"
          onClick={onClose}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-control text-[var(--fg-1)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-0)] transition-colors"
        >
          <PlusIcon size={14} className="text-[var(--signal)]" />
          <span>New Project</span>
        </Link>
      </div>
    </div>
  );
}

export function SwitcherTriggerButton({
  onClick,
  isOpen,
}: {
  onClick: () => void;
  isOpen: boolean;
}) {
  const { currentWorkspace, currentProject } = useApp();

  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={isOpen}
      aria-label="Switch workspace or project"
      className="flex items-center gap-2 px-2 py-1 rounded-control border border-[var(--line-1)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] text-left transition-colors text-xs font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] cursor-pointer"
    >
      <span className="w-5 h-5 rounded bg-[var(--bg-2)] border border-[var(--line-2)] flex items-center justify-center font-bold text-[11px] text-[var(--signal)]">
        {currentWorkspace ? currentWorkspace.name.charAt(0).toUpperCase() : "D"}
      </span>
      <div className="flex flex-col text-left truncate max-w-[140px]">
        <span className="text-[11px] font-semibold text-[var(--fg-0)] truncate leading-tight">
          {currentWorkspace?.name || "Workspace"}
        </span>
        <span className="text-[10px] text-[var(--fg-2)] truncate leading-tight">
          {currentProject?.name || "Select project"}
        </span>
      </div>
      <ChevronDownIcon
        size={14}
        className={`text-[var(--fg-2)] transition-transform duration-160 ${
          isOpen ? "rotate-180" : ""
        }`}
      />
    </button>
  );
}
