import * as vscode from "vscode";

export type ScanTreeItem =
  | ScanStatusTreeItem
  | ScanRulesTreeItem
  | ScanCountTreeItem
  | SkippedGroupTreeItem
  | SkippedFileTreeItem
  | ScanActionsGroupTreeItem
  | ScanActionTreeItem;

export interface SkippedFile {
  file: string;
  reason: string;
}

export class ScanStatusTreeItem extends vscode.TreeItem {
  constructor(status: "idle" | "scanning" | "completed", progress = 0) {
    let label = "Status: Idle";
    let icon = "circle-outline";

    if (status === "scanning") {
      label = `Status: Scanning (${progress}%)...`;
      icon = "sync~spin";
    } else if (status === "completed") {
      label = "Status: Scan Completed";
      icon = "pass";
    }

    super(label, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(icon);
    this.description =
      status === "scanning" ? "AST & guard resolution active" : "Local engine ready";
  }
}

export class ScanRulesTreeItem extends vscode.TreeItem {
  constructor(version = "1.0.0") {
    super(`Rule Pack: v${version}`, vscode.TreeItemCollapsibleState.None);
    this.description = "Semantic auth invariants & secret redaction";
    this.tooltip = "DevMind rule pack v1.0.0 (authz, authn, secret scanning)";
    this.iconPath = new vscode.ThemeIcon("law");
  }
}

export class ScanCountTreeItem extends vscode.TreeItem {
  constructor(count: number) {
    super(`Analyzed Files: ${count}`, vscode.TreeItemCollapsibleState.None);
    this.description = "Local AST cache up to date";
    this.iconPath = new vscode.ThemeIcon("files");
  }
}

export class SkippedGroupTreeItem extends vscode.TreeItem {
  constructor(public readonly skipped: SkippedFile[]) {
    super(`Skipped Files (${skipped.length})`, vscode.TreeItemCollapsibleState.Collapsed);
    this.description = "Excluded per privacy & scanner policy";
    this.iconPath = new vscode.ThemeIcon("eye-closed");
  }
}

export class SkippedFileTreeItem extends vscode.TreeItem {
  constructor(skipped: SkippedFile) {
    super(skipped.file, vscode.TreeItemCollapsibleState.None);
    this.description = skipped.reason;
    this.iconPath = skipped.file.includes(".env")
      ? new vscode.ThemeIcon("lock")
      : new vscode.ThemeIcon("file-code");
  }
}

export class ScanActionsGroupTreeItem extends vscode.TreeItem {
  constructor() {
    super("Actions", vscode.TreeItemCollapsibleState.Expanded);
    this.iconPath = new vscode.ThemeIcon("tools");
  }
}

export class ScanActionTreeItem extends vscode.TreeItem {
  constructor(label: string, command: string, icon: string) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(icon);
    this.command = {
      command,
      title: label,
    };
  }
}

export class ScanViewProvider implements vscode.TreeDataProvider<ScanTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<ScanTreeItem | undefined | void> =
    new vscode.EventEmitter<ScanTreeItem | undefined | void>();
  readonly onDidChangeTreeData: vscode.Event<ScanTreeItem | undefined | void> =
    this._onDidChangeTreeData.event;

  private status: "idle" | "scanning" | "completed" = "idle";
  private progress = 0;
  private analyzedFilesCount = 18;
  private skippedFiles: SkippedFile[] = [
    { file: ".env", reason: "Credential file · path-only handling (ADR-047)" },
    { file: "package-lock.json", reason: "Lockfile · AST parse skipped" },
    { file: "dist/", reason: "Build artifact directory · ignored" },
  ];

  public refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  public setScanning(isScanning: boolean, progress = 0): void {
    this.status = isScanning ? "scanning" : "idle";
    this.progress = progress;
    this.refresh();
  }

  public setCompleted(analyzedCount = 18): void {
    this.status = "completed";
    this.progress = 100;
    this.analyzedFilesCount = analyzedCount;
    this.refresh();
  }

  public cancelScan(): void {
    this.status = "idle";
    this.progress = 0;
    this.refresh();
  }

  public getTreeItem(element: ScanTreeItem): vscode.TreeItem {
    return element;
  }

  public async getChildren(element?: ScanTreeItem): Promise<ScanTreeItem[]> {
    if (element instanceof SkippedGroupTreeItem) {
      return element.skipped.map((s) => new SkippedFileTreeItem(s));
    }

    if (element instanceof ScanActionsGroupTreeItem) {
      return [
        new ScanActionTreeItem("Run Workspace Scan", "devmind.scanWorkspace", "play"),
        new ScanActionTreeItem("Cancel Active Scan", "devmind.cancelScan", "stop"),
      ];
    }

    if (
      element instanceof ScanStatusTreeItem ||
      element instanceof ScanRulesTreeItem ||
      element instanceof ScanCountTreeItem ||
      element instanceof SkippedFileTreeItem ||
      element instanceof ScanActionTreeItem
    ) {
      return [];
    }

    // Root items
    return [
      new ScanStatusTreeItem(this.status, this.progress),
      new ScanRulesTreeItem("1.0.0"),
      new ScanCountTreeItem(this.analyzedFilesCount),
      new SkippedGroupTreeItem(this.skippedFiles),
      new ScanActionsGroupTreeItem(),
    ];
  }
}
