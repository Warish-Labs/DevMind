import { describe, it, expect, beforeEach, afterEach } from "vitest";
import path from "node:path";
import fs from "node:fs/promises";
import os from "node:os";
import { LocalManifestStore, CURRENT_RULES_VERSION } from "../src/scanner/manifest";
import { DiscoveredFile } from "../src/scanner/types";

describe("Local Manifest Store (docs/06 §5)", () => {
  let tmpStorageDir: string;
  let tmpWorkspaceDir: string;
  let store: LocalManifestStore;

  beforeEach(async () => {
    tmpStorageDir = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-storage-"));
    tmpWorkspaceDir = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-workspace-"));
    store = new LocalManifestStore(tmpStorageDir, tmpWorkspaceDir);
  });

  afterEach(async () => {
    await fs.rm(tmpStorageDir, { recursive: true, force: true });
    await fs.rm(tmpWorkspaceDir, { recursive: true, force: true });
  });

  it("initializes clean and persists manifest to disk outside workspace", async () => {
    await store.load();
    expect(store.getAllRecords()).toHaveLength(0);

    const dummyFile: DiscoveredFile = {
      relativePath: "src/app.ts",
      absolutePath: path.join(tmpWorkspaceDir, "src/app.ts"),
      size: 120,
      mtimeMs: 1000,
      languageTier: 1,
      languageId: "typescript",
      status: "ok",
      isCredential: false,
    };

    store.recordFile(dummyFile, "hash_app_123", 5, 2, ["f_rule_01"]);
    await store.save();

    // Re-instantiate from storage to verify persistence
    const reloaded = new LocalManifestStore(tmpStorageDir, tmpWorkspaceDir);
    await reloaded.load();

    const record = reloaded.getRecord("src/app.ts");
    expect(record).toBeDefined();
    expect(record?.contentHash).toBe("hash_app_123");
    expect(record?.symbolCount).toBe(5);
    expect(record?.relationshipCount).toBe(2);
    expect(record?.findingIds).toContain("f_rule_01");
    expect(record?.rulesVersion).toBe(CURRENT_RULES_VERSION);
  });

  it("handles fast-path and content dirty-checking per docs/06 §5", async () => {
    const filePath = path.join(tmpWorkspaceDir, "src/service.ts");
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, "export const s = 1;\n");
    const stat = await fs.stat(filePath);

    const file: DiscoveredFile = {
      relativePath: "src/service.ts",
      absolutePath: filePath,
      size: stat.size,
      mtimeMs: stat.mtimeMs,
      languageTier: 1,
      languageId: "typescript",
      status: "ok",
      isCredential: false,
    };

    // 1. Unseen file returns 'new'
    const check1 = await store.checkDirty(file);
    expect(check1.status).toBe("new");
    expect(check1.contentHash).toBeDefined();

    store.recordFile(file, check1.contentHash);

    // 2. Unchanged size & mtime returns 'unchanged' (fast-path)
    const check2 = await store.checkDirty(file);
    expect(check2.status).toBe("unchanged");
    expect(check2.contentHash).toBe(check1.contentHash);

    // 3. File modified -> returns 'modified'
    await fs.writeFile(filePath, "export const s = 2; // modified\n");
    const stat2 = await fs.stat(filePath);
    const modifiedFile: DiscoveredFile = {
      ...file,
      size: stat2.size,
      mtimeMs: stat2.mtimeMs,
    };

    const check3 = await store.checkDirty(modifiedFile);
    expect(check3.status).toBe("modified");
    expect(check3.contentHash).not.toBe(check1.contentHash);
  });

  it("prunes deleted files from manifest and tracks pending sync items", async () => {
    await store.load();

    const fileA: DiscoveredFile = {
      relativePath: "src/a.ts",
      absolutePath: path.join(tmpWorkspaceDir, "src/a.ts"),
      size: 50,
      mtimeMs: 100,
      languageTier: 1,
      languageId: "typescript",
      status: "ok",
      isCredential: false,
    };

    const fileB: DiscoveredFile = {
      relativePath: "src/b.ts",
      absolutePath: path.join(tmpWorkspaceDir, "src/b.ts"),
      size: 60,
      mtimeMs: 200,
      languageTier: 1,
      languageId: "typescript",
      status: "ok",
      isCredential: false,
    };

    store.recordFile(fileA, "hash_a");
    store.recordFile(fileB, "hash_b");

    // Both files are un-synced initially
    expect(store.getPendingSyncFiles()).toHaveLength(2);

    // Mark fileA as synced
    store.markSynced("src/a.ts", "hash_a");
    expect(store.getPendingSyncFiles()).toHaveLength(1);
    expect(store.getPendingSyncFiles()[0].relativePath).toBe("src/b.ts");

    // Prune removed files (suppose b.ts was deleted from workspace)
    const activePaths = new Set(["src/a.ts"]);
    const removed = store.pruneRemovedFiles(activePaths);

    expect(removed).toEqual(["src/b.ts"]);
    expect(store.getRecord("src/b.ts")).toBeUndefined();
    expect(store.getRecord("src/a.ts")).toBeDefined();
  });
});
