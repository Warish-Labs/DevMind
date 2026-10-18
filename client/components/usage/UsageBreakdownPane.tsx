"use client";

import React, { useState, useMemo } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Tabs,
  TabList,
  TabTrigger,
  Input,
} from "@/components/ui";
import type { TaskUsageBreakdown, ProjectUsageBreakdown } from "./types";

interface UsageBreakdownPaneProps {
  tasks: TaskUsageBreakdown[];
  projects: ProjectUsageBreakdown[];
  totalTokens: number;
}

export function UsageBreakdownPane({ tasks, projects, totalTokens }: UsageBreakdownPaneProps) {
  const [activeTab, setActiveTab] = useState<string>("task");
  const [searchQuery, setSearchQuery] = useState("");

  const formatNumber = (num: number) => num.toLocaleString("en-US");

  const filteredTasks = useMemo(() => {
    if (!searchQuery.trim()) return tasks;
    const q = searchQuery.toLowerCase();
    return tasks.filter((t) => t.task.toLowerCase().includes(q));
  }, [tasks, searchQuery]);

  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const q = searchQuery.toLowerCase();
    return projects.filter(
      (p) => p.projectName.toLowerCase().includes(q) || p.projectId.toLowerCase().includes(q)
    );
  }, [projects, searchQuery]);

  return (
    <Card variant="default" className="space-y-4">
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <CardTitle className="text-base font-semibold">Token Consumption Accounting</CardTitle>
            <p className="text-xs text-[var(--fg-2)] mt-0.5">
              Metered usage across agentic reasoning, code scanning, and AST indexing.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Tabs defaultValue="task" value={activeTab} onValueChange={setActiveTab}>
              <TabList>
                <TabTrigger value="task">By Agent Task</TabTrigger>
                <TabTrigger value="project">By Project</TabTrigger>
              </TabList>
            </Tabs>
          </div>
        </div>

        {/* Filter Input */}
        <div className="pt-2">
          <Input
            id="usage-search-filter"
            type="search"
            placeholder={
              activeTab === "task"
                ? "Filter by task name (e.g., security_scan, ast_indexing)..."
                : "Filter by project name or ID..."
            }
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-md font-mono text-xs"
          />
        </div>
      </CardHeader>

      <CardContent>
        {activeTab === "task" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs" data-testid="task-usage-table">
              <thead>
                <tr className="border-b border-[var(--line-1)] text-[var(--fg-2)] uppercase text-[10px] tracking-wider">
                  <th scope="col" className="py-2.5 px-3">
                    Agent Task
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Invocations
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Prompt Tokens
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Completion Tokens
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Total Tokens
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    % of Usage
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-1)]">
                {filteredTasks.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[var(--fg-2)]">
                      No tasks matched your search query.
                    </td>
                  </tr>
                ) : (
                  filteredTasks.map((t) => {
                    const percent = totalTokens > 0 ? (t.totalTokens / totalTokens) * 100 : 0;
                    return (
                      <tr
                        key={t.task}
                        className="hover:bg-[var(--bg-1)] transition-colors"
                        data-testid={`task-row-${t.task}`}
                      >
                        <td className="py-2.5 px-3 font-medium text-[var(--fg-0)]">
                          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--signal)]">
                            {t.task}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right text-[var(--fg-1)]">{t.jobCount}</td>
                        <td className="py-2.5 px-3 text-right text-[var(--fg-2)]">
                          {formatNumber(t.promptTokens)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-[var(--fg-2)]">
                          {formatNumber(t.completionTokens)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-semibold text-[var(--fg-0)]">
                          {formatNumber(t.totalTokens)}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-[var(--bg-2)] overflow-hidden">
                              <div
                                className="h-full bg-[var(--signal)] rounded-full"
                                style={{ width: `${Math.min(percent, 100)}%` }}
                              />
                            </div>
                            <span className="w-10 text-[var(--fg-1)]">{percent.toFixed(1)}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs" data-testid="project-usage-table">
              <thead>
                <tr className="border-b border-[var(--line-1)] text-[var(--fg-2)] uppercase text-[10px] tracking-wider">
                  <th scope="col" className="py-2.5 px-3">
                    Project
                  </th>
                  <th scope="col" className="py-2.5 px-3">
                    Project ID
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Jobs Executed
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Total Tokens
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Last Active
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    % of Usage
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-1)]">
                {filteredProjects.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[var(--fg-2)]">
                      No projects matched your search query.
                    </td>
                  </tr>
                ) : (
                  filteredProjects.map((p) => {
                    const percent = totalTokens > 0 ? (p.totalTokens / totalTokens) * 100 : 0;
                    return (
                      <tr
                        key={p.projectId}
                        className="hover:bg-[var(--bg-1)] transition-colors"
                        data-testid={`project-row-${p.projectId}`}
                      >
                        <td className="py-2.5 px-3 font-medium text-[var(--fg-0)]">
                          {p.projectName}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--fg-2)] text-[11px]">
                          {p.projectId}
                        </td>
                        <td className="py-2.5 px-3 text-right text-[var(--fg-1)]">{p.jobCount}</td>
                        <td className="py-2.5 px-3 text-right font-semibold text-[var(--fg-0)]">
                          {formatNumber(p.totalTokens)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-[var(--fg-2)] text-[11px]">
                          {p.lastActive}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-[var(--bg-2)] overflow-hidden">
                              <div
                                className="h-full bg-[var(--signal)] rounded-full"
                                style={{ width: `${Math.min(percent, 100)}%` }}
                              />
                            </div>
                            <span className="w-10 text-[var(--fg-1)]">{percent.toFixed(1)}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Privacy & Zero-Retention Notice */}
        <div className="mt-6 p-3 rounded bg-[var(--bg-1)] border border-[var(--line-1)] flex items-start gap-3">
          <span className="w-2 h-2 rounded-full bg-[var(--signal)] mt-1.5 shrink-0" />
          <div className="text-[11px] font-mono text-[var(--fg-2)] leading-relaxed">
            <strong className="text-[var(--fg-0)]">Privacy Disclosure:</strong> DevMind meters token
            counts and duration for accounting and quota enforcement only. Raw prompts, completions,
            code excerpts, and customer secrets are never retained in the usage database per{" "}
            <strong>ADR-047</strong> and <strong>docs/07 §15</strong>.
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
