/**
 * Types for DevMind Local Scanner, Discovery, and File Ingestion (docs/06 §4-§8).
 */

export type LanguageTier = 1 | 2 | 3;

export type ScanStatus =
  | "ok"
  | "skipped_too_large"
  | "skipped_binary"
  | "skipped_credential"
  | "skipped_ignored"
  | "partial"
  | "failed";

export interface DiscoveredFile {
  relativePath: string;
  absolutePath: string;
  size: number;
  mtimeMs: number;
  languageTier: LanguageTier;
  languageId: string;
  status: ScanStatus;
  isCredential: boolean;
  contentHash?: string;
  skipReason?: string;
}

export interface DiscoveryOptions {
  workspaceRoot: string;
  maxFileSize?: number; // Default: 1 MB (1,048,576 bytes)
  customIgnoreGlobs?: string[];
}

export interface ScanSummary {
  workspaceRoot: string;
  scannedAt: string;
  totalFilesDiscovered: number;
  includedFilesCount: number;
  tier1Count: number;
  tier2Count: number;
  tier3Count: number;
  skippedCount: number;
  skippedFiles: Array<{ path: string; reason: string }>;
}
