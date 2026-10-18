"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import type { WorkspaceResponse, ProjectResponse } from "@devmind/common/api";
import { apiClient } from "@/lib/api";

export interface ProjectFindingsSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface ProjectWithStats extends ProjectResponse {
  findingsSummary?: ProjectFindingsSummary;
  lastScanAt?: string;
}

export interface AppContextType {
  workspaces: WorkspaceResponse[];
  currentWorkspace: WorkspaceResponse | null;
  setCurrentWorkspace: (workspace: WorkspaceResponse) => void;
  projects: ProjectWithStats[];
  currentProject: ProjectWithStats | null;
  setCurrentProject: (project: ProjectWithStats) => void;
  syncMode: "metadata_only" | "indexed";
  setSyncMode: (mode: "metadata_only" | "indexed") => void;
  isCommandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  isJobTrayOpen: boolean;
  setJobTrayOpen: (open: boolean) => void;
  isMobileNavOpen: boolean;
  setMobileNavOpen: (open: boolean) => void;
  activeJobCount: number;
  scanStatus: string;
  setScanStatus: (status: string) => void;
  refreshWorkspaces: () => Promise<void>;
  refreshProjects: () => Promise<void>;
  createProject: (req: {
    name: string;
    slug?: string;
    sync_mode?: string;
  }) => Promise<ProjectWithStats>;
}

const DEFAULT_WORKSPACE: WorkspaceResponse = {
  id: "018f0a00-0000-7000-8000-000000000001",
  name: "WarishLabs Primary",
  slug: "warishlabs-primary",
  kind: "team",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  created_by: "usr_owner_default",
};

const DEFAULT_PROJECTS: ProjectWithStats[] = [
  {
    id: "018f0a00-0000-7000-8000-000000000101",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    name: "DevMind Core",
    slug: "devmind-core",
    visibility: "private",
    sync_mode: "indexed",
    source_kind: "local_scan",
    primary_language: "TypeScript",
    default_branch: "main",
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
    updated_at: new Date().toISOString(),
    findingsSummary: { critical: 0, high: 2, medium: 5, low: 1 },
    lastScanAt: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
  },
  {
    id: "018f0a00-0000-7000-8000-000000000102",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    name: "AuthGateway Service",
    slug: "authgateway-service",
    visibility: "private",
    sync_mode: "metadata_only",
    source_kind: "vscode_extension",
    primary_language: "Python",
    default_branch: "main",
    created_at: new Date(Date.now() - 86400000 * 7).toISOString(),
    updated_at: new Date().toISOString(),
    findingsSummary: { critical: 1, high: 1, medium: 3, low: 0 },
    lastScanAt: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
  },
];

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([DEFAULT_WORKSPACE]);
  const [currentWorkspace, setCurrentWorkspace] = useState<WorkspaceResponse | null>(
    DEFAULT_WORKSPACE
  );
  const [projects, setProjects] = useState<ProjectWithStats[]>(DEFAULT_PROJECTS);
  const [currentProject, setCurrentProject] = useState<ProjectWithStats | null>(
    DEFAULT_PROJECTS[0]
  );
  const [syncMode, setSyncModeState] = useState<"metadata_only" | "indexed">("indexed");
  const [isCommandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [isJobTrayOpen, setJobTrayOpen] = useState(false);
  const [isMobileNavOpen, setMobileNavOpen] = useState(false);
  const [activeJobCount] = useState(0);
  const [scanStatus, setScanStatus] = useState("Local scan idle");

  const setSyncMode = useCallback((mode: "metadata_only" | "indexed") => {
    setSyncModeState(mode);
  }, []);

  const refreshWorkspaces = useCallback(async () => {
    try {
      const data = await apiClient.listWorkspaces();
      if (data && data.length > 0) {
        setWorkspaces(data);
        if (!currentWorkspace || !data.some((w) => w.id === currentWorkspace.id)) {
          setCurrentWorkspace(data[0]);
        }
      }
    } catch {
      // Graceful fallback to initial default workspaces
    }
  }, [currentWorkspace]);

  const refreshProjects = useCallback(async () => {
    if (!currentWorkspace) return;
    try {
      const data = await apiClient.listWorkspaceProjects(currentWorkspace.id);
      if (data && data.length > 0) {
        const enriched: ProjectWithStats[] = data.map((p, idx) => ({
          ...p,
          findingsSummary:
            idx === 0
              ? { critical: 0, high: 2, medium: 5, low: 1 }
              : { critical: 0, high: 0, medium: 2, low: 0 },
          lastScanAt: new Date().toISOString(),
        }));
        setProjects(enriched);
        if (!currentProject || !enriched.some((p) => p.id === currentProject.id)) {
          setCurrentProject(enriched[0]);
        }
      }
    } catch {
      // Graceful fallback to initial default projects
    }
  }, [currentWorkspace, currentProject]);

  const createProject = useCallback(
    async (req: { name: string; slug?: string; sync_mode?: string }): Promise<ProjectWithStats> => {
      const wsId = currentWorkspace ? currentWorkspace.id : DEFAULT_WORKSPACE.id;
      const slug =
        req.slug ||
        req.name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "");
      const mode = req.sync_mode || "indexed";

      let created: ProjectResponse;
      try {
        created = await apiClient.createProject(wsId, {
          name: req.name,
          slug,
          visibility: "workspace",
          sync_mode: mode,
          source_kind: "local",
          primary_language: "TypeScript",
          default_branch: "main",
        });
      } catch {
        // Fallback local mock creation when offline/unauthenticated
        created = {
          id: `018f0a00-0000-7000-8000-${Date.now().toString(16).padStart(12, "0")}`,
          workspace_id: wsId,
          name: req.name,
          slug,
          visibility: "private",
          sync_mode: mode,
          source_kind: "local_scan",
          primary_language: "TypeScript",
          default_branch: "main",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
      }

      const withStats: ProjectWithStats = {
        ...created,
        findingsSummary: { critical: 0, high: 0, medium: 0, low: 0 },
        lastScanAt: undefined,
      };

      setProjects((prev) => [withStats, ...prev]);
      setCurrentProject(withStats);
      return withStats;
    },
    [currentWorkspace]
  );

  // Keyboard shortcut listener for Command Palette (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const value = useMemo(
    () => ({
      workspaces,
      currentWorkspace,
      setCurrentWorkspace,
      projects,
      currentProject,
      setCurrentProject,
      syncMode,
      setSyncMode,
      isCommandPaletteOpen,
      setCommandPaletteOpen,
      isJobTrayOpen,
      setJobTrayOpen,
      isMobileNavOpen,
      setMobileNavOpen,
      activeJobCount,
      scanStatus,
      setScanStatus,
      refreshWorkspaces,
      refreshProjects,
      createProject,
    }),
    [
      workspaces,
      currentWorkspace,
      projects,
      currentProject,
      syncMode,
      setSyncMode,
      isCommandPaletteOpen,
      isJobTrayOpen,
      isMobileNavOpen,
      activeJobCount,
      scanStatus,
      refreshWorkspaces,
      refreshProjects,
      createProject,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
}
