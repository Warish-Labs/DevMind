import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { SyncLogStore, SyncLogEntry } from "../src/scanner/syncLog";
import { SyncClient } from "../src/services/syncClient";
import { ExtensionAuthService } from "../src/services/auth";
import { LocalManifestStore } from "../src/scanner/manifest";
import {
  SyncViewProvider,
  SyncReceiptTreeItem,
  SyncHistoryGroupTreeItem,
  SyncLogEntryTreeItem,
  SyncActionsGroupTreeItem,
} from "../src/views/syncView";
import { MockSecretStorage } from "./vscode-mock";
import * as vscode from "vscode";

describe("Extension Sync Log (Milestone M9-07, docs/06 §9, §11.3, §13)", () => {
  let tempDir: string;
  let storageDir: string;
  let workspaceRoot: string;
  let logStore: SyncLogStore;

  beforeEach(async () => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "devmind-synclog-test-"));
    storageDir = path.join(tempDir, "storage");
    workspaceRoot = path.join(tempDir, "workspace");
    fs.mkdirSync(storageDir, { recursive: true });
    fs.mkdirSync(workspaceRoot, { recursive: true });

    logStore = new SyncLogStore(storageDir, workspaceRoot);
    await logStore.load();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  describe("SyncLogStore", () => {
    it("persists entries outside workspace root in designated storage path", async () => {
      expect(logStore.getStoragePath()).toBe(path.join(storageDir, "sync-log.json"));
      expect(logStore.getStoragePath().startsWith(workspaceRoot)).toBe(false);

      const entry = await logStore.record({
        projectId: "01920000-0000-7000-8000-000000000001",
        status: "success",
        filesCount: 15,
        versionsCreated: 15,
        removedCount: 0,
        symbolsCount: 64,
        relationshipsCount: 32,
        findingsIngested: 4,
        staleBaseRecovered: false,
        syncMode: "metadata_only",
        receiptHash: "receipt-01920000-12345",
        durationMs: 125,
      });

      expect(entry.id).toBeDefined();
      expect(entry.timestamp).toBeDefined();
      expect(fs.existsSync(logStore.getStoragePath())).toBe(true);

      // Verify file contents
      const fileData = JSON.parse(fs.readFileSync(logStore.getStoragePath(), "utf-8"));
      expect(fileData.entries.length).toBe(1);
      expect(fileData.entries[0].filesCount).toBe(15);
      expect(fileData.entries[0].receiptHash).toBe("receipt-01920000-12345");
    });

    it("orders entries newest first and retrieves last sync", async () => {
      await logStore.record({
        projectId: "01920000-0000-7000-8000-000000000001",
        status: "failed",
        filesCount: 0,
        versionsCreated: 0,
        removedCount: 0,
        symbolsCount: 0,
        relationshipsCount: 0,
        findingsIngested: 0,
        staleBaseRecovered: false,
        syncMode: "metadata_only",
        error: "Network timeout",
      });

      await logStore.record({
        projectId: "01920000-0000-7000-8000-000000000001",
        status: "success",
        filesCount: 20,
        versionsCreated: 20,
        removedCount: 1,
        symbolsCount: 88,
        relationshipsCount: 40,
        findingsIngested: 6,
        staleBaseRecovered: true,
        syncMode: "metadata_only",
        receiptHash: "receipt-01920000-latest",
      });

      const recent = logStore.getRecent(10);
      expect(recent.length).toBe(2);
      expect(recent[0].status).toBe("success");
      expect(recent[1].status).toBe("failed");

      const last = logStore.getLastSync();
      expect(last?.status).toBe("success");
      expect(last?.receiptHash).toBe("receipt-01920000-latest");
    });

    it("enforces maximum entries ceiling (100 entries)", async () => {
      for (let i = 0; i < 110; i++) {
        await logStore.record({
          projectId: "01920000-0000-7000-8000-000000000001",
          status: "success",
          filesCount: i,
          versionsCreated: i,
          removedCount: 0,
          symbolsCount: 10,
          relationshipsCount: 5,
          findingsIngested: 1,
          staleBaseRecovered: false,
          syncMode: "metadata_only",
        });
      }

      const all = logStore.getAll();
      expect(all.length).toBe(100);
      // Newest should be i = 109
      expect(all[0].filesCount).toBe(109);
    });

    it("clears entries when clear() is invoked", async () => {
      await logStore.record({
        projectId: "01920000-0000-7000-8000-000000000001",
        status: "success",
        filesCount: 5,
        versionsCreated: 5,
        removedCount: 0,
        symbolsCount: 20,
        relationshipsCount: 10,
        findingsIngested: 2,
        staleBaseRecovered: false,
        syncMode: "metadata_only",
      });

      expect(logStore.getAll().length).toBe(1);
      await logStore.clear();
      expect(logStore.getAll().length).toBe(0);
      expect(logStore.getLastSync()).toBeUndefined();
    });
  });

  describe("SyncClient Integration with SyncLogStore", () => {
    it("records failed sync attempt when not authenticated", async () => {
      const mockSecrets = new MockSecretStorage();
      const authService = ExtensionAuthService.init(mockSecrets as unknown as vscode.SecretStorage);
      const syncClient = new SyncClient(authService);
      const manifestStore = new LocalManifestStore(storageDir, workspaceRoot);

      const res = await syncClient.sync({
        projectId: "01920000-0000-7000-8000-000000000001",
        workspaceRoot,
        manifestStore,
        syncLogStore: logStore,
        findings: [],
        modules: [],
        databaseModels: [],
      });

      expect(res.success).toBe(false);
      expect(logStore.getAll().length).toBe(1);

      const entry = logStore.getLastSync();
      expect(entry?.status).toBe("failed");
      expect(entry?.error).toContain("Not authenticated");
      expect(entry?.durationMs).toBeGreaterThanOrEqual(0);
    });
  });

  describe("SyncViewProvider Integration", () => {
    it("renders 6 root items including dynamic receipt and Sync History group", async () => {
      const provider = new SyncViewProvider(logStore);
      const roots = await provider.getChildren();

      expect(roots.length).toBe(6);

      const receiptItem = roots.find(
        (r): r is SyncReceiptTreeItem => r instanceof SyncReceiptTreeItem
      );
      expect(receiptItem?.label).toContain("Last Receipt: Simulated local receipt");

      const historyGroup = roots.find(
        (r): r is SyncHistoryGroupTreeItem => r instanceof SyncHistoryGroupTreeItem
      );
      expect(historyGroup).toBeDefined();
      expect(historyGroup?.label).toBe("Sync History");
      expect(historyGroup?.description).toBe("0 event(s)");
    });

    it("populates SyncLogEntryTreeItem children when events exist in store", async () => {
      await logStore.record({
        projectId: "01920000-0000-7000-8000-000000000001",
        status: "success",
        filesCount: 12,
        versionsCreated: 12,
        removedCount: 0,
        symbolsCount: 45,
        relationshipsCount: 22,
        findingsIngested: 3,
        staleBaseRecovered: false,
        syncMode: "metadata_only",
        receiptHash: "receipt-sha256-abc12345",
        durationMs: 95,
      });

      const provider = new SyncViewProvider(logStore);
      const roots = await provider.getChildren();

      const receiptItem = roots.find(
        (r): r is SyncReceiptTreeItem => r instanceof SyncReceiptTreeItem
      );
      expect(receiptItem?.label).toContain("receipt-sha256-a...");
      expect(receiptItem?.description).toContain("✓ 12 file(s)");

      const historyGroup = roots.find(
        (r): r is SyncHistoryGroupTreeItem => r instanceof SyncHistoryGroupTreeItem
      );
      const historyChildren = await provider.getChildren(historyGroup);
      expect(historyChildren.length).toBe(1);

      const entryItem = historyChildren[0] as SyncLogEntryTreeItem;
      expect(entryItem.label).toContain("✓");
      expect(entryItem.description).toContain("12 file(s), 45 sym (95ms)");
      expect(entryItem.tooltip).toContain("receipt-sha256-abc12345");
      expect(entryItem.command?.command).toBe("devmind.showSyncLog");
    });

    it("includes View Sync Log and Clear Sync History in Actions group", async () => {
      const provider = new SyncViewProvider(logStore);
      const roots = await provider.getChildren();

      const actionsGroup = roots.find(
        (r): r is SyncActionsGroupTreeItem => r instanceof SyncActionsGroupTreeItem
      );
      expect(actionsGroup).toBeDefined();

      const actions = await provider.getChildren(actionsGroup);
      expect(actions.length).toBe(4);
      expect(actions.some((a) => a.command?.command === "devmind.showSyncLog")).toBe(true);
      expect(actions.some((a) => a.command?.command === "devmind.clearSyncLog")).toBe(true);
    });
  });
});
