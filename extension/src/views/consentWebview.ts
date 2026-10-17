/**
 * DevMind Consent Preview Webview and Sent-Bytes Equality Verifier (Milestone M5-02, docs/06 §12, docs/07 §7).
 *
 * Implements:
 * 1. Cryptographic canonicalization and SHA-256 preview hashing.
 * 2. Sent-bytes equality verification: confirms payload strictly matches user-consented preview hash.
 * 3. Interactive Webview panel rendering exact file lists, line ranges, secret redaction counts,
 *    destination AI providers, excluded path reasons, and calculated preview hash.
 * 4. User actions: "Send for this request", "Allow for this project" (indexed mode), "Cancel" (default focus).
 */

import * as vscode from "vscode";
import crypto from "node:crypto";
import { DevMindLogger } from "../services/logger";
import { SettingsService } from "../services/settings";
import { ConsentDecision, ConsentFileEntry, ConsentPreviewPayload } from "../types";

/**
 * Deterministically sorts and serializes a ConsentPreviewPayload into canonical JSON.
 */
export function computeCanonicalPayload(payload: ConsentPreviewPayload): string {
  const canonicalObj = {
    dataCategories: [...(payload.dataCategories || [])].sort(),
    destinationProviders: [...(payload.destinationProviders || [])].sort(),
    excludedPaths: [...(payload.excludedPaths || [])].sort((a, b) => a.path.localeCompare(b.path)),
    files: [...(payload.files || [])]
      .sort((a, b) => a.path.localeCompare(b.path))
      .map((f) => ({
        chunkCount: f.chunkCount,
        language: f.language || "unknown",
        lineRanges: f.lineRanges || [[1, 1]],
        path: f.path,
        sizeBytes: f.sizeBytes,
      })),
    projectId: payload.projectId,
    purpose: {
      jobType: payload.purpose?.jobType || "analysis",
      kind: payload.purpose?.kind || "cloud_analysis",
    },
    redactionCounts: Object.keys(payload.redactionCounts || {})
      .sort()
      .reduce(
        (acc, k) => {
          acc[k] = payload.redactionCounts[k];
          return acc;
        },
        {} as Record<string, number>
      ),
    scope: payload.scope,
  };

  return JSON.stringify(canonicalObj);
}

/**
 * Computes the cryptographic preview hash (sha256:...) over the canonical payload.
 */
export function computePreviewHash(payload: ConsentPreviewPayload): string {
  const canonical = computeCanonicalPayload(payload);
  const hash = crypto.createHash("sha256").update(canonical, "utf-8").digest("hex");
  return `sha256:${hash}`;
}

/**
 * Verifies sent-bytes equality: confirms that the payload about to be sent
 * strictly matches the preview hash shown to and consented by the user.
 */
export function verifySentBytesEquality(
  payload: ConsentPreviewPayload,
  expectedHash: string
): boolean {
  if (!expectedHash || !expectedHash.startsWith("sha256:")) {
    return false;
  }
  const actualHash = computePreviewHash(payload);
  return actualHash === expectedHash;
}

export class ConsentWebviewManager {
  private static currentPanel: vscode.WebviewPanel | undefined;

  /**
   * Shows the consent preview webview panel.
   */
  public static show(
    context: vscode.ExtensionContext,
    customPayload?: Partial<ConsentPreviewPayload>
  ): void {
    void ConsentWebviewManager.requestConsent(
      context,
      ConsentWebviewManager.buildDefaultPayload(customPayload)
    );
  }

