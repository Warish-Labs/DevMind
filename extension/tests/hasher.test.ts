import { describe, it, expect } from "vitest";
import path from "node:path";
import fs from "node:fs/promises";
import os from "node:os";
import {
  computeFileHash,
  computeNormalizedTextHash,
  computeRedactedTokenHash,
} from "../src/scanner/hasher";

describe("Scanner Hasher (docs/06 §5)", () => {
  it("computes deterministic SHA-256 over raw file content", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-hasher-"));
    const filePath = path.join(tmpDir, "sample.ts");
    await fs.writeFile(filePath, "const x = 42;\n", "utf-8");

    const hash = await computeFileHash(filePath, "sample.ts");
    expect(hash).toBeDefined();
    expect(hash).toHaveLength(64); // SHA-256 hex is 64 chars

    // Clean up
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("strictly refuses to read or hash credential files (path-only guard)", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-hasher-cred-"));
    const envFile = path.join(tmpDir, ".env.production");
    await fs.writeFile(envFile, "SECRET_KEY=supersecret123\n", "utf-8");

    await expect(computeFileHash(envFile, ".env.production")).rejects.toThrow(
      /Security violation: Attempted to read content of credential file/
    );

    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("normalizes CRLF to LF for consistent cross-platform chunk hashing", () => {
    const lfText = "line1\nline2\nline3\n";
    const crlfText = "line1\r\nline2\r\nline3\r\n";

    const hash1 = computeNormalizedTextHash(lfText);
    const hash2 = computeNormalizedTextHash(crlfText);

    expect(hash1).toBe(hash2);
  });

  it("produces deterministic 8-char redaction hash [REDACTED:token:hash8]", () => {
    const token = "sk_live_1234567890abcdef";
    const hash8 = computeRedactedTokenHash(token);

    expect(hash8).toHaveLength(8);
    expect(computeRedactedTokenHash(token)).toBe(hash8);
    expect(computeRedactedTokenHash("different_token")).not.toBe(hash8);
  });
});
