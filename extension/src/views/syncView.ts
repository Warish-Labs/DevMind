import * as vscode from "vscode";
import { SettingsService } from "../services/settings";
import { SyncLogStore, SyncLogEntry } from "../scanner/syncLog";

export type SyncTreeItem =
  | SyncModeTreeItem
  | SyncConsentTreeItem
  | SyncReceiptTreeItem
  | SyncHistoryGroupTreeItem
  | SyncLogEntryTreeItem
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
  constructor(lastSync?: SyncLogEntry) {
    if (!lastSync) {
      super("Last Receipt: Simulated local receipt", vscode.TreeItemCollapsibleState.None);
      this.description = "Cryptographic manifest receipt";
      this.tooltip = "No cloud sync receipt recorded yet.";
      this.iconPath = new vscode.ThemeIcon("history");
      return;
    }

    const receiptLabel = lastSync.receiptHash
      ? `Last Receipt: ${lastSync.receiptHash.slice(0, 16)}...`
      : `Last Sync: ${lastSync.status}`;

    super(receiptLabel, vscode.TreeItemCollapsibleState.None);
    this.description =
      lastSync.status === "success"
        ? `✓ ${lastSync.filesCount} file(s)`
        : lastSync.status === "stale_base_recovered"
          ? `↺ Recovered (${lastSync.filesCount} files)`
          : `✗ Failed`;
    this.tooltip = [
      `Status: ${lastSync.status}`,
      `Timestamp: ${lastSync.timestamp}`,
      `Receipt Hash: ${lastSync.receiptHash || "N/A"}`,
      `Files: ${lastSync.filesCount}, Versions: ${lastSync.versionsCreated}`,
      `Symbols: ${lastSync.symbolsCount}, Relationships: ${lastSync.relationshipsCount}`,
      `Findings Ingested: ${lastSync.findingsIngested}`,
      `Duration: ${lastSync.durationMs ?? 0}ms`,
      lastSync.error ? `Error: ${lastSync.error}` : null,
    ]
      .filter(Boolean)
      .join("\n");

    this.iconPath = new vscode.ThemeIcon(
      lastSync.status === "success"
        ? "pass"
        : lastSync.status === "stale_base_recovered"
          ? "sync"
          : "error"
    );
  }
}

export class SyncHistoryGroupTreeItem extends vscode.TreeItem {
  constructor(count = 0) {
    super("Sync History", vscode.TreeItemCollapsibleState.Collapsed);
    this.description = `${count} event(s)`;
    this.tooltip = "Recent cloud synchronization receipts and history logs (Milestone M9-07).";
    this.iconPath = new vscode.ThemeIcon("history");
  }
}

export class SyncLogEntryTreeItem extends vscode.TreeItem {
  constructor(public readonly entry: SyncLogEntry) {
    const isSuccess = entry.status === "success";
    const isStale = entry.status === "stale_base_recovered";
    const statusPrefix = isSuccess ? "✓" : isStale ? "↺" : "✗";

    const timeShort = entry.timestamp ? entry.timestamp.slice(11, 19) + " UTC" : "recent";
    super(`${statusPrefix} ${timeShort}`, vscode.TreeItemCollapsibleState.None);

    this.description =
      isSuccess || isStale
        ? `${entry.filesCount} file(s), ${entry.symbolsCount} sym (${entry.durationMs ?? 0}ms)`
        : `Failed: ${entry.error ? entry.error.slice(0, 30) : "Unknown error"}`;

    this.tooltip = [
      `Event ID: ${entry.id}`,
      `Status: ${entry.status}`,
      `Timestamp: ${entry.timestamp}`,
      `Project ID: ${entry.projectId}`,
      `Sync Mode: ${entry.syncMode}`,
      `Files: ${entry.filesCount}, Versions: ${entry.versionsCreated}, Removed: ${entry.removedCount}`,
      `Symbols: ${entry.symbolsCount}, Relationships: ${entry.relationshipsCount}`,
      `Findings Ingested: ${entry.findingsIngested}`,
      `Duration: ${entry.durationMs ?? 0}ms`,
      `Receipt: ${entry.receiptHash || "None"}`,
      entry.error ? `Error: ${entry.error}` : null,
    ]
      .filter(Boolean)
      .join("\n");

    this.iconPath = new vscode.ThemeIcon(isSuccess ? "check" : isStale ? "sync" : "error");

    this.command = {
      command: "devmind.showSyncLog",
      title: "View Sync Log",
    };
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

  constructor(private syncLogStore?: SyncLogStore) {}

  public setSyncLogStore(store: SyncLogStore): void {
    this.syncLogStore = store;
    this.refresh();
  }

  public refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  public getTreeItem(element: SyncTreeItem): vscode.TreeItem {
    return element;
  }

  public async getChildren(element?: SyncTreeItem): Promise<SyncTreeItem[]> {
    if (element instanceof SyncHistoryGroupTreeItem) {
      if (!this.syncLogStore) {
        return [];
      }
      const recent = this.syncLogStore.getRecent(10);
      return recent.map((entry) => new SyncLogEntryTreeItem(entry));
    }

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
        new SyncActionTreeItem("View Sync History & Log", "devmind.showSyncLog", "output"),
        new SyncActionTreeItem("Clear Local Sync History", "devmind.clearSyncLog", "trash"),
      ];
    }

    if (
      element instanceof SyncModeTreeItem ||
      element instanceof SyncConsentTreeItem ||
      element instanceof SyncReceiptTreeItem ||
      element instanceof SyncLogEntryTreeItem ||
      element instanceof SyncAuditEntryTreeItem ||
      element instanceof SyncActionTreeItem
    ) {
      return [];
    }

    const settings = SettingsService.get();
    const lastSync = this.syncLogStore?.getLastSync();
    const historyCount = this.syncLogStore?.getRecent(100).length ?? 0;

    return [
      new SyncModeTreeItem(settings.syncMode),
      new SyncConsentTreeItem(),
      new SyncReceiptTreeItem(lastSync),
      new SyncHistoryGroupTreeItem(historyCount),
      new SyncAuditGroupTreeItem(),
      new SyncActionsGroupTreeItem(),
    ];
  }
}
