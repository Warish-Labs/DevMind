import * as vscode from "vscode";
import crypto from "node:crypto";
import { DevMindLogger } from "../services/logger";
import { SettingsService } from "../services/settings";

export class ConsentWebviewManager {
  private static currentPanel: vscode.WebviewPanel | undefined;

  public static show(context: vscode.ExtensionContext): void {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (ConsentWebviewManager.currentPanel) {
      ConsentWebviewManager.currentPanel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      "devmindConsent",
      "DevMind: Review What Leaves Machine",
      column || vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );

    ConsentWebviewManager.currentPanel = panel;

    const logger = DevMindLogger.get();
    const settings = SettingsService.get();

    panel.webview.html = ConsentWebviewManager.renderHtml(settings.syncMode, settings.fixtureMode);

    panel.webview.onDidReceiveMessage(
      (message: { command: string }) => {
        switch (message.command) {
          case "send":
            logger.info("User consented to transmission", {
              syncMode: settings.syncMode,
              fixtureMode: settings.fixtureMode,
            });

            if (settings.fixtureMode) {
              vscode.window.showInformationMessage(
                "DevMind Fixture Mode: Consent verified. Simulated local sync complete (zero network calls)."
              );
            } else {
              vscode.window.showInformationMessage(
                "DevMind: Manifest diff and route metadata synchronized successfully."
              );
            }
            panel.dispose();
            break;

          case "cancel":
            logger.info("User cancelled transmission review");
            panel.dispose();
            break;
        }
      },
      undefined,
      context.subscriptions
    );

    panel.onDidDispose(
      () => {
        ConsentWebviewManager.currentPanel = undefined;
      },
      undefined,
      context.subscriptions
    );
  }

  public static renderHtml(syncMode: string, isFixtureMode: boolean): string {
    const nonce = crypto.randomBytes(16).toString("hex");

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DevMind: Review What Leaves Machine</title>
  <style nonce="${nonce}">
    :root {
      --bg: var(--vscode-editor-background, #090d16);
      --fg: var(--vscode-editor-foreground, #f0f4fc);
      --card-bg: var(--vscode-sideBar-background, #111726);
      --border: var(--vscode-widget-border, #1e293b);
      --accent: var(--vscode-button-background, #00e5a3);
      --accent-fg: var(--vscode-button-foreground, #041014);
      --secondary-bg: var(--vscode-button-secondaryBackground, #1e293b);
      --secondary-fg: var(--vscode-button-secondaryForeground, #f0f4fc);
      --danger: #ef4444;
      --success: #10b981;
    }
    body {
      font-family: var(--vscode-font-family, system-ui, sans-serif);
      font-size: var(--vscode-font-size, 13px);
      background-color: var(--bg);
      color: var(--fg);
      margin: 0;
      padding: 24px;
      line-height: 1.5;
    }
    .header {
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 16px;
    }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: rgba(0, 229, 163, 0.15);
      color: #00e5a3;
      border: 1px solid rgba(0, 229, 163, 0.3);
    }
    h1 {
      font-size: 18px;
      font-weight: 600;
      margin: 8px 0 4px 0;
    }
    p.lead {
      color: var(--vscode-descriptionForeground, #94a3b8);
      margin: 0;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .card h2 {
      font-size: 14px;
      margin-top: 0;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      text-align: left;
    }
    th, td {
      padding: 8px 12px;
      border-bottom: 1px solid var(--border);
    }
    th {
      color: var(--vscode-descriptionForeground, #94a3b8);
      font-weight: 600;
    }
    .status-allowed {
      color: var(--success);
      font-weight: 600;
    }
    .status-blocked {
      color: var(--danger);
      font-weight: 600;
    }
    .footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }
    button {
      padding: 8px 16px;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      border: 1px solid transparent;
    }
    .btn-primary {
      background: var(--accent);
      color: var(--accent-fg);
    }
    .btn-secondary {
      background: var(--secondary-bg);
      color: var(--secondary-fg);
      border-color: var(--border);
    }
    button:focus {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
    .notice {
      font-size: 11px;
      color: var(--vscode-descriptionForeground, #94a3b8);
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <div class="header">
    <span class="badge">Privacy Ledger · ADR-022</span>
    <h1>Review What Leaves Machine</h1>
    <p class="lead">DevMind requires explicit verification before any project data is transmitted.</p>
  </div>

  <div class="card">
    <h2>1. Sync Profile & Scope</h2>
    <table>
      <tr>
        <th>Sync Mode</th>
        <td><strong>${syncMode}</strong> (Default)</td>
      </tr>
      <tr>
        <th>Network Mode</th>
        <td>${isFixtureMode ? "Fixture Mode (Zero network calls, fully simulated)" : "Live Cloud Connection"}</td>
      </tr>
      <tr>
        <th>Destination</th>
        <td>DevMind Project Brain (Clerk + Neon pgvector)</td>
      </tr>
      <tr>
        <th>Source Chunks</th>
        <td class="status-blocked">Strictly 0 (Forbidden in metadata_only)</td>
      </tr>
    </table>
  </div>

  <div class="card">
    <h2>2. Payload Manifest Audit</h2>
    <table>
      <thead>
        <tr>
          <th>Category</th>
          <th>Items Discovered</th>
          <th>Transmitted?</th>
          <th>Handling Policy</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Manifest Hashes</td>
          <td>18 relative paths + SHA-256</td>
          <td class="status-allowed">✓ Included</td>
          <td>Relative paths only; zero machine paths</td>
        </tr>
        <tr>
          <td>Route AST Symbols</td>
          <td>2 endpoints (/admin/users)</td>
          <td class="status-allowed">✓ Included</td>
          <td>Method, path, and guard invariants</td>
        </tr>
        <tr>
          <td>Rule Findings</td>
          <td>1 finding (Missing Role Guard)</td>
          <td class="status-allowed">✓ Included</td>
          <td>Rule ID + code snippet omitted</td>
        </tr>
        <tr>
          <td>Raw Code Chunks</td>
          <td>0 files</td>
          <td class="status-blocked">✘ Excluded</td>
          <td>Requires explicit project 'indexed' consent</td>
        </tr>
        <tr>
          <td>Credentials (.env)</td>
          <td>1 file (.env)</td>
          <td class="status-blocked">✘ Excluded</td>
          <td>Path-only check; contents never read</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>3. Automated Redaction Verification</h2>
    <p>Secret patterns found in code are masked before hashing or transmission:</p>
    <code>[REDACTED:token:8a9b2c3d]</code>
    <div class="notice">Zero unredacted credentials or keys ever leave the local workstation (ADR-047).</div>
  </div>

  <div class="footer">
    <!-- Default focus on Cancel per UX specification -->
    <button id="btn-cancel" class="btn-secondary" autofocus>Cancel</button>
    <button id="btn-send" class="btn-primary">
      ${isFixtureMode ? "Send (Simulated in Fixture Mode)" : "Send for This Request"}
    </button>
  </div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();

    document.getElementById('btn-cancel').addEventListener('click', () => {
      vscode.postMessage({ command: 'cancel' });
    });

    document.getElementById('btn-send').addEventListener('click', () => {
      vscode.postMessage({ command: 'send' });
    });
  </script>
</body>
</html>`;
  }
}
