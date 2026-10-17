import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { SyncClient } from "../src/services/syncClient";
import { ExtensionAuthService } from "../src/services/auth";
import { LocalManifestStore } from "../src/scanner/manifest";
import { MockSecretStorage } from "./vscode-mock";
import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

describe("SyncClient (M4-09)", () => {
  let mockSecrets: MockSecretStorage;
  let authService: ExtensionAuthService;
  let syncClient: SyncClient;
  let tempDir: string;
  let manifestStore: LocalManifestStore;

  beforeEach(async () => {
    mockSecrets = new MockSecretStorage();
    authService = ExtensionAuthService.init(mockSecrets as unknown as vscode.SecretStorage);
    syncClient = new SyncClient(authService);

    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "devmind-sync-test-"));
    const manifestDir = path.join(tempDir, "manifest");
    fs.mkdirSync(manifestDir, { recursive: true });
    manifestStore = new LocalManifestStore(manifestDir, tempDir);
    await manifestStore.load();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("aborts with clear error when user is not authenticated", async () => {
    const result = await syncClient.sync({
      projectId: "01920000-0000-7000-8000-000000000001",
      workspaceRoot: tempDir,
      manifestStore,
      findings: [],
      modules: [],
      databaseModels: [],
    });

    expect(result.success).toBe(false);
    expect(result.error).toContain("Not authenticated");
  });

  it("executes successful end-to-end sync and updates manifest receipts", async () => {
    // 1. Authenticate
    await authService.saveTokens({
      accessToken: "dme_at_valid_token_123",
      refreshToken: "dme_rt_valid_token_456",
      registrationId: "01920000-0000-7000-8000-000000000001",
      expiresIn: 3600,
    });

    // 2. Add files to manifest
    manifestStore.recordFile(
      {
        relativePath: "src/index.ts",
        absolutePath: path.join(tempDir, "src/index.ts"),
        size: 100,
        mtimeMs: 1000,
        languageTier: 1,
        languageId: "typescript",
        status: "ok",
        isCredential: false,
      },
      "hash123",
      1,
      0,
      []
    );

    const requests: Array<{ url: string; method: string; body: any }> = [];

    // Mock global fetch
    const fetchMock = vi.fn().mockImplementation(async (url: string, init: any) => {
      const parsedBody = init?.body ? JSON.parse(init.body) : undefined;
      requests.push({ url, method: init?.method ?? "GET", body: parsedBody });

      if (url.includes("/manifest/diff")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            unchanged: 0,
            new: 1,
            changed: 0,
            removed: [],
            missing_files: [],
          }),
        };
      }
      if (url.includes("/manifest")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            files_count: 1,
            versions_created: 1,
            removed_count: 0,
          }),
        };
      }
      if (url.includes("/symbols")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            upserted: 1,
          }),
        };
      }
      if (url.includes("/relationships")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            upserted: 1,
          }),
        };
      }
      if (url.includes("/findings:batch")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            ingested: 1,
            updated: 0,
            reopened: 0,
          }),
        };
      }
      return { ok: false, status: 404, text: async () => "Not found" };
    });
    vi.stubGlobal("fetch", fetchMock);

    // 3. Run sync
    const progressUpdates: string[] = [];
    const result = await syncClient.sync({
      projectId: "01920000-0000-7000-8000-000000000001",
      workspaceRoot: tempDir,
      manifestStore,
      findings: [
        {
          id: "finding-1",
          ruleId: "devmind/unprotected-route",
          name: "Unprotected Route",
          severity: "high",
          file: "src/index.ts",
          lineStart: 10,
          lineEnd: 20,
          message: "Route lacks authentication",
          remediation: "Add AuthGuard",
          evidenceLabel: "E1: AST parsed handler",
        },
      ],
      modules: [
        {
          file: "src/index.ts",
          framework: "express",
          routes: [
            {
              path: "/api/users",
              method: "GET",
              lineStart: 10,
              lineEnd: 20,
              auth: false,
              roleGuard: true,
            },
          ],
        },
      ],
      databaseModels: [
        {
          name: "User",
          sourceFile: "src/models/user.ts",
          framework: "prisma",
          fields: [{ name: "id", type: "Int", isId: true }],
        },
      ],
      onProgress: (msg) => progressUpdates.push(msg),
    });

    expect(result.success).toBe(true);
    expect(result.filesCount).toBe(1);
    expect(result.versionsCreated).toBe(1);
    expect(result.symbolsCount).toBe(1);
    expect(result.relationshipsCount).toBe(1);
    expect(result.findingsIngested).toBe(1);
    expect(result.staleBaseRecovered).toBe(false);
    expect(progressUpdates.length).toBeGreaterThan(0);

    // Verify evidence ceiling invariant (strictly E1)
    const findingsReq = requests.find((r) => r.url.includes("/findings:batch"));
    expect(findingsReq).toBeDefined();
    expect(findingsReq?.body.findings[0].evidence_level).toBe("E1");
    expect(findingsReq?.body.findings[0].evidence[0].snippet_hash).toMatch(/^sha256:[a-f0-9]{64}$/);

    // Verify manifest record marked as synced
    const record = manifestStore.getRecord("src/index.ts");
    expect(record?.lastSyncedHash).toBe("hash123");
  });

  it("recovers automatically from 409 sync.stale_base by re-diffing cleanly", async () => {
    await authService.saveTokens({
      accessToken: "dme_at_valid_token_123",
      refreshToken: "dme_rt_valid_token_456",
      registrationId: "01920000-0000-7000-8000-000000000001",
      expiresIn: 3600,
    });

    manifestStore.recordFile(
      {
        relativePath: "src/index.ts",
        absolutePath: path.join(tempDir, "src/index.ts"),
        size: 100,
        mtimeMs: 1000,
        languageTier: 1,
        languageId: "typescript",
        status: "ok",
        isCredential: false,
      },
      "hash123",
      1,
      0,
      []
    );

    let diffCallCount = 0;
    const diffBodies: any[] = [];

    const fetchMock = vi.fn().mockImplementation(async (url: string, init: any) => {
      const parsedBody = init?.body ? JSON.parse(init.body) : undefined;

      if (url.includes("/manifest/diff")) {
        diffCallCount++;
        diffBodies.push(parsedBody);
        if (diffCallCount === 1) {
          // Simulate 409 sync.stale_base
          return {
            ok: false,
            status: 409,
            text: async () => JSON.stringify({ code: "sync.stale_base" }),
          };
        }
        // Second attempt succeeds
        return {
          ok: true,
          status: 200,
          json: async () => ({
            unchanged: 1,
            new: 0,
            changed: 0,
            removed: [],
            missing_files: [],
          }),
        };
      }
      if (url.includes("/manifest")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            files_count: 1,
            versions_created: 0,
            removed_count: 0,
          }),
        };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncClient.sync({
      projectId: "01920000-0000-7000-8000-000000000001",
      workspaceRoot: tempDir,
      manifestStore,
      baseSnapshotId: "01920000-0000-7000-8000-000000000099",
      findings: [],
      modules: [],
      databaseModels: [],
    });

    expect(result.success).toBe(true);
    expect(result.staleBaseRecovered).toBe(true);
    expect(diffCallCount).toBe(2);
    // First call sent baseSnapshotId, second call cleared it
    expect(diffBodies[0].base_snapshot_id).toBe("01920000-0000-7000-8000-000000000099");
    expect(diffBodies[1].base_snapshot_id).toBeUndefined();
  });

  it("retries on 401 with refreshed access token", async () => {
    await authService.saveTokens({
      accessToken: "dme_at_expired_token",
      refreshToken: "dme_rt_refresh_token",
      registrationId: "01920000-0000-7000-8000-000000000001",
      expiresIn: 3600,
    });

    manifestStore.recordFile(
      {
        relativePath: "src/index.ts",
        absolutePath: path.join(tempDir, "src/index.ts"),
        size: 100,
        mtimeMs: 1000,
        languageTier: 1,
        languageId: "typescript",
        status: "ok",
        isCredential: false,
      },
      "hash123",
      1,
      0,
      []
    );

    let refreshCalled = false;
    let diffAttempt = 0;

    const fetchMock = vi.fn().mockImplementation(async (url: string, init: any) => {
      const authHeader = init?.headers?.["Authorization"] || init?.headers?.Authorization;

      if (url.includes("/token/refresh")) {
        refreshCalled = true;
        return {
          ok: true,
          status: 200,
          json: async () => ({
            access_token: "dme_at_fresh_token",
            refresh_token: "dme_rt_fresh_refresh",
            token_type: "Bearer",
            expires_in: 3600,
          }),
        };
      }

      if (url.includes("/manifest/diff")) {
        diffAttempt++;
        if (diffAttempt === 1) {
          expect(authHeader).toBe("Bearer dme_at_expired_token");
          return {
            ok: false,
            status: 401,
            text: async () => "Unauthorized",
          };
        }
        expect(authHeader).toBe("Bearer dme_at_fresh_token");
        return {
          ok: true,
          status: 200,
          json: async () => ({
            unchanged: 1,
            new: 0,
            changed: 0,
            removed: [],
            missing_files: [],
          }),
        };
      }

      if (url.includes("/manifest")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            files_count: 1,
            versions_created: 0,
            removed_count: 0,
          }),
        };
      }

      return { ok: true, status: 200, json: async () => ({}) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncClient.sync({
      projectId: "01920000-0000-7000-8000-000000000001",
      workspaceRoot: tempDir,
      manifestStore,
      findings: [],
      modules: [],
      databaseModels: [],
    });

    expect(result.success).toBe(true);
    expect(refreshCalled).toBe(true);
    expect(diffAttempt).toBe(2);
    expect(await authService.getAccessToken()).toBe("dme_at_fresh_token");
  });

  it("handles network failure cleanly without throwing unhandled exceptions", async () => {
    await authService.saveTokens({
      accessToken: "dme_at_valid_token_123",
      refreshToken: "dme_rt_valid_token_456",
      registrationId: "01920000-0000-7000-8000-000000000001",
      expiresIn: 3600,
    });

    const fetchMock = vi.fn().mockImplementation(async () => {
      throw new Error("Network connection refused");
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncClient.sync({
      projectId: "01920000-0000-7000-8000-000000000001",
      workspaceRoot: tempDir,
      manifestStore,
      findings: [],
      modules: [],
      databaseModels: [],
    });

    expect(result.success).toBe(false);
    expect(result.error).toContain("Network connection refused");
  });
});
