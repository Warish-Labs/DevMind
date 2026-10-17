import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  ConsentWebviewManager,
  computeCanonicalPayload,
  computePreviewHash,
  verifySentBytesEquality,
} from "../src/views/consentWebview";
import { ConsentPreviewPayload } from "../src/types";
import * as vscode from "vscode";

describe("ConsentWebview & Sent-Bytes Equality (M5-02)", () => {
  const samplePayload: ConsentPreviewPayload = {
    projectId: "01920000-0000-7000-8000-000000000001",
    scope: "snippet_transmission",
    purpose: {
      kind: "cloud_analysis",
      jobType: "security_review",
    },
    destinationProviders: ["anthropic", "openai"],
    dataCategories: ["code_snippets", "ast_metadata"],
    files: [
      {
        path: "src/routes/admin.ts",
        lineRanges: [[10, 45]],
        sizeBytes: 1240,
        chunkCount: 2,
        language: "typescript",
      },
    ],
    redactionCounts: {
      token: 1,
      api_key: 1,
    },
    excludedPaths: [{ path: ".env", reason: "Guarded credential file path (Rule 5)" }],
  };

  it("computes deterministic SHA-256 preview hash", () => {
    const hash1 = computePreviewHash(samplePayload);
    const hash2 = computePreviewHash(samplePayload);

    expect(hash1).toMatch(/^sha256:[a-f0-9]{64}$/);
    expect(hash1).toBe(hash2);
  });

  it("produces identical preview hash regardless of key or array order", () => {
    const permutedPayload: ConsentPreviewPayload = {
      ...samplePayload,
      destinationProviders: ["openai", "anthropic"], // Reordered
      dataCategories: ["ast_metadata", "code_snippets"], // Reordered
      redactionCounts: {
        api_key: 1,
        token: 1,
      },
    };

    const hashOriginal = computePreviewHash(samplePayload);
    const hashPermuted = computePreviewHash(permutedPayload);

    expect(hashOriginal).toBe(hashPermuted);
  });

  it("detects payload tampering and changes preview hash", () => {
    const hashOriginal = computePreviewHash(samplePayload);

    const tamperedPayload: ConsentPreviewPayload = {
      ...samplePayload,
      files: [
        {
          path: "src/routes/admin.ts",
          lineRanges: [[10, 46]], // Tampered line range
          sizeBytes: 1240,
          chunkCount: 2,
          language: "typescript",
        },
      ],
    };

    const hashTampered = computePreviewHash(tamperedPayload);
    expect(hashTampered).not.toBe(hashOriginal);
  });

  it("verifies sent-bytes equality accurately", () => {
    const validHash = computePreviewHash(samplePayload);

    // Equality matches
    expect(verifySentBytesEquality(samplePayload, validHash)).toBe(true);

    // Malformed expected hash
    expect(verifySentBytesEquality(samplePayload, "not-a-hash")).toBe(false);
    expect(verifySentBytesEquality(samplePayload, "")).toBe(false);

    // Mutated payload fails equality verification
    const mutated = {
      ...samplePayload,
      destinationProviders: ["anthropic"], // Removed provider
    };
    expect(verifySentBytesEquality(mutated, validHash)).toBe(false);
  });

  it("renders valid webview HTML containing CSP, nonce, and preview hash", () => {
    const hash = computePreviewHash(samplePayload);
    const html = ConsentWebviewManager.renderHtml(samplePayload, hash, "metadata_only", false);

    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("Content-Security-Policy");
    expect(html).toContain(hash);
    expect(html).toContain("src/routes/admin.ts");
    expect(html).toContain("L10-45");
    expect(html).toContain("anthropic");
    expect(html).toContain("openai");
    expect(html).toContain(".env");
    expect(html).toContain("btn-cancel");
    expect(html).toContain("btn-send-single");
    expect(html).toContain("btn-allow-project");
  });

  it("handles user consent resolution for single request, project indexed, and cancel", async () => {
    let messageHandler: ((msg: { command: string }) => void) | undefined;

    const mockWebview = {
      html: "",
      onDidReceiveMessage: vi.fn().mockImplementation((handler) => {
        messageHandler = handler;
        return { dispose: vi.fn() };
      }),
    };

    const mockPanel = {
      webview: mockWebview,
      reveal: vi.fn(),
      dispose: vi.fn(),
      onDidDispose: vi.fn().mockImplementation((cb) => ({ dispose: vi.fn() })),
    };

    vi.spyOn(vscode.window, "createWebviewPanel").mockReturnValue(mockPanel as any);

    const mockContext = { subscriptions: [] } as any;

    // 1. Single request grant
    const promise1 = ConsentWebviewManager.requestConsent(mockContext, samplePayload);
    expect(messageHandler).toBeDefined();
    messageHandler!({ command: "send_single_request" });
    const decision1 = await promise1;
    expect(decision1.granted).toBe(true);
    expect(decision1.grantedFor).toBe("single_request");
    expect(decision1.previewHash).toBe(computePreviewHash(samplePayload));

    // Reset panel static reference
    (ConsentWebviewManager as any).currentPanel = undefined;

    // 2. Project-wide grant
    const promise2 = ConsentWebviewManager.requestConsent(mockContext, samplePayload);
    messageHandler!({ command: "allow_project_indexed" });
    const decision2 = await promise2;
    expect(decision2.granted).toBe(true);
    expect(decision2.grantedFor).toBe("project");

    // Reset panel
    (ConsentWebviewManager as any).currentPanel = undefined;

    // 3. User cancel
    const promise3 = ConsentWebviewManager.requestConsent(mockContext, samplePayload);
    messageHandler!({ command: "cancel" });
    const decision3 = await promise3;
    expect(decision3.granted).toBe(false);
    expect(decision3.userCancelled).toBe(true);
  });
});
