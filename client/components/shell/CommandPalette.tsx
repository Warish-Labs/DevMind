"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/context/AppContext";
import {
  SearchIcon,
  OverviewIcon,
  BrainIcon,
  ChatIcon,
  FindingsIcon,
  JobsIcon,
  GitPullRequestIcon,
  SettingsIcon,
  FolderIcon,
  ExternalLinkIcon,
  CloseIcon,
} from "./icons";
import { Badge } from "@/components/ui/Badge";

interface CommandItem {
  id: string;
  category: "Navigation" | "Projects" | "Actions";
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  onSelect: () => void;
  badge?: string;
}

export function CommandPalette() {
  const router = useRouter();
  const {
    isCommandPaletteOpen,
    setCommandPaletteOpen,
    currentProject,
    projects,
    setCurrentProject,
    syncMode,
    setSyncMode,
    setScanStatus,
  } = useApp();

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const pid = currentProject?.id || "default";

  // Build commands
  const commands: CommandItem[] = useMemo(() => {
    const list: CommandItem[] = [
      // Navigation
      {
        id: "nav-projects",
        category: "Navigation",
        title: "All Projects",
        subtitle: "Workspace project directory (S-03)",
        icon: <FolderIcon size={16} className="text-[var(--ref)]" />,
        onSelect: () => router.push("/projects"),
      },
      {
        id: "nav-overview",
        category: "Navigation",
        title: "Project Overview",
        subtitle: "Health score, coverage, and recent jobs (S-04)",
        icon: <OverviewIcon size={16} className="text-[var(--signal)]" />,
        onSelect: () => router.push(`/projects/${pid}`),
      },
      {
        id: "nav-brain",
        category: "Navigation",
        title: "Project Brain Explorer",
        subtitle: "File tree, symbols, and knowledge graph (S-05)",
        icon: <BrainIcon size={16} className="text-[var(--ref)]" />,
        onSelect: () => router.push(`/projects/${pid}/brain`),
      },
      {
        id: "nav-chat",
        category: "Navigation",
        title: "Project Conversation",
        subtitle: "Ask questions grounded in codebase evidence (S-06)",
        icon: <ChatIcon size={16} className="text-[var(--fg-1)]" />,
        onSelect: () => router.push(`/projects/${pid}/chat`),
      },
      {
        id: "nav-findings",
        category: "Navigation",
        title: "Findings & Security",
        subtitle: "Evidence-ranked findings with verifiable E0-E3 status (S-07)",
        icon: <FindingsIcon size={16} className="text-[var(--danger)]" />,
        onSelect: () => router.push(`/projects/${pid}/findings`),
        badge: "E0-E3",
      },
      {
        id: "nav-jobs",
        category: "Navigation",
        title: "Job Center",
        subtitle: "Queue, worker status, and audit logs (S-09)",
        icon: <JobsIcon size={16} className="text-[var(--warn)]" />,
        onSelect: () => router.push(`/projects/${pid}/jobs`),
      },
      {
        id: "nav-pull-requests",
        category: "Navigation",
        title: "Pull Requests & Impact",
        subtitle: "Mirrored PRs, change-impact graph, and ReviewBuddy checklist (S-14)",
        icon: <GitPullRequestIcon size={16} className="text-[var(--signal)]" />,
        onSelect: () => router.push(`/projects/${pid}/pull-requests`),
        badge: "PRAgent",
      },
      {
        id: "nav-settings",
        category: "Navigation",
        title: "Project Settings",
        subtitle: "Sync modes, consent, and repository configuration (S-10)",
        icon: <SettingsIcon size={16} className="text-[var(--fg-2)]" />,
        onSelect: () => router.push(`/projects/${pid}/settings`),
      },
      // Actions
      {
        id: "act-scan",
        category: "Actions",
        title: "Trigger Local Scan",
        subtitle: "Initiate AST structural extraction and local diagnostics",
        icon: <BrainIcon size={16} className="text-[var(--signal)]" />,
        onSelect: () => {
          setScanStatus("Scanning 42 files (Tier 1)...");
          setTimeout(() => setScanStatus("Scan complete · 42 files up to date"), 2500);
        },
      },
      {
        id: "act-sync-toggle",
        category: "Actions",
        title: `Switch Sync Mode to ${syncMode === "indexed" ? "metadata_only" : "indexed"}`,
        subtitle:
          syncMode === "indexed"
            ? "Downgrades to metadata-only (no source text leaves your machine)"
            : "Enables cloud indexed mode with full embeddings and retrieval",
        icon: <SettingsIcon size={16} className="text-[var(--warn)]" />,
        onSelect: () => {
          setSyncMode(syncMode === "indexed" ? "metadata_only" : "indexed");
        },
        badge: syncMode === "indexed" ? "Indexed" : "Metadata Only",
      },
      {
        id: "act-vscode",
        category: "Actions",
        title: "Connect VS Code Extension",
        subtitle: "Deep-link to local editor companion",
        icon: <ExternalLinkIcon size={16} className="text-[var(--ref)]" />,
        onSelect: () => {
          if (typeof window !== "undefined") {
            window.location.assign("vscode://devmind.devmind-vscode/connect");
          }
        },
      },
    ];

    // Add projects
    projects.forEach((proj) => {
      list.push({
        id: `proj-${proj.id}`,
        category: "Projects",
        title: proj.name,
        subtitle: `${proj.sync_mode} · ${proj.primary_language || "Codebase"}`,
        icon: <FolderIcon size={16} className="text-[var(--fg-1)]" />,
        onSelect: () => {
          setCurrentProject(proj);
          router.push(`/projects/${proj.id}`);
        },
        badge: proj.sync_mode,
      });
    });

    return list;
  }, [pid, router, projects, setCurrentProject, syncMode, setSyncMode, setScanStatus]);

  // Filter commands
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        (c.subtitle && c.subtitle.toLowerCase().includes(q)) ||
        c.category.toLowerCase().includes(q)
    );
  }, [commands, query]);

  const activeIndex = selectedIndex < filtered.length ? selectedIndex : 0;

  // Auto focus input when opened
  useEffect(() => {
    if (isCommandPaletteOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isCommandPaletteOpen]);

  // Keyboard navigation inside palette
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1 < filtered.length ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : filtered.length - 1));
    } else if (e.key === "Enter" && filtered[activeIndex]) {
      e.preventDefault();
      filtered[activeIndex].onSelect();
      setCommandPaletteOpen(false);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setCommandPaletteOpen(false);
    }
  };

  if (!isCommandPaletteOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-[var(--bg-0)]/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) setCommandPaletteOpen(false);
      }}
    >
      <div className="w-full max-w-xl rounded-panel border border-[var(--line-2)] bg-[var(--bg-1)] shadow-2xl overflow-hidden font-mono text-xs">
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--line-1)] bg-[var(--bg-2)]/60">
          <SearchIcon size={18} className="text-[var(--fg-2)] flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-list"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search (e.g. Findings, Scan, Brain)..."
            className="flex-1 bg-transparent text-sm text-[var(--fg-0)] placeholder-[var(--fg-2)] focus:outline-none"
          />
          <button
            type="button"
            onClick={() => setCommandPaletteOpen(false)}
            aria-label="Close command palette"
            className="p-1 rounded-control text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors cursor-pointer"
          >
            <CloseIcon size={16} />
          </button>
        </div>

        {/* Results List */}
        <div
          id="command-list"
          ref={listRef}
          role="listbox"
          className="max-h-80 overflow-y-auto p-2 space-y-1"
        >
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-xs text-[var(--fg-2)]">
              No matching commands or navigation targets found for &quot;{query}&quot;
            </div>
          ) : (
            filtered.map((item, index) => {
              const isSelected = index === activeIndex;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    item.onSelect();
                    setCommandPaletteOpen(false);
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-control text-left transition-colors cursor-pointer ${
                    isSelected
                      ? "bg-[var(--bg-2)] text-[var(--fg-0)] border-l-2 border-[var(--signal)]"
                      : "text-[var(--fg-1)] hover:bg-[var(--bg-2)]/60 hover:text-[var(--fg-0)]"
                  }`}
                >
                  <div className="flex items-center gap-3 truncate">
                    <span className="flex-shrink-0">{item.icon}</span>
                    <div className="truncate">
                      <div className="font-medium text-xs text-[var(--fg-0)] truncate">
                        {item.title}
                      </div>
                      {item.subtitle && (
                        <div className="text-[11px] text-[var(--fg-2)] truncate">
                          {item.subtitle}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                    {item.badge && (
                      <Badge variant="neutral" size="sm" className="text-[10px]">
                        {item.badge}
                      </Badge>
                    )}
                    <span className="text-[10px] text-[var(--fg-2)] uppercase">
                      {item.category}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer shortcuts helper */}
        <div className="px-4 py-2 border-t border-[var(--line-1)] bg-[var(--bg-0)] flex items-center justify-between text-[10px] text-[var(--fg-2)]">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="px-1 py-0.5 rounded border border-[var(--line-2)] bg-[var(--bg-1)]">
                ↑
              </kbd>{" "}
              <kbd className="px-1 py-0.5 rounded border border-[var(--line-2)] bg-[var(--bg-1)]">
                ↓
              </kbd>{" "}
              navigate
            </span>
            <span>
              <kbd className="px-1 py-0.5 rounded border border-[var(--line-2)] bg-[var(--bg-1)]">
                ↵
              </kbd>{" "}
              select
            </span>
            <span>
              <kbd className="px-1 py-0.5 rounded border border-[var(--line-2)] bg-[var(--bg-1)]">
                esc
              </kbd>{" "}
              close
            </span>
          </div>
          <span>DevMind Global Nav</span>
        </div>
      </div>
    </div>
  );
}
