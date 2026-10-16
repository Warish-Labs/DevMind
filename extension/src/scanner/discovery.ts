/**
 * DevMind Workspace File Discovery Engine (docs/06 §4).
 * Recursively walks workspace, respecting exclusions, ignore files, credential guards, and size limits.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { DiscoveredFile, DiscoveryOptions, ScanSummary } from "./types";
import {
  isHardExcludedDirectory,
  isCredentialPath,
  isGeneratedOrMinified,
  isBinaryExtension,
  isBinaryContent,
  getLanguageMetadata,
  IgnoreMatcher,
} from "./ignore";
import { computeFileHash } from "./hasher";

const DEFAULT_MAX_FILE_SIZE = 1024 * 1024; // 1 MB ceiling

export class FileDiscoveryEngine {
  private readonly root: string;
  private readonly maxFileSize: number;
  private readonly ignoreMatcher: IgnoreMatcher;

  constructor(options: DiscoveryOptions) {
    this.root = path.resolve(options.workspaceRoot);
    this.maxFileSize = options.maxFileSize ?? DEFAULT_MAX_FILE_SIZE;
    this.ignoreMatcher = new IgnoreMatcher(options.customIgnoreGlobs ?? []);
  }

  /**
   * Discovers all workspace files adhering to the order of exclusion:
   * Hard exclusions -> .gitignore -> .devmindignore -> settings globs -> size/binary limits.
   */
  public async discover(): Promise<{ files: DiscoveredFile[]; summary: ScanSummary }> {
    // 1. Load root .gitignore and .devmindignore if present
    await this.loadIgnoreFile(".gitignore");
    await this.loadIgnoreFile(".devmindignore");

    const files: DiscoveredFile[] = [];
    await this.walkDirectory(this.root, "", files);

    // Build ScanSummary
    let tier1Count = 0;
    let tier2Count = 0;
    let tier3Count = 0;
    let skippedCount = 0;
    const skippedFiles: Array<{ path: string; reason: string }> = [];

    for (const f of files) {
      if (f.status === "ok") {
        if (f.languageTier === 1) tier1Count++;
        else if (f.languageTier === 2) tier2Count++;
        else tier3Count++;
      } else {
        skippedCount++;
        skippedFiles.push({
          path: f.relativePath,
          reason: f.skipReason ?? f.status,
        });
      }
    }

    const summary: ScanSummary = {
      workspaceRoot: this.root,
      scannedAt: new Date().toISOString(),
      totalFilesDiscovered: files.length,
      includedFilesCount: files.length - skippedCount,
      tier1Count,
      tier2Count,
      tier3Count,
      skippedCount,
      skippedFiles,
    };

    return { files, summary };
  }

  private async loadIgnoreFile(filename: string): Promise<void> {
    const filePath = path.join(this.root, filename);
    try {
      const content = await fs.readFile(filePath, "utf-8");
      this.ignoreMatcher.addPatterns(content.split(/\r?\n/));
    } catch {
      // Ignore file does not exist or cannot be read
    }
  }

  private async walkDirectory(
    currentDir: string,
    relParent: string,
    results: DiscoveredFile[]
  ): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(currentDir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      const name = entry.name;
      const relPath = relParent ? `${relParent}/${name}` : name;
      const absPath = path.join(currentDir, name);

      if (entry.isDirectory()) {
        if (isHardExcludedDirectory(name)) {
          continue; // Hard exclusion: never enter directory
        }
        if (this.ignoreMatcher.isIgnored(relPath + "/")) {
          continue; // Ignored directory
        }
        await this.walkDirectory(absPath, relPath, results);
      } else if (entry.isFile()) {
        const fileRecord = await this.evaluateFile(absPath, relPath);
        results.push(fileRecord);
      }
    }
  }

  private async evaluateFile(absPath: string, relPath: string): Promise<DiscoveredFile> {
    let stat;
    try {
      stat = await fs.stat(absPath);
    } catch {
      return {
        relativePath: relPath,
        absolutePath: absPath,
        size: 0,
        mtimeMs: 0,
        languageTier: 3,
        languageId: "unknown",
        status: "failed",
        isCredential: false,
        skipReason: "Could not stat file",
      };
    }

    const size = stat.size;
    const mtimeMs = stat.mtimeMs;
    const isCred = isCredentialPath(relPath);
    const { id: langId, tier } = getLanguageMetadata(relPath);

    // 1. Credential file: path-only handling, content NEVER read
    if (isCred) {
      return {
        relativePath: relPath,
        absolutePath: absPath,
        size,
        mtimeMs,
        languageTier: 3,
        languageId: langId,
        status: "skipped_credential",
        isCredential: true,
        skipReason: "Credential file (content never read per docs/06 §4)",
      };
    }

    // 2. Ignore check (.gitignore, .devmindignore, user globs)
    if (this.ignoreMatcher.isIgnored(relPath)) {
      return {
        relativePath: relPath,
        absolutePath: absPath,
        size,
        mtimeMs,
        languageTier: tier,
        languageId: langId,
        status: "skipped_ignored",
        isCredential: false,
        skipReason: "Matches ignore pattern",
      };
    }

    // 3. Generated / minified check
    if (isGeneratedOrMinified(relPath)) {
      return {
        relativePath: relPath,
        absolutePath: absPath,
        size,
        mtimeMs,
        languageTier: tier,
        languageId: langId,
        status: "skipped_ignored",
        isCredential: false,
        skipReason: "Generated or minified artifact",
      };
    }

    // 4. Binary extension check
    if (isBinaryExtension(relPath)) {
      return {
        relativePath: relPath,
        absolutePath: absPath,
        size,
        mtimeMs,
        languageTier: 3,
        languageId: langId,
        status: "skipped_binary",
        isCredential: false,
        skipReason: "Binary file extension",
      };
    }

    // 5. Size ceiling check (default 1 MB)
    if (size > this.maxFileSize) {
      return {
        relativePath: relPath,
        absolutePath: absPath,
        size,
        mtimeMs,
        languageTier: tier,
        languageId: langId,
        status: "skipped_too_large",
        isCredential: false,
        skipReason: `File size (${size} bytes) exceeds analysis ceiling (${this.maxFileSize} bytes)`,
      };
    }

    // 6. Sniff first 512 bytes for binary or generated header
    try {
      const handle = await fs.open(absPath, "r");
      const buffer = Buffer.alloc(Math.min(size, 512));
      if (buffer.length > 0) {
        await handle.read(buffer, 0, buffer.length, 0);
      }
      await handle.close();

      if (isBinaryContent(buffer)) {
        return {
          relativePath: relPath,
          absolutePath: absPath,
          size,
          mtimeMs,
          languageTier: 3,
          languageId: langId,
          status: "skipped_binary",
          isCredential: false,
          skipReason: "Binary content detected via null byte sniffing",
        };
      }

      const headerText = buffer.toString("utf-8");
      if (isGeneratedOrMinified(relPath, headerText)) {
        return {
          relativePath: relPath,
          absolutePath: absPath,
          size,
          mtimeMs,
          languageTier: tier,
          languageId: langId,
          status: "skipped_ignored",
          isCredential: false,
          skipReason: "Generated code header marker detected",
        };
      }
    } catch {
      // Fallback if read fails
    }

    // 7. Compute SHA-256 hash
    let contentHash: string | undefined;
    try {
      contentHash = await computeFileHash(absPath, relPath);
    } catch {
      contentHash = undefined;
    }

    return {
      relativePath: relPath,
      absolutePath: absPath,
      size,
      mtimeMs,
      languageTier: tier,
      languageId: langId,
      status: "ok",
      isCredential: false,
      contentHash,
    };
  }
}
