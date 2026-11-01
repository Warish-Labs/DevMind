"use client";

import React, { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import type { EnvVarCheckResultSchema } from "./types";

interface LogCitationsViewerProps {
  logSnippet: string;
  primaryLogLine?: number | null;
  referencedFiles?: Array<{
    file_path?: string;
    line_number?: number;
    function_name?: string;
    [key: string]: unknown;
  }>;
  referencedEnvVars?: string[];
  envVarCheck?: EnvVarCheckResultSchema | null;
}

export function LogCitationsViewer({
  logSnippet,
  primaryLogLine,
  referencedFiles = [],
  referencedEnvVars = [],
  envVarCheck,
}: LogCitationsViewerProps) {
  const [activeTab, setActiveTab] = useState<"log" | "env" | "code">("log");

  const lines = logSnippet ? logSnippet.split("\n") : [];

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--bg-0)] overflow-hidden">
      {/* Header & Sub-navigation */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--bg-1)] border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("log")}
            className={`px-2.5 py-1 text-xs font-mono rounded transition-colors ${
              activeTab === "log"
                ? "bg-[var(--bg-2)] text-[var(--fg-1)] font-medium border border-[var(--border)]"
                : "text-[var(--fg-2)] hover:text-[var(--fg-1)]"
            }`}
          >
            {`Log Citations (${lines.length} lines)`}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("env")}
            className={`px-2.5 py-1 text-xs font-mono rounded transition-colors flex items-center gap-1.5 ${
              activeTab === "env"
                ? "bg-[var(--bg-2)] text-[var(--fg-1)] font-medium border border-[var(--border)]"
                : "text-[var(--fg-2)] hover:text-[var(--fg-1)]"
            }`}
          >
            <span>Environment Variables</span>
            {referencedEnvVars.length > 0 && (
              <Badge variant="neutral" size="sm">
                {referencedEnvVars.length}
              </Badge>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("code")}
            className={`px-2.5 py-1 text-xs font-mono rounded transition-colors flex items-center gap-1.5 ${
              activeTab === "code"
                ? "bg-[var(--bg-2)] text-[var(--fg-1)] font-medium border border-[var(--border)]"
                : "text-[var(--fg-2)] hover:text-[var(--fg-1)]"
            }`}
          >
            <span>Referenced Stack Frames</span>
            {referencedFiles.length > 0 && (
              <Badge variant="neutral" size="sm">
                {referencedFiles.length}
              </Badge>
            )}
          </button>
        </div>

        {primaryLogLine !== undefined && primaryLogLine !== null && (
          <span className="text-[11px] font-mono text-[var(--warn)]">
            {`Primary failure focus: Line ${primaryLogLine + 1}`}
          </span>
        )}
      </div>

      {/* Tab 1: Cited Log Lines */}
      {activeTab === "log" && (
        <div className="overflow-x-auto max-h-80 select-text font-mono text-xs p-2">
          {lines.length === 0 ? (
            <div className="p-4 text-center text-xs text-[var(--fg-3)]">
              No log snippet available.
            </div>
          ) : (
            <table className="w-full border-collapse">
              <tbody>
                {lines.map((line, idx) => {
                  const isPrimary = primaryLogLine === idx;
                  const isError =
                    line.includes("ERROR") ||
                    line.includes("ValidationError") ||
                    line.includes("CRITICAL") ||
                    line.includes("FAILED");

                  return (
                    <tr
                      key={idx}
                      className={`${
                        isPrimary
                          ? "bg-[var(--warn)]/15 border-l-4 border-l-[var(--warn)]"
                          : isError
                            ? "bg-[var(--danger)]/10"
                            : "hover:bg-[var(--bg-1)]"
                      } transition-colors`}
                    >
                      <td className="px-2 py-0.5 text-right text-[11px] text-[var(--fg-3)] select-none w-12 border-r border-[var(--border)]">
                        {idx + 1}
                      </td>
                      <td className="px-3 py-0.5 whitespace-pre font-mono text-[var(--fg-1)]">
                        {isPrimary && (
                          <span className="inline-block text-[10px] uppercase font-bold text-[var(--warn)] mr-2 select-none">
                            ▶ CAUSE
                          </span>
                        )}
                        {line}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab 2: Environment Variables & Typos */}
      {activeTab === "env" && (
        <div className="p-4 space-y-4">
          <div>
            <h4 className="text-xs font-semibold text-[var(--fg-2)] uppercase tracking-wider mb-2">
              Referenced in Log or Stack Trace
            </h4>
            {referencedEnvVars.length === 0 ? (
              <p className="text-xs text-[var(--fg-3)]">
                No environment variables explicitly detected.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {referencedEnvVars.map((v) => (
                  <span
                    key={v}
                    className="font-mono text-xs px-2.5 py-1 rounded bg-[var(--bg-1)] border border-[var(--border)] text-[var(--accent)]"
                  >
                    {v}
                  </span>
                ))}
              </div>
            )}
          </div>

          {envVarCheck && (
            <div className="space-y-3 pt-3 border-t border-[var(--border)]">
              {envVarCheck.missing_required && envVarCheck.missing_required.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-[var(--danger)] uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                    <span>Missing Required Variables</span>
                    <Badge variant="danger" size="sm">
                      {envVarCheck.missing_required.length}
                    </Badge>
                  </h4>
                  <ul className="space-y-1">
                    {envVarCheck.missing_required.map((v) => (
                      <li
                        key={v}
                        className="text-xs font-mono text-[var(--danger)] bg-[var(--danger)]/10 px-2 py-1 rounded flex items-center justify-between"
                      >
                        <span>{v}</span>
                        <span className="text-[11px] text-[var(--fg-3)]">Not configured</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {envVarCheck.suspected_typos && envVarCheck.suspected_typos.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-[var(--warn)] uppercase tracking-wider mb-1.5">
                    Suggested Typo Corrections
                  </h4>
                  <div className="space-y-1.5">
                    {envVarCheck.suspected_typos.map((cand, i) => {
                      const refName = (cand.referenced_name as string) || "variable";
                      const templName = (cand.template_name as string) || "template_var";
                      const sim = typeof cand.similarity === "number" ? cand.similarity : 0.8;

                      return (
                        <div
                          key={i}
                          className="text-xs font-mono p-2 rounded bg-[var(--bg-1)] border border-[var(--border)] flex items-center justify-between"
                        >
                          <div>
                            <span className="text-[var(--danger)]">{refName}</span>
                            <span className="text-[var(--fg-3)] mx-2">→</span>
                            <span className="text-[var(--signal)] font-semibold">{templName}</span>
                          </div>
                          <Badge variant="warn" size="sm">
                            {`${Math.round(sim * 100)}% match`}
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {envVarCheck.valid_configured && envVarCheck.valid_configured.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-[var(--fg-3)] uppercase tracking-wider mb-1">
                    {`Configured Variables Verified (${envVarCheck.valid_configured.length})`}
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {envVarCheck.valid_configured.map((v) => (
                      <span
                        key={v}
                        className="font-mono text-[11px] px-2 py-0.5 rounded bg-[var(--bg-1)] text-[var(--fg-3)] border border-[var(--border)]"
                      >
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Stack Trace Frames */}
      {activeTab === "code" && (
        <div className="p-4">
          {referencedFiles.length === 0 ? (
            <p className="text-xs text-[var(--fg-3)]">
              No project source files detected in log trace.
            </p>
          ) : (
            <div className="space-y-2">
              {referencedFiles.map((frame, i) => (
                <div
                  key={i}
                  className="p-3 rounded-md bg-[var(--bg-1)] border border-[var(--border)] font-mono text-xs flex items-center justify-between"
                >
                  <div>
                    <span className="text-[var(--fg-1)] font-medium">{frame.file_path}</span>
                    {frame.line_number && (
                      <span className="text-[var(--accent)] ml-2">:{frame.line_number}</span>
                    )}
                    {frame.function_name && (
                      <span className="text-[var(--fg-3)] ml-2">in {frame.function_name}()</span>
                    )}
                  </div>
                  <Badge variant="neutral" size="sm">
                    Frame #{i + 1}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
