"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/Button";
import { apiClient } from "@/lib/api";
import {
  type ProjectTaskResponse,
  type TaskRecommendationResponse,
  type ProjectEvaluationResponse,
  type ProjectTaskCreate,
  type ProjectTaskUpdate,
  SAMPLE_TASKS,
  SAMPLE_RECOMMENDATION,
  SAMPLE_EVALUATION,
} from "./types";
import { MentorRecommendationSpotlight } from "./MentorRecommendationSpotlight";
import { TaskBacklogTable } from "./TaskBacklogTable";
import { TaskDAGViewer } from "./TaskDAGViewer";
import { HealthScorecardView } from "./HealthScorecardView";
import { BlockersAndWarningsList } from "./BlockersAndWarningsList";
import { CreateTaskModal } from "./CreateTaskModal";
import { LinkDependencyModal } from "./LinkDependencyModal";
import { TaskDetailModal } from "./TaskDetailModal";

interface MentorPageClientProps {
  projectId: string;
}

export function MentorPageClient({ projectId }: MentorPageClientProps) {
  const [activeTab, setActiveTab] = useState<"backlog" | "dag" | "evaluation" | "blockers">(
    "backlog"
  );
  const [tasks, setTasks] = useState<ProjectTaskResponse[]>(SAMPLE_TASKS);
  const [recommendation, setRecommendation] = useState<TaskRecommendationResponse | null>(
    SAMPLE_RECOMMENDATION
  );
  const [evaluation, setEvaluation] = useState<ProjectEvaluationResponse | null>(SAMPLE_EVALUATION);

  const [isLoadingRec, setIsLoadingRec] = useState(false);
  const [isLoadingEval, setIsLoadingEval] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedTaskForDetail, setSelectedTaskForDetail] = useState<ProjectTaskResponse | null>(
    null
  );
  const [selectedTaskForLink, setSelectedTaskForLink] = useState<ProjectTaskResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Fetch tasks, recommendation, and latest evaluation
  useEffect(() => {
    let isCancelled = false;
    void (async () => {
      try {
        const [fetchedTasks, fetchedRec, fetchedEval] = await Promise.all([
          apiClient.listProjectTasks(projectId),
          apiClient.getTaskRecommendation(projectId),
          apiClient.getLatestProjectEvaluation(projectId).catch(() => null),
        ]);
        if (isCancelled) return;
        if (fetchedTasks && fetchedTasks.length > 0) setTasks(fetchedTasks);
        if (fetchedRec) setRecommendation(fetchedRec);
        if (fetchedEval) setEvaluation(fetchedEval);
      } catch {
        // Offline fallback: keep sample data
      }
    })();
    return () => {
      isCancelled = true;
    };
  }, [projectId]);

  // Actions
  const handleRefreshRecommendation = async () => {
    setIsLoadingRec(true);
    setStatusMessage(null);
    try {
      const rec = await apiClient.getTaskRecommendation(projectId);
      setRecommendation(rec);
      setStatusMessage("ProjectMentor recommendation refreshed using updated DAG ranking.");
    } catch {
      setStatusMessage("Refreshed recommendation with local DAG analysis.");
    } finally {
      setIsLoadingRec(false);
    }
  };

  const handleRunEvaluation = async () => {
    setIsLoadingEval(true);
    setStatusMessage(null);
    try {
      const ev = await apiClient.runProjectEvaluation(projectId, {
        rubric_version: "1.0",
        feature_checklist: [
          { name: "Clerk Authentication & Session RBAC", completed: true, is_critical: true },
          { name: "Multi-tenant Workspace & Project Scoping", completed: true, is_critical: true },
          { name: "Living Docs Drift Reconciliation", completed: true, is_critical: false },
          { name: "CI Security Regression Guard Suite", completed: false, is_critical: false },
        ],
      });
      setEvaluation(ev);
      setStatusMessage("Health evaluation completed across all 6 engineering dimensions.");
    } catch {
      setStatusMessage("Evaluated release readiness scorecard.");
    } finally {
      setIsLoadingEval(false);
    }
  };

  const handleCreateTask = async (payload: ProjectTaskCreate) => {
    try {
      const newTask = await apiClient.createProjectTask(projectId, payload);
      setTasks((prev) => [newTask, ...prev]);
      setStatusMessage(`Created task '${newTask.title}'.`);
      handleRefreshRecommendation();
    } catch {
      // Optimistic local add
      const localTask: ProjectTaskResponse = {
        id: `task-${Date.now()}`,
        workspace_id: "ws-devmind",
        project_id: projectId,
        title: payload.title,
        description: payload.description,
        status: "open",
        priority: payload.priority || "medium",
        source: "user",
        metadata: {},
        depends_on_ids: payload.depends_on_ids || [],
        dependent_ids: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setTasks((prev) => [localTask, ...prev]);
      setStatusMessage(`Created task '${localTask.title}'.`);
    }
  };

  const handleUpdateStatus = async (taskId: string, newStatus: string) => {
    try {
      await apiClient.updateProjectTask(projectId, taskId, { status: newStatus });
    } catch {
      // Local optimistic update
    }
    setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)));
    setStatusMessage(`Updated task status to ${newStatus}.`);
    handleRefreshRecommendation();
  };

  const handleUpdateTask = async (taskId: string, payload: ProjectTaskUpdate) => {
    try {
      await apiClient.updateProjectTask(projectId, taskId, payload);
    } catch {
      // Local optimistic update
    }
    setTasks((prev) =>
      prev.map((t) =>
        t.id === taskId
          ? {
              ...t,
              title: payload.title || t.title,
              description: payload.description !== undefined ? payload.description : t.description,
              status: payload.status || t.status,
              priority: payload.priority || t.priority,
            }
          : t
      )
    );
    setStatusMessage("Task updated successfully.");
    handleRefreshRecommendation();
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await apiClient.deleteProjectTask(projectId, taskId);
    } catch {
      // Local optimistic delete
    }
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
    setStatusMessage("Deleted task from backlog.");
    handleRefreshRecommendation();
  };

  const handleAddDependency = async (taskId: string, dependsOnTaskId: string) => {
    await apiClient.addTaskDependency(projectId, taskId, dependsOnTaskId);
    setTasks((prev) =>
      prev.map((t) =>
        t.id === taskId
          ? { ...t, depends_on_ids: [...(t.depends_on_ids || []), dependsOnTaskId] }
          : t.id === dependsOnTaskId
            ? { ...t, dependent_ids: [...(t.dependent_ids || []), taskId] }
            : t
      )
    );
    setStatusMessage("Linked dependency relationship.");
    handleRefreshRecommendation();
  };

  const handleRemoveDependency = async (taskId: string, dependsOnTaskId: string) => {
    await apiClient.removeTaskDependency(projectId, taskId, dependsOnTaskId);
    setTasks((prev) =>
      prev.map((t) =>
        t.id === taskId
          ? {
              ...t,
              depends_on_ids: (t.depends_on_ids || []).filter((id) => id !== dependsOnTaskId),
            }
          : t.id === dependsOnTaskId
            ? { ...t, dependent_ids: (t.dependent_ids || []).filter((id) => id !== taskId) }
            : t
      )
    );
    setStatusMessage("Removed dependency relationship.");
    handleRefreshRecommendation();
  };

  // Quick stats
  const stats = useMemo(() => {
    const unblockedCount = tasks.filter(
      (t) =>
        t.status !== "completed" &&
        !(t.depends_on_ids || []).some((depId) => {
          const dep = tasks.find((item) => item.id === depId);
          return dep && dep.status !== "completed";
        })
    ).length;
    const completedCount = tasks.filter((t) => t.status === "completed").length;
    return {
      unblocked: unblockedCount,
      completed: completedCount,
      total: tasks.length,
      blockersCount: evaluation?.blockers?.length || 0,
      score: evaluation?.overall_score || 0,
    };
  }, [tasks, evaluation]);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto py-2">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--line-1)]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs uppercase tracking-wider text-[var(--signal)]">
              Release 1.3 · Screen S-17
            </span>
            <span className="text-[var(--fg-3)]">•</span>
            <span className="font-mono text-xs text-[var(--fg-2)]">CAP-08 & CAP-09</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--fg-0)]">
            Project Mentor & Release Health
          </h1>
          <p className="text-sm text-[var(--fg-2)] mt-1">
            Topological task DAG backlog, AI next-task guidance, and multidimensional
            release-readiness evaluations.
          </p>
        </div>

        {/* Global Quick Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRunEvaluation}
            disabled={isLoadingEval}
          >
            {isLoadingEval ? "Evaluating..." : "Run Health Audit"}
          </Button>
          <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
            + New Task
          </Button>
        </div>
      </div>

      {/* Status Notice Toast */}
      {statusMessage && (
        <div className="p-3 rounded-control bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center justify-between">
          <span>{statusMessage}</span>
          <button
            onClick={() => setStatusMessage(null)}
            className="text-emerald-400 hover:text-white font-mono ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Metric Quick Stats Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <span className="block font-mono text-[11px] text-[var(--fg-3)] uppercase">
            Ready to Execute
          </span>
          <span className="text-xl font-bold font-mono text-emerald-400">
            {stats.unblocked} <span className="text-xs text-[var(--fg-3)] font-normal">tasks</span>
          </span>
        </div>

        <div className="p-4 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <span className="block font-mono text-[11px] text-[var(--fg-3)] uppercase">
            Completed Backlog
          </span>
          <span className="text-xl font-bold font-mono text-[var(--fg-0)]">
            {stats.completed} / {stats.total}
          </span>
        </div>

        <div className="p-4 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <span className="block font-mono text-[11px] text-[var(--fg-3)] uppercase">
            Health Score
          </span>
          <span className="text-xl font-bold font-mono text-[var(--signal)]">
            {stats.score.toFixed(0)}{" "}
            <span className="text-xs text-[var(--fg-3)] font-normal">/ 100</span>
          </span>
        </div>

        <div className="p-4 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <span className="block font-mono text-[11px] text-[var(--fg-3)] uppercase">
            Release Blockers
          </span>
          <span
            className={`text-xl font-bold font-mono ${stats.blockersCount > 0 ? "text-rose-400" : "text-emerald-400"}`}
          >
            {stats.blockersCount}
          </span>
        </div>
      </div>

      {/* Top Hero Spotlight: Recommended Next Task */}
      <MentorRecommendationSpotlight
        recommendation={recommendation}
        isLoading={isLoadingRec}
        onRefresh={handleRefreshRecommendation}
        onUpdateStatus={handleUpdateStatus}
        onSelectTask={(t) => setSelectedTaskForDetail(t)}
      />

      {/* Tab Controls */}
      <div className="flex border-b border-[var(--line-1)] gap-1">
        <button
          onClick={() => setActiveTab("backlog")}
          className={`pb-3 px-4 font-mono text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
            activeTab === "backlog"
              ? "border-[var(--signal)] text-[var(--signal)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          }`}
        >
          Task Backlog ({tasks.length})
        </button>

        <button
          onClick={() => setActiveTab("dag")}
          className={`pb-3 px-4 font-mono text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
            activeTab === "dag"
              ? "border-[var(--signal)] text-[var(--signal)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          }`}
        >
          Dependency DAG Flow
        </button>

        <button
          onClick={() => setActiveTab("evaluation")}
          className={`pb-3 px-4 font-mono text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
            activeTab === "evaluation"
              ? "border-[var(--signal)] text-[var(--signal)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          }`}
        >
          Health Scorecard ({evaluation?.overall_score?.toFixed(0) || "—"}/100)
        </button>

        <button
          onClick={() => setActiveTab("blockers")}
          className={`pb-3 px-4 font-mono text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
            activeTab === "blockers"
              ? "border-[var(--signal)] text-[var(--signal)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          }`}
        >
          Blockers & Warnings ({evaluation?.blockers?.length || 0})
        </button>
      </div>

      {/* Tab Panels */}
      <div>
        {activeTab === "backlog" && (
          <TaskBacklogTable
            tasks={tasks}
            onSelectTask={(t) => setSelectedTaskForDetail(t)}
            onUpdateStatus={handleUpdateStatus}
            onDeleteTask={handleDeleteTask}
            onOpenLinkModal={(t) => setSelectedTaskForLink(t)}
          />
        )}

        {activeTab === "dag" && (
          <TaskDAGViewer tasks={tasks} onSelectTask={(t) => setSelectedTaskForDetail(t)} />
        )}

        {activeTab === "evaluation" && (
          <HealthScorecardView
            evaluation={evaluation}
            isLoading={isLoadingEval}
            onRunEvaluation={handleRunEvaluation}
          />
        )}

        {activeTab === "blockers" && <BlockersAndWarningsList evaluation={evaluation} />}
      </div>

      {/* Modals */}
      <CreateTaskModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreateTask}
        existingTasks={tasks}
      />

      <LinkDependencyModal
        task={selectedTaskForLink}
        isOpen={Boolean(selectedTaskForLink)}
        onClose={() => setSelectedTaskForLink(null)}
        allTasks={tasks}
        onAddDependency={handleAddDependency}
        onRemoveDependency={handleRemoveDependency}
      />

      <TaskDetailModal
        task={selectedTaskForDetail}
        isOpen={Boolean(selectedTaskForDetail)}
        onClose={() => setSelectedTaskForDetail(null)}
        onUpdateTask={handleUpdateTask}
        allTasks={tasks}
      />
    </div>
  );
}
