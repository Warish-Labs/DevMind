"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Button,
  Badge,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Input,
} from "../../components/ui";

export type OnboardingStep = 1 | 2 | 3;
export type SyncMode = "metadata_only" | "indexed";

interface OnboardingState {
  workspaceName: string;
  workspaceId: string | null;
  projectName: string;
  projectId: string | null;
  projectSource: "extension" | "manual";
  syncMode: SyncMode;
  consentAgreed: boolean;
}

export default function OnboardingPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<OnboardingStep>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [state, setState] = useState<OnboardingState>({
    workspaceName: "My Workspace",
    workspaceId: "ws_default_personal",
    projectName: "DevMind-Core",
    projectId: "p_core_init",
    projectSource: "extension",
    syncMode: "metadata_only",
    consentAgreed: false,
  });

  const handleStep1Submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!state.workspaceName.trim()) {
      setFormError("Workspace name is required.");
      return;
    }
    setFormError(null);
    setCurrentStep(2);
  };

  const handleStep2Submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!state.projectName.trim()) {
      setFormError("Project name is required.");
      return;
    }
    setFormError(null);
    setCurrentStep(3);
  };

  const handleStep3Submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!state.consentAgreed) {
      setFormError("You must acknowledge the data synchronization consent to proceed.");
      return;
    }
    setFormError(null);
    setIsSubmitting(true);

    // Simulate finalization and redirect to project overview
    setTimeout(() => {
      router.push(`/projects/${state.projectId || "p_core_init"}`);
    }, 600);
  };

  return (
    <div className="min-h-[85vh] flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl flex flex-col gap-8">
        {/* Onboarding Header */}
        <div className="flex flex-col items-center text-center gap-2">
          <Badge variant="signal" mono>
            {`STEP ${currentStep} OF 3 · S-02 ONBOARDING`}
          </Badge>
          <h1 className="text-2xl sm:text-3xl font-semibold text-[var(--fg-0)] tracking-tight">
            Connect your codebase to DevMind
          </h1>
          <p className="text-sm text-[var(--fg-2)] max-w-md">
            Set up your tenant boundaries, link your project source, and choose your
            privacy-preserving sync mode.
          </p>
        </div>

        {/* 3-Step Progress Rail (docs/08 §11 S-02) */}
        <div className="flex items-center justify-between w-full border-b border-[var(--line-1)] pb-4 px-2">
          <div className="flex items-center gap-2">
            <span
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono font-semibold ${
                currentStep >= 1
                  ? "bg-[var(--signal)] text-[var(--bg-0)]"
                  : "bg-[var(--bg-2)] text-[var(--fg-2)]"
              }`}
            >
              1
            </span>
            <span
              className={`text-sm font-medium ${
                currentStep === 1 ? "text-[var(--fg-0)]" : "text-[var(--fg-2)]"
              }`}
            >
              Workspace
            </span>
          </div>

          <div className="w-12 h-px bg-[var(--line-2)]" aria-hidden="true" />

          <div className="flex items-center gap-2">
            <span
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono font-semibold ${
                currentStep >= 2
                  ? "bg-[var(--signal)] text-[var(--bg-0)]"
                  : "bg-[var(--bg-2)] text-[var(--fg-2)]"
              }`}
            >
              2
            </span>
            <span
              className={`text-sm font-medium ${
                currentStep === 2 ? "text-[var(--fg-0)]" : "text-[var(--fg-2)]"
              }`}
            >
              Project Source
            </span>
          </div>

          <div className="w-12 h-px bg-[var(--line-2)]" aria-hidden="true" />

          <div className="flex items-center gap-2">
            <span
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono font-semibold ${
                currentStep === 3
                  ? "bg-[var(--signal)] text-[var(--bg-0)]"
                  : "bg-[var(--bg-2)] text-[var(--fg-2)]"
              }`}
            >
              3
            </span>
            <span
              className={`text-sm font-medium ${
                currentStep === 3 ? "text-[var(--fg-0)]" : "text-[var(--fg-2)]"
              }`}
            >
              Sync &amp; Consent
            </span>
          </div>
        </div>

        {/* Step 1: Workspace Creation / Selection */}
        {currentStep === 1 && (
          <Card variant="elevated" data-testid="onboarding-step-1">
            <CardHeader>
              <CardTitle>1. Create or Choose Workspace</CardTitle>
              <CardDescription>
                Workspaces isolate tenant data, membership, and billing. All repositories and
                findings belong to a workspace.
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleStep1Submit}>
              <CardContent className="flex flex-col gap-4">
                <Input
                  id="workspaceName"
                  label="Workspace Name"
                  placeholder="e.g. Acme Engineering or Personal"
                  value={state.workspaceName}
                  onChange={(e) => {
                    setState((s) => ({ ...s, workspaceName: e.target.value }));
                    if (formError) setFormError(null);
                  }}
                  error={formError || undefined}
                  required
                />
                <div className="p-3 bg-[var(--bg-2)] border border-[var(--line-1)] rounded-[var(--radius-control)] text-xs text-[var(--fg-2)] leading-relaxed">
                  <span className="font-semibold text-[var(--fg-1)]">Tenant Guarantee:</span> Every
                  query, Project Brain chunk, and security finding is strictly partitioned by this
                  workspace ID.
                </div>
              </CardContent>
              <CardFooter>
                <span className="text-xs text-[var(--fg-2)]">Next: Project Source</span>
                <Button type="submit" variant="primary">
                  Continue to Project Source
                </Button>
              </CardFooter>
            </form>
          </Card>
        )}

        {/* Step 2: Project Source (VS Code extension or manual) */}
        {currentStep === 2 && (
          <Card variant="elevated" data-testid="onboarding-step-2">
            <CardHeader>
              <CardTitle>2. Connect Project Source</CardTitle>
              <CardDescription>
                Connect via the VS Code extension for local AST scanning or register a manual
                repository.
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleStep2Submit}>
              <CardContent className="flex flex-col gap-5">
                <Input
                  id="projectName"
                  label="Project Identifier / Name"
                  placeholder="e.g. backend-api or web-client"
                  value={state.projectName}
                  onChange={(e) => {
                    setState((s) => ({ ...s, projectName: e.target.value }));
                    if (formError) setFormError(null);
                  }}
                  error={formError || undefined}
                  required
                />

                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium text-[var(--fg-1)]">
                    Connection Method
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setState((s) => ({ ...s, projectSource: "extension" }))}
                      className={`p-4 rounded-[var(--radius-control)] border text-left flex flex-col gap-1 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
                        state.projectSource === "extension"
                          ? "border-[var(--signal)] bg-[rgba(32,227,162,0.06)]"
                          : "border-[var(--line-2)] bg-[var(--bg-2)] hover:border-[var(--fg-2)]"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-[var(--fg-0)]">
                          VS Code Extension
                        </span>
                        {state.projectSource === "extension" && (
                          <Badge variant="signal">Recommended</Badge>
                        )}
                      </div>
                      <p className="text-xs text-[var(--fg-2)] leading-relaxed mt-1">
                        Scans locally on your machine. Source code stays local by default; syncs
                        findings on demand.
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setState((s) => ({ ...s, projectSource: "manual" }))}
                      className={`p-4 rounded-[var(--radius-control)] border text-left flex flex-col gap-1 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
                        state.projectSource === "manual"
                          ? "border-[var(--signal)] bg-[rgba(32,227,162,0.06)]"
                          : "border-[var(--line-2)] bg-[var(--bg-2)] hover:border-[var(--fg-2)]"
                      }`}
                    >
                      <span className="text-sm font-semibold text-[var(--fg-0)]">
                        Repository Manual Register
                      </span>
                      <p className="text-xs text-[var(--fg-2)] leading-relaxed mt-1">
                        Register repository metadata directly for CI workflows or API analysis jobs.
                      </p>
                    </button>
                  </div>
                </div>

                {state.projectSource === "extension" && (
                  <div className="p-3 bg-[var(--bg-2)] border border-[var(--line-1)] rounded-[var(--radius-control)] flex items-center justify-between gap-3">
                    <div className="text-xs text-[var(--fg-1)]">
                      <p className="font-semibold">VS Code Deep Link</p>
                      <p className="text-[var(--fg-2)]">
                        Link local editor session to this project
                      </p>
                    </div>
                    <a
                      href={`vscode://devmind.devmind-vscode/connect?project=${encodeURIComponent(
                        state.projectName
                      )}`}
                      className="px-3 py-1.5 text-xs bg-[var(--bg-1)] border border-[var(--line-3)] text-[var(--fg-0)] rounded-[var(--radius-control)] hover:bg-[var(--bg-0)] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ref)]"
                    >
                      Open in VS Code
                    </a>
                  </div>
                )}
              </CardContent>
              <CardFooter>
                <Button type="button" variant="secondary" onClick={() => setCurrentStep(1)}>
                  Back
                </Button>
                <Button type="submit" variant="primary">
                  Continue to Privacy &amp; Sync
                </Button>
              </CardFooter>
            </form>
          </Card>
        )}

        {/* Step 3: Synchronization Mode & Consent (docs/08 §11 S-02) */}
        {currentStep === 3 && (
          <Card variant="elevated" data-testid="onboarding-step-3">
            <CardHeader>
              <CardTitle>3. Choose Synchronization Mode &amp; Consent</CardTitle>
              <CardDescription>
                DevMind guarantees clear data boundaries. Source code leaves your machine only with
                recorded consent.
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleStep3Submit}>
              <CardContent className="flex flex-col gap-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Mode 1: metadata_only */}
                  <div
                    onClick={() => setState((s) => ({ ...s, syncMode: "metadata_only" }))}
                    className={`p-4 rounded-[var(--radius-control)] border cursor-pointer flex flex-col justify-between transition-all ${
                      state.syncMode === "metadata_only"
                        ? "border-[var(--signal)] bg-[rgba(32,227,162,0.06)]"
                        : "border-[var(--line-2)] bg-[var(--bg-2)] hover:border-[var(--fg-2)]"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold text-[var(--fg-0)]">
                          metadata_only
                        </span>
                        <Badge variant="signal">Local-First</Badge>
                      </div>
                      <p className="text-xs text-[var(--fg-1)] leading-relaxed mb-3">
                        Only AST symbols, line ranges, and finding IDs leave your machine.
                      </p>
                      <ul className="text-xs text-[var(--fg-2)] space-y-1 list-disc list-inside">
                        <li>Zero raw source code stored on server</li>
                        <li>Rule-based deterministic verification</li>
                        <li>Fastest and completely private</li>
                      </ul>
                    </div>
                  </div>

                  {/* Mode 2: indexed */}
                  <div
                    onClick={() => setState((s) => ({ ...s, syncMode: "indexed" }))}
                    className={`p-4 rounded-[var(--radius-control)] border cursor-pointer flex flex-col justify-between transition-all ${
                      state.syncMode === "indexed"
                        ? "border-[var(--signal)] bg-[rgba(32,227,162,0.06)]"
                        : "border-[var(--line-2)] bg-[var(--bg-2)] hover:border-[var(--fg-2)]"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold text-[var(--fg-0)]">indexed</span>
                        <Badge variant="ref">Deep Reasoning</Badge>
                      </div>
                      <p className="text-xs text-[var(--fg-1)] leading-relaxed mb-3">
                        Chunks and vectors stored in Neon pgvector with tenant isolation.
                      </p>
                      <ul className="text-xs text-[var(--fg-2)] space-y-1 list-disc list-inside">
                        <li>Hybrid search (keyword + vector + symbol)</li>
                        <li>CodeMate context pack synthesis</li>
                        <li>Strict secret redaction before upload</li>
                      </ul>
                    </div>
                  </div>
                </div>

                {/* Consent Checkbox */}
                <div className="p-4 bg-[var(--bg-0)] border border-[var(--line-2)] rounded-[var(--radius-control)] flex flex-col gap-2">
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      id="consentAgreed"
                      checked={state.consentAgreed}
                      onChange={(e) => {
                        setState((s) => ({ ...s, consentAgreed: e.target.checked }));
                        if (formError) setFormError(null);
                      }}
                      className="mt-1 h-4 w-4 rounded-[var(--radius-chip)] border-[var(--line-3)] bg-[var(--bg-2)] text-[var(--signal)] focus:ring-[var(--ref)] focus:ring-offset-[var(--bg-0)]"
                    />
                    <div className="text-xs text-[var(--fg-1)] leading-relaxed">
                      <span className="font-semibold text-[var(--fg-0)]">
                        I consent to synchronization under the selected {state.syncMode} policy.
                      </span>
                      <p className="text-[var(--fg-2)] mt-0.5">
                        DevMind never shares repository code with untrusted third parties. Consent
                        can be revoked at any time in workspace settings, triggering an automated
                        verification purge (NFR-PRV-02).
                      </p>
                    </div>
                  </label>
                  {formError && (
                    <p
                      className="text-xs text-[var(--danger)] flex items-center gap-1 mt-1 font-medium"
                      role="alert"
                    >
                      <span aria-hidden="true">✕</span>
                      <span>{formError}</span>
                    </p>
                  )}
                </div>
              </CardContent>
              <CardFooter>
                <Button type="button" variant="secondary" onClick={() => setCurrentStep(2)}>
                  Back
                </Button>
                <Button type="submit" variant="primary" isLoading={isSubmitting}>
                  Complete Onboarding &amp; Enter DevMind
                </Button>
              </CardFooter>
            </form>
          </Card>
        )}
      </div>
    </div>
  );
}
