/**
 * DevMind TypeScript / JavaScript Semantic Extractor (docs/06 §8).
 * Extracts routes, middleware guards, and database models from Express, Next.js, and Prisma.
 */

import path from "node:path";
import { DatabaseModel, DatabaseField, ProjectModule, RouteDetail } from "../../types";

const AUTH_MIDDLEWARE_NAMES = new Set([
  "requireauth",
  "authenticate",
  "auth",
  "authmiddleware",
  "verifytoken",
  "checkauth",
  "ensureauth",
  "requireuser",
  "isauthenticated",
]);

const ROLE_GUARD_PATTERNS = [
  /requirerole\s*\(/i,
  /hasrole\s*\(/i,
  /checkpermission\s*\(/i,
  /authorize\s*\(/i,
  /isadmin/i,
  /adminonly/i,
  /rolecheck\s*\(/i,
  /requirepermission\s*\(/i,
];

export function extractExpressRoutes(content: string, relPath: string): ProjectModule | null {
  const lines = content.split(/\r?\n/);
  const routes: RouteDetail[] = [];

  // 1. Check for Express router or app definitions
  const hasExpress =
    content.includes("express") ||
    content.includes("Router") ||
    content.includes("router.") ||
    content.includes("app.");

  if (!hasExpress) {
    return null;
  }

  // Regex matching router.<method>(path, ...middlewares)
  const routeRegex =
    /(?:router|app)\.(get|post|put|delete|patch|options|head|all)\s*\(\s*(["'`])([^"'`]+)\2([\s\S]*?)(?:\)|=>|\bfunction\b)/gi;

  let match: RegExpExecArray | null;
  while ((match = routeRegex.exec(content)) !== null) {
    const rawMethod = match[1];
    const routePath = match[3];
    const middlewareSection = match[4] || "";

    if (!rawMethod || !routePath) {
      continue;
    }

    const method = rawMethod.toUpperCase();

    // Compute line numbers
    const charIndex = match.index;
    const lineStart = content.slice(0, charIndex).split("\n").length;
    const matchLines = match[0].split("\n").length;
    const lineEnd = lineStart + matchLines - 1;

    // Check for auth middleware
    let auth = false;
    let roleGuard = false;

    // Check words in middleware section
    const tokens = middlewareSection
      .split(/[\s,()]+/)
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

    for (const token of tokens) {
      if (AUTH_MIDDLEWARE_NAMES.has(token)) {
        auth = true;
      }
    }

    for (const pattern of ROLE_GUARD_PATTERNS) {
      if (pattern.test(middlewareSection)) {
        roleGuard = true;
        // If a role guard is present, authentication is inherently part of the requirement
        auth = true;
        break;
      }
    }

    routes.push({
      method,
      path: routePath,
      auth,
      roleGuard,
      lineStart,
      lineEnd,
    });
  }

  if (routes.length === 0) {
    return null;
  }

  // Module name from filename (e.g. src/routes/admin.ts -> admin)
  const moduleName = path.basename(relPath, path.extname(relPath));

  return {
    name: moduleName,
    file: relPath,
    routes,
  };
}

export function extractNextJsRoutes(content: string, relPath: string): ProjectModule | null {
  const normPath = relPath.replace(/\\/g, "/");
  // Check if this is a Next.js App Router route handler (e.g. app/.../route.ts)
  if (!normPath.endsWith("/route.ts") && !normPath.endsWith("/route.js")) {
    return null;
  }

  // Determine route path from directory structure
  // e.g. "app/api/admin/users/route.ts" -> "/api/admin/users"
  let routePath = "/";
  const appIndex = normPath.indexOf("app/");
  if (appIndex !== -1) {
    const sub = normPath.slice(appIndex + 4); // strip "app/"
    const dir = path.dirname(sub);
    routePath = "/" + dir.replace(/\[([^\]]+)\]/g, ":$1"); // convert [id] to :id
  }

  const routes: RouteDetail[] = [];
  const handlerRegex =
    /export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(([^)]*)\)/g;

  let match: RegExpExecArray | null;
  while ((match = handlerRegex.exec(content)) !== null) {
    const rawMethod = match[1];
    if (!rawMethod) {
      continue;
    }
    const method = rawMethod.toUpperCase();
    const charIndex = match.index;
    const lineStart = content.slice(0, charIndex).split("\n").length;

    // Check function body or file for auth patterns
    const auth =
      content.includes("auth(") ||
      content.includes("currentUser(") ||
      content.includes("getAuth(") ||
      content.includes("getServerSession(") ||
      content.includes("requireAuth");

    const roleGuard = ROLE_GUARD_PATTERNS.some((p) => p.test(content));

    routes.push({
      method,
      path: routePath,
      auth,
      roleGuard,
      lineStart,
      lineEnd: lineStart,
    });
  }

  if (routes.length === 0) {
    return null;
  }

  const moduleName = path.basename(path.dirname(normPath));
  return {
    name: moduleName || "route",
    file: relPath,
    routes,
  };
}

export function extractPrismaModels(content: string, relPath: string): DatabaseModel[] {
  if (!relPath.endsWith(".prisma")) {
    return [];
  }

  const models: DatabaseModel[] = [];
  const modelRegex = /model\s+([A-Za-z0-9_]+)\s*\{([^}]+)\}/g;

  let match: RegExpExecArray | null;
  while ((match = modelRegex.exec(content)) !== null) {
    const modelName = match[1];
    const body = match[2];
    if (!modelName || !body) {
      continue;
    }
    const fields: DatabaseField[] = [];

    const fieldLines = body
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    for (const line of fieldLines) {
      if (line.startsWith("//") || line.startsWith("@@")) {
        continue;
      }

      const parts = line.split(/\s+/);
      if (parts.length >= 2 && parts[0] && parts[1]) {
        const fieldName = parts[0];
        const rawType = parts[1];
        const isPrimary = line.includes("@id");
        const isUnique = line.includes("@unique");
        const isForeignKey = line.includes("@relation");

        fields.push({
          name: fieldName,
          type: rawType,
          isPrimary: isPrimary || undefined,
          isUnique: isUnique || undefined,
          isForeignKey: isForeignKey || undefined,
        });
      }
    }

    models.push({
      name: modelName,
      sourceFile: relPath,
      fields,
    });
  }

  return models;
}
