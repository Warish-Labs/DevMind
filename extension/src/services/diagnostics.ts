import * as vscode from "vscode";
import path from "node:path";
import { Finding, Severity } from "../types";
import { DevMindLogger } from "./logger";

export class DiagnosticService {
  private collection: vscode.DiagnosticCollection;
  private logger = DevMindLogger.get();

  constructor() {
    this.collection = vscode.languages.createDiagnosticCollection("DevMind");
  }

  public getCollection(): vscode.DiagnosticCollection {
    return this.collection;
  }

  public updateDiagnostics(findings: Finding[], workspaceRoot?: string): void {
    this.collection.clear();

    if (!findings || findings.length === 0) {
      return;
    }

    // Group findings by file URI
    const fileMap = new Map<string, { uri: vscode.Uri; diags: vscode.Diagnostic[] }>();

    for (const finding of findings) {
      const fullPath =
        workspaceRoot && !path.isAbsolute(finding.file)
          ? path.join(workspaceRoot, finding.file)
          : finding.file;

      const uri = vscode.Uri.file(fullPath);
      const uriKey = uri.fsPath;

      if (!fileMap.has(uriKey)) {
        fileMap.set(uriKey, { uri, diags: [] });
      }

      const diagnostic = this.createDiagnostic(finding);
      fileMap.get(uriKey)!.diags.push(diagnostic);
    }

    // Set diagnostics per file
    for (const { uri, diags } of fileMap.values()) {
      this.collection.set(uri, diags);
    }

    this.logger.info("Updated DevMind diagnostics", {
      filesCount: fileMap.size,
      totalFindings: findings.length,
    });
  }

  public clear(): void {
    this.collection.clear();
  }

  public dispose(): void {
    this.collection.dispose();
  }

  private createDiagnostic(finding: Finding): vscode.Diagnostic {
    const startLine = Math.max(0, finding.lineStart - 1);
    const endLine = Math.max(startLine, (finding.lineEnd || finding.lineStart) - 1);
    const range = new vscode.Range(
      new vscode.Position(startLine, 0),
      new vscode.Position(endLine, 120)
    );

    // E1 evidence level gets "Possible:" prefix per docs/06 §9
    const isE1 = finding.evidenceLevel === "E1";
    const prefix = isE1 ? "Possible: " : "";

    // Do not convey status by color alone: include severity and evidence label in text
    const sevLabel = finding.severity.toUpperCase();
    const evidence = finding.evidenceLabel || finding.evidenceLevel;

    let messageText = `${prefix}[${sevLabel} · ${evidence}] ${finding.name}: ${finding.message}`;
    if (finding.remediation) {
      messageText += ` (Remediation: ${finding.remediation})`;
    }

    const severity = this.mapSeverity(finding.severity);
    const diagnostic = new vscode.Diagnostic(range, messageText, severity);

    diagnostic.source = "DevMind";
    diagnostic.code = finding.ruleId;

    return diagnostic;
  }

  private mapSeverity(severity: Severity): vscode.DiagnosticSeverity {
    switch (severity) {
      case "critical":
      case "high":
        return vscode.DiagnosticSeverity.Error;
      case "medium":
        return vscode.DiagnosticSeverity.Warning;
      case "low":
        return vscode.DiagnosticSeverity.Information;
      case "info":
      default:
        return vscode.DiagnosticSeverity.Hint;
    }
  }
}
