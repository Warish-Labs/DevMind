import * as vscode from "vscode";
import { Finding, FindingsSource, Severity } from "../types";

export type FindingsTreeItem = SeverityGroupTreeItem | FindingItemTreeItem | EmptyFindingsTreeItem;

export class SeverityGroupTreeItem extends vscode.TreeItem {
  constructor(
    public readonly severity: Severity,
    public readonly findings: Finding[]
  ) {
    const capitalized = severity.charAt(0).toUpperCase() + severity.slice(1);
    super(`${capitalized} (${findings.length})`, vscode.TreeItemCollapsibleState.Expanded);

    this.description =
      severity === "critical" || severity === "high"
        ? "Possible security invariant violations"
        : "Architectural and hygiene advisories";
    this.iconPath = getSeverityIcon(severity);
    this.contextValue = "severityGroup";
  }
}

export class FindingItemTreeItem extends vscode.TreeItem {
  constructor(public readonly finding: Finding) {
    super(finding.name, vscode.TreeItemCollapsibleState.None);

    this.description = `${finding.file}:${finding.lineStart}`;
    this.tooltip = createFindingTooltip(finding);
    this.iconPath = getSeverityIcon(finding.severity);
    this.contextValue = "devmindFinding";
    this.command = {
      command: "devmind.openFindingLocation",
      title: "Open Finding Location",
      arguments: [finding.file, finding.lineStart, finding.lineEnd],
    };
  }
}

export class EmptyFindingsTreeItem extends vscode.TreeItem {
  constructor() {
    super("No findings detected (Workspace clean)", vscode.TreeItemCollapsibleState.None);
    this.description = "All architectural invariants satisfied";
    this.iconPath = new vscode.ThemeIcon("pass");
  }
}

function getSeverityIcon(severity: Severity): vscode.ThemeIcon {
  switch (severity) {
    case "critical":
      return new vscode.ThemeIcon("error", new vscode.ThemeColor("errorForeground"));
    case "high":
      return new vscode.ThemeIcon("warning", new vscode.ThemeColor("list.warningForeground"));
    case "medium":
      return new vscode.ThemeIcon("info", new vscode.ThemeColor("list.warningForeground"));
    case "low":
      return new vscode.ThemeIcon("info");
    case "info":
    default:
      return new vscode.ThemeIcon("lightbulb");
  }
}

function createFindingTooltip(finding: Finding): string {
  const parts = [
    `Finding: ${finding.name}`,
    `Rule ID: ${finding.ruleId}`,
    `Severity: ${finding.severity.toUpperCase()}`,
    `Evidence: ${finding.evidenceLabel} (${finding.evidenceLevel})`,
    `Location: ${finding.file}:${finding.lineStart}-${finding.lineEnd}`,
    "",
    `Message: ${finding.message}`,
  ];

  if (finding.remediation) {
    parts.push("", `Remediation: ${finding.remediation}`);
  }

  return parts.join("\n");
}

export class FindingsViewProvider implements vscode.TreeDataProvider<FindingsTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<FindingsTreeItem | undefined | void> =
    new vscode.EventEmitter<FindingsTreeItem | undefined | void>();
  readonly onDidChangeTreeData: vscode.Event<FindingsTreeItem | undefined | void> =
    this._onDidChangeTreeData.event;

  constructor(private findingsSource: FindingsSource) {}

  public refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  public getTreeItem(element: FindingsTreeItem): vscode.TreeItem {
    return element;
  }

  public async getChildren(element?: FindingsTreeItem): Promise<FindingsTreeItem[]> {
    if (element instanceof SeverityGroupTreeItem) {
      return element.findings.map((f) => new FindingItemTreeItem(f));
    }

    if (element instanceof FindingItemTreeItem || element instanceof EmptyFindingsTreeItem) {
      return [];
    }

    // Root level: fetch findings
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    const findings = await this.findingsSource.getFindings(workspaceRoot);

    if (!findings || findings.length === 0) {
      return [new EmptyFindingsTreeItem()];
    }

    const severities: Severity[] = ["critical", "high", "medium", "low", "info"];
    const groups: SeverityGroupTreeItem[] = [];

    for (const sev of severities) {
      const matching = findings.filter((f) => f.severity === sev);
      if (matching.length > 0) {
        groups.push(new SeverityGroupTreeItem(sev, matching));
      }
    }

    return groups;
  }
}
