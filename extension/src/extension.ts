import * as vscode from "vscode";
import { DevMindLogger } from "./services/logger";
import { SettingsService } from "./services/settings";
import { FixtureFindingsSource } from "./sources/fixtureFindingsSource";
import { FindingsSource } from "./types";

let findingsSource: FindingsSource;

export function activate(context: vscode.ExtensionContext): void {
  const logger = DevMindLogger.get();
  const settings = SettingsService.get();

  logger.info("DevMind Companion activating...", {
    fixtureMode: settings.fixtureMode,
    syncMode: settings.syncMode,
  });

  findingsSource = new FixtureFindingsSource();

  // Register devmind.scanWorkspace command
  const scanCmd = vscode.commands.registerCommand("devmind.scanWorkspace", async () => {
    logger.info("Scan command triggered");
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "DevMind: Scanning workspace...",
        cancellable: false,
      },
      async (progress) => {
        progress.report({ increment: 30, message: "Parsing routes & guards..." });
        const findings = await findingsSource.getFindings(workspaceRoot);
        progress.report({ increment: 70, message: "Resolving policy invariants..." });

        logger.info("Scan complete", { findingsCount: findings.length });
        vscode.window.showInformationMessage(
          `DevMind scan complete: ${findings.length} finding(s) detected.`
        );
      }
    );
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

  // Listen to setting changes
  const settingsSub = SettingsService.onDidChange((newSettings) => {
    logger.info("DevMind settings changed", {
      fixtureMode: newSettings.fixtureMode,
      syncMode: newSettings.syncMode,
    });
  });

  context.subscriptions.push(scanCmd, openFindingsCmd, showLogsCmd, syncNowCmd, settingsSub);

  logger.info("DevMind Companion activated successfully.");
}

export function deactivate(): void {
  const logger = DevMindLogger.get();
  logger.info("DevMind Companion deactivated.");
}