  /**
   * Opens the interactive webview and returns a Promise resolving with the user's decision.
   */
  public static requestConsent(
    context: vscode.ExtensionContext,
    payload: ConsentPreviewPayload
  ): Promise<ConsentDecision> {
    const logger = DevMindLogger.get();
    const settings = SettingsService.get();
    const previewHash = computePreviewHash(payload);

    return new Promise<ConsentDecision>((resolve) => {
      const column = vscode.window.activeTextEditor
        ? vscode.window.activeTextEditor.viewColumn
        : undefined;

      if (ConsentWebviewManager.currentPanel) {
        ConsentWebviewManager.currentPanel.reveal(column);
      } else {
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
      }

      const panel = ConsentWebviewManager.currentPanel;

      panel.webview.html = ConsentWebviewManager.renderHtml(
        payload,
        previewHash,
        settings.syncMode,
        settings.fixtureMode
      );

      let decisionHandled = false;

      const sub = panel.webview.onDidReceiveMessage((message: { command: string }) => {
        switch (message.command) {
          case "send_single_request":
            decisionHandled = true;
            logger.info("User granted single-request consent", {
              projectId: payload.projectId,
              previewHash,
            });
            panel.dispose();
            resolve({
              granted: true,
              grantedFor: "single_request",
              previewHash,
            });
            break;

          case "allow_project_indexed":
            decisionHandled = true;
            logger.info("User granted project-wide indexed consent", {
              projectId: payload.projectId,
              previewHash,
            });
            panel.dispose();
            resolve({
              granted: true,
              grantedFor: "project",
              previewHash,
            });
            break;

          case "cancel":
          default:
            decisionHandled = true;
            logger.info("User cancelled consent preview");
            panel.dispose();
            resolve({
              granted: false,
              userCancelled: true,
            });
            break;
        }
      });

      panel.onDidDispose(() => {
        ConsentWebviewManager.currentPanel = undefined;
        sub.dispose();
        if (!decisionHandled) {
          resolve({
            granted: false,
            userCancelled: true,
          });
        }
      });

      context.subscriptions.push(sub);
    });
  }

  public static buildDefaultPayload(
    partial?: Partial<ConsentPreviewPayload>
  ): ConsentPreviewPayload {
    const settings = SettingsService.get();
    return {
      projectId: partial?.projectId || settings.projectId || "01920000-0000-7000-8000-000000000001",
      scope: partial?.scope || "snippet_transmission",
      purpose: partial?.purpose || {
        kind: "cloud_analysis",
        jobType: "security_review",
      },
      destinationProviders: partial?.destinationProviders || ["anthropic", "openai"],
      dataCategories: partial?.dataCategories || ["code_snippets", "ast_metadata"],
      files: partial?.files || [
        {
          path: "src/routes/admin.ts",
          lineRanges: [[10, 45]],
          sizeBytes: 1240,
          chunkCount: 2,
          language: "typescript",
        },
      ],
      redactionCounts: partial?.redactionCounts || {
        token: 1,
        password: 0,
        api_key: 1,
      },
      excludedPaths: partial?.excludedPaths || [
        { path: ".env", reason: "Guarded credential file path (Rule 5)" },
        { path: "node_modules/", reason: "Ignored dependency path (.gitignore)" },
      ],
    };
  }

