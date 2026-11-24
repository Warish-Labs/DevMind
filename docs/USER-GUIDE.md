# 🧠 DevMind — User Guide

> **Your codebase, understood.** DevMind keeps a live, evidence-backed mental model of your entire project — security findings, bug history, living docs, deployment incidents, and more — shared between VS Code and your browser.

---

## ✨ What is DevMind?

DevMind is an **agentic software engineering platform** built around a continuously synchronized **Project Brain**. Instead of re-reading your repository from scratch on every AI request, DevMind maintains a knowledge graph of symbols, call hierarchies, AST dependencies, and semantic embeddings — updated locally by your VS Code extension, securely synced to the cloud on demand.

```
Your Machine (VS Code)          DevMind Cloud (Project Brain)
─────────────────────────       ─────────────────────────────
 Source code stays here    →    Symbols, findings, embeddings
 AST parsed locally        →    Hybrid RAG (keyword + vector)
 You consent before sync   →    Zero raw code stored
```

**Three ironclad guarantees:**
| Guarantee | What it means |
|---|---|
| 🔒 **Local-First** | Source code never leaves your machine without your explicit consent |
| 🧾 **Evidence-Gated** | Every finding has a resolvable E0–E2 proof — no hallucinations |
| 🏢 **Tenant-Isolated** | Your data is strictly partitioned from every other workspace |

---

## 🚀 Quick Start (3 Steps)

### Step 1 — Sign Up on the Web

