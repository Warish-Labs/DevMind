/**
 * DevMind Deterministic Hasher (docs/06 §5).
 * Computes SHA-256 hashes over raw file bytes and normalized chunk content.
 */

import crypto from "node:crypto";
import fs from "node:fs/promises";
import { isCredentialPath } from "./ignore";

/**
 * Computes SHA-256 hash over raw file bytes.
 * Throws error if attempted on a credential file to enforce the path-only boundary.
 */
export async function computeFileHash(absolutePath: string, relativePath: string): Promise<string> {
  if (isCredentialPath(relativePath)) {
    throw new Error(
      `Security violation: Attempted to read content of credential file ${relativePath}. Credential files are path-only.`
    );
  }

  const bytes = await fs.readFile(absolutePath);
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

/**
 * Computes SHA-256 hash over line-ending-normalized text (CRLF -> LF).
 * Used for stable chunk and snippet hashing across Windows/Linux checkouts.
 */
export function computeNormalizedTextHash(text: string): string {
  const normalized = text.replace(/\r\n/g, "\n");
  return crypto.createHash("sha256").update(normalized, "utf8").digest("hex");
}

/**
 * Computes an 8-character deterministic token digest for safe redacted logging: [REDACTED:token:hash8].
 */
export function computeRedactedTokenHash(token: string): string {
  const hash = crypto.createHash("sha256").update(token, "utf8").digest("hex");
  return hash.slice(0, 8);
}
