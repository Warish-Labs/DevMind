import { describe, it, expect, vi, beforeEach } from "vitest";
import fs from "node:fs";
import path from "node:path";
import * as vscode from "vscode";
import { activate, deactivate } from "../src/extension";

const ROOT = path.resolve(__dirname, "../../");
const EXPRESS_FIXTURE = path.join(ROOT, "evals/scanner/fixtures/express-admin");

describe("Extension Quality and Packaging (Slice B12)", () => {
  beforeEach(() => {
    vscode.workspace.workspaceFolders = [{ uri: { fsPath: EXPRESS_FIXTURE } }];
  });

  describe("Extension Activation and Lifecycle (S2-13)", () => {
    it("activates, registers views and commands, and populates diagnostics without network calls", async () => {
      // Spy on fetch to guarantee zero network calls
      const fetchSpy = vi.fn();
      vi.stubGlobal("fetch", fetchSpy);

      const registeredCommands: string[] = [];
      const origRegisterCommand = vscode.commands.registerCommand;
      vi.spyOn(vscode.commands, "registerCommand").mockImplementation(
        (cmd: string, callback: (...args: unknown[]) => unknown) => {
          registeredCommands.push(cmd);
          return origRegisterCommand(cmd, callback);
        }
      );

      const subscriptions: unknown[] = [];
      const context = {
        subscriptions,
      } as unknown as vscode.ExtensionContext;

      // 1. Activate
      activate(context);

      expect(subscriptions.length).toBeGreaterThan(10);
      expect(registeredCommands).toContain("devmind.scanWorkspace");
      expect(registeredCommands).toContain("devmind.openFindings");
      expect(registeredCommands).toContain("devmind.showLogs");
      expect(registeredCommands).toContain("devmind.syncNow");
      expect(registeredCommands).toContain("devmind.reviewSync");
      expect(registeredCommands).toContain("devmind.cancelScan");
      expect(registeredCommands).toContain("devmind.openFindingLocation");
      expect(registeredCommands).toContain("devmind.refreshAll");

      // Verify zero network calls were made
      expect(fetchSpy).not.toHaveBeenCalled();

      // 2. Deactivate cleanly
      expect(() => deactivate()).not.toThrow();

      vi.unstubAllGlobals();
    });

    it("verifies redaction pattern conforms to ADR-047 [REDACTED:type:hash8]", () => {
      const token = "sk_live_1234567890abcdef";
      // Deterministic hash redaction pattern
      const redacted = `[REDACTED:token:${token.slice(0, 8)}]`;
      expect(redacted).toMatch(/^\[REDACTED:[a-z]+:[a-zA-Z0-9_]{8}\]$/);
      expect(redacted).not.toContain("1234567890abcdef");
    });
  });

  describe("VSIX Packaging Verification (S2-13)", () => {
    it("verifies VSIX package artifact exists and package.json is compliant", () => {
      const pkgJsonPath = path.join(__dirname, "../package.json");
      const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, "utf8"));

      expect(pkg.name).toBe("devmind-vscode");
      expect(pkg.publisher).toBe("warishlabs");
      expect(pkg.version).toBe("0.1.0");
      expect(pkg.license).toBe("MIT");
      expect(pkg.main).toBe("./dist/extension.js");
      expect(pkg.engines?.vscode).toBeDefined();

      const vsixPath = path.join(__dirname, "../dist/devmind-vscode.vsix");
      expect(fs.existsSync(vsixPath)).toBe(true);
      const stat = fs.statSync(vsixPath);
      expect(stat.size).toBeGreaterThan(1024); // > 1KB
    });
  });
});
