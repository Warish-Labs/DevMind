/**
 * DevMind Extension Sync Log Store (Milestone M9-07, docs/06 §9, §11.3, §13).
 *
 * Persists an append-only audit log of local-to-cloud synchronization attempts
 * outside the repository (Rule 5, ADR-047), tracking sync receipts, file counts,
 * staleness recoveries, and errors.
 */

import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

export type SyncStatus = "success" | "failed" | "stale_base_recovered" | "offline_queued";

export interface SyncLogEntry {
  id: string;
  timestamp: string; // ISO 8601 UTC
  projectId: string;
  status: SyncStatus;
  filesCount: number;
  versionsCreated: number;
  removedCount: number;
  symbolsCount: number;
  relationshipsCount: number;
  findingsIngested: number;
  staleBaseRecovered: boolean;
  syncMode: string;
  receiptHash?: string;
  durationMs?: number;
  error?: string;
}

export interface SyncLogData {
  version: number;
  workspaceRoot: string;
  entries: SyncLogEntry[];
}

export class SyncLogStore {
  private readonly storagePath: string;
  private readonly workspaceRoot: string;
  private data: SyncLogData;
  private loaded = false;
  private readonly maxEntries = 100;

  constructor(storageDirectory: string, workspaceRoot: string) {
    this.workspaceRoot = path.resolve(workspaceRoot);
    // Sync log is always persisted outside the repository per docs/06 §5 and ADR-047
    this.storagePath = path.join(storageDirectory, "sync-log.json");
    this.data = {
      version: 1,
      workspaceRoot: this.workspaceRoot,
      entries: [],
    };
  }

  public async load(): Promise<void> {
    try {
      const content = await fs.readFile(this.storagePath, "utf-8");
      const parsed = JSON.parse(content) as SyncLogData;
      if (parsed.workspaceRoot === this.workspaceRoot && Array.isArray(parsed.entries)) {
        this.data = parsed;
      }
    } catch {
      // Initialize fresh store if missing or corrupt
      this.data = {
        version: 1,
        workspaceRoot: this.workspaceRoot,
        entries: [],
      };
    }
    this.loaded = true;
  }

  public async save(): Promise<void> {
    const dir = path.dirname(this.storagePath);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(this.storagePath, JSON.stringify(this.data, null, 2), "utf-8");
  }

  /**
   * Records a new sync execution event in the log.
   */
  public async record(entry: Omit<SyncLogEntry, "id" | "timestamp">): Promise<SyncLogEntry> {
    if (!this.loaded) {
      await this.load();
    }

    const logEntry: SyncLogEntry = {
      ...entry,
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    };

    // Prepend new entry and cap to maxEntries
    this.data.entries.unshift(logEntry);
    if (this.data.entries.length > this.maxEntries) {
      this.data.entries = this.data.entries.slice(0, this.maxEntries);
    }

    await this.save();
    return logEntry;
  }

  /**
   * Returns recent sync log entries (newest first).
   */
  public getRecent(limit = 10): SyncLogEntry[] {
    return this.data.entries.slice(0, limit);
  }

  /**
   * Returns all recorded sync entries.
   */
  public getAll(): SyncLogEntry[] {
    return [...this.data.entries];
  }

  /**
   * Returns the most recent sync entry, or undefined if no syncs have run.
   */
  public getLastSync(): SyncLogEntry | undefined {
    return this.data.entries[0];
  }

  /**
   * Clears the sync log outside the repository.
   */
  public async clear(): Promise<void> {
    this.data.entries = [];
    await this.save();
  }

  public getStoragePath(): string {
    return this.storagePath;
  }
}
