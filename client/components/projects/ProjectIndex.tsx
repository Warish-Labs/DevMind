"use client";

import React, { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useApp, ProjectWithStats } from "@/context/AppContext";
import { FolderIcon, PlusIcon, SearchIcon, ExternalLinkIcon } from "@/components/shell/icons";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { CreateProjectDialog } from "./CreateProjectDialog";

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Never";
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function ProjectIndex() {
  const router = useRouter();
  const { currentWorkspace, projects, setCurrentProject } = useApp();
  const [searchQuery, setSearchQuery] = useState("");
  const [syncFilter, setSyncFilter] = useState<"all" | "indexed" | "metadata_only">("all");
  const [isCreateOpen, setCreateOpen] = useState(false);

  // Filter projects by search and sync mode
  const filteredProjects = useMemo(() => {
    return projects.filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.primary_language &&
          p.primary_language.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesSync = syncFilter === "all" || p.sync_mode === syncFilter;
      return matchesSearch && matchesSync;
    });
  }, [projects, searchQuery, syncFilter]);

  const handleOpenProject = (project: ProjectWithStats) => {
    setCurrentProject(project);
    router.push(`/projects/${project.id}`);
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* S-03 Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[var(--line-1)]">
        <div>
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-[var(--fg-2)] mb-1">
            <span>Workspace</span>
            <span className="text-[var(--line-3)]">·</span>
            <span className="text-[var(--signal)]">S-03 Project Selection</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[var(--fg-0)] tracking-tight">
            {currentWorkspace?.name || "DevMind Workspace"}
          </h1>
          <p className="text-xs text-[var(--fg-2)] mt-0.5">
            Select a project to explore its Project Brain, run code conversations, and inspect
            evidence-ranked findings.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href="vscode://devmind.devmind-vscode/connect"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control border border-[var(--line-2)] text-[var(--fg-1)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-1)] transition-colors text-xs font-mono"
          >
            <span>Connect VS Code</span>
            <ExternalLinkIcon size={12} className="text-[var(--signal)]" />
          </a>

          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-1.5"
          >
            <PlusIcon size={14} />
            <span>New Project</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <SearchIcon
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fg-2)]"
          />
          <input
            type="text"
            placeholder="Filter projects by name or language..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-control bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--fg-0)] placeholder-[var(--fg-2)] focus:outline-none focus:border-[var(--line-3)]"
          />
        </div>

        {/* Sync Mode Filter Tabs */}
        <div className="flex items-center gap-1 p-1 rounded-control bg-[var(--bg-1)] border border-[var(--line-1)] text-[11px]">
          {(
            [
              { id: "all", label: "All" },
              { id: "indexed", label: "Indexed" },
              { id: "metadata_only", label: "Metadata only" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setSyncFilter(tab.id)}
              className={`px-2.5 py-1 rounded-control transition-colors cursor-pointer ${
                syncFilter === tab.id
                  ? "bg-[var(--bg-2)] text-[var(--signal)] font-medium"
                  : "text-[var(--fg-2)] hover:text-[var(--fg-0)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Empty State */}
      {filteredProjects.length === 0 ? (
        <Card className="text-center py-12 px-4 border-dashed border-[var(--line-2)]">
          <CardHeader>
            <div className="w-12 h-12 mx-auto rounded-full bg-[var(--bg-2)] border border-[var(--line-2)] flex items-center justify-center text-[var(--signal)] mb-3">
              <FolderIcon size={24} />
            </div>
            <CardTitle>Create your first project</CardTitle>
            <CardDescription className="max-w-md mx-auto mt-2">
              No projects match your current filter. Connect your local workspace from the DevMind
              VS Code extension or create a project manually to initialize the Project Brain.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-center gap-3 pt-4">
            <a
              href="vscode://devmind.devmind-vscode/connect"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control border border-[var(--line-2)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] text-xs font-mono text-[var(--fg-0)] transition-colors"
            >
              <span>Connect VS Code</span>
              <ExternalLinkIcon size={14} className="text-[var(--signal)]" />
            </a>
            <Button variant="primary" size="default" onClick={() => setCreateOpen(true)}>
              + Create Project
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Desktop Table View (≥1024px) */}
          <div className="hidden lg:block rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--line-1)] bg-[var(--bg-2)]/60 text-[10px] text-[var(--fg-2)] uppercase tracking-wider">
                  <th className="py-3 px-4 font-semibold">Project</th>
                  <th className="py-3 px-4 font-semibold">Source</th>
                  <th className="py-3 px-4 font-semibold">Sync Mode</th>
                  <th className="py-3 px-4 font-semibold">Last Scan</th>
                  <th className="py-3 px-4 font-semibold">Open Findings</th>
                  <th className="py-3 px-4 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-1)]">
                {filteredProjects.map((project) => {
                  const summary = project.findingsSummary || {
                    critical: 0,
                    high: 0,
                    medium: 0,
                    low: 0,
                  };
                  return (
                    <tr
                      key={project.id}
                      className="hover:bg-[var(--bg-2)]/40 transition-colors group cursor-pointer"
                      onClick={() => handleOpenProject(project)}
                    >
                      {/* Name & Slug */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2.5">
                          <FolderIcon
                            size={16}
                            className="text-[var(--signal)] flex-shrink-0 group-hover:scale-110 transition-transform"
                          />
                          <div>
                            <div className="font-semibold text-xs text-[var(--fg-0)] group-hover:text-[var(--signal)] transition-colors">
                              {project.name}
                            </div>
                            <div className="text-[11px] text-[var(--fg-2)]">
                              {project.slug} · {project.primary_language || "General"}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Source */}
                      <td className="py-3.5 px-4 text-[var(--fg-1)]">
                        <span className="capitalize">{project.source_kind.replace(/_/g, " ")}</span>
                      </td>

                      {/* Sync Mode */}
                      <td className="py-3.5 px-4">
                        <Badge
                          variant={project.sync_mode === "indexed" ? "signal" : "warn"}
                          size="sm"
                        >
                          {project.sync_mode}
                        </Badge>
                      </td>

                      {/* Last Scan */}
                      <td className="py-3.5 px-4 text-[var(--fg-2)]">
                        {formatRelativeTime(project.lastScanAt)}
                      </td>

                      {/* Open Findings by Severity */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {summary.critical > 0 && (
                            <Badge variant="danger" size="sm">
                              {summary.critical} Crit
                            </Badge>
                          )}
                          {summary.high > 0 && (
                            <Badge variant="warn" size="sm">
                              {summary.high} High
                            </Badge>
                          )}
                          {summary.medium > 0 && (
                            <Badge variant="ref" size="sm">
                              {summary.medium} Med
                            </Badge>
                          )}
                          {summary.low > 0 && (
                            <Badge variant="neutral" size="sm">
                              {summary.low} Low
                            </Badge>
                          )}
                          {summary.critical === 0 &&
                            summary.high === 0 &&
                            summary.medium === 0 &&
                            summary.low === 0 && (
                              <span className="text-[11px] text-[var(--fg-2)]">0 open</span>
                            )}
                        </div>
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 text-right">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenProject(project);
                          }}
                        >
                          Open →
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Stacked Rows View (<1024px) */}
          <div className="block lg:hidden space-y-3">
            {filteredProjects.map((project) => {
              const summary = project.findingsSummary || {
                critical: 0,
                high: 0,
                medium: 0,
                low: 0,
              };
              return (
                <div
                  key={project.id}
                  onClick={() => handleOpenProject(project)}
                  className="p-4 rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] hover:border-[var(--line-2)] hover:bg-[var(--bg-2)]/40 transition-colors cursor-pointer space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <FolderIcon size={16} className="text-[var(--signal)] flex-shrink-0" />
                      <div>
                        <div className="font-semibold text-xs text-[var(--fg-0)]">
                          {project.name}
                        </div>
                        <div className="text-[11px] text-[var(--fg-2)]">
                          {project.slug} · {project.primary_language || "General"}
                        </div>
                      </div>
                    </div>
                    <Badge variant={project.sync_mode === "indexed" ? "signal" : "warn"} size="sm">
                      {project.sync_mode}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px] text-[var(--fg-2)] pt-1 border-t border-[var(--line-1)]">
                    <div>
                      <span>Source: </span>
                      <span className="text-[var(--fg-1)] capitalize">
                        {project.source_kind.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div>
                      <span>Last scan: </span>
                      <span className="text-[var(--fg-1)]">
                        {formatRelativeTime(project.lastScanAt)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-[var(--line-1)]">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {summary.critical > 0 && (
                        <Badge variant="danger" size="sm">
                          {summary.critical} Crit
                        </Badge>
                      )}
                      {summary.high > 0 && (
                        <Badge variant="warn" size="sm">
                          {summary.high} High
                        </Badge>
                      )}
                      {summary.medium > 0 && (
                        <Badge variant="ref" size="sm">
                          {summary.medium} Med
                        </Badge>
                      )}
                      {summary.critical === 0 && summary.high === 0 && summary.medium === 0 && (
                        <span className="text-[10px] text-[var(--fg-2)]">0 findings</span>
                      )}
                    </div>

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenProject(project);
                      }}
                    >
                      Open →
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Create Project Modal */}
      <CreateProjectDialog
        isOpen={isCreateOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(newPid) => router.push(`/projects/${newPid}`)}
      />
    </div>
  );
}
