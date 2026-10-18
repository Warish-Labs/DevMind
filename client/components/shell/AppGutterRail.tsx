"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApp } from "@/context/AppContext";
import {
  OverviewIcon,
  BrainIcon,
  ChatIcon,
  FindingsIcon,
  JobsIcon,
  SettingsIcon,
  FolderIcon,
} from "./icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { WorkspaceProjectSwitcher } from "./WorkspaceProjectSwitcher";

export function AppGutterRail() {
  const pathname = usePathname();
  const { currentWorkspace, currentProject } = useApp();
  const [isSwitcherOpen, setSwitcherOpen] = useState(false);

  const pid = currentProject?.id || "default";

  const navItems = [
    {
      label: "All Projects (S-03)",
      href: "/projects",
      icon: <FolderIcon size={18} />,
      isActive: pathname === "/projects",
    },
    {
      label: "Project Overview (S-04)",
      href: `/projects/${pid}`,
      icon: <OverviewIcon size={18} />,
      isActive:
        pathname === `/projects/${pid}` ||
        (pathname.startsWith("/projects/") && pathname.endsWith(pid)),
    },
    {
      label: "Project Brain Explorer (S-05)",
      href: `/projects/${pid}/brain`,
      icon: <BrainIcon size={18} />,
      isActive: pathname.includes("/brain"),
    },
    {
      label: "AI Project Conversation (S-06)",
      href: `/projects/${pid}/chat`,
      icon: <ChatIcon size={18} />,
      isActive: pathname.includes("/chat"),
    },
    {
      label: "Findings & Security (S-07)",
      href: `/projects/${pid}/findings`,
      icon: <FindingsIcon size={18} />,
      isActive: pathname.includes("/findings"),
    },
    {
      label: "Job Center (S-09)",
      href: `/projects/${pid}/jobs`,
      icon: <JobsIcon size={18} />,
      isActive: pathname.includes("/jobs"),
    },
    {
      label: "Project Settings (S-10)",
      href: `/projects/${pid}/settings`,
      icon: <SettingsIcon size={18} />,
      isActive: pathname.includes("/settings") && !pathname.includes("/workspaces/"),
    },
  ];

  return (
    <aside
      aria-label="App Navigation Rail"
      className="hidden lg:flex fixed left-0 top-0 bottom-0 w-14 z-40 flex-col items-center justify-between border-r border-[var(--line-1)] bg-[var(--bg-0)] py-3 font-mono"
    >
      {/* Top: Workspace Icon & Switcher Trigger */}
      <div className="relative flex flex-col items-center gap-4 w-full">
        <Tooltip content={`Workspace: ${currentWorkspace?.name || "DevMind"}`} position="right">
          <button
            type="button"
            onClick={() => setSwitcherOpen((prev) => !prev)}
            aria-label="Toggle workspace switcher"
            aria-expanded={isSwitcherOpen}
            className="w-9 h-9 rounded-control bg-[var(--bg-1)] border border-[var(--line-2)] hover:border-[var(--signal)] text-[var(--signal)] font-bold text-sm flex items-center justify-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] cursor-pointer"
          >
            {currentWorkspace ? currentWorkspace.name.charAt(0).toUpperCase() : "D"}
          </button>
        </Tooltip>

        {isSwitcherOpen && (
          <WorkspaceProjectSwitcher isGutterRail onClose={() => setSwitcherOpen(false)} />
        )}

        <div className="w-8 border-t border-[var(--line-1)] my-1" />

        {/* Navigation Item Icons */}
        <nav aria-label="Project sections" className="flex flex-col items-center gap-1.5 w-full">
          {navItems.map((item) => {
            const activeClass = item.isActive
              ? "bg-[var(--bg-2)] text-[var(--signal)] border-l-2 border-[var(--signal)]"
              : "text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-1)]";

            return (
              <Tooltip key={item.href} content={item.label} position="right">
                <Link
                  href={item.href}
                  aria-label={item.label}
                  aria-current={item.isActive ? "page" : undefined}
                  className={`w-10 h-10 rounded-control flex items-center justify-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${activeClass}`}
                >
                  {item.icon}
                </Link>
              </Tooltip>
            );
          })}
        </nav>
      </div>

      {/* Bottom: Account & Settings */}
      <div className="flex flex-col items-center gap-2 w-full">
        <div className="w-8 border-t border-[var(--line-1)] my-1" />

        <Tooltip content="Documentation & Specifications" position="right">
          <a
            href="https://github.com/WarishLabs/DevMind"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="DevMind Documentation"
            className="w-10 h-10 rounded-control flex items-center justify-center text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-1)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)]"
          >
            <span className="text-xs font-mono">docs</span>
          </a>
        </Tooltip>

        <Tooltip content="Account & Privacy (S-11)" position="right">
          <Link
            href="/account"
            aria-label="Account and Privacy Settings"
            className="w-8 h-8 rounded-full bg-[var(--bg-2)] border border-[var(--line-2)] flex items-center justify-center text-xs font-bold text-[var(--fg-1)] hover:text-[var(--fg-0)] hover:border-[var(--signal)] transition-colors"
          >
            A
          </Link>
        </Tooltip>
      </div>
    </aside>
  );
}
