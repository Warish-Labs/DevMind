import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  DeploymentPageClient,
  LogDiagnosisForm,
  performClientRedactionPreview,
  LogCitationsViewer,
  DiagnosisReportView,
  IncidentsHistoryTable,
  IncidentDetailModal,
  DocumentResolutionModal,
  SAMPLE_INCIDENTS,
  SAMPLE_DIAGNOSIS_RESPONSE,
  SAMPLE_LOG_SNIPPET,
} from "../components/deployment";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/deployments",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M12-16: Deployment Diagnosis Web Screens & Incident Ledger (Screen S-18)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("Client Redaction Pre-filter (performClientRedactionPreview)", () => {
    it("redacts database connection strings and sensitive variable assignments", () => {
      const input = `
        DATABASE_URL=postgresql://user:pass123@db.example.com:5432/production
        REDIS_URL=redis://default:myredispass@redis.example.com:6379/0
        CLERK_SECRET_KEY=dummy_mock_secret_key_12345
        Normal log text without secrets
      `;

      const { redactedText, redactionCount } = performClientRedactionPreview(input);

      expect(redactionCount).toBeGreaterThanOrEqual(2);
      expect(redactedText).toContain("[REDACTED:db_uri]");
      expect(redactedText).not.toContain("pass123");
      expect(redactedText).not.toContain("myredispass");
    });

    it("returns clean response when no secrets present", () => {
      const input = "Starting web service on port 8000\nCompilation completed in 2.3s";
      const { redactedText, redactionCount } = performClientRedactionPreview(input);

      expect(redactionCount).toBe(0);
      expect(redactedText).toBe(input);
    });
  });

  describe("LogDiagnosisForm", () => {
    it("renders form controls, sample button, environment selector, and diagnosis CTA", () => {
      const html = renderToString(<LogDiagnosisForm onDiagnose={vi.fn()} isLoading={false} />);

      expect(html).toContain("DeployDoctor Log Diagnostics");
      expect(html).toContain("Load Sample Log");
      expect(html).toContain("Upload .log");
      expect(html).toContain("Target Environment");
      expect(html).toContain("Production");
      expect(html).toContain("Staging");
      expect(html).toContain("Service Name");
      expect(html).toContain("Raw Input Log");
      expect(html).toContain("Redaction Preview");
      expect(html).toContain("Diagnose Deployment");
    });

    it("displays loading state when diagnosis is in flight", () => {
      const html = renderToString(<LogDiagnosisForm onDiagnose={vi.fn()} isLoading={true} />);

      expect(html).toContain("Diagnosing with DeployDoctor...");
    });
  });

  describe("LogCitationsViewer", () => {
    it("renders log lines with primary failure focus indicator and citations", () => {
      const html = renderToString(
        <LogCitationsViewer
          logSnippet={SAMPLE_LOG_SNIPPET}
          primaryLogLine={1}
          referencedFiles={SAMPLE_DIAGNOSIS_RESPONSE.referenced_files}
          referencedEnvVars={SAMPLE_DIAGNOSIS_RESPONSE.referenced_env_vars}
          envVarCheck={SAMPLE_DIAGNOSIS_RESPONSE.env_var_check}
        />
      );

      expect(html).toContain("Log Citations");
      expect(html).toContain("Environment Variables");
      expect(html).toContain("Referenced Stack Frames");
      expect(html).toContain("Primary failure focus: Line 2");
      expect(html).toContain("pydantic_core._pydantic_core.ValidationError");
      expect(html).toContain("DATABASE_URL");
    });
  });

  describe("DiagnosisReportView", () => {
    it("renders category badge, confidence meter, summary, probable cause, and ranked hypotheses", () => {
      const html = renderToString(
        <DiagnosisReportView
          diagnosis={SAMPLE_DIAGNOSIS_RESPONSE}
          rawLog={SAMPLE_LOG_SNIPPET}
          onViewIncidentDetail={vi.fn()}
          onDocumentResolution={vi.fn()}
        />
      );

      expect(html).toContain("Missing Environment Variable");
      expect(html).toContain("Confidence: 95%");
      expect(html).toContain("New Incident");
      expect(html).toContain(
        "Application failed to boot because required environment variable DATABASE_URL is missing"
      );
      expect(html).toContain("Probable Root Cause");
      expect(html).toContain(
        "Pydantic Settings initialization raised ValidationError: DATABASE_URL field required"
      );
      expect(html).toContain("Recommended Remediation");
      expect(html).toContain("Ranked Hypotheses (2)");
      expect(html).toContain("DATABASE_URL is not set in the container environment");
      expect(html).toContain("Similar Past Incidents");
      expect(html).toContain("Document Resolution");
      expect(html).toContain("View Record");
    });
  });

  describe("IncidentsHistoryTable", () => {
    it("renders incidents list, categories, environments, occurrence badges, and action buttons", () => {
      const html = renderToString(
        <IncidentsHistoryTable
          incidents={SAMPLE_INCIDENTS}
          onSelectIncident={vi.fn()}
          onDocumentResolution={vi.fn()}
          onDeleteIncident={vi.fn()}
        />
      );

      // Headers
      expect(html).toContain("Incident &amp; Category");
      expect(html).toContain("Probable Cause");
      expect(html).toContain("Environment");
      expect(html).toContain("Occurrences");
      expect(html).toContain("Status");
      expect(html).toContain("Actions");

      // Items
      expect(html).toContain("Missing DATABASE_URL during FastAPI startup");
      expect(html).toContain("Missing Environment Variable");
      expect(html).toContain("Alembic schema migration failed: relation already exists");
      expect(html).toContain("Database Migration Failed");
      expect(html).toContain("Port binding error: address already in use on port 8000");
      expect(html).toContain("Port Binding Conflict");

      // Badges
      expect(html).toContain("Resolved");
      expect(html).toContain("Open");
      expect(html).toContain("4x");

      // Action triggers
      expect(html).toContain("View");
      expect(html).toContain("Delete");
    });

    it("renders empty state message when incidents array is empty", () => {
      const html = renderToString(
        <IncidentsHistoryTable
          incidents={[]}
          onSelectIncident={vi.fn()}
          onDocumentResolution={vi.fn()}
        />
      );

      expect(html).toContain("No deployment incidents found matching current filters.");
    });
  });

  describe("IncidentDetailModal & DocumentResolutionModal", () => {
    it("renders full incident details when modal is open", () => {
      const html = renderToString(
        <IncidentDetailModal
          isOpen={true}
          onClose={vi.fn()}
          incident={SAMPLE_INCIDENTS[0]}
          onDocumentResolution={vi.fn()}
        />
      );

      expect(html).toContain("Deployment Incident Record");
      expect(html).toContain("Missing DATABASE_URL during FastAPI startup");
      expect(html).toContain("Probable Root Cause");
      expect(html).toContain("Canonical Error Signature");
      expect(html).toContain("Documented Resolution");
      expect(html).toContain("Added Neon Postgres connection URI into Render Environment Group");
    });

    it("renders resolution form textarea and save button", () => {
      const html = renderToString(
        <DocumentResolutionModal
          isOpen={true}
          onClose={vi.fn()}
          incident={SAMPLE_INCIDENTS[1]}
          onSaveResolution={vi.fn()}
        />
      );

      expect(html).toContain("Document Incident Resolution");
      expect(html).toContain("Proven Resolution or Remediation Applied");
      expect(html).toContain("Save Resolution");
    });
  });

  describe("DeploymentPageClient", () => {
    it("renders main page container with DeployDoctor heading and tab switcher", () => {
      const html = renderToString(<DeploymentPageClient projectId={projectId} />);

      expect(html).toContain("Deployment Diagnosis (S-18)");
      expect(html).toContain("DeployDoctor");
      expect(html).toContain("Diagnose Log");
      expect(html).toContain("Incident Ledger");
      expect(html).toContain("DeployDoctor Log Diagnostics");
    });
  });
});