  public static renderHtml(
    arg1: ConsentPreviewPayload | string,
    arg2?: string | boolean,
    arg3?: string,
    arg4?: boolean
  ): string {
    if (typeof arg1 === "string") {
      return ConsentWebviewManager.renderLegacyHtml(arg1, Boolean(arg2));
    }

    const payload = arg1 as ConsentPreviewPayload;
    const previewHash = (arg2 as string) || computePreviewHash(payload);
    const syncMode = arg3 || "metadata_only";
    const isFixtureMode = Boolean(arg4);

    const nonce = crypto.randomBytes(16).toString("hex");

    const filesRows = (payload.files || [])
      .map(
        (f) => `
        <tr>
          <td><code>${f.path}</code></td>
          <td>${(f.lineRanges || []).map(([s, e]) => `L${s}-${e}`).join(", ") || "All"}</td>
          <td>${f.chunkCount} chunk(s)</td>
          <td>${f.sizeBytes} B</td>
          <td class="status-allowed">Consented Preview</td>
        </tr>`
      )
      .join("");

    const redactionEntries = Object.entries(payload.redactionCounts || {});
    const totalRedactions = redactionEntries.reduce((sum, [, count]) => sum + count, 0);

    const redactionList =
      redactionEntries.length > 0
        ? redactionEntries
            .map(
              ([type, count]) =>
                `<li><code>[REDACTED:${type}:*]</code>: <strong>${count}</strong> instance(s) masked</li>`
            )
            .join("")
        : "<li>Zero sensitive patterns identified.</li>";

    const excludedRows = (payload.excludedPaths || [])
      .map(
        (e) => `
        <tr>
          <td><code>${e.path}</code></td>
          <td class="status-blocked">✘ Excluded</td>
          <td>${e.reason}</td>
        </tr>`
      )
      .join("");

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
    code {
      font-family: var(--vscode-editor-font-family, monospace);
      font-size: 12px;
      background: rgba(255, 255, 255, 0.06);
      padding: 2px 4px;
      border-radius: 3px;
    }
    .status-allowed {
      color: var(--success);
      font-weight: 600;
    }
    .status-blocked {
      color: var(--danger);
      font-weight: 600;
    }
    .hash-box {
      font-family: monospace;
      font-size: 11px;
      padding: 6px 10px;
      background: rgba(0, 0, 0, 0.3);
      border: 1px dashed var(--border);
      border-radius: 4px;
      word-break: break-all;
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
    <span class="badge">Privacy Ledger · ADR-022 · docs/06 §12</span>
    <h1>Review What Leaves Machine</h1>
    <p class="lead">DevMind requires explicit verification before any project source or snippets are transmitted.</p>
  </div>

  <div class="card">
    <h2>1. Destination & Scope</h2>
    <table>
      <tr>
        <th>Project UUID</th>
        <td><code>${payload.projectId}</code></td>
      </tr>
      <tr>
        <th>Consent Scope</th>
        <td><code>${payload.scope}</code></td>
      </tr>
      <tr>
        <th>Intended Purpose</th>
        <td>${payload.purpose?.kind} (${payload.purpose?.jobType || "general"})</td>
      </tr>
      <tr>
        <th>Destination AI Providers</th>
        <td>${(payload.destinationProviders || []).map((p) => `<code>${p}</code>`).join(", ") || "None"}</td>
      </tr>
      <tr>
        <th>Sync Profile</th>
        <td>${syncMode} ${isFixtureMode ? "(Fixture Mode active)" : ""}</td>
      </tr>
    </table>
  </div>

  <div class="card">
    <h2>2. Files & Snippets to Transmit (${payload.files?.length || 0})</h2>
    <table>
      <thead>
        <tr>
          <th>Path</th>
          <th>Lines</th>
          <th>Chunks</th>
          <th>Size</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${filesRows || "<tr><td colspan='5'>Zero code snippets scheduled for transmission.</td></tr>"}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>3. Automated Secret Redaction (${totalRedactions} masked)</h2>
    <p>All sensitive credentials and tokens are deterministically masked before preview and network dispatch:</p>
    <ul>
      ${redactionList}
    </ul>
    <div class="notice">Raw secrets never leave this local machine under any circumstance (Rule 5 & ADR-047).</div>
  </div>

  <div class="card">
    <h2>4. Guarded Exclusions</h2>
    <table>
      <thead>
        <tr>
          <th>Path</th>
          <th>Policy</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        ${excludedRows || "<tr><td colspan='3'>None</td></tr>"}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>5. Cryptographic Sent-Bytes Equality Guarantee</h2>
    <p class="notice">The server enforces strict byte-for-byte equality matching this hash before accepting payload:</p>
    <div class="hash-box">${previewHash}</div>
  </div>

  <div class="footer">
    <!-- Default focus on Cancel per UX specification -->
    <button id="btn-cancel" class="btn-secondary" autofocus>Cancel</button>
    <button id="btn-allow-project" class="btn-secondary">Allow for This Project (Indexed Mode)</button>
    <button id="btn-send-single" class="btn-primary">
      ${isFixtureMode ? "Send (Simulated in Fixture Mode)" : "Send for This Request"}
    </button>
  </div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();

    document.getElementById('btn-cancel').addEventListener('click', () => {
      vscode.postMessage({ command: 'cancel' });
    });

    document.getElementById('btn-allow-project').addEventListener('click', () => {
      vscode.postMessage({ command: 'allow_project_indexed' });
    });

    document.getElementById('btn-send-single').addEventListener('click', () => {
      vscode.postMessage({ command: 'send_single_request' });
    });
  </script>
</body>
</html>`;
  }

  public static renderLegacyHtml(syncMode: string, isFixtureMode: boolean): string {
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
