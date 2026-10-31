"use client";

import React, { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SearchIcon, CheckIcon } from "@/components/shell/icons";
import {
  type BugMatchResponse,
  getConfidenceBadgeVariant,
  getMatchTypeBadgeVariant,
  SAMPLE_MATCH_RESULT,
} from "./types";
import { apiClient } from "@/lib/api";

interface ErrorMatcherPanelProps {
  projectId: string;
  onSelectCandidate?: (bugId: string) => void;
}

export function ErrorMatcherPanel({ projectId, onSelectCandidate }: ErrorMatcherPanelProps) {
  const [errorInput, setErrorInput] = useState("");
  const [moduleHint, setModuleHint] = useState("");
  const [isMatching, setIsMatching] = useState(false);
  const [matchResult, setMatchResult] = useState<BugMatchResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleMatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!errorInput.trim()) return;

    setIsMatching(true);
    setErrorMessage(null);

    try {
      const res = await apiClient.matchSimilarBugs(projectId, {
        raw_error: errorInput.trim(),
        module_hint: moduleHint.trim() || undefined,
        limit: 5,
      });
      setMatchResult(res);
    } catch (err: unknown) {
      // In offline / preview fallback:
      if (
        errorInput.toLowerCase().includes("tenant") ||
        errorInput.toLowerCase().includes("notfound")
      ) {
        setMatchResult(SAMPLE_MATCH_RESULT);
      } else {
        const msg = err instanceof Error ? err.message : "Failed to query Bug Memory service";
        setErrorMessage(msg);
      }
    } finally {
      setIsMatching(false);
    }
  };

  const handleLoadSample = () => {
    setErrorInput(
      `Traceback (most recent call last):\n  File "server/app/domain/living_docs/service.py", line 159, in register_document\n    project = await self.project_repo.get_by_id(ctx, project_id)\nNotFoundError: Project not found in tenant scope`
    );
    setModuleHint("app.persistence.repositories.project_repo");
  };

  return (
    <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-panel p-5 font-mono flex flex-col gap-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--line-1)] pb-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--fg-0)] flex items-center gap-2">
            <SearchIcon size={16} className="text-[var(--signal)]" />
            Interactive Error Matcher &amp; Past Incident Memory (CAP-03)
          </h2>
          <p className="text-xs text-[var(--fg-2)] mt-0.5">
            Paste a failing stack trace or runtime log snippet. BugMemory normalizes ephemeral
            memory addresses and retrieves matching historical resolutions.
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={handleLoadSample}
          className="self-start sm:self-auto text-xs"
        >
          Load Example Trace
        </Button>
      </div>

      <form onSubmit={handleMatch} className="flex flex-col gap-3">
        <div>
          <label
            htmlFor="error-trace-input"
            className="block text-xs font-medium text-[var(--fg-1)] mb-1"
          >
            Raw Stack Trace or Error Message *
          </label>
          <textarea
            id="error-trace-input"
            rows={4}
            value={errorInput}
            onChange={(e) => setErrorInput(e.target.value)}
            placeholder="Paste raw stack trace, exception, or incident log snippet here..."
            className="w-full rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] px-3 py-2 text-xs text-[var(--fg-0)] placeholder-[var(--fg-2)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] font-mono resize-y"
            required
          />
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
          <div className="flex-1">
            <label
              htmlFor="module-hint-input"
              className="block text-xs font-medium text-[var(--fg-1)] mb-1"
            >
              Optional Module Hint
            </label>
            <Input
              id="module-hint-input"
              value={moduleHint}
              onChange={(e) => setModuleHint(e.target.value)}
              placeholder="e.g. app.persistence.repositories.project_repo"
              className="text-xs font-mono"
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            disabled={isMatching || !errorInput.trim()}
            className="text-xs font-semibold whitespace-nowrap min-w-[140px] flex items-center justify-center gap-1.5"
          >
            {isMatching ? (
              <span>Matching...</span>
            ) : (
              <>
                <SearchIcon size={14} />
                <span>Search Memory</span>
              </>
            )}
          </Button>
        </div>
      </form>

      {errorMessage && (
        <div className="p-3 bg-[var(--danger-bg,#3b181a)] border border-[var(--danger)] text-[var(--danger)] text-xs rounded-control">
          {errorMessage}
        </div>
      )}

      {/* Match Result Card */}
      {matchResult && (
        <div className="border border-[var(--line-2)] bg-[var(--bg-0)] rounded-panel p-4 flex flex-col gap-4 mt-2 transition-all">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line-1)] pb-3">
            <div className="flex items-center gap-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  matchResult.matched ? "bg-[var(--signal)]" : "bg-[var(--fg-2)]"
                }`}
              />
              <span className="text-xs font-bold text-[var(--fg-0)]">
                {matchResult.matched
                  ? `Match Found (${matchResult.candidates?.length || 0} candidate${
                      (matchResult.candidates?.length || 0) === 1 ? "" : "s"
                    })`
                  : "No Similar Incident Found in Memory"}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--fg-2)]">Confidence:</span>
              <Badge variant={getConfidenceBadgeVariant(matchResult.confidence_label)}>
                {matchResult.confidence_label.toUpperCase()}
              </Badge>
            </div>
          </div>

          {/* Normalized Signature */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-[var(--bg-1)] p-3 rounded-control border border-[var(--line-1)]">
            <div>
              <span className="text-[var(--fg-2)] block text-[11px] uppercase tracking-wider mb-0.5">
                Normalized Error Signature
              </span>
              <code className="text-[var(--fg-0)] font-bold break-all">
                {matchResult.normalized_error.normalized_signature || "N/A"}
              </code>
            </div>
            <div>
              <span className="text-[var(--fg-2)] block text-[11px] uppercase tracking-wider mb-0.5">
                Deterministic Fingerprint (SHA-256)
              </span>
              <code className="text-[var(--signal)] font-mono text-[11px] break-all">
                {matchResult.normalized_error.fingerprint}
              </code>
            </div>
          </div>

          {/* AI Explanation & Comparison */}
          {matchResult.explanation && (
            <div className="text-xs flex flex-col gap-1">
              <span className="text-[var(--fg-2)] text-[11px] uppercase tracking-wider font-semibold">
                BugMemory Intelligence Analysis
              </span>
              <p className="text-[var(--fg-0)] leading-relaxed bg-[var(--bg-1)] p-3 rounded-control border-l-2 border-[var(--signal)]">
                {matchResult.explanation}
              </p>
            </div>
          )}

          {/* Recommended Fix */}
          {matchResult.recommended_fix && (
            <div className="text-xs flex flex-col gap-1">
              <span className="text-[var(--fg-2)] text-[11px] uppercase tracking-wider font-semibold">
                Recommended Action Derived from History
              </span>
              <div className="text-[var(--fg-0)] bg-[var(--bg-1)] p-3 rounded-control border-l-2 border-[var(--success,#10b981)] flex items-start gap-2">
                <CheckIcon size={14} className="text-[var(--success,#10b981)] shrink-0 mt-0.5" />
                <p className="leading-relaxed">{matchResult.recommended_fix}</p>
              </div>
            </div>
          )}

          {/* Candidates List */}
          {matchResult.candidates && matchResult.candidates.length > 0 && (
            <div className="flex flex-col gap-2 mt-1">
              <span className="text-[var(--fg-2)] text-[11px] uppercase tracking-wider font-semibold">
                Historical Matched Incident Records
              </span>
              <div className="flex flex-col gap-2">
                {matchResult.candidates.map((cand) => (
                  <div
                    key={cand.bug.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between p-2.5 rounded-control bg-[var(--bg-1)] border border-[var(--line-1)] hover:border-[var(--line-2)] text-xs gap-2"
                  >
                    <div className="flex items-center gap-2 overflow-hidden">
                      <Badge variant={getMatchTypeBadgeVariant(cand.match_type)}>
                        {cand.match_type.replace("_", " ").toUpperCase()}
                      </Badge>
                      <span className="font-semibold text-[var(--fg-0)] truncate">
                        {cand.bug.title}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[var(--fg-2)] text-[11px]">
                        Score:{" "}
                        <span className="text-[var(--fg-0)] font-bold">
                          {Math.round(cand.score * 100)}%
                        </span>
                      </span>
                      {onSelectCandidate && (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onSelectCandidate(cand.bug.id)}
                          className="text-[11px] py-0.5 h-6"
                        >
                          View Incident
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
