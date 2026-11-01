"use client";

import React, { useState, useMemo } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { RocketIcon } from "@/components/shell/icons";
import { SAMPLE_LOG_SNIPPET, type DeploymentDiagnosisRequest } from "./types";

interface LogDiagnosisFormProps {
  onDiagnose: (payload: DeploymentDiagnosisRequest) => Promise<void>;
  isLoading: boolean;
}

export function performClientRedactionPreview(rawLog: string): {
  redactedText: string;
  redactionCount: number;
} {
  if (!rawLog) return { redactedText: "", redactionCount: 0 };

  let count = 0;

  // 1. Database & connection strings
  const dbUriRegex = /\b(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp):\/\/[^\s"']+/gi;
  let redacted = rawLog.replace(dbUriRegex, () => {
    count++;
    return "[REDACTED:db_uri]";
  });

  // 2. Sensitive tokens & keys (e.g. Stripe, GitHub PAT, JWT)
  const tokenRegex = /\b(?:sk_live_|sk_test_|ghp_|github_pat_|eyJh)[A-Za-z0-9_\-\.]{10,}\b/g;
  redacted = redacted.replace(tokenRegex, () => {
    count++;
    return "[REDACTED:token]";
  });

  // 3. Env var or config assignments with sensitive variable names
  const assignmentRegex =
    /\b(SECRET|KEY|PASSWORD|TOKEN|CREDENTIAL|AUTH|API_KEY)\s*[:=]\s*(['"]?)(?!\[REDACTED)([^'"\s\r\n]{4,})\2/gi;
  redacted = redacted.replace(assignmentRegex, (_match, varName, quote) => {
    count++;
    return `${varName}=${quote}[REDACTED:secret]${quote}`;
  });

  return { redactedText: redacted, redactionCount: count };
}

export function LogDiagnosisForm({ onDiagnose, isLoading }: LogDiagnosisFormProps) {
  const [rawLog, setRawLog] = useState("");
  const [environment, setEnvironment] = useState("production");
  const [serviceName, setServiceName] = useState("api-web");
  const [configuredEnvVars, setConfiguredEnvVars] = useState("");
  const [exampleEnvContent, setExampleEnvContent] = useState("");
  const [recentChanges, setRecentChanges] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [activeTab, setActiveTab] = useState<"raw" | "preview">("raw");

  const { redactedText, redactionCount } = useMemo(() => {
    return performClientRedactionPreview(rawLog);
  }, [rawLog]);

  const handleFillSample = () => {
    setRawLog(SAMPLE_LOG_SNIPPET);
    setEnvironment("production");
    setServiceName("devmind-api");
    setExampleEnvContent(
      "# Environment Template\nDATABASE_URL=postgresql://localhost:5432/app\nREDIS_URL=redis://localhost:6379\nCLERK_SECRET_KEY=dummy_clerk_secret\nPORT=8000"
    );
    setConfiguredEnvVars("PORT, REDIS_URL, CLERK_SECRET_KEY");
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        setRawLog(content);
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawLog.trim() || isLoading) return;

    const envVarsList = configuredEnvVars
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);

    await onDiagnose({
      raw_log: rawLog,
      environment,
      service_name: serviceName.trim() || undefined,
      configured_env_vars: envVarsList.length > 0 ? envVarsList : undefined,
      example_env_content: exampleEnvContent.trim() || undefined,
      recent_changes: recentChanges.trim() || undefined,
    });
  };

  return (
    <Card className="p-6 border-[var(--border)] bg-[var(--bg-1)]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 pb-4 border-b border-[var(--border)]">
        <div>
          <h2 className="text-lg font-semibold text-[var(--fg-1)] flex items-center gap-2">
            <RocketIcon size={20} className="text-[var(--signal)]" />
            <span>DeployDoctor Log Diagnostics</span>
          </h2>
          <p className="text-xs text-[var(--fg-2)] mt-0.5">
            Deterministic pre-redaction runs locally before transmission. No secret values are ever
            stored or sent to external services.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleFillSample}
            disabled={isLoading}
            className="text-xs"
          >
            Load Sample Log
          </Button>
          <label className="cursor-pointer">
            <span className="inline-flex items-center justify-center font-mono text-xs px-3 py-1.5 rounded-md border border-[var(--border)] hover:bg-[var(--bg-2)] text-[var(--fg-1)] transition-colors">
              Upload .log
            </span>
            <input
              type="file"
              accept=".log,.txt,text/plain"
              onChange={handleFileUpload}
              className="sr-only"
            />
          </label>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Environment & Service Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--fg-2)] mb-1">
              Target Environment
            </label>
            <select
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-md bg-[var(--bg-0)] border border-[var(--border)] text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] font-mono"
            >
              <option value="production">Production</option>
              <option value="staging">Staging</option>
              <option value="preview">Preview / PR</option>
              <option value="development">Local / Dev</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--fg-2)] mb-1">
              Service Name
            </label>
            <Input
              type="text"
              placeholder="e.g. devmind-api, worker, frontend"
              value={serviceName}
              onChange={(e) => setServiceName(e.target.value)}
            />
          </div>
        </div>

        {/* Tab switcher: Raw Input vs Redacted Preview */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveTab("raw")}
                className={`text-xs font-mono px-3 py-1 rounded transition-colors ${
                  activeTab === "raw"
                    ? "bg-[var(--bg-2)] text-[var(--fg-1)] font-semibold border border-[var(--border)]"
                    : "text-[var(--fg-2)] hover:text-[var(--fg-1)]"
                }`}
              >
                Raw Input Log
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("preview")}
                className={`text-xs font-mono px-3 py-1 rounded transition-colors flex items-center gap-1.5 ${
                  activeTab === "preview"
                    ? "bg-[var(--bg-2)] text-[var(--fg-1)] font-semibold border border-[var(--border)]"
                    : "text-[var(--fg-2)] hover:text-[var(--fg-1)]"
                }`}
              >
                <span>Redaction Preview</span>
                {redactionCount > 0 ? (
                  <Badge variant="signal" size="sm">
                    {redactionCount} masked
                  </Badge>
                ) : (
                  <Badge variant="neutral" size="sm">
                    clean
                  </Badge>
                )}
              </button>
            </div>
            {rawLog && (
              <span className="text-[11px] font-mono text-[var(--fg-3)]">
                {rawLog.split("\n").length} lines · {rawLog.length} chars
              </span>
            )}
          </div>

          {activeTab === "raw" ? (
            <textarea
              rows={8}
              value={rawLog}
              onChange={(e) => setRawLog(e.target.value)}
              placeholder="Paste failed deployment or container startup logs here (e.g. from Render, Vercel, Docker, GitHub Actions)..."
              className="w-full px-3 py-2 text-xs font-mono rounded-md bg-[var(--bg-0)] border border-[var(--border)] text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-y"
              required
            />
          ) : (
            <div className="relative">
              <pre className="w-full h-48 overflow-auto px-3 py-2 text-xs font-mono rounded-md bg-[var(--bg-0)] border border-[var(--border)] text-[var(--fg-2)] whitespace-pre-wrap select-text">
                {redactedText || "// No log content pasted yet."}
              </pre>
              <div className="mt-1 text-[11px] text-[var(--fg-3)] flex items-center justify-between">
                <span>All tokens, DB passwords, and secrets are pre-filtered before analysis.</span>
                <span>Deterministic E1 Redactor</span>
              </div>
            </div>
          )}
        </div>

        {/* Advanced Options Toggle */}
        <div className="pt-1">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-xs text-[var(--accent)] hover:underline flex items-center gap-1 font-mono"
          >
            <span>
              {showAdvanced ? "▼ Hide" : "▶ Show"} Environment & Template Comparison Options
            </span>
          </button>
        </div>

        {showAdvanced && (
          <div className="space-y-3 p-4 rounded-md bg-[var(--bg-0)] border border-[var(--border)] animate-fadeIn">
            <div>
              <label className="block text-xs font-medium text-[var(--fg-2)] mb-1">
                Configured Platform Variable Names (Keys only, comma-separated)
              </label>
              <Input
                type="text"
                placeholder="e.g. DATABASE_URL, REDIS_URL, CLERK_SECRET_KEY"
                value={configuredEnvVars}
                onChange={(e) => setConfiguredEnvVars(e.target.value)}
              />
              <span className="text-[11px] text-[var(--fg-3)] mt-0.5 block">
                Never enter secrets. Provide variable names to check for missing settings or typos.
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-[var(--fg-2)] mb-1">
                  Reference .env.example Content
                </label>
                <textarea
                  rows={4}
                  value={exampleEnvContent}
                  onChange={(e) => setExampleEnvContent(e.target.value)}
                  placeholder="DATABASE_URL=&#10;REDIS_URL=&#10;PORT=8000"
                  className="w-full px-3 py-2 text-xs font-mono rounded-md bg-[var(--bg-1)] border border-[var(--border)] text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-y"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--fg-2)] mb-1">
                  Recent Changes or Git Commits (Optional)
                </label>
                <textarea
                  rows={4}
                  value={recentChanges}
                  onChange={(e) => setRecentChanges(e.target.value)}
                  placeholder="e.g. feat(server): upgrade pydantic to v2, changed config schema..."
                  className="w-full px-3 py-2 text-xs font-mono rounded-md bg-[var(--bg-1)] border border-[var(--border)] text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-y"
                />
              </div>
            </div>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            type="submit"
            variant="primary"
            size="default"
            disabled={isLoading || !rawLog.trim()}
            className="flex items-center gap-2"
          >
            <RocketIcon size={16} />
            <span>{isLoading ? "Diagnosing with DeployDoctor..." : "Diagnose Deployment"}</span>
          </Button>
        </div>
      </form>
    </Card>
  );
}