1. Open **[https://devmind.warishlabs.in](https://devmind.warishlabs.in)**
2. Click **Sign Up** (top right) and authenticate with **Google**, **GitHub**, or **Email**
3. Complete the **3-step onboarding wizard**:
   - Name your workspace (e.g. `my-projects`)
   - Create a project (e.g. `backend-api`)
   - Choose sync mode — start with **metadata_only** (safest, recommended)

> **Already have an account?** Click **Sign In** — after authentication the header shows a **Dashboard →** button and your avatar instead of the sign-in/up buttons.

---

### Step 2 — Link Your VS Code Extension

Install the DevMind Companion extension into VS Code:

```bash
code --install-extension /path/to/DevMind/extension/dist/devmind-vscode.vsix
```

Or from the VS Code UI: `Extensions sidebar → ⋯ → Install from VSIX…`

**🔗 One-click linking (recommended):**

1. In the web app, go to **Settings → Extension Token** (`/settings/extension-token`)
2. Click **"Open in VS Code & Link Automatically"**
3. VS Code opens, the extension signs in, and your project is linked — done!

**Manual linking (alternative):**

1. Copy your token from the Extension Token page
2. In VS Code: `Ctrl+Shift+P` → `DevMind: Sign In` → paste token
3. `Ctrl+Shift+P` → `DevMind: Link Workspace to Project` → paste Project ID

---

### Step 3 — Scan & Sync

1. Open your project folder in VS Code
2. `Ctrl+Shift+P` → **`DevMind: Scan Workspace`**
3. Watch findings appear in the sidebar — zero network calls during scan!
4. When ready: `Ctrl+Shift+P` → **`DevMind: Trigger Sync Now`**
5. A **Consent Preview** shows exactly what will be uploaded — click **Accept & Sync**
6. Open the web app to see your Project Brain populate in real time

---

## 🔐 How the Extension Knows Who You Are

This is the key security design:

```
Web Browser (Clerk session)        VS Code Extension
──────────────────────────         ─────────────────
 1. Sign in with Clerk
 2. Visit /settings/extension-token
 3. Server issues scoped ext token  →  4. Token saved in SecretStorage
 5. Click "Open in VS Code" link    →  vscode://WarishLabs.devmind-vscode/connect?token=...
                                        Extension auto-signs in + links project
```

The extension token (`dme_at_...`) is:
- **Scoped** to your account only — it cannot access other workspaces
- **Stored encrypted** in VS Code's native `SecretStorage` (OS keychain-backed)
- **Never logged** or exposed in the output channel
- **Revocable** anytime from workspace settings on the web

---

## 🌐 Web Platform — What You Can Do

After signing in, navigate to your project to access:

### 🧠 Project Brain (`/projects/[id]/brain`)
Explore your codebase as a living knowledge graph. Inspect symbols, caller-callee chains, and semantic search across your entire codebase.

### 🤖 Project Mentor (`/projects/[id]/tasks`)
AI-powered task backlog with topological DAG scheduling. Never get blocked — Mentor always surfaces the next unblocked, highest-impact work item.

### 📖 Living Documentation (`/projects/[id]/docs`)
Automatically detects documentation drift between your code and your Markdown/OpenAPI specs. One-click unified diff patches to fix it.

### 🐛 Bug Memory (`/projects/[id]/bugs`)
Deduplicates runtime exceptions by canonical signature. Surfaces verified resolutions from historical incidents instantly.

### 🚀 Deployment Diagnosis (`/projects/[id]/deployments`)
Paste raw deployment logs. Gets probable root cause, cited log lines, and step-by-step fix commands. Auto-redacts credentials.

### 🔎 PR Intelligence (`/projects/[id]/pull-requests`)
GitHub App integration analyzes incoming PRs with evidence-backed security and architecture checks.

---

## 🔄 Sync Modes — Choosing Your Privacy Level

| Mode | What syncs | Use case |
|---|---|---|
| `metadata_only` | AST symbols, line ranges, finding IDs only | **Default — Maximum privacy** |
| `indexed` | Consented code chunks → pgvector embeddings | Full hybrid RAG / CodeMate reasoning |
| `disabled` | Nothing — local scan only | Fully air-gapped development |

Switch modes anytime in `Workspace Settings → Sync Mode`. Switching to `metadata_only` automatically purges any stored chunks (NFR-PRV-02).

---

## 🔧 VS Code Extension Commands

| Command | What it does |
|---|---|
| `DevMind: Scan Workspace` | Run full local AST scan (zero network) |
| `DevMind: Trigger Sync Now` | Sync scan metadata to Project Brain (shows consent preview) |
| `DevMind: Sign In` | Paste extension token to authenticate |
| `DevMind: Sign Out` | Clear tokens from SecretStorage |
| `DevMind: Link Workspace to Project` | Set the Project ID for this workspace |
| `DevMind: Review What Leaves Machine` | Open consent preview webview |
| `DevMind: Show Sync Log` | View full audit log of past sync operations |

---

## ⚙️ Configuration Reference

| Setting | Description | Default |
|---|---|---|
| `devmind.apiBaseUrl` | DevMind API endpoint | `https://api.devmind.warishlabs.in/api/v1` |
| `devmind.projectId` | Project UUID for sync | *(set via Link command)* |
| `devmind.syncMode` | `metadata_only` / `indexed` / `disabled` | `metadata_only` |
| `devmind.fixtureMode` | Offline mode with fixture data | `false` in production |

---

## 🛡️ Privacy & Security Guarantees

- **No source code stored** without `indexed` mode consent
- **Dual-tier redaction** — credentials masked client-side AND server-side before storage
- **Cross-tenant isolation** — every query scoped by `workspace_id + project_id`
- **Zero live DB connections** — schemas discovered from migrations, never from live TCP
- **Extension reads only** — all writes require explicit human approval

---

## ❓ Troubleshooting

### "Sign In / Sign Up buttons still show after I signed in"
Hard-refresh (`Ctrl+Shift+R`) — Clerk's session state needs a client-side hydration cycle. If it persists, check that `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set in `client/.env.local`.

### "Developer Access" form shows instead of Clerk sign-in
The `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` environment variable is missing. Add it to `client/.env.local`. You can still use the developer form to reach onboarding in local/offline mode.

### Extension shows "You must sign in before syncing"
Run `Ctrl+Shift+P` → `DevMind: Sign In`. Get your token from the web portal at `/settings/extension-token`.

### "Project ID cannot be empty" when syncing
Run `DevMind: Link Workspace to Project` and paste your project's UUID from the web app (`/projects` page → copy the ID from the URL).

### Sync succeeds but Brain shows no data
Make sure you ran `DevMind: Scan Workspace` first. Sync sends the last scan result — without a scan there is nothing to upload.

### Testing locally with no external services
```bash
node scripts/test-all.mjs --fast   # Full suite: client + server + extension + common
```

Set `devmind.fixtureMode: true` in VS Code settings to run the extension with zero network calls.

---

## 🏗️ Architecture at a Glance

```
┌─────────────────────────────────────┐
│          devmind.warishlabs.in      │  ← Next.js (Vercel Hobby)
│  Sign In · Dashboard · Brain UI     │
└──────────────┬──────────────────────┘
               │ Clerk JWT / API calls
┌──────────────▼──────────────────────┐
│   api.devmind.warishlabs.in         │  ← FastAPI + Celery (Render Free)
│   LangGraph agents · LLM gateway    │
│   Project Brain · Hybrid RAG        │
└──────────────┬──────────────────────┘
               │ pgvector + PostgreSQL
┌──────────────▼──────────────────────┐
│          Neon (Free tier)           │  ← 18 schema tables, HNSW index
└─────────────────────────────────────┘

VS Code Extension (local, zero network during scan)
  ↕ vscode://WarishLabs.devmind-vscode/connect  ← deep-link from web portal
  ↕ POST /api/v1/ext/token                   ← extension auth
  ↕ POST /api/v1/ext/sync                    ← consented metadata upload
```

---

*Last updated: 2026-11-24 · DevMind v0.2.1*
