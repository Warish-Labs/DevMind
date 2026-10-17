/**
 * DevMind Authorization & Authentication Rules (docs/06 §8).
 * Evaluates route definitions against security invariants.
 * Produces E1 (Possible) findings conforming to docs/03 §12.1.
 */

import { Finding, ProjectModule, RouteDetail } from "../../types";

const ADMIN_PATH_KEYWORDS = ["/admin", "/manage", "/internal", "/settings/security", "/billing"];

export function evaluateAuthRules(module: ProjectModule, fileContent: string): Finding[] {
  const findings: Finding[] = [];
  const lines = fileContent.split(/\r?\n/);
  const isPython = module.file.endsWith(".py");

  for (let i = 0; i < module.routes.length; i++) {
    const route = module.routes[i];
    if (!route) continue;

    const pathLower = route.path.toLowerCase();
    const isAdminRoute = ADMIN_PATH_KEYWORDS.some((kw) => pathLower.includes(kw));

    const lineStart = route.lineStart ?? 1;
    const lineEnd = route.lineEnd ?? lineStart;

    // Extract exact code snippet for the route header
    let codeSnippet = "";
    if (lines.length >= lineStart) {
      const snippetLines = lines.slice(lineStart - 1, Math.min(lineEnd, lineStart + 2));
      codeSnippet = snippetLines.join("\n").trim();
    }

    // 1. devmind.authz.missing_role_check
    // Condition: Route has authentication verified (auth === true), but lacks role authorization check (roleGuard === false)
    if (isAdminRoute && route.auth && !route.roleGuard) {
      // Deterministic finding ID
      const findingId = isPython
        ? `py-find-${String(i + 1).padStart(2, "0")}`
        : `exp-find-${String(i + 1).padStart(2, "0")}`;
      route.findingId = findingId;

      const remediation = isPython
        ? "Replace Depends(get_current_user) with Depends(require_admin)."
        : 'Add requireRole("admin") to route middleware stack.';

      findings.push({
        id: findingId,
        ruleId: "devmind.authz.missing_role_check",
        name: "Missing Role Authorization Check",
        severity: "high",
        category: "authorization",
        evidenceLevel: "E1",
        evidenceLabel: "E1 · Possible",
        file: module.file,
        lineStart,
        lineEnd,
        message:
          "Sensitive administrative operation has authentication verified but lacks role or permission authorization validation.",
        codeSnippet,
        remediation,
      });
    }

    // 2. devmind.authn.unprotected_route
    // Condition: Route is administrative or mutating, but completely unauthenticated
    if (isAdminRoute && !route.auth && !route.roleGuard) {
      const findingId = `authn-find-${String(i + 1).padStart(2, "0")}`;
      route.findingId = findingId;

      findings.push({
        id: findingId,
        ruleId: "devmind.authn.unprotected_route",
        name: "Unprotected Sensitive Endpoint",
        severity: "high",
        category: "authentication",
        evidenceLevel: "E1",
        evidenceLabel: "E1 · Possible",
        file: module.file,
        lineStart,
        lineEnd,
        message:
          "Sensitive administrative endpoint lacks authentication middleware or credentials verification.",
        codeSnippet,
        remediation: isPython
          ? "Add authentication dependency: user: CurrentUser = Depends(get_current_user)"
          : "Add requireAuth middleware to route definition.",
      });
    }
  }

  return findings;
}
