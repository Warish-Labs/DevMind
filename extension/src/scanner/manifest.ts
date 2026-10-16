/**
 * DevMind Local Manifest Store (docs/06 §5).
 * Stores version-aware file hashes, language tiers, parse statuses, and finding IDs outside the repository.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { DiscoveredFile, LanguageTier, ScanStatus } from "./types";
import { computeFileHash } from "./hasher";

export const CURRENT_RULES_VERSION = "0.1.0";

export interface ManifestRecord {
  relativePath: string;
  size: number;
  mtimeMs: number;
  contentHash: string;
  languageTier: LanguageTier;
  languageId: string;
  parseStatus: ScanStatus;
  symbolCount: number;
  relationshipCount: number;
  rulesVersion: string;
  findingIds: string[];
  lastSyncedHash?: string;
  updatedAt: string;
}

export interface ManifestData {
  version: number;
  rulesVersion: string;
  workspaceRoot: string;
  lastScannedAt?: string;
  files: Record<string, ManifestRecord>;
}

export type FileDirtyStatus = "unchanged" | "modified" | "new" | "deleted";

export class LocalManifestStore {
  private readonly storagePath: string;
  private readonly workspaceRoot: string;
  private data: ManifestData;
  private loaded = false;

  constructor(storageDirectory: string, workspaceRoot: string) {
    this.workspaceRoot = path.resolve(workspaceRoot);
    // Manifest is always stored outside the repository per docs/06 §5
    this.storagePath = path.join(storageDirectory, "manifest.json");
    this.data = {
      version: 1,
      rulesVersion: CURRENT_RULES_VERSION,
      workspaceRoot: this.workspaceRoot,
      files: {},
    };
  }

  public async load(): Promise<void> {
    try {
      const content = await fs.readFile(this.storagePath, "utf-8");
      const parsed = JSON.parse(content) as ManifestData;
      if (parsed.workspaceRoot === this.workspaceRoot) {
        this.data = parsed;
      }
    } catch {
      // Manifest does not exist or corrupted; re-initialize clean
      this.data = {
        version: 1,
        rulesVersion: CURRENT_RULES_VERSION,
        workspaceRoot: this.workspaceRoot,
        files: {},
      };
    }
    this.loaded = true;
  }

  public async save(): Promise<void> {
    const dir = path.dirname(this.storagePath);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(this.storagePath, JSON.stringify(this.data, null, 2), "utf-8");
  }

  public getRecord(relativePath: string): ManifestRecord | undefined {
    return this.data.files[relativePath];
  }

  public getAllRecords(): ManifestRecord[] {
    return Object.values(this.data.files);
  }

  /**
   * Fast incremental dirty-checking algorithm (docs/06 §5):
   * 1. If not in manifest: "new"
   * 2. If size & mtime unchanged: "unchanged" (keep stored hash without disk read)
   * 3. Otherwise compute content hash:
   *    - if hash matches stored hash: update (size, mtime) and return "unchanged"
   *    - if hash differs: "modified"
   */
  public async checkDirty(
    file: DiscoveredFile
  ): Promise<{ status: FileDirtyStatus; contentHash: string }> {
    if (!this.loaded) {
      await this.load();
    }

    const existing = this.data.files[file.relativePath];
    if (!existing) {
      const hash =
        file.contentHash ?? (await computeFileHash(file.absolutePath, file.relativePath));
      return { status: "new", contentHash: hash };
    }

    // Fast path: unchanged size & mtime
    if (existing.size === file.size && existing.mtimeMs === file.mtimeMs) {
      return { status: "unchanged", contentHash: existing.contentHash };
    }

    // Size or mtime differed: verify content hash
    const currentHash =
      file.contentHash ?? (await computeFileHash(file.absolutePath, file.relativePath));

    if (currentHash === existing.contentHash) {
      // False alarm (e.g. touch or line-ending preserved): update timestamps without rescan
      existing.size = file.size;
      existing.mtimeMs = file.mtimeMs;
      return { status: "unchanged", contentHash: currentHash };
    }

    return { status: "modified", contentHash: currentHash };
  }

  /**
   * Updates manifest with completed scan results.
   */
  public recordFile(
    file: DiscoveredFile,
    contentHash: string,
    symbolCount = 0,
    relationshipCount = 0,
    findingIds: string[] = []
  ): void {
    const existing = this.data.files[file.relativePath];
    this.data.files[file.relativePath] = {
      relativePath: file.relativePath,
      size: file.size,
      mtimeMs: file.mtimeMs,
      contentHash,
      languageTier: file.languageTier,
      languageId: file.languageId,
      parseStatus: file.status,
      symbolCount,
      relationshipCount,
      rulesVersion: CURRENT_RULES_VERSION,
      findingIds,
      lastSyncedHash: existing?.lastSyncedHash,
      updatedAt: new Date().toISOString(),
    };
  }

  /**
   * Prunes removed paths that no longer exist in the discovered files list.
   */
  public pruneRemovedFiles(activeRelativePaths: Set<string>): string[] {
    const removed: string[] = [];
    for (const relPath of Object.keys(this.data.files)) {
      if (!activeRelativePaths.has(relPath)) {
        delete this.data.files[relPath];
        removed.push(relPath);
      }
    }
    return removed;
  }

  /**
   * Computes diff of files whose content hash has changed since last sync.
   */
  public getPendingSyncFiles(): ManifestRecord[] {
    return Object.values(this.data.files).filter(
      (rec) => rec.parseStatus === "ok" && rec.contentHash !== rec.lastSyncedHash
    );
  }

  /**
   * Marks files as synced to cloud Project Brain with given receipt hash.
   */
  public markSynced(relativePath: string, receiptHash: string): void {
    const rec = this.data.files[relativePath];
    if (rec) {
      rec.lastSyncedHash = receiptHash;
    }
  }
}
