import * as vscode from "vscode";
import { SettingsService } from "../services/settings";

export type SyncTreeItem =
  | SyncModeTreeItem
  | SyncConsentTreeItem
  | SyncReceiptTreeItem
  | SyncAuditGroupTreeItem
  | SyncAuditEntryTreeItem
  | SyncActionsGroupTreeItem
  | SyncActionTreeItem;

export class SyncModeTreeItem extends vscode.TreeItem {
  constructor(mode: string) {
    super(`Mode: ${mode}`, vscode.TreeItemCollapsibleState.None);
    this.description =
      mode === "metadata_only"
        ? "Zero source code chunks transmitted"
        : mode === "indexed"
          ? "Consented chunks indexed"
          : "Sync disabled";
    this.tooltip =
      "DevMind Sync Mode (ADR-022).\nIn metadata_only mode, only manifest diffs, route schemas, and finding IDs leave the machine.\nZero raw code content is transmitted.";
    this.iconPath = new vscode.ThemeIcon("shield");
  }
}

export class SyncConsentTreeItem extends vscode.TreeItem {
  constructor() {
    super("Consent: Consented for Metadata", vscode.TreeItemCollapsibleState.None);
    this.description = "Local workspace consent verified";
    this.iconPath = new vscode.ThemeIcon("check");
  }
}

export class SyncReceiptTreeItem extends vscode.TreeItem {
  constructor(lastReceipt = "Simulated local receipt") {
    super(`Last Receipt: ${lastReceipt}`, vscode.TreeItemCollapsibleState.None);
    this.description = "Cryptographic manifest receipt";
    this.iconPath = new vscode.ThemeIcon("history");
  }
}

export class SyncAuditGroupTreeItem extends vscode.TreeItem {
  constructor() {
    super("What Leaves Machine (Audit)", vscode.TreeItemCollapsibleState.Expanded);
    this.description = "Verifiable privacy ledger";
    this.iconPath = new vscode.ThemeIcon("output");
  }
}

export class SyncAuditEntryTreeItem extends vscode.TreeItem {
  constructor(label: string, description: string, icon: string) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.description = description;
    this.iconPath = new vscode.ThemeIcon(icon);
  }
}

export class SyncActionsGroupTreeItem extends vscode.TreeItem {
  constructor() {
    super("Actions", vscode.TreeItemCollapsibleState.Expanded);
    this.iconPath = new vscode.ThemeIcon("tools");
  }
}

export class SyncActionTreeItem extends vscode.TreeItem {
  constructor(label: string, command: string, icon: string) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(icon);
    this.command = {
      command,
      title: label,
    };
  }
}

export class SyncViewProvider implements vscode.TreeDataProvider<SyncTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<SyncTreeItem | undefined | void> =
    new vscode.EventEmitter<SyncTreeItem | undefined | void>();
  readonly onDidChangeTreeData: vscode.Event<SyncTreeItem | undefined | void> =
    this._onDidChangeTreeData.event;

  public refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  public getTreeItem(element: SyncTreeItem): vscode.TreeItem {
    return element;
  }

  public async getChildren(element?: SyncTreeItem): Promise<SyncTreeItem[]> {
    if (element instanceof SyncAuditGroupTreeItem) {
      return [
        new SyncAuditEntryTreeItem("Manifest Diffs", "0 uncommitted changes", "diff"),
        new SyncAuditEntryTreeItem(
          "Discovered Routes",
          "Metadata symbols only",
          "symbol-interface"
        ),
        new SyncAuditEntryTreeItem("Secret Redaction", "Active ([REDACTED:token:8a9b])", "lock"),
        new SyncAuditEntryTreeItem(
          "Raw Code Chunks",
          "0 chunks (Forbidden in metadata_only)",
          "circle-slash"
        ),
      ];
    }

    if (element instanceof SyncActionsGroupTreeItem) {
      return [
        new SyncActionTreeItem("Review What Leaves Machine", "devmind.showWhatLeaves", "eye"),
        new SyncActionTreeItem("Trigger Sync Now", "devmind.syncNow", "cloud-upload"),
      ];
    }

    if (
      element instanceof SyncModeTreeItem ||
      element instanceof SyncConsentTreeItem ||
      element instanceof SyncReceiptTreeItem ||
      element instanceof SyncAuditEntryTreeItem ||
      element instanceof SyncActionTreeItem
    ) {
      return [];
    }

    const settings = SettingsService.get();

    return [
      new SyncModeTreeItem(settings.syncMode),
      new SyncConsentTreeItem(),
      new SyncReceiptTreeItem(),
      new SyncAuditGroupTreeItem(),
      new SyncActionsGroupTreeItem(),
    ];
  }
}
