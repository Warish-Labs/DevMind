"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApp } from "@/context/AppContext";
import {
  SearchIcon,
  MenuIcon,
  JobsIcon,
  CloseIcon,
  OverviewIcon,
  BrainIcon,
  ChatIcon,
  FindingsIcon,
  GitPullRequestIcon,
  SettingsIcon,
  FolderIcon,
} from "./icons";
import { SwitcherTriggerButton, WorkspaceProjectSwitcher } from "./WorkspaceProjectSwitcher";

export function AppTopBar() {
  const pathname = usePathname();
  const {
    currentWorkspace,
    currentProject,
    setCommandPaletteOpen,
    activeJobCount,
    isMobileNavOpen,
    setMobileNavOpen,
  } = useApp();

  const [isSwitcherOpen, setSwitcherOpen] = useState(false);

  // Compute breadcrumbs
  const getSectionName = () => {
    if (pathname.includes("/brain")) return "Brain Explorer (S-05)";
    if (pathname.includes("/chat")) return "Conversation (S-06)";
    if (pathname.includes("/findings")) return "Findings (S-07)";
    if (pathname.includes("/jobs")) return "Job Center (S-09)";
    if (pathname.includes("/pull-requests")) return "Pull Requests & Impact (S-14)";
    if (pathname.includes("/settings")) return "Settings (S-10)";
    if (pathname.startsWith("/projects/") && pathname.split("/").length === 3)
      return "Overview (S-04)";
    if (pathname === "/projects") return "Projects Index (S-03)";
    return "Console";
  };

  const pid = currentProject?.id || "default";

  return (
    <header className="sticky top-0 z-30 w-full h-12 border-b border-[var(--line-1)] bg-[var(--bg-0)]/90 backdrop-blur-md px-4 flex items-center justify-between font-mono text-xs">
      {/* Left: Mobile Menu Toggle + Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setMobileNavOpen(!isMobileNavOpen)}
          aria-label="Toggle mobile menu"
          className="lg:hidden p-1.5 rounded-control text-[var(--fg-1)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-1)] transition-colors cursor-pointer"
        >
          {isMobileNavOpen ? <CloseIcon size={18} /> : <MenuIcon size={18} />}
        </button>

        {/* Workspace & Project Switcher Dropdown */}
        <div className="relative">
          <SwitcherTriggerButton
            isOpen={isSwitcherOpen}
            onClick={() => setSwitcherOpen((prev) => !prev)}
          />

          {isSwitcherOpen && (
            <WorkspaceProjectSwitcher onClose={() => setSwitcherOpen(false)} align="left" />
          )}
        </div>

        <span className="text-[var(--line-3)] hidden sm:inline">/</span>

        {/* Current Active Section Breadcrumb */}
        <span className="hidden sm:inline-flex items-center gap-1.5 text-[var(--fg-1)] font-medium">
          {getSectionName()}
        </span>
      </div>

      {/* Right: Command Palette Trigger + Job Tray + User */}
      <div className="flex items-center gap-3">
        {/* Command Palette Trigger Button (Cmd+K) */}
        <button
          type="button"
          onClick={() => setCommandPaletteOpen(true)}
          aria-label="Open command palette (Press Cmd+K)"
          className="flex items-center gap-2 px-3 py-1.5 rounded-control border border-[var(--line-1)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] hover:border-[var(--line-2)] text-[var(--fg-2)] hover:text-[var(--fg-0)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)]"
        >
          <SearchIcon size={14} />
          <span className="hidden md:inline text-[11px]">Search or jump...</span>
          <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded border border-[var(--line-2)] bg-[var(--bg-0)] text-[10px] text-[var(--fg-1)]">
            ⌘K
          </kbd>
        </button>

        {/* Job Tray Link */}
        <Link
          href={`/projects/${pid}/jobs`}
          aria-label="Job tray status"
          className="flex items-center gap-1.5 px-2 py-1 rounded-control border border-[var(--line-1)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] text-[var(--fg-1)] transition-colors"
        >
          <JobsIcon size={14} className="text-[var(--signal)]" />
          <span className="hidden sm:inline text-[11px]">
            {activeJobCount > 0 ? `${activeJobCount} running` : "Jobs"}
          </span>
          {activeJobCount > 0 && (
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)] animate-pulse" />
          )}
        </Link>

        {/* User avatar / fallback */}
        <div className="w-7 h-7 rounded-full bg-[var(--bg-2)] border border-[var(--line-2)] flex items-center justify-center font-bold text-[11px] text-[var(--signal)] select-none">
          {currentWorkspace ? currentWorkspace.name.charAt(0) : "U"}
        </div>
      </div>

      {/* Mobile Drawer Navigation (When open on <1024px) */}
      {isMobileNavOpen && (
        <div
          role="dialog"
          aria-label="Mobile Navigation"
          className="lg:hidden fixed inset-x-0 top-12 bottom-0 z-50 bg-[var(--bg-0)]/95 backdrop-blur-md p-4 flex flex-col gap-4 border-t border-[var(--line-1)]"
        >
          <div className="font-semibold text-xs text-[var(--fg-2)] uppercase tracking-wider px-2">
            Navigation
          </div>
          <nav className="flex flex-col gap-1">
            {[
              { label: "All Projects (S-03)", href: "/projects", icon: <FolderIcon size={16} /> },
              {
                label: "Project Overview (S-04)",
                href: `/projects/${pid}`,
                icon: <OverviewIcon size={16} />,
              },
              {
                label: "Project Brain Explorer (S-05)",
                href: `/projects/${pid}/brain`,
                icon: <BrainIcon size={16} />,
              },
              {
                label: "Conversation (S-06)",
                href: `/projects/${pid}/chat`,
                icon: <ChatIcon size={16} />,
              },
              {
                label: "Findings & Security (S-07)",
                href: `/projects/${pid}/findings`,
                icon: <FindingsIcon size={16} />,
              },
              {
                label: "Job Center (S-09)",
                href: `/projects/${pid}/jobs`,
                icon: <JobsIcon size={16} />,
              },
              {
                label: "Pull Requests (S-14)",
                href: `/projects/${pid}/pull-requests`,
                icon: <GitPullRequestIcon size={16} />,
              },
              {
                label: "Settings (S-10)",
                href: `/projects/${pid}/settings`,
                icon: <SettingsIcon size={16} />,
              },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileNavOpen(false)}
                className="flex items-center gap-3 px-3 py-2.5 rounded-control text-sm text-[var(--fg-1)] hover:bg-[var(--bg-1)] hover:text-[var(--fg-0)] transition-colors"
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
