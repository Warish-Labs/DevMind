"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { BugIcon } from "@/components/shell/icons";
import {
  type DeploymentDiagnosisResponse,
  getCategoryBadgeVariant,
  formatCategoryLabel,
  formatConfidence,
} from "./types";
import { LogCitationsViewer } from "./LogCitationsViewer";

interface DiagnosisReportViewProps {
  diagnosis: DeploymentDiagnosisResponse;
  rawLog: string;
  onViewIncidentDetail?: (incidentId: string) => void;
  onDocumentResolution?: (incidentId: string) => void;
}

export function DiagnosisReportView({
  diagnosis,
  rawLog,
  onViewIncidentDetail,
  onDocumentResolution,
}: DiagnosisReportViewProps) {
  const categoryVariant = getCategoryBadgeVariant(diagnosis.failure_category);

  return (
    <Card className="p-6 border-[var(--border)] bg-[var(--bg-1)] space-y-6">
      {/* Top Banner / Verdict */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <Badge variant={categoryVariant} size="md">
              {formatCategoryLabel(diagnosis.failure_category)}
            </Badge>
            <Badge variant="signal" size="md">
              {`Confidence: ${formatConfidence(diagnosis.confidence)}`}
            </Badge>
            {diagnosis.is_new_incident ? (
              <Badge variant="neutral" size="sm">
                New Incident
              </Badge>
            ) : (
              <Badge variant="warn" size="sm">
                Recurring Incident
              </Badge>
            )}
            {diagnosis.redaction_count > 0 && (
              <Badge variant="neutral" size="sm">
                {diagnosis.redaction_count} secrets masked
              </Badge>
            )}
          </div>
          <h3 className="text-base font-semibold text-[var(--fg-1)]">{diagnosis.summary}</h3>
          <p className="text-xs text-[var(--fg-2)] mt-0.5">
            Fingerprint:{" "}
            <code className="font-mono text-[var(--fg-3)]">
              {diagnosis.fingerprint.slice(0, 16)}...
            </code>
          </p>
        </div>

        <div className="flex items-center gap-2">
          {onDocumentResolution && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => onDocumentResolution(diagnosis.incident_id)}
              className="text-xs"
            >
              Document Resolution
            </Button>
          )}
          {onViewIncidentDetail && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => onViewIncidentDetail(diagnosis.incident_id)}
              className="text-xs"
            >
              View Record
            </Button>
          )}
        </div>
      </div>

      {/* Insufficient Log Alert */}
      {diagnosis.is_insufficient_log && (
        <div className="p-4 rounded-md bg-[var(--warn)]/10 border border-[var(--warn)]/30 text-xs text-[var(--warn)] space-y-1">
          <div className="font-semibold flex items-center gap-2">
            <span>⚠️ Incomplete Log Output Detected</span>
          </div>
          <p>
            {diagnosis.missing_information_needed ||
              "The log output ends abruptly or is truncated. DeployDoctor recommends providing additional trailing lines or container exit codes."}
          </p>
        </div>
      )}

      {/* Probable Cause & Recommended Action */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-md bg-[var(--bg-0)] border border-[var(--border)]">
          <h4 className="text-xs font-semibold text-[var(--danger)] uppercase tracking-wider mb-2">
            Probable Root Cause
          </h4>
          <p className="text-sm text-[var(--fg-1)] leading-relaxed">{diagnosis.probable_cause}</p>
        </div>

        <div className="p-4 rounded-md bg-[var(--bg-0)] border border-[var(--border)]">
          <h4 className="text-xs font-semibold text-[var(--signal)] uppercase tracking-wider mb-2">
            Recommended Remediation
          </h4>
          <p className="text-sm text-[var(--fg-1)] leading-relaxed">
            {diagnosis.recommended_action}
          </p>
        </div>
      </div>

      {/* Ranked Hypotheses */}
      {diagnosis.hypotheses && diagnosis.hypotheses.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-[var(--fg-2)] uppercase tracking-wider">
            {`Ranked Hypotheses (${diagnosis.hypotheses.length})`}
          </h4>
          <div className="space-y-2.5">
            {diagnosis.hypotheses.map((hyp, i) => (
              <div
                key={i}
                className="p-3.5 rounded-md bg-[var(--bg-0)] border border-[var(--border)] space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-[var(--fg-1)] flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[var(--bg-2)] flex items-center justify-center text-[10px] font-mono text-[var(--fg-2)]">
                      {i + 1}
                    </span>
                    <span>{hyp.probable_cause}</span>
                  </span>
                  <Badge
                    variant={
                      hyp.confidence >= 0.7 ? "signal" : hyp.confidence >= 0.4 ? "warn" : "neutral"
                    }
                    size="sm"
                  >
                    {`${Math.round(hyp.confidence * 100)}% likelihood`}
                  </Badge>
                </div>

                {hyp.log_line_citations && hyp.log_line_citations.length > 0 && (
                  <div className="text-xs text-[var(--fg-2)] pl-7 font-mono flex items-center gap-1.5">
                    <span className="text-[var(--fg-3)]">Cited Lines:</span>
                    {hyp.log_line_citations.map((line) => (
                      <span
                        key={line}
                        className="px-1.5 py-0.5 rounded bg-[var(--bg-2)] text-[var(--fg-1)] text-[11px]"
                      >
                        Line {line + 1}
                      </span>
                    ))}
                  </div>
                )}

                <div className="pl-7 text-xs text-[var(--accent)] font-medium">
                  → Action: {hyp.recommended_action}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Embedded Citations Viewer */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-semibold text-[var(--fg-2)] uppercase tracking-wider">
            Log Citations & Evidence Analysis
          </h4>
        </div>
        <LogCitationsViewer
          logSnippet={rawLog}
          primaryLogLine={diagnosis.primary_log_line}
          referencedFiles={diagnosis.referenced_files}
          referencedEnvVars={diagnosis.referenced_env_vars}
          envVarCheck={diagnosis.env_var_check}
        />
      </div>

      {/* Similar Historical Incidents */}
      {diagnosis.similar_past_incidents && diagnosis.similar_past_incidents.length > 0 && (
        <div className="space-y-3 pt-2">
          <h4 className="text-xs font-semibold text-[var(--fg-2)] uppercase tracking-wider flex items-center gap-1.5">
            <BugIcon size={14} className="text-[var(--warn)]" />
            <span>{`Similar Past Incidents (${diagnosis.similar_past_incidents.length})`}</span>
          </h4>
          <div className="space-y-2">
            {diagnosis.similar_past_incidents.map((past) => (
              <div
                key={past.incident_id}
                className="p-3 rounded-md bg-[var(--bg-0)] border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-[var(--fg-1)]">{past.summary}</span>
                    <Badge variant={getCategoryBadgeVariant(past.failure_category)} size="sm">
                      {past.failure_category}
                    </Badge>
                    <span className="text-[11px] font-mono text-[var(--fg-3)]">
                      Match: {past.match_type}
                    </span>
                  </div>
                  {past.resolution ? (
                    <p className="text-xs text-[var(--signal)]">
                      {`Proven fix: ${past.resolution}`}
                    </p>
                  ) : (
                    <p className="text-xs text-[var(--fg-3)]">No documented resolution yet</p>
                  )}
                </div>
                <Badge variant="signal" size="sm">
                  {`${Math.round(past.similarity_score * 100)}% match`}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
