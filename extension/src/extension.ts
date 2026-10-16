import * as vscode from "vscode";
import fs from "node:fs";
import path from "node:path";
import { DevMindLogger } from "./services/logger";
import { SettingsService } from "./services/settings";
import { FixtureFindingsSource } from "./sources/fixtureFindingsSource";
import { FindingsSource } from "./types";
import { FindingsViewProvider } from "./views/findingsView";
import { StructureViewProvider } from "./views/structureView";
import { ScanViewProvider } from "./views/scanView";
import { SyncViewProvider } from "./views/syncView";
import { DatabaseViewProvider } from "./views/databaseView";

let findingsSource: FindingsSource;
let findingsProvider: FindingsViewProvider;
let structureProvider: StructureViewProvider;
let scanProvider: ScanViewProvider;
let syncProvider: SyncViewProvider;
let databaseProvider: DatabaseViewProvider;

export function activate(context: vscode.ExtensionContext): void {
  const logger = DevMindLogger.get();
  const settings = SettingsService.get();

  logger.info("DevMind Companion activating...", {
    fixtureMode: settings.fixtureMode,
    syncMode: settings.syncMode,
  });

  findingsSource = new FixtureFindingsSource();

  // Initialize TreeView Providers
  findingsProvider = new FindingsViewProvider(findingsSource);
  structureProvider = new StructureViewProvider(findingsSource);
  scanProvider = new ScanViewProvider();
  syncProvider = new SyncViewProvider();
  databaseProvider = new DatabaseViewProvider(findingsSource);

  // Register TreeDataProviders
  const regFindings = vscode.window.registerTreeDataProvider(
    "devmind.views.findings",
    findingsProvider
  );
  const regStructure = vscode.window.registerTreeDataProvider(
    "devmind.views.structure",
    structureProvider
  );
  const regScan = vscode.window.registerTreeDataProvider("devmind.views.scan", scanProvider);
  const regSync = vscode.window.registerTreeDataProvider("devmind.views.sync", syncProvider);
  const regDb = vscode.window.registerTreeDataProvider("devmind.views.database", databaseProvider);

  // Register devmind.scanWorkspace command
  const scanCmd = vscode.commands.registerCommand("devmind.scanWorkspace", async () => {
    logger.info("Scan command triggered");
    scanProvider.setScanning(true, 10);
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "DevMind: Scanning workspace...",
        cancellable: false,
      },
      async (progress) => {
        progress.report({ increment: 30, message: "Parsing routes & guards..." });
        scanProvider.setScanning(true, 50);

        const findings = await findingsSource.getFindings(workspaceRoot);
        progress.report({ increment: 70, message: "Resolving policy invariants..." });

        scanProvider.setCompleted(18);
        findingsProvider.refresh();
        structureProvider.refresh();
        databaseProvider.refresh();

        logger.info("Scan complete", { findingsCount: findings.length });
        vscode.window.showInformationMessage(
          `DevMind scan complete: ${findings.length} finding(s) detected.`
        );
      }
    );
  });

  // Register devmind.cancelScan command
  const cancelScanCmd = vscode.commands.registerCommand("devmind.cancelScan", () => {
    scanProvider.cancelScan();
    logger.info("DevMind scan canceled by user");
    vscode.window.showInformationMessage("DevMind scan canceled.");
  });

  // Register devmind.openFindings command
  const openFindingsCmd = vscode.commands.registerCommand("devmind.openFindings", () => {
    vscode.commands.executeCommand("devmind.views.findings.focus");
  });

  // Register devmind.showLogs command
  const showLogsCmd = vscode.commands.registerCommand("devmind.showLogs", () => {
    logger.show();
  });

  // Register devmind.syncNow command
  const syncNowCmd = vscode.commands.registerCommand("devmind.syncNow", () => {
    const currentSettings = SettingsService.get();
    if (currentSettings.fixtureMode) {
      vscode.window.showInformationMessage(
        "DevMind is in Fixture Mode. Sync is simulated locally (zero network calls)."
      );
      logger.info("Sync requested in fixture mode: simulated local sync complete.");
    } else {
      vscode.window.showInformationMessage("Syncing with DevMind Project Brain...");
    }
  });

  // Register devmind.showWhatLeaves command
  const showWhatLeavesCmd = vscode.commands.registerCommand("devmind.showWhatLeaves", () => {
    const currentSettings = SettingsService.get();
    const ledger = [
      "DevMind Privacy Ledger (ADR-022, ADR-047)",
      "-----------------------------------------",
      `Current Mode: ${currentSettings.syncMode}`,
      "✓ Stays Local: Source code, credentials (.env), AST tokens, test bodies",
      "✓ Reaches Cloud: Manifest hashes, route signatures, finding IDs",
      "✓ Redaction: [REDACTED:secret:hash8] before any transmission",
      "✘ Prohibited: Live DB connections, execution of project scripts",
    ].join("\n");

    vscode.window.showInformationMessage(ledger, { modal: false });
    logger.info("Privacy ledger reviewed by user");
  });

  // Register devmind.openFindingLocation command
  const openLocCmd = vscode.commands.registerCommand(
    "devmind.openFindingLocation",
    async (fileRelPath: string, lineStart = 1, _lineEnd = 1) => {
      const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      const fullPath =
        workspaceRoot && !path.isAbsolute(fileRelPath)
          ? path.join(workspaceRoot, fileRelPath)
          : fileRelPath;

      if (fs.existsSync(fullPath)) {
        const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(fullPath));
        const lineIndex = Math.max(0, lineStart - 1);
        const pos = new vscode.Position(lineIndex, 0);
        await vscode.window.showTextDocument(doc, {
          selection: new vscode.Range(pos, pos),
        });
      } else {
        vscode.window.showWarningMessage(`DevMind: File not found at ${fullPath}`);
      }
    }
  );

  // Register devmind.refreshAll command
  const refreshAllCmd = vscode.commands.registerCommand("devmind.refreshAll", () => {
    findingsProvider.refresh();
    structureProvider.refresh();
    scanProvider.refresh();
    syncProvider.refresh();
    databaseProvider.refresh();
    logger.info("All DevMind views refreshed");
  });

  // Listen to setting changes
  const settingsSub = SettingsService.onDidChange((newSettings) => {
    logger.info("DevMind settings changed", {
      fixtureMode: newSettings.fixtureMode,
      syncMode: newSettings.syncMode,
    });
    syncProvider.refresh();
  });

  context.subscriptions.push(
    regFindings,
    regStructure,
    regScan,
    regSync,
    regDb,
    scanCmd,
    cancelScanCmd,
    openFindingsCmd,
    showLogsCmd,
    syncNowCmd,
    showWhatLeavesCmd,
    openLocCmd,
    refreshAllCmd,
    settingsSub
  );

  logger.info("DevMind Companion activated successfully with 5 view providers.");
}

export function deactivate(): void {
  const logger = DevMindLogger.get();
  logger.info("DevMind Companion deactivated.");
}
