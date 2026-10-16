import { describe, it, expect } from "vitest";
import path from "node:path";
import fs from "node:fs/promises";
import os from "node:os";
import { FileDiscoveryEngine } from "../src/scanner/discovery";
import { IgnoreMatcher, isCredentialPath, isHardExcludedDirectory } from "../src/scanner/ignore";

describe("File Discovery & Ignore Engine (docs/06 §4)", () => {
  it("verifies hard exclusion directory set", () => {
    expect(isHardExcludedDirectory("node_modules")).toBe(true);
    expect(isHardExcludedDirectory(".git")).toBe(true);
    expect(isHardExcludedDirectory(".next")).toBe(true);
    expect(isHardExcludedDirectory("dist")).toBe(true);
    expect(isHardExcludedDirectory("build")).toBe(true);
    expect(isHardExcludedDirectory(".venv")).toBe(true);
    expect(isHardExcludedDirectory("src")).toBe(false);
  });

  it("identifies credential paths per docs/06 §4", () => {
    expect(isCredentialPath(".env")).toBe(true);
    expect(isCredentialPath(".env.local")).toBe(true);
    expect(isCredentialPath(".env.production")).toBe(true);
    expect(isCredentialPath("server.key")).toBe(true);
    expect(isCredentialPath("cert.pem")).toBe(true);
    expect(isCredentialPath("id_rsa")).toBe(true);
    expect(isCredentialPath("id_ed25519")).toBe(true);
    expect(isCredentialPath("credentials.json")).toBe(true);
    expect(isCredentialPath("vault.kdbx")).toBe(true);

    expect(isCredentialPath("config.json")).toBe(false);
    expect(isCredentialPath("env.ts")).toBe(false);
    expect(isCredentialPath("keyboard.ts")).toBe(false);
  });

  it("matches gitignore and devmindignore globs", () => {
    const matcher = new IgnoreMatcher(["*.log", "temp/", "docs/*.tmp", "!docs/keep.tmp"]);

    expect(matcher.isIgnored("app.log")).toBe(true);
    expect(matcher.isIgnored("server/debug.log")).toBe(true);
    expect(matcher.isIgnored("temp/file.txt")).toBe(true);
    expect(matcher.isIgnored("docs/notes.tmp")).toBe(true);
    expect(matcher.isIgnored("docs/keep.tmp")).toBe(false);
    expect(matcher.isIgnored("src/index.ts")).toBe(false);
  });

  describe("FileDiscoveryEngine traversal", () => {
    it("discovers files with correct tiers, ignores hard-excluded dirs, and protects credentials", async () => {
      const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-discovery-"));

      // Create folder structure
      await fs.mkdir(path.join(tmpDir, "src"), { recursive: true });
      await fs.mkdir(path.join(tmpDir, "node_modules/pkg"), { recursive: true });
      await fs.mkdir(path.join(tmpDir, ".git/objects"), { recursive: true });
      await fs.mkdir(path.join(tmpDir, "docs"), { recursive: true });

      // Create files
      await fs.writeFile(path.join(tmpDir, "src/index.ts"), "export const a = 1;\n");
      await fs.writeFile(path.join(tmpDir, "src/main.py"), "print('hello')\n");
      await fs.writeFile(path.join(tmpDir, "src/app.min.js"), "function(){}\n");
      await fs.writeFile(path.join(tmpDir, "docs/readme.md"), "# Readme\n");
      await fs.writeFile(path.join(tmpDir, ".env.local"), "SECRET=classified\n");
      await fs.writeFile(path.join(tmpDir, "node_modules/pkg/index.js"), "console.log(1)\n");
      await fs.writeFile(path.join(tmpDir, ".git/HEAD"), "ref: refs/heads/main\n");
      await fs.writeFile(path.join(tmpDir, ".gitignore"), "*.ignored\n");
      await fs.writeFile(path.join(tmpDir, "src/test.ignored"), "ignore me\n");

      // Binary file
      const binaryBuf = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x00, 0x00, 0x00]);
      await fs.writeFile(path.join(tmpDir, "src/logo.png"), binaryBuf);

      const engine = new FileDiscoveryEngine({
        workspaceRoot: tmpDir,
      });

      const { files, summary } = await engine.discover();

      // node_modules and .git must NEVER be entered
      expect(
        files.some(
          (f) => f.relativePath.startsWith("node_modules/") || f.relativePath === "node_modules"
        )
      ).toBe(false);
      expect(
        files.some((f) => f.relativePath.startsWith(".git/") || f.relativePath === ".git")
      ).toBe(false);

      // index.ts: Tier 1, status ok
      const tsFile = files.find((f) => f.relativePath === "src/index.ts");
      expect(tsFile).toBeDefined();
      expect(tsFile?.status).toBe("ok");
      expect(tsFile?.languageTier).toBe(1);
      expect(tsFile?.languageId).toBe("typescript");
      expect(tsFile?.contentHash).toHaveLength(64);

      // main.py: Tier 1, status ok
      const pyFile = files.find((f) => f.relativePath === "src/main.py");
      expect(pyFile).toBeDefined();
      expect(pyFile?.status).toBe("ok");
      expect(pyFile?.languageTier).toBe(1);
      expect(pyFile?.languageId).toBe("python");

      // readme.md: Tier 2, status ok
      const mdFile = files.find((f) => f.relativePath === "docs/readme.md");
      expect(mdFile).toBeDefined();
      expect(mdFile?.status).toBe("ok");
      expect(mdFile?.languageTier).toBe(2);

      // .env.local: Credential guard
      const credFile = files.find((f) => f.relativePath === ".env.local");
      expect(credFile).toBeDefined();
      expect(credFile?.status).toBe("skipped_credential");
      expect(credFile?.isCredential).toBe(true);
      expect(credFile?.contentHash).toBeUndefined(); // Content NEVER read or hashed

      // app.min.js: Ignored generated
      const minFile = files.find((f) => f.relativePath === "src/app.min.js");
      expect(minFile).toBeDefined();
      expect(minFile?.status).toBe("skipped_ignored");

      // test.ignored: Ignored by .gitignore
      const ignoredFile = files.find((f) => f.relativePath === "src/test.ignored");
      expect(ignoredFile).toBeDefined();
      expect(ignoredFile?.status).toBe("skipped_ignored");

      // logo.png: Binary file
      const binFile = files.find((f) => f.relativePath === "src/logo.png");
      expect(binFile).toBeDefined();
      expect(binFile?.status).toBe("skipped_binary");

      // Summary checks
      expect(summary.totalFilesDiscovered).toBe(files.length);
      expect(summary.tier1Count).toBe(2); // ts, py
      expect(summary.tier2Count).toBe(1); // docs/readme.md
      expect(summary.skippedCount).toBeGreaterThan(0);

      // Cleanup
      await fs.rm(tmpDir, { recursive: true, force: true });
    });

    it("respects per-file analysis ceiling (skips files larger than maxFileSize)", async () => {
      const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-discovery-size-"));
      const largeFile = path.join(tmpDir, "large.ts");
      // 2 KB limit, write 5 KB file
      await fs.writeFile(largeFile, "x".repeat(5000));

      const engine = new FileDiscoveryEngine({
        workspaceRoot: tmpDir,
        maxFileSize: 2048,
      });

      const { files, summary } = await engine.discover();
      const record = files.find((f) => f.relativePath === "large.ts");
      expect(record?.status).toBe("skipped_too_large");
      expect(summary.skippedCount).toBe(1);

      await fs.rm(tmpDir, { recursive: true, force: true });
    });
  });
});
