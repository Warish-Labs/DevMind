import { describe, it, expect, beforeEach } from "vitest";
import path from "node:path";
import * as vscode from "vscode";
import { FixtureFindingsSource } from "../src/sources/fixtureFindingsSource";
import {
  FindingsViewProvider,
  SeverityGroupTreeItem,
  FindingItemTreeItem,
  EmptyFindingsTreeItem,
} from "../src/views/findingsView";
import { StructureViewProvider, ModuleTreeItem, RouteTreeItem } from "../src/views/structureView";
import {
  ScanViewProvider,
  ScanStatusTreeItem,
  ScanRulesTreeItem,
  ScanCountTreeItem,
  SkippedGroupTreeItem,
  ScanActionsGroupTreeItem,
} from "../src/views/scanView";
import {
  SyncViewProvider,
  SyncModeTreeItem,
  SyncConsentTreeItem,
  SyncAuditGroupTreeItem,
  SyncActionsGroupTreeItem,
} from "../src/views/syncView";
import {
  DatabaseViewProvider,
  DatabaseNoticeTreeItem,
  DatabaseModelTreeItem,
  DatabaseFieldTreeItem,
} from "../src/views/databaseView";
import { FindingsSource } from "../src/types";

const ROOT = path.resolve(__dirname, "../../");
const EXPRESS_FIXTURE = path.join(ROOT, "evals/scanner/fixtures/express-admin");

