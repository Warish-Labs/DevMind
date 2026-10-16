/**
 * DevMind Python Semantic Extractor (docs/06 §8).
 * Extracts routes, dependencies, and SQLAlchemy models from FastAPI and Starlette.
 */

import path from "node:path";
import { DatabaseModel, DatabaseField, ProjectModule, RouteDetail } from "../../types";

const PYTHON_AUTH_DEPENDENCY_PATTERNS = [
  /depends\s*\(\s*get_current_user/i,
  /depends\s*\(\s*get_current_active_user/i,
  /depends\s*\(\s*authenticate/i,
  /depends\s*\(\s*auth/i,
  /security\s*\(/i,
  /depends\s*\(\s*get_auth_context/i,
  /currentuser/i,
];

const PYTHON_ROLE_GUARD_PATTERNS = [
  /depends\s*\(\s*require_admin/i,
  /depends\s*\(\s*require_role/i,
  /depends\s*\(\s*check_permission/i,
  /depends\s*\(\s*has_role/i,
  /rolechecker/i,
  /is_admin/i,
  /require_superuser/i,
];

export function extractFastApiRoutes(content: string, relPath: string): ProjectModule | null {
  if (!relPath.endsWith(".py")) {
    return null;
  }

  const lines = content.split(/\r?\n/);

  // 1. Detect Router Prefix, e.g. router = APIRouter(prefix="/admin", ...)
  let prefix = "";
  const prefixMatch = /APIRouter\s*\([^)]*prefix\s*=\s*["']([^"']+)["']/i.exec(content);
  if (prefixMatch && prefixMatch[1]) {
    prefix = prefixMatch[1].replace(/\/+$/, ""); // normalize trailing slash
  }

  // 2. Extract Route Decorators: @router.get("/users") or @app.post("/items")
  const routeRegex =
    /@(?:router|app)\.(get|post|put|delete|patch|options|head)\s*\(\s*["']([^"']+)["']([\s\S]*?)\)\s*(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(([\s\S]*?)\):/g;

  const routes: RouteDetail[] = [];
  let match: RegExpExecArray | null;

  while ((match = routeRegex.exec(content)) !== null) {
    const rawMethod = match[1];
    const subPath = match[2];
    const decoratorOptions = match[3] || "";
    const handlerParams = match[5] || "";

    if (!rawMethod || !subPath) {
      continue;
    }

    const method = rawMethod.toUpperCase();

    // Combine prefix and subPath
    let fullPath = subPath;
    if (prefix) {
      const cleanSub = subPath.startsWith("/") ? subPath : `/${subPath}`;
      fullPath = `${prefix}${cleanSub}`;
    }

    // Line start
    const charIndex = match.index;
    const lineStart = content.slice(0, charIndex).split("\n").length;
    const matchLines = match[0].split("\n").length;
    const lineEnd = lineStart + matchLines - 1;

    // Check for auth and role guards across decorator options + handler params
    const contextText = `${decoratorOptions} ${handlerParams}`;

    let auth = false;
    let roleGuard = false;

    for (const pat of PYTHON_AUTH_DEPENDENCY_PATTERNS) {
      if (pat.test(contextText)) {
        auth = true;
        break;
      }
    }

    for (const pat of PYTHON_ROLE_GUARD_PATTERNS) {
      if (pat.test(contextText)) {
        roleGuard = true;
        auth = true; // Role guard implies authentication
        break;
      }
    }

    routes.push({
      method,
      path: fullPath,
      auth,
      roleGuard,
      lineStart,
      lineEnd,
    });
  }

  if (routes.length === 0) {
    return null;
  }

  const moduleName = path.basename(relPath, ".py");
  return {
    name: moduleName,
    file: relPath,
    routes,
  };
}

export function extractSqlAlchemyModels(content: string, relPath: string): DatabaseModel[] {
  if (!relPath.endsWith(".py")) {
    return [];
  }

  const models: DatabaseModel[] = [];

  // Match: class User(Base): or class AuditLog(DeclarativeBase):
  const classRegex =
    /class\s+([A-Za-z0-9_]+)\s*\((?:Base|DeclarativeBase|Model|db\.Model)\)\s*:\s*\n([\s\S]*?)(?=\nclass\s|\n\S|$)/g;

  let match: RegExpExecArray | null;
  while ((match = classRegex.exec(content)) !== null) {
    const modelName = match[1];
    const classBody = match[2];
    if (!modelName || !classBody) {
      continue;
    }
    const fields: DatabaseField[] = [];

    const fieldLines = classBody
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    for (const line of fieldLines) {
      // Column format: name = Column(Type, ...)
      const colMatch = /^([A-Za-z0-9_]+)\s*=\s*(?:mapped_column|Column)\s*\(([^)]*)\)/.exec(line);

      // Mapped format: name: Mapped[Type] = ...
      const mappedMatch = /^([A-Za-z0-9_]+)\s*:\s*Mapped\[([^\]]+)\]/.exec(line);

      if (colMatch && colMatch[1] && colMatch[2]) {
        const fieldName = colMatch[1];
        const colArgs = colMatch[2];
        const isPrimary = /primary_key\s*=\s*True/i.test(colArgs);
        const isUnique = /unique\s*=\s*True/i.test(colArgs);
        const isForeignKey = /ForeignKey\s*\(/i.test(colArgs);

        const typeMatch = /^(?:UUID|String|Integer|DateTime|Boolean|Float)/i.exec(colArgs.trim());
        const typeStr = typeMatch ? typeMatch[0] : "unknown";

        fields.push({
          name: fieldName,
          type: typeStr,
          isPrimary: isPrimary || undefined,
          isUnique: isUnique || undefined,
          isForeignKey: isForeignKey || undefined,
        });
      } else if (mappedMatch && mappedMatch[1] && mappedMatch[2]) {
        const fieldName = mappedMatch[1];
        const rawType = mappedMatch[2].trim();
        const isPrimary = /primary_key\s*=\s*True/i.test(line);
        const isUnique = /unique\s*=\s*True/i.test(line);
        const isForeignKey = /ForeignKey\s*\(/i.test(line);

        fields.push({
          name: fieldName,
          type: rawType,
          isPrimary: isPrimary || undefined,
          isUnique: isUnique || undefined,
          isForeignKey: isForeignKey || undefined,
        });
      }
    }

    if (fields.length > 0) {
      models.push({
        name: modelName,
        sourceFile: relPath,
        fields,
      });
    }
  }

  return models;
}
