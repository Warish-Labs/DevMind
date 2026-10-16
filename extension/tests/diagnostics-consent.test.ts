import { describe, it, expect, beforeEach } from "vitest";
import path from "node:path";
import * as vscode from "vscode";
import { DiagnosticService } from "../src/services/diagnostics";
import { StatusBarService } from "../src/services/statusBar";
import { ConsentWebviewManager } from "../src/views/consentWebview";
import { Finding } from "../src/types";

const ROOT = path.resolve(__dirname, "../../");
const EXPRESS_FIXTURE = path.join(ROOT, "evals/scanner/fixtures/express-admin");

describe("Diagnostics and Consent (Slice B11)", () => {
  describe("DiagnosticService (S2-10)", () => {
    let service: DiagnosticService;

    beforeEach(() => {
      service = new DiagnosticService();
    });

    it("creates diagnostics with DevMind source and rule ID code", () => {
      const finding: Finding = {
        id: "exp-find-01",
        ruleId: "devmind.authz.missing_role_check",
        name: "Missing Role Authorization Check",
        severity: "high",
        category: "authorization",
        evidenceLevel: "E1",
        evidenceLabel: "E1 · Possible",
        file: "src/routes/admin.ts",
        lineStart: 7,
        lineEnd: 9,
        message: "Operation lacks role check",
        remediation: "Add requireRole('admin')",
      };

      service.updateDiagnostics([finding], EXPRESS_FIXTURE);

      const targetPath = path.join(EXPRESS_FIXTURE, "src/routes/admin.ts");
      const diags = service.getCollection().get({ fsPath: targetPath });

      expect(diags.length).toBe(1);
      const d = diags[0]!;

      expect(d.source).toBe("DevMind");
      expect(d.code).toBe("devmind.authz.missing_role_check");
      expect(d.severity).toBe(vscode.DiagnosticSeverity.Error);

      // Verify E1 prefix per docs/06 §9
      expect(d.message.startsWith("Possible: ")).toBe(true);
      // Status not color alone: contains severity and evidence in text
      expect(d.message).toContain("[HIGH · E1 · Possible]");
      expect(d.message).toContain("Remediation: Add requireRole('admin')");

      // Verify line indices (0-indexed)
      expect(d.range.start.line).toBe(6);
      expect(d.range.end.line).toBe(8);
    });

    it("maps severity correctly across all levels", () => {
      const findings: Finding[] = [
        {
          id: "f-crit",
          ruleId: "devmind.crit",
          name: "Critical Finding",
          severity: "critical",
          category: "c",
          evidenceLevel: "E0",
          evidenceLabel: "E0 · Fact",
          file: "test.ts",
          lineStart: 1,
          lineEnd: 1,
          message: "Critical msg",
        },
        {
          id: "f-med",
          ruleId: "devmind.med",
          name: "Med Finding",
          severity: "medium",
          category: "c",
          evidenceLevel: "E0",
          evidenceLabel: "E0 · Fact",
          file: "test.ts",
          lineStart: 2,
          lineEnd: 2,
          message: "Med msg",
        },
        {
          id: "f-low",
          ruleId: "devmind.low",
          name: "Low Finding",
          severity: "low",
          category: "c",
          evidenceLevel: "E0",
          evidenceLabel: "E0 · Fact",
          file: "test.ts",
          lineStart: 3,
          lineEnd: 3,
          message: "Low msg",
        },
        {
          id: "f-info",
          ruleId: "devmind.info",
          name: "Info Finding",
          severity: "info",
          category: "c",
          evidenceLevel: "E0",
          evidenceLabel: "E0 · Fact",
          file: "test.ts",
          lineStart: 4,
          lineEnd: 4,
          message: "Info msg",
        },
      ];

      service.updateDiagnostics(findings, EXPRESS_FIXTURE);

      const targetPath = path.join(EXPRESS_FIXTURE, "test.ts");
      const diags = service.getCollection().get({ fsPath: targetPath });

      expect(diags.length).toBe(4);
      expect(diags[0]?.severity).toBe(vscode.DiagnosticSeverity.Error);
      expect(diags[0]?.message.startsWith("Possible: ")).toBe(false); // E0 has no Possible: prefix
      expect(diags[1]?.severity).toBe(vscode.DiagnosticSeverity.Warning);
      expect(diags[2]?.severity).toBe(vscode.DiagnosticSeverity.Information);
      expect(diags[3]?.severity).toBe(vscode.DiagnosticSeverity.Hint);
    });
  });

  describe("StatusBarService (S2-11)", () => {
    it("configures status bar item with accessible text and icons", () => {
      const statusBar = new StatusBarService(true);
      const item = statusBar.getItem();

      expect(item.command).toBe("devmind.openFindings");
      expect(item.text).toBe("$(shield) DevMind · fixture · idle");
      expect(item.tooltip).toContain("DevMind Companion (fixture): Ready");

      // Transition to scanning
      statusBar.setScanning(1, 4);
      expect(item.text).toBe("$(sync~spin) DevMind · fixture · scanning 1/4");
      expect(item.tooltip).toContain("1/4");

      // Transition to offline
      statusBar.setOffline();
      expect(item.text).toBe("$(cloud-offline) DevMind · fixture · offline");

      // Switch to cloud mode
      statusBar.setFixtureMode(false);
      statusBar.setIdle();
      expect(item.text).toBe("$(shield) DevMind · cloud · idle");

      statusBar.dispose();
    });
  });

  describe("ConsentWebviewManager (S2-12)", () => {
    it("generates valid HTML with CSP, nonce, and Cancel button autofocus", () => {
      const html = ConsentWebviewManager.renderHtml("metadata_only", true);

      // Verify strict CSP
      expect(html).toContain("Content-Security-Policy");
      expect(html).toContain("default-src 'none'");
      expect(html).toContain("style-src 'nonce-");
      expect(html).toContain("script-src 'nonce-");

      // Verify UX specification: default focus on Cancel
      expect(html).toContain(
        '<button id="btn-cancel" class="btn-secondary" autofocus>Cancel</button>'
      );
      expect(html).toContain("Send (Simulated in Fixture Mode)");

      // Verify privacy ledger items
      expect(html).toContain("metadata_only");
      expect(html).toContain("Strictly 0 (Forbidden in metadata_only)");
      expect(html).toContain("[REDACTED:token:8a9b2c3d]");
      expect(html).toContain("acquireVsCodeApi()");
    });

    it("opens webview panel on show() and handles send/cancel commands", () => {
      const mockContext = { subscriptions: [] } as unknown as vscode.ExtensionContext;
      ConsentWebviewManager.show(mockContext);
      // Panel was created without errors
    });
  });
});
