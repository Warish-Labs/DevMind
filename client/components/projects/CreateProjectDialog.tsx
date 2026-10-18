"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

interface CreateProjectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (projectId: string) => void;
}

export function CreateProjectDialog({ isOpen, onClose, onCreated }: CreateProjectDialogProps) {
  const { createProject, currentWorkspace } = useApp();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [syncMode, setSyncMode] = useState<"indexed" | "metadata_only">("indexed");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setName(val);
    setSlug(
      val
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Project name is required");
      return;
    }
    setError(null);
    setIsSubmitting(true);

    try {
      const created = await createProject({
        name: name.trim(),
        slug: slug.trim() || undefined,
        sync_mode: syncMode,
      });
      setName("");
      setSlug("");
      onClose();
      onCreated?.(created.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create project";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Project"
      description={`Add a project to workspace "${currentWorkspace?.name || "DevMind"}". Projects are strictly tenant-isolated at E0.`}
    >
      <form onSubmit={handleSubmit} className="mt-4 space-y-4 font-mono text-xs">
        {error && (
          <div className="p-3 rounded-control border border-[var(--danger)] bg-[var(--danger)]/10 text-[var(--danger)] text-xs">
            {error}
          </div>
        )}

        <div>
          <Input
            label="Project Name"
            placeholder="e.g. Payments Gateway"
            value={name}
            onChange={handleNameChange}
            required
            autoFocus
          />
        </div>

        <div>
          <Input
            label="Project Slug (URL Identifier)"
            placeholder="e.g. payments-gateway"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            helperText="Used in route paths and extension connection manifests"
          />
        </div>

        {/* Sync Mode Selection */}
        <div className="space-y-2">
          <label className="block text-xs font-medium text-[var(--fg-1)]">
            Synchronization Mode
          </label>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setSyncMode("indexed")}
              className={`p-3 rounded-panel border text-left transition-colors cursor-pointer ${
                syncMode === "indexed"
                  ? "border-[var(--signal)] bg-[var(--bg-2)]"
                  : "border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)]"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-[var(--fg-0)]">Indexed Mode</span>
                <Badge variant="signal" size="sm">
                  Recommended
                </Badge>
              </div>
              <p className="text-[11px] text-[var(--fg-2)] leading-normal">
                Full AST, symbols, embeddings, and evidence citations. Enables deep reasoning.
              </p>
            </button>

            <button
              type="button"
              onClick={() => setSyncMode("metadata_only")}
              className={`p-3 rounded-panel border text-left transition-colors cursor-pointer ${
                syncMode === "metadata_only"
                  ? "border-[var(--warn)] bg-[var(--bg-2)]"
                  : "border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)]"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-[var(--fg-0)]">Metadata Only</span>
                <Badge variant="warn" size="sm">
                  Zero Source Text
                </Badge>
              </div>
              <p className="text-[11px] text-[var(--fg-2)] leading-normal">
                Only structural symbols leave your machine. Source code never touches the cloud.
              </p>
            </button>
          </div>
        </div>

        {/* Dialog Actions */}
        <div className="mt-6 flex items-center justify-end gap-3 pt-3 border-t border-[var(--line-1)]">
          <Button type="button" variant="tertiary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : "Create Project"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
