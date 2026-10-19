import * as vscode from "vscode";
import fs from "node:fs";
import path from "node:path";
import { DevMindLogger } from "./services/logger";
import { SettingsService } from "./services/settings";
import { DiagnosticService } from "./services/diagnostics";
import { StatusBarService } from "./services/statusBar";
import { LocalScanFindingsSource } from "./sources/localScanFindingsSource";
import { FindingsViewProvider } from "./views/findingsView";
import { StructureViewProvider } from "./views/structureView";
import { ScanViewProvider } from "./views/scanView";
import { SyncViewProvider } from "./views/syncView";
import { DatabaseViewProvider } from "./views/databaseView";
import { ConsentWebviewManager } from "./views/consentWebview";

import { ExtensionAuthService } from "./services/auth";
import { SyncClient } from "./services/syncClient";
import { SyncLogStore } from "./scanner/syncLog";

let findingsSource: LocalScanFindingsSource;
let diagnosticService: DiagnosticService;
let statusBarService: StatusBarService;
let authService: ExtensionAuthService;
let syncLogStore: SyncLogStore;
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

  const secrets = context.secrets ?? {
    store: async () => {},
    get: async () => undefined,
    delete: async () => {},
    onDidChange: () => ({ dispose: () => {} }),
  };
  authService = ExtensionAuthService.init(secrets as vscode.SecretStorage);

  const storageDir = context.storageUri?.fsPath || context.globalStorageUri?.fsPath || "";
  const initialRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
  findingsSource = new LocalScanFindingsSource(storageDir);
  diagnosticService = new DiagnosticService();
  statusBarService = new StatusBarService(settings.fixtureMode);
  syncLogStore = new SyncLogStore(storageDir, initialRoot);
  syncLogStore.load().catch(() => {});

  // Initialize TreeView Providers
  findingsProvider = new FindingsViewProvider(findingsSource);
  structureProvider = new StructureViewProvider(findingsSource);
  scanProvider = new ScanViewProvider();
  syncProvider = new SyncViewProvider(syncLogStore);
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

  // Function to perform scan and update all listeners
  const runScan = async () => {
    logger.info("Scan command triggered");
    scanProvider.setScanning(true, 10);
    statusBarService.setScanning(1, 2);
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

    if (!workspaceRoot) {
      vscode.window.showWarningMessage("DevMind: No workspace folder open to scan.");
      scanProvider.cancelScan();
      statusBarService.setIdle();
      return;
    }

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "DevMind: Scanning workspace...",
        cancellable: false,
      },
      async (progress) => {
        progress.report({ increment: 20, message: "Discovering workspace files..." });
        scanProvider.setScanning(true, 30);

        const scanResult = await findingsSource.scan(workspaceRoot, (msg, pct) => {
          progress.report({ message: msg, increment: 10 });
          scanProvider.setScanning(true, pct);
        });

        diagnosticService.updateDiagnostics(scanResult.findings, workspaceRoot);
        scanProvider.setCompleted(scanResult.analyzedFilesCount, scanResult.skippedFiles);
        statusBarService.setIdle();
        findingsProvider.refresh();
        structureProvider.refresh();
        databaseProvider.refresh();

        logger.info("Scan complete", {
          findingsCount: scanResult.findings.length,
          analyzedFilesCount: scanResult.analyzedFilesCount,
          skippedCount: scanResult.skippedFiles.length,
        });
        vscode.window.showInformationMessage(
          `DevMind scan complete: ${scanResult.findings.length} finding(s) detected.`
        );
      }
    );
  };

  // Register devmind.scanWorkspace command
  const scanCmd = vscode.commands.registerCommand("devmind.scanWorkspace", runScan);

  // Register devmind.cancelScan command
  const cancelScanCmd = vscode.commands.registerCommand("devmind.cancelScan", () => {
    scanProvider.cancelScan();
    statusBarService.setIdle();
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

  // Real sync implementation coordinating SyncClient and Project Brain
  const runSync = async () => {
    const currentSettings = SettingsService.get();
    if (currentSettings.fixtureMode) {
      vscode.window.showInformationMessage(
        "DevMind is in Fixture Mode. Sync is simulated locally (zero network calls)."
      );
      logger.info("Sync requested in fixture mode: simulated local sync complete.");
      return;
    }

    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceRoot) {
      vscode.window.showWarningMessage("DevMind: No workspace folder open to sync.");
      return;
    }

    const isAuthed = await authService.isAuthenticated();
    if (!isAuthed) {
      const choice = await vscode.window.showWarningMessage(
        "DevMind: You must sign in before syncing with Project Brain.",
        "Sign In"
      );
      if (choice === "Sign In") {
        await vscode.commands.executeCommand("devmind.signIn");
      }
      return;
    }

    let projectId = currentSettings.projectId;
    if (!projectId) {
      const input = await vscode.window.showInputBox({
        title: "DevMind: Link Project",
        prompt: "Enter your DevMind Project ID (UUID) to sync this workspace",
        placeHolder: "01920000-0000-7000-8000-000000000001",
        validateInput: (val) => (val.trim().length === 0 ? "Project ID cannot be empty" : null),
      });
      if (!input) {
        return;
      }
      projectId = input.trim();
      await vscode.workspace
        .getConfiguration("devmind")
        .update("projectId", projectId, vscode.ConfigurationTarget.Workspace);
    }

    statusBarService.setScanning(1, 1);

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "DevMind: Syncing with Project Brain...",
        cancellable: false,
      },
      async (progress) => {
        try {
          const syncClient = new SyncClient(authService);
          const manifestStore = findingsSource.getManifestStore(workspaceRoot);
          await manifestStore.load();

          const lastScan = findingsSource.getLastResult();
          const findings = lastScan?.findings ?? (await findingsSource.getFindings(workspaceRoot));
          const modules = lastScan?.modules ?? (await findingsSource.getStructure(workspaceRoot));
          const databaseModels =
            lastScan?.databaseModels ?? (await findingsSource.getDatabaseModels(workspaceRoot));

          const res = await syncClient.sync({
            projectId,
            workspaceRoot,
            manifestStore,
            syncLogStore,
            findings,
            modules,
            databaseModels,
            onProgress: (msg, pct) => {
              progress.report({ message: msg, increment: pct / 5 });
            },
          });

          statusBarService.setIdle();
          syncProvider.refresh();

          if (res.success) {
            vscode.window.showInformationMessage(
              `DevMind sync complete: ${res.filesCount} file(s), ${res.symbolsCount} symbol(s), ${res.findingsIngested} finding(s) synced.`
            );
          } else {
            vscode.window.showErrorMessage(`DevMind sync failed: ${res.error || "Unknown error"}`);
          }
        } catch (err) {
          statusBarService.setIdle();
          syncProvider.refresh();
          vscode.window.showErrorMessage(`DevMind sync encountered an error: ${String(err)}`);
        }
      }
    );
  };

  // Register devmind.syncNow and devmind.syncProject commands
  const syncNowCmd = vscode.commands.registerCommand("devmind.syncNow", runSync);
  const syncProjectCmd = vscode.commands.registerCommand("devmind.syncProject", runSync);

  // Register devmind.linkProject command
  const linkProjectCmd = vscode.commands.registerCommand("devmind.linkProject", async () => {
    const current = SettingsService.get().projectId || "";
    const input = await vscode.window.showInputBox({
      title: "DevMind: Link Project",
      prompt: "Enter your DevMind Project ID (UUID)",
      value: current,
      validateInput: (val) => (val.trim().length === 0 ? "Project ID cannot be empty" : null),
    });
    if (input) {
      await vscode.workspace
        .getConfiguration("devmind")
        .update("projectId", input.trim(), vscode.ConfigurationTarget.Workspace);
      vscode.window.showInformationMessage(`DevMind: Workspace linked to Project ${input.trim()}`);
    }
  });

  // Register devmind.showWhatLeaves & devmind.reviewSync commands
  const reviewSyncHandler = () => {
    ConsentWebviewManager.show(context);
    logger.info("Consent preview webview opened");
  };

  const showWhatLeavesCmd = vscode.commands.registerCommand(
    "devmind.showWhatLeaves",
    reviewSyncHandler
  );
  const reviewSyncCmd = vscode.commands.registerCommand("devmind.reviewSync", reviewSyncHandler);

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
    statusBarService.setFixtureMode(newSettings.fixtureMode);
    findingsSource.clearCache();
    findingsProvider.refresh();
    structureProvider.refresh();
    databaseProvider.refresh();
    syncProvider.refresh();

    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (workspaceRoot) {
      findingsSource.getFindings(workspaceRoot).then((findings) => {
        diagnosticService.updateDiagnostics(findings, workspaceRoot);
      });
    }
  });

  // Register devmind.signIn & devmind.signOut commands (ADR-012)
  const signInCmd = vscode.commands.registerCommand("devmind.signIn", async () => {
    const isFixture = SettingsService.get().fixtureMode;
    if (isFixture) {
      await authService.saveTokens({
        accessToken: "dme_at_simulated_fixture_token",
        refreshToken: "dme_rt_simulated_fixture_token",
        registrationId: "01920000-0000-7000-8000-000000000001",
        expiresIn: 3600,
      });
      vscode.window.showInformationMessage("DevMind: Signed in (Simulated fixture session).");
      return;
    }

    const tokenInput = await vscode.window.showInputBox({
      title: "DevMind Sign In",
      prompt: "Paste your DevMind extension token (dme_at_...)",
      password: true,
      ignoreFocusOut: true,
    });

    if (tokenInput && tokenInput.trim()) {
      const cleanToken = tokenInput.trim();
      await authService.saveTokens({
        accessToken: cleanToken,
        refreshToken: "dme_rt_" + cleanToken.replace("dme_at_", ""),
        registrationId: "01920000-0000-7000-8000-000000000001",
        expiresIn: 3600,
      });
      vscode.window.showInformationMessage("DevMind: Extension signed in successfully.");
    }
  });

  const signOutCmd = vscode.commands.registerCommand("devmind.signOut", async () => {
    await authService.clearTokens();
    vscode.window.showInformationMessage(
      "DevMind: Signed out. Extension tokens cleared from SecretStorage."
    );
  });

  // Register devmind.showSyncLog & devmind.clearSyncLog commands (Milestone M9-07)
  const syncOutputChannel = vscode.window.createOutputChannel("DevMind: Sync Log");
  const showSyncLogCmd = vscode.commands.registerCommand("devmind.showSyncLog", async () => {
    await syncLogStore.load();
    const entries = syncLogStore.getAll();
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "Unknown";

    syncOutputChannel.clear();
    syncOutputChannel.appendLine(
      "================================================================================"
    );
    syncOutputChannel.appendLine(
      "DEVMIND EXTENSION CLOUD SYNCHRONIZATION LOG (Milestone M9-07, docs/06 §9, §11.3)"
    );
    syncOutputChannel.appendLine(
      "================================================================================"
    );
    syncOutputChannel.appendLine(`Workspace Root:    ${workspaceRoot}`);
    syncOutputChannel.appendLine(`Log Storage:       ${syncLogStore.getStoragePath()}`);
    syncOutputChannel.appendLine(`Generated At:      ${new Date().toISOString()}`);
    syncOutputChannel.appendLine(`Total Recorded:    ${entries.length} sync event(s)\n`);

    if (entries.length === 0) {
      syncOutputChannel.appendLine("No cloud synchronization events recorded yet.");
      syncOutputChannel.appendLine(
        "Run 'DevMind: Trigger Sync Now' to synchronize local metadata."
      );
    } else {
      for (const e of entries) {
        syncOutputChannel.appendLine(`[${e.timestamp}] STATUS: ${e.status.toUpperCase()}`);
        syncOutputChannel.appendLine(`  Event ID:             ${e.id}`);
        syncOutputChannel.appendLine(`  Project ID:           ${e.projectId}`);
        syncOutputChannel.appendLine(`  Sync Mode:            ${e.syncMode}`);
        syncOutputChannel.appendLine(
          `  Files Synced:         ${e.filesCount} (versions created: ${e.versionsCreated}, removed: ${e.removedCount})`
        );
        syncOutputChannel.appendLine(
          `  Symbols / Edges:      ${e.symbolsCount} symbols, ${e.relationshipsCount} relationships`
        );
        syncOutputChannel.appendLine(
          `  Findings Ingested:    ${e.findingsIngested} (capped at E1)`
        );
        syncOutputChannel.appendLine(`  Duration:             ${e.durationMs ?? 0}ms`);
        syncOutputChannel.appendLine(`  Receipt Hash:         ${e.receiptHash || "None"}`);
        if (e.staleBaseRecovered) {
          syncOutputChannel.appendLine(
            `  Stale Base Recovery:  Yes (resolved 409 conflict via re-diff)`
          );
        }
        if (e.error) {
          syncOutputChannel.appendLine(`  Error Detail:         ${e.error}`);
        }
        syncOutputChannel.appendLine(
          "--------------------------------------------------------------------------------"
        );
      }
    }
    syncOutputChannel.show(true);
  });

  const clearSyncLogCmd = vscode.commands.registerCommand("devmind.clearSyncLog", async () => {
    await syncLogStore.clear();
    syncProvider.refresh();
    vscode.window.showInformationMessage("DevMind: Local sync history cleared.");
    logger.info("Local sync history cleared");
  });

  context.subscriptions.push(
    diagnosticService.getCollection(),
    statusBarService.getItem(),
    syncOutputChannel,
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
    syncProjectCmd,
    linkProjectCmd,
    showWhatLeavesCmd,
    reviewSyncCmd,
    showSyncLogCmd,
    clearSyncLogCmd,
    openLocCmd,
    refreshAllCmd,
    signInCmd,
    signOutCmd,
    settingsSub
  );

  // Initial load
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (workspaceRoot) {
    findingsSource.getFindings(workspaceRoot).then((findings) => {
      diagnosticService.updateDiagnostics(findings, workspaceRoot);
    });
  }

  logger.info("DevMind Companion activated successfully with diagnostics and consent webview.");
}

export function deactivate(): void {
  const logger = DevMindLogger.get();
  diagnosticService?.dispose();
  statusBarService?.dispose();
  logger.info("DevMind Companion deactivated.");
}