describe("Extension Views", () => {
  let source: FixtureFindingsSource;

  beforeEach(() => {
    source = new FixtureFindingsSource();
    // Configure mock workspace folder
    vscode.workspace.workspaceFolders = [{ uri: { fsPath: EXPRESS_FIXTURE } }];
  });

  describe("FindingsViewProvider (S2-04)", () => {
    it("groups findings by severity and displays finding items", async () => {
      const provider = new FindingsViewProvider(source);
      const roots = await provider.getChildren();

      expect(roots.length).toBeGreaterThan(0);
      const highGroup = roots.find(
        (r): r is SeverityGroupTreeItem =>
          r instanceof SeverityGroupTreeItem && r.severity === "high"
      );
      expect(highGroup).toBeDefined();
      expect(highGroup?.label).toContain("High (1)");
      expect(highGroup?.collapsibleState).toBe(vscode.TreeItemCollapsibleState.Expanded);

      // Inspect child findings
      const children = await provider.getChildren(highGroup);
      expect(children.length).toBe(1);

      const findingItem = children[0] as FindingItemTreeItem;
      expect(findingItem.label).toBe("Missing Role Authorization Check");
      expect(findingItem.description).toBe("src/routes/admin.ts:7");
      expect(findingItem.tooltip).toContain("Rule ID: devmind.authz.missing_role_check");
      expect(findingItem.tooltip).toContain("Evidence: E1 · Possible (E1)");
      expect(findingItem.command?.command).toBe("devmind.openFindingLocation");
      expect(findingItem.command?.arguments).toEqual(["src/routes/admin.ts", 7, 9]);
    });

    it("returns empty findings tree item when no findings are detected", async () => {
      const emptySource: FindingsSource = {
        getFindings: async () => [],
        getStructure: async () => [],
        getDatabaseModels: async () => [],
      };
      const provider = new FindingsViewProvider(emptySource);
      const roots = await provider.getChildren();

      expect(roots.length).toBe(1);
      expect(roots[0] instanceof EmptyFindingsTreeItem).toBe(true);
      expect(roots[0]?.label).toContain("No findings detected");
    });
  });

  describe("StructureViewProvider (S2-05)", () => {
    it("renders project modules and route details with guard chips", async () => {
      const provider = new StructureViewProvider(source);
      const roots = await provider.getChildren();

      expect(roots.length).toBeGreaterThan(0);
      const adminModule = roots.find(
        (r): r is ModuleTreeItem => r instanceof ModuleTreeItem && r.module.name === "admin"
      );
      expect(adminModule).toBeDefined();
      expect(adminModule?.label).toBe("Module: admin");
      expect(adminModule?.description).toBe("2 route(s)");

      // Inspect routes
      const routes = await provider.getChildren(adminModule);
      expect(routes.length).toBe(2);

      const getRoute = routes.find(
        (r): r is RouteTreeItem => r instanceof RouteTreeItem && r.route.method === "GET"
      );
      expect(getRoute?.label).toBe("GET /admin/users");
      expect(getRoute?.description).toBe("Missing Role Guard");
      expect(getRoute?.tooltip).toContain("Authentication: Required");
      expect(getRoute?.tooltip).toContain("Role Guard: Missing (Vulnerability)");

      const deleteRoute = routes.find(
        (r): r is RouteTreeItem => r instanceof RouteTreeItem && r.route.method === "DELETE"
      );
      expect(deleteRoute?.label).toBe("DELETE /admin/users/:id");
      expect(deleteRoute?.description).toBe("Protected [Role Checked]");
    });
  });

  describe("ScanViewProvider (S2-06)", () => {
    it("renders scan status, rules pack, counts, skipped files, and actions", async () => {
      const provider = new ScanViewProvider();
      const roots = await provider.getChildren();

      expect(roots.length).toBe(5);

      const statusItem = roots.find(
        (r): r is ScanStatusTreeItem => r instanceof ScanStatusTreeItem
      );
      expect(statusItem?.label).toBe("Status: Idle");

      const rulesItem = roots.find((r): r is ScanRulesTreeItem => r instanceof ScanRulesTreeItem);
      expect(rulesItem?.label).toContain("Rule Pack: v1.0.0");

      const countItem = roots.find((r): r is ScanCountTreeItem => r instanceof ScanCountTreeItem);
      expect(countItem?.label).toContain("Analyzed Files: 18");

      const skippedGroup = roots.find(
        (r): r is SkippedGroupTreeItem => r instanceof SkippedGroupTreeItem
      );
      expect(skippedGroup).toBeDefined();
      const skippedChildren = await provider.getChildren(skippedGroup);
      expect(skippedChildren.some((c) => c.label === ".env")).toBe(true);

      const actionsGroup = roots.find(
        (r): r is ScanActionsGroupTreeItem => r instanceof ScanActionsGroupTreeItem
      );
      expect(actionsGroup).toBeDefined();
      const actionItems = await provider.getChildren(actionsGroup);
      expect(actionItems.length).toBe(2);
      expect(actionItems[0]?.command?.command).toBe("devmind.scanWorkspace");
      expect(actionItems[1]?.command?.command).toBe("devmind.cancelScan");
    });

    it("updates scan state when progress changes or finishes", async () => {
      const provider = new ScanViewProvider();
      provider.setScanning(true, 45);

      let roots = await provider.getChildren();
      let statusItem = roots.find((r): r is ScanStatusTreeItem => r instanceof ScanStatusTreeItem);
      expect(statusItem?.label).toBe("Status: Scanning (45%)...");

      provider.setCompleted(25);
      roots = await provider.getChildren();
      statusItem = roots.find((r): r is ScanStatusTreeItem => r instanceof ScanStatusTreeItem);
      expect(statusItem?.label).toBe("Status: Scan Completed");

      provider.cancelScan();
      roots = await provider.getChildren();
      statusItem = roots.find((r): r is ScanStatusTreeItem => r instanceof ScanStatusTreeItem);
      expect(statusItem?.label).toBe("Status: Idle");
    });
  });

  describe("SyncViewProvider (S2-07)", () => {
    it("renders sync mode, consent, audit log, and review action", async () => {
      const provider = new SyncViewProvider();
      const roots = await provider.getChildren();

      expect(roots.length).toBe(5);

      const modeItem = roots.find((r): r is SyncModeTreeItem => r instanceof SyncModeTreeItem);
      expect(modeItem?.label).toBe("Mode: metadata_only");
      expect(modeItem?.description).toBe("Zero source code chunks transmitted");

      const consentItem = roots.find(
        (r): r is SyncConsentTreeItem => r instanceof SyncConsentTreeItem
      );
      expect(consentItem?.label).toContain("Consent: Consented for Metadata");

      const auditGroup = roots.find(
        (r): r is SyncAuditGroupTreeItem => r instanceof SyncAuditGroupTreeItem
      );
      expect(auditGroup).toBeDefined();
      const auditEntries = await provider.getChildren(auditGroup);
      expect(auditEntries.length).toBe(4);
      expect(auditEntries.some((e) => e.label === "Raw Code Chunks")).toBe(true);

      const actionsGroup = roots.find(
        (r): r is SyncActionsGroupTreeItem => r instanceof SyncActionsGroupTreeItem
      );
      expect(actionsGroup).toBeDefined();
      const actionItems = await provider.getChildren(actionsGroup);
      expect(actionItems.some((a) => a.command?.command === "devmind.showWhatLeaves")).toBe(true);
    });
  });

  describe("DatabaseViewProvider (S2-08)", () => {
    it("renders ADR-034 zero-live-connection notice and discovered models", async () => {
      const provider = new DatabaseViewProvider(source);
      const roots = await provider.getChildren();

      expect(roots.length).toBeGreaterThan(1);

      const notice = roots[0] as DatabaseNoticeTreeItem;
      expect(notice.label).toContain("Discovered from files · Zero live connections");
      expect(notice.description).toBe("ADR-034 enforced");

      const userModel = roots.find(
        (r): r is DatabaseModelTreeItem =>
          r instanceof DatabaseModelTreeItem && r.model.name === "User"
      );
      expect(userModel).toBeDefined();
      expect(userModel?.description).toContain("fields · src/models/user.ts");

      const fields = await provider.getChildren(userModel);
      expect(fields.length).toBe(4);

      const idField = fields.find(
        (f): f is DatabaseFieldTreeItem =>
          f instanceof DatabaseFieldTreeItem && f.label.startsWith("id:")
      );
      expect(idField?.description).toContain("[PK]");
    });
  });
});
