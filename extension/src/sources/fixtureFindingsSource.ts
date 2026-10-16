import fs from "node:fs";
import path from "node:path";
import { DatabaseModel, Finding, FindingsSource, ProjectModule } from "../types";
import { DevMindLogger } from "../services/logger";

const FALLBACK_EXPRESS_FINDINGS: Finding[] = [
  {
    id: "exp-find-01",
    ruleId: "devmind.authz.missing_role_check",
    name: "Missing Role Authorization Check",
    severity: "high",
    category: "authorization",
    evidenceLevel: "E1",
    evidenceLabel: "E1 · Possible",
    file: "src/routes/admin.ts",
    lineStart: 7,
    lineEnd: 9,
    message:
      "Sensitive administrative operation has authentication verified but lacks role or permission authorization validation.",
    codeSnippet: 'router.get("/admin/users", requireAuth, (req, res) => {',
    remediation: 'Add requireRole("admin") to route middleware stack.',
  },
];

const FALLBACK_EXPRESS_MODULES: ProjectModule[] = [
  {
    name: "admin",
    file: "src/routes/admin.ts",
    routes: [
      {
        method: "GET",
        path: "/admin/users",
        auth: true,
        roleGuard: false,
        findingId: "exp-find-01",
      },
      {
        method: "DELETE",
        path: "/admin/users/:id",
        auth: true,
        roleGuard: true,
      },
    ],
  },
];

const FALLBACK_EXPRESS_DATABASE_MODELS: DatabaseModel[] = [
  {
    name: "User",
    sourceFile: "src/models/user.ts",
    fields: [
      { name: "id", type: "string (UUID)", isPrimary: true },
      { name: "email", type: "string", isUnique: true },
      { name: "role", type: "RoleEnum" },
      { name: "created_at", type: "Date" },
    ],
  },
  {
    name: "AuditLog",
    sourceFile: "src/models/audit.ts",
    fields: [
      { name: "id", type: "string (UUID)", isPrimary: true },
      { name: "workspace_id", type: "string (UUID)", isForeignKey: true },
      { name: "action", type: "string" },
      { name: "timestamp", type: "Date" },
    ],
  },
];

const FALLBACK_FASTAPI_FINDINGS: Finding[] = [
  {
    id: "py-find-01",
    ruleId: "devmind.authz.missing_role_check",
    name: "Missing Role Authorization Check",
    severity: "high",
    category: "authorization",
    evidenceLevel: "E1",
    evidenceLabel: "E1 · Possible",
    file: "app/routes/admin.py",
    lineStart: 7,
    lineEnd: 9,
    message:
      "Sensitive administrative operation has authentication verified but lacks role or permission authorization validation.",
    codeSnippet:
      '@router.get("/users")\nasync def list_admin_users(user: CurrentUser = Depends(get_current_user)):',
    remediation: "Replace Depends(get_current_user) with Depends(require_admin).",
  },
];

const FALLBACK_FASTAPI_MODULES: ProjectModule[] = [
  {
    name: "admin",
    file: "app/routes/admin.py",
    routes: [
      {
        method: "GET",
        path: "/admin/users",
        auth: true,
        roleGuard: false,
        findingId: "py-find-01",
      },
      {
        method: "DELETE",
        path: "/admin/users/{user_id}",
        auth: true,
        roleGuard: true,
      },
    ],
  },
];

const FALLBACK_FASTAPI_DATABASE_MODELS: DatabaseModel[] = [
  {
    name: "User",
    sourceFile: "app/models/user.py",
    fields: [
      { name: "id", type: "UUID", isPrimary: true },
      { name: "email", type: "str", isUnique: true },
      { name: "role", type: "RoleEnum" },
      { name: "created_at", type: "datetime" },
    ],
  },
  {
    name: "AuditLog",
    sourceFile: "app/models/audit.py",
    fields: [
      { name: "id", type: "UUID", isPrimary: true },
      { name: "workspace_id", type: "UUID", isForeignKey: true },
      { name: "action", type: "str" },
      { name: "timestamp", type: "datetime" },
    ],
  },
];

export class FixtureFindingsSource implements FindingsSource {
  private logger = DevMindLogger.get();

  public async getFindings(workspaceRoot?: string): Promise<Finding[]> {
    if (workspaceRoot) {
      const loaded = this.tryLoadExpectedJson(workspaceRoot);
      if (loaded?.findings) {
        this.logger.info("Loaded findings from workspace expected.json fixture", {
          count: loaded.findings.length,
          fixture: loaded.fixtureName,
        });
        return loaded.findings;
      }

      // Check if Python or TS workspace
      if (fs.existsSync(path.join(workspaceRoot, "pyproject.toml"))) {
        return FALLBACK_FASTAPI_FINDINGS;
      }
    }

    this.logger.info("Using default express-admin fixture findings");
    return FALLBACK_EXPRESS_FINDINGS;
  }

  public async getStructure(workspaceRoot?: string): Promise<ProjectModule[]> {
    if (workspaceRoot) {
      const loaded = this.tryLoadExpectedJson(workspaceRoot);
      if (loaded?.expectedModules) {
        this.logger.info("Loaded structure from workspace expected.json fixture", {
          count: loaded.expectedModules.length,
        });
        return loaded.expectedModules;
      }

      if (fs.existsSync(path.join(workspaceRoot, "pyproject.toml"))) {
        return FALLBACK_FASTAPI_MODULES;
      }
    }

    return FALLBACK_EXPRESS_MODULES;
  }

  public async getDatabaseModels(workspaceRoot?: string): Promise<DatabaseModel[]> {
    if (workspaceRoot) {
      const loaded = this.tryLoadExpectedJson(workspaceRoot);
      if (loaded?.databaseModels) {
        this.logger.info("Loaded database models from workspace expected.json fixture", {
          count: loaded.databaseModels.length,
        });
        return loaded.databaseModels;
      }

      if (fs.existsSync(path.join(workspaceRoot, "pyproject.toml"))) {
        return FALLBACK_FASTAPI_DATABASE_MODELS;
      }
    }

    return FALLBACK_EXPRESS_DATABASE_MODELS;
  }

  private tryLoadExpectedJson(workspaceRoot: string): {
    fixtureName?: string;
    findings?: Finding[];
    expectedModules?: ProjectModule[];
    databaseModels?: DatabaseModel[];
  } | null {
    try {
      const directExpected = path.join(workspaceRoot, "expected.json");
      if (fs.existsSync(directExpected)) {
        return JSON.parse(fs.readFileSync(directExpected, "utf8"));
      }

      // Check parent or evals/scanner/fixtures
      const fixtureExpress = path.join(
        workspaceRoot,
        "evals/scanner/fixtures/express-admin/expected.json"
      );
      if (fs.existsSync(fixtureExpress)) {
        return JSON.parse(fs.readFileSync(fixtureExpress, "utf8"));
      }
    } catch (err) {
      this.logger.warn("Failed to parse expected.json", { error: String(err) });
    }
    return null;
  }
}
