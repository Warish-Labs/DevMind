"use client";

import React from "react";
import { AppProvider } from "@/context/AppContext";
import { AppGutterRail } from "./AppGutterRail";
import { AppTopBar } from "./AppTopBar";
import { AppStatusBar } from "./AppStatusBar";
import { CommandPalette } from "./CommandPalette";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <AppProvider>
      <div className="min-h-screen flex flex-col bg-[var(--bg-0)] text-[var(--fg-0)] selection:bg-[var(--signal)] selection:text-[var(--bg-0)]">
        {/* Left 56px Gutter Rail on Desktop */}
        <AppGutterRail />

        {/* Main Application Area (offset by gutter rail on lg screens) */}
        <div className="flex-1 flex flex-col lg:pl-14 pb-7">
          <AppTopBar />

          <div
            id="app-main"
            role="region"
            aria-label="Application content"
            className="flex-1 w-full p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto"
          >
            {children}
          </div>

          <AppStatusBar />
        </div>

        {/* Global Accessible Command Palette (Cmd+K) */}
        <CommandPalette />
      </div>
    </AppProvider>
  );
}
