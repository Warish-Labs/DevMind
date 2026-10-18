"""Deterministic guard resolution and structural route check (docs/05 §6.3, docs/03 §3.2, docs/03 §12.1).

Implements deterministic E2/E1 route security analysis:
1. Route enumeration across supported frameworks (Next.js, Express, FastAPI) from `defines_route` edges and symbols.
2. Guard chain resolution (middleware, dependencies, decorators, inline checks) from `guarded_by` and `calls` edges.
3. Deterministic route sensitivity classification (public, authenticated, sensitive/admin).
4. Authentication and authorization presence evaluation.
5. Deterministic E2 confirmation with required `analysis_scope` tracking examined callees and unresolved dependencies.
6. Recording of unsupported or unresolved frameworks as 'not analyzed' (never reported as 'safe').
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.brain import CodeRelationship, CodeSymbol
from app.persistence.repositories.brain_repo import BrainRepository

# --- Canonical Rule IDs (docs/03 §12.1, evals/scanner/fixtures) ---
RULE_MISSING_AUTH = "devmind.authn.unprotected_route"
RULE_MISSING_ROLE_CHECK = "devmind.authz.missing_role_check"

# --- Framework and Sensitivity Enums ---


class RouteFramework(StrEnum):
    """Supported route frameworks in MVP (docs/05 §6.3)."""

    FASTAPI = "fastapi"
    EXPRESS = "express"
    NEXTJS = "nextjs"
    UNKNOWN = "unknown"


class RouteSensitivity(StrEnum):
    """Classification of endpoint sensitivity."""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    SENSITIVE = "sensitive"


class GuardType(StrEnum):
    """Mechanism providing authentication or authorization."""

    MIDDLEWARE = "middleware"
    DEPENDENCY = "dependency"
    DECORATOR = "decorator"
    INLINE_CHECK = "inline_check"
    UNKNOWN = "unknown"


# --- Analysis Models ---


class ResolvedGuard(BaseModel):
    """Resolved guard element in an endpoint's execution chain."""

    symbol_id: UUID | None = None
    symbol_key: str | None = None
    name: str
    guard_type: GuardType = GuardType.UNKNOWN
    is_authentication: bool = False
    is_authorization: bool = False
    raw_expression: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RouteDefinition(BaseModel):
    """Normalized route endpoint extracted from code symbols and relationships."""

    symbol_id: UUID
    symbol_key: str
    name: str
    file_path: str
    start_line: int
    end_line: int
    file_version_id: UUID | None = None
    http_method: str = "GET"
    http_route: str = "/"
    framework: RouteFramework = RouteFramework.UNKNOWN
    framework_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GuardResolutionChain(BaseModel):
    """Complete resolution chain for a single route endpoint."""

    route_symbol_key: str
    guards: list[ResolvedGuard] = Field(default_factory=list)
    callees_examined: list[str] = Field(default_factory=list)
    unresolved_elements: list[str] = Field(default_factory=list)
    is_fully_resolved: bool = True
    depth_reached: int = 0

    @property
    def has_authentication(self) -> bool:
        return any(g.is_authentication for g in self.guards)

    @property
    def has_authorization(self) -> bool:
        return any(g.is_authorization for g in self.guards)

    @property
    def authentication_summary(self) -> str:
        auth_guards = [g.name for g in self.guards if g.is_authentication]
        return ", ".join(auth_guards) if auth_guards else "none found"

    @property
    def authorization_summary(self) -> str:
        authz_guards = [g.name for g in self.guards if g.is_authorization]
        return ", ".join(authz_guards) if authz_guards else "none found"

    @property
    def analysis_scope_summary(self) -> str:
        """Format analysis scope strictly matching docs/03 §12.1 and docs/05 §6.3."""
        callees_count = len(self.callees_examined)
        callee_word = "callee" if callees_count == 1 else "callees"
        if not self.unresolved_elements:
            return f"handler and {callees_count} resolved {callee_word}; 0 unresolved dependencies"
        unresolved_count = len(self.unresolved_elements)
        unresolved_desc = ", ".join(self.unresolved_elements)
        return (
            f"handler and {callees_count} resolved {callee_word}; "
            f"unresolved: {unresolved_count} dynamic dependency ({unresolved_desc})"
        )


class DraftFinding(BaseModel):
    """Draft finding emitted with deterministic evidence level (docs/03 §12.1)."""

    rule_id: str
    category: str
    title: str
    summary: str
    explanation: str | None = None
    severity: str
    confidence: str
    evidence_level: str  # E1 or E2
    status: str = "open"
    file_path: str
    start_line: int
    end_line: int
    canonical_identifier: str
    fingerprint: str
    evidence_details: dict[str, Any]
    suggested_fix_description: str | None = None
    suggested_fix_diff: str | None = None

    def to_finding_dict(self) -> dict[str, Any]:
        """Convert to standard FindingPayload dictionary structure."""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "explanation": self.explanation,
            "severity": self.severity,
            "confidence": self.confidence,
            "evidence_level": self.evidence_level,
            "status": self.status,
            "location": {
                "path": self.file_path,
                "start_line": self.start_line,
                "end_line": self.end_line,
            },
            "canonical_identifier": self.canonical_identifier,
            "fingerprint": self.fingerprint,
            "evidence": [
                {
                    "role": "primary",
                    "path": self.file_path,
                    "start_line": self.start_line,
                    "end_line": self.end_line,
                    "snippet_hash": self.evidence_details.get("snippet_hash", ""),
                    "detail": self.evidence_details,
                }
            ],
            "suggested_fix": {
                "kind": "proposal",
                "description": self.suggested_fix_description or "Add required security guard.",
                "diff": self.suggested_fix_diff,
            },
        }


class RouteSecurityEvaluation(BaseModel):
    """Result of structural security analysis on a single endpoint."""

    route: RouteDefinition
    sensitivity: RouteSensitivity
    status: str  # protected | missing_auth | missing_authz | public_exempt | not_analyzed
    evidence_level: str  # E0 | E1 | E2
    guard_chain: GuardResolutionChain
    draft_finding: DraftFinding | None = None
    reason: str | None = None


class ProjectSecurityConfig(BaseModel):
    """Project-specific customization for route sensitivity and security patterns."""

    public_routes: list[str] = Field(default_factory=list)
    sensitive_routes: list[str] = Field(default_factory=list)
    custom_authn_patterns: list[str] = Field(default_factory=list)
    custom_authz_patterns: list[str] = Field(default_factory=list)
    exempt_symbol_keys: list[str] = Field(default_factory=list)


class RouteAnalysisResult(BaseModel):
    """Aggregate result of analyzing routes in a project."""

    total_routes_discovered: int = 0
    total_analyzed: int = 0
    protected_count: int = 0
    missing_auth_count: int = 0
    missing_authz_count: int = 0
    public_exempt_count: int = 0
    unsupported_count: int = 0
    evaluations: list[RouteSecurityEvaluation] = Field(default_factory=list)
    draft_findings: list[DraftFinding] = Field(default_factory=list)
    unsupported_routes: list[dict[str, Any]] = Field(default_factory=list)


# --- Deterministic Fingerprinting Helper ---


def compute_fingerprint(rule_id: str, path: str, canonical_identifier: str) -> str:
    """Compute stable 64-character SHA-256 fingerprint."""
    clean_path = path.strip().replace("\\", "/").lstrip("/")
    identifier = canonical_identifier.strip()
    raw = f"{rule_id}:{clean_path}:{identifier}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --- Guard & Sensitivity Patterns ---

DEFAULT_PUBLIC_PATTERNS = (
    r"^/healthz?$",
    r"^/livez?$",
    r"^/readyz?$",
    r"^/ping$",
    r"^/metrics$",
    r"^/docs/?",
    r"^/redoc/?",
    r"^/openapi\.json$",
    r"^/favicon\.ico$",
    r"^/robots\.txt$",
    r"^/api/v1/auth/(?:login|register|callback|refresh)$",
    r"^/auth/(?:login|register|callback|signin|signup)$",
    r"^/(?:login|register|signup|forgot-password|reset-password)$",
)

DEFAULT_SENSITIVE_PATTERNS = (
    r"^/admin(?:/.*)?$",
    r"^/internal(?:/.*)?$",
    r"^/superadmin(?:/.*)?$",
    r"^/system(?:/.*)?$",
    r"^/api/v\d+/workspaces/[^/]+/members(?:/.*)?$",
    r"^/api/v\d+/projects/[^/]+/settings(?:/.*)?$",
)

AUTHN_KEYWORDS = (
    "current_user",
    "get_current_user",
    "verify_token",
    "verify_jwt",
    "jwt",
    "authenticate",
    "authenticated",
    "auth_context",
    "authcontext",
    "clerk",
    "session",
    "get_session",
    "getserversession",
    "bearer",
    "passport",
    "require_auth",
    "requireauth",
    "auth_required",
    "withauth",
    "with_auth",
)

AUTHZ_KEYWORDS = (
    "require_role",
    "requirerole",
    "has_role",
    "hasrole",
    "require_permission",
    "requirepermission",
    "has_permission",
    "haspermission",
    "check_permission",
    "checkpermission",
    "admin",
    "require_admin",
    "requireadmin",
    "is_admin",
    "isadmin",
    "policy",
    "policyservice",
    "authorize",
    "authorized",
    "rbac",
    "scope",
    "scopes",
    "requirescope",
    "require_scope",
)


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Safely extract field from dict or object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    val = getattr(obj, name, default)
    return val if val is not None else default


# --- Route Guard Analyzer ---


class RouteGuardAnalyzer:
    """Deterministic analyzer for route enumeration, guard resolution, and E2 verification."""

    def __init__(self, config: ProjectSecurityConfig | None = None) -> None:
        self.config = config or ProjectSecurityConfig()

    def detect_framework(
        self,
        symbol: CodeSymbol | dict[str, Any],
        path: str = "",
    ) -> RouteFramework:
        """Detect the web framework of a symbol per docs/05 §6.3."""
        framework_tags = _attr(symbol, "framework_tags", [])
        tags_lower = {str(t).lower() for t in framework_tags}
        metadata = _attr(symbol, "metadata", {}) or {}
        meta_framework = str(metadata.get("framework") or "").lower()

        if "fastapi" in tags_lower or meta_framework == "fastapi":
            return RouteFramework.FASTAPI
        if "express" in tags_lower or meta_framework == "express":
            return RouteFramework.EXPRESS
        if "nextjs" in tags_lower or meta_framework == "nextjs":
            return RouteFramework.NEXTJS

        # If another non-MVP framework is explicitly tagged or declared, return UNKNOWN
        if meta_framework or any(
            t in tags_lower for t in {"django", "flask", "rails", "spring", "gin", "fiber", "koa"}
        ):
            return RouteFramework.UNKNOWN

        kind = _attr(symbol, "kind", "")
        if kind == "server_action":
            return RouteFramework.NEXTJS

        # File path heuristics
        norm_path = path.lower().replace("\\", "/")
        if "route.ts" in norm_path or "route.js" in norm_path:
            return RouteFramework.NEXTJS
        if norm_path.endswith(".py"):
            return RouteFramework.FASTAPI
        if norm_path.endswith((".ts", ".js")):
            return RouteFramework.EXPRESS

        return RouteFramework.UNKNOWN

    def enumerate_routes(
        self,
        symbols: list[CodeSymbol | dict[str, Any]],
        relationships: list[CodeRelationship | dict[str, Any]],
        file_path_map: dict[UUID, str] | None = None,
    ) -> list[RouteDefinition]:
        """Enumerate all route handler and server action symbols in the project."""
        path_map = file_path_map or {}
        routes: list[RouteDefinition] = []

        # 1. Build map of symbols by ID and symbol_key
        symbol_by_id: dict[UUID, CodeSymbol | dict[str, Any]] = {}
        for s in symbols:
            s_id = _attr(s, "id")
            if s_id is not None:
                symbol_by_id[s_id] = s

        # 2. Extract defines_route relationships
        defines_route_edges: list[CodeRelationship | dict[str, Any]] = []
        for r in relationships:
            if _attr(r, "kind") == "defines_route":
                defines_route_edges.append(r)

        processed_symbol_ids: set[UUID] = set()

        for edge in defines_route_edges:
            from_id = _attr(edge, "from_symbol_id")
            to_ext = _attr(edge, "to_external")
            sym = symbol_by_id.get(from_id) if from_id else None
            if not sym or from_id in processed_symbol_ids:
                continue

            processed_symbol_ids.add(from_id)
            meta = _attr(sym, "metadata", {}) or {}
            file_v_id = _attr(sym, "file_version_id")
            file_path = meta.get("path") or path_map.get(file_v_id, "unknown")

            # Parse HTTP method & route from edge.to_external or metadata
            method = "GET"
            route_path = "/"
            if to_ext:
                parts = to_ext.strip().split(maxsplit=1)
                if len(parts) == 2 and parts[0].upper() in {
                    "GET",
                    "POST",
                    "PUT",
                    "DELETE",
                    "PATCH",
                    "OPTIONS",
                    "HEAD",
                }:
                    method = parts[0].upper()
                    route_path = parts[1]
                else:
                    route_path = to_ext
            else:
                method = meta.get("http_method", "GET").upper()
                route_path = meta.get("http_path") or meta.get("route", "/")

            framework = self.detect_framework(sym, file_path)

            routes.append(
                RouteDefinition(
                    symbol_id=from_id,
                    symbol_key=_attr(sym, "symbol_key", ""),
                    name=_attr(sym, "name", ""),
                    file_path=file_path,
                    start_line=_attr(sym, "start_line", 1),
                    end_line=_attr(sym, "end_line", 1),
                    file_version_id=file_v_id,
                    http_method=method,
                    http_route=route_path,
                    framework=framework,
                    framework_tags=_attr(sym, "framework_tags", []),
                    metadata=meta,
                )
            )

        # 3. Also check symbols marked kind in ("route_handler", "server_action") not yet processed
        for sym in symbols:
            s_id = _attr(sym, "id")
            if s_id in processed_symbol_ids:
                continue
            kind = _attr(sym, "kind", "")
            meta = _attr(sym, "metadata", {}) or {}
            tags = _attr(sym, "framework_tags", [])
            has_route_tag = any(
                str(t).lower() in {"route", "endpoint", "api", "route_handler"} for t in tags
            )

            if (
                kind in {"route_handler", "server_action"}
                or has_route_tag
                or "http_path" in meta
                or "http_method" in meta
            ):
                processed_symbol_ids.add(s_id)
                file_v_id = _attr(sym, "file_version_id")
                file_path = meta.get("path") or path_map.get(file_v_id, "unknown")

                name = _attr(sym, "name", "")
                if kind == "server_action":
                    method = "POST"
                    route_path = f"/action/{name}"
                else:
                    method = meta.get("http_method") or (
                        name.upper()
                        if name.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}
                        else "GET"
                    )
                    route_path = meta.get("http_path") or meta.get("route") or f"/{name.lower()}"

                framework = self.detect_framework(sym, file_path)

                routes.append(
                    RouteDefinition(
                        symbol_id=s_id,
                        symbol_key=_attr(sym, "symbol_key", ""),
                        name=name,
                        file_path=file_path,
                        start_line=_attr(sym, "start_line", 1),
                        end_line=_attr(sym, "end_line", 1),
                        file_version_id=file_v_id,
                        http_method=method,
                        http_route=route_path,
                        framework=framework,
                        framework_tags=tags,
                        metadata=meta,
                    )
                )

        return routes

    def resolve_guard_chain(
        self,
        route: RouteDefinition,
        symbols_by_id: dict[UUID, CodeSymbol | dict[str, Any]],
        symbols_by_key: dict[str, CodeSymbol | dict[str, Any]],
        outgoing_edges: dict[UUID, list[CodeRelationship | dict[str, Any]]],
        max_depth: int = 3,
    ) -> GuardResolutionChain:
        """Resolve the guard and callee chain starting from a route symbol."""
        chain = GuardResolutionChain(route_symbol_key=route.symbol_key)
        visited_symbols: set[UUID] = {route.symbol_id}
        queue: list[tuple[UUID, int]] = [(route.symbol_id, 0)]
        max_depth_seen = 0

        # Also inspect route symbol's own metadata for decorators/dependencies
        route_meta = route.metadata
        if "dependencies" in route_meta and isinstance(route_meta["dependencies"], list):
            for dep in route_meta["dependencies"]:
                dep_str = str(dep)
                is_authn = self._matches_authn(dep_str)
                is_authz = self._matches_authz(dep_str)
                chain.guards.append(
                    ResolvedGuard(
                        name=dep_str,
                        guard_type=GuardType.DEPENDENCY,
                        is_authentication=is_authn,
                        is_authorization=is_authz,
                        raw_expression=dep_str,
                    )
                )

        if "decorators" in route_meta and isinstance(route_meta["decorators"], list):
            for dec in route_meta["decorators"]:
                dec_str = str(dec)
                is_authn = self._matches_authn(dec_str)
                is_authz = self._matches_authz(dec_str)
                chain.guards.append(
                    ResolvedGuard(
                        name=dec_str,
                        guard_type=GuardType.DECORATOR,
                        is_authentication=is_authn,
                        is_authorization=is_authz,
                        raw_expression=dec_str,
                    )
                )

        while queue:
            curr_id, curr_depth = queue.pop(0)
            if curr_depth > max_depth_seen:
                max_depth_seen = curr_depth

            edges = outgoing_edges.get(curr_id, [])
            for edge in edges:
                e_kind = _attr(edge, "kind")
                to_id = _attr(edge, "to_symbol_id")
                to_ext = _attr(edge, "to_external")
                resolution = _attr(edge, "resolution", "resolved")

                if e_kind in {"guarded_by", "calls"}:
                    if to_id is not None and to_id in symbols_by_id:
                        target_sym = symbols_by_id[to_id]
                        target_name = _attr(target_sym, "name", "")
                        target_key = _attr(target_sym, "symbol_key", "")

                        chain.callees_examined.append(target_name or target_key)

                        is_authn = self._matches_authn(target_name) or self._matches_authn(
                            target_key
                        )
                        is_authz = self._matches_authz(target_name) or self._matches_authz(
                            target_key
                        )

                        if is_authn or is_authz or e_kind == "guarded_by":
                            guard_type = (
                                GuardType.DEPENDENCY
                                if route.framework == RouteFramework.FASTAPI
                                else (
                                    GuardType.MIDDLEWARE
                                    if route.framework == RouteFramework.EXPRESS
                                    else GuardType.INLINE_CHECK
                                )
                            )
                            chain.guards.append(
                                ResolvedGuard(
                                    symbol_id=to_id,
                                    symbol_key=target_key,
                                    name=target_name,
                                    guard_type=guard_type,
                                    is_authentication=is_authn,
                                    is_authorization=is_authz,
                                )
                            )

                        if to_id not in visited_symbols and curr_depth < max_depth:
                            visited_symbols.add(to_id)
                            queue.append((to_id, curr_depth + 1))

                    elif to_ext:
                        # External or unlinked reference
                        is_authn = self._matches_authn(to_ext)
                        is_authz = self._matches_authz(to_ext)
                        if is_authn or is_authz or e_kind == "guarded_by":
                            chain.guards.append(
                                ResolvedGuard(
                                    name=to_ext,
                                    guard_type=GuardType.MIDDLEWARE
                                    if route.framework == RouteFramework.EXPRESS
                                    else GuardType.DEPENDENCY,
                                    is_authentication=is_authn,
                                    is_authorization=is_authz,
                                    raw_expression=to_ext,
                                )
                            )
                        if resolution == "unresolved" or not (is_authn or is_authz):
                            chain.unresolved_elements.append(to_ext)
                    else:
                        if resolution == "unresolved":
                            chain.unresolved_elements.append("unresolved_call_target")

        chain.depth_reached = max_depth_seen
        chain.is_fully_resolved = len(chain.unresolved_elements) == 0
        return chain

    def classify_sensitivity(self, route: RouteDefinition) -> RouteSensitivity:
        """Classify route sensitivity deterministically."""
        norm_path = route.http_route.strip()

        # 1. Check custom overrides
        for pub_pat in self.config.public_routes:
            if re.search(pub_pat, norm_path, re.IGNORECASE):
                return RouteSensitivity.PUBLIC

        for sens_pat in self.config.sensitive_routes:
            if re.search(sens_pat, norm_path, re.IGNORECASE):
                return RouteSensitivity.SENSITIVE

        # 2. Check default public patterns
        for pub_pat in DEFAULT_PUBLIC_PATTERNS:
            if re.search(pub_pat, norm_path, re.IGNORECASE):
                return RouteSensitivity.PUBLIC

        if route.http_method in {"OPTIONS", "HEAD"}:
            return RouteSensitivity.PUBLIC

        # 3. Check default sensitive patterns
        for sens_pat in DEFAULT_SENSITIVE_PATTERNS:
            if re.search(sens_pat, norm_path, re.IGNORECASE):
                return RouteSensitivity.SENSITIVE

        # Mutating endpoints on non-public APIs are sensitive
        if route.http_method in {"POST", "PUT", "PATCH", "DELETE"}:
            return RouteSensitivity.SENSITIVE

        # 4. Default for normal resource reads
        return RouteSensitivity.AUTHENTICATED

    def evaluate_route_security(
        self,
        route: RouteDefinition,
        guard_chain: GuardResolutionChain,
    ) -> RouteSecurityEvaluation:
        """Evaluate route security and produce a deterministic E2/E1 finding if vulnerable."""
        # 1. Unsupported framework check
        if route.framework == RouteFramework.UNKNOWN:
            return RouteSecurityEvaluation(
                route=route,
                sensitivity=RouteSensitivity.AUTHENTICATED,
                status="not_analyzed",
                evidence_level="E0",
                guard_chain=guard_chain,
                reason="Unsupported framework (MVP supports Next.js, Express, FastAPI). Absence of finding is not safe.",
            )

        # 2. Sensitivity check
        sensitivity = self.classify_sensitivity(route)
        if sensitivity == RouteSensitivity.PUBLIC:
            return RouteSecurityEvaluation(
                route=route,
                sensitivity=RouteSensitivity.PUBLIC,
                status="public_exempt",
                evidence_level="E0",
                guard_chain=guard_chain,
                reason="Endpoint matches public route pattern and is exempt from authentication requirements.",
            )

        has_authn = guard_chain.has_authentication
        has_authz = guard_chain.has_authorization
        is_resolved = guard_chain.is_fully_resolved
        canonical_id = f"{route.http_method} {route.http_route}"
        snippet_hash = f"sha256:{hashlib.sha256(f'{route.file_path}:{route.start_line}:{route.end_line}:{canonical_id}'.encode()).hexdigest()}"

        # 3. Missing Authentication Evaluation
        if not has_authn:
            evidence_level = "E2" if is_resolved else "E1"
            confidence = "high" if is_resolved else "medium"
            severity = (
                "critical"
                if sensitivity == RouteSensitivity.SENSITIVE
                and route.http_method in {"POST", "PUT", "PATCH", "DELETE"}
                else "high"
            )
            title = (
                "Sensitive endpoint has no authentication guard"
                if is_resolved
                else "Possible unauthenticated sensitive route"
            )
            summary = (
                "Route is classified as sensitive but no authentication check was found on the analyzed call path."
                if is_resolved
                else "No authentication guard was identified, but call-path resolution is incomplete."
            )

            detail = {
                "route": canonical_id,
                "authentication": "none found",
                "authorization": "none found",
                "analysis_scope": guard_chain.analysis_scope_summary,
                "snippet_hash": snippet_hash,
            }

            fingerprint = compute_fingerprint(RULE_MISSING_AUTH, route.file_path, canonical_id)
            fix_desc = "Add an authentication dependency or middleware to verify caller identity."

            finding = DraftFinding(
                rule_id=RULE_MISSING_AUTH,
                category="authentication",
                title=title,
                summary=summary,
                severity=severity,
                confidence=confidence,
                evidence_level=evidence_level,
                status="open",
                file_path=route.file_path,
                start_line=route.start_line,
                end_line=route.end_line,
                canonical_identifier=canonical_id,
                fingerprint=fingerprint,
                evidence_details=detail,
                suggested_fix_description=fix_desc,
            )

            return RouteSecurityEvaluation(
                route=route,
                sensitivity=sensitivity,
                status="missing_auth",
                evidence_level=evidence_level,
                guard_chain=guard_chain,
                draft_finding=finding,
                reason=summary,
            )

        # 4. Missing Authorization Evaluation (Authenticated, but missing role/permission check)
        # Required for admin routes and sensitive mutating operations
        is_admin_or_destructive = bool(
            re.search(r"^/(?:admin|internal|superadmin)(?:/.*)?$", route.http_route, re.IGNORECASE)
            or (
                sensitivity == RouteSensitivity.SENSITIVE
                and route.http_method in {"POST", "PUT", "PATCH", "DELETE"}
            )
        )

        if is_admin_or_destructive and not has_authz:
            evidence_level = "E2" if is_resolved else "E1"
            confidence = "high" if is_resolved else "medium"
            severity = "high" if is_resolved else "medium"
            title = (
                "Administrative route has no role check"
                if is_resolved
                else "Possible missing role authorization check"
            )
            summary = (
                "Authentication is required but no authorization check was found on the call path."
                if is_resolved
                else "Authentication is present but authorization could not be verified on the incomplete call path."
            )

            detail = {
                "route": canonical_id,
                "authentication": guard_chain.authentication_summary,
                "authorization": "none found",
                "analysis_scope": guard_chain.analysis_scope_summary,
                "snippet_hash": snippet_hash,
            }

            fingerprint = compute_fingerprint(
                RULE_MISSING_ROLE_CHECK, route.file_path, canonical_id
            )
            fix_desc = "Replace general authentication with an explicit role check (e.g. require_admin or requireRole)."

            finding = DraftFinding(
                rule_id=RULE_MISSING_ROLE_CHECK,
                category="authorization",
                title=title,
                summary=summary,
                severity=severity,
                confidence=confidence,
                evidence_level=evidence_level,
                status="open",
                file_path=route.file_path,
                start_line=route.start_line,
                end_line=route.end_line,
                canonical_identifier=canonical_id,
                fingerprint=fingerprint,
                evidence_details=detail,
                suggested_fix_description=fix_desc,
            )

            return RouteSecurityEvaluation(
                route=route,
                sensitivity=sensitivity,
                status="missing_authz",
                evidence_level=evidence_level,
                guard_chain=guard_chain,
                draft_finding=finding,
                reason=summary,
            )

        # 5. Route is properly protected
        return RouteSecurityEvaluation(
            route=route,
            sensitivity=sensitivity,
            status="protected",
            evidence_level="E0",
            guard_chain=guard_chain,
            reason="Endpoint has verified authentication and appropriate authorization guards.",
        )

    def analyze_routes(
        self,
        symbols: list[CodeSymbol | dict[str, Any]],
        relationships: list[CodeRelationship | dict[str, Any]],
        file_path_map: dict[UUID, str] | None = None,
    ) -> RouteAnalysisResult:
        """Execute full route enumeration, guard resolution, and structural verification."""
        routes = self.enumerate_routes(symbols, relationships, file_path_map)

        # Build symbol lookup maps
        symbols_by_id: dict[UUID, CodeSymbol | dict[str, Any]] = {}
        symbols_by_key: dict[str, CodeSymbol | dict[str, Any]] = {}
        for s in symbols:
            s_id = _attr(s, "id")
            s_key = _attr(s, "symbol_key")
            if s_id is not None:
                symbols_by_id[s_id] = s
            if s_key:
                symbols_by_key[s_key] = s

        # Build outgoing edge graph
        outgoing_edges: dict[UUID, list[CodeRelationship | dict[str, Any]]] = {}
        for r in relationships:
            from_id = _attr(r, "from_symbol_id")
            if from_id is not None:
                outgoing_edges.setdefault(from_id, []).append(r)

        result = RouteAnalysisResult(total_routes_discovered=len(routes))

        for route in routes:
            # Check exempt symbol keys
            if route.symbol_key in self.config.exempt_symbol_keys:
                continue

            guard_chain = self.resolve_guard_chain(
                route=route,
                symbols_by_id=symbols_by_id,
                symbols_by_key=symbols_by_key,
                outgoing_edges=outgoing_edges,
            )

            evaluation = self.evaluate_route_security(route, guard_chain)
            result.evaluations.append(evaluation)

            if evaluation.status == "protected":
                result.protected_count += 1
                result.total_analyzed += 1
            elif evaluation.status == "missing_auth":
                result.missing_auth_count += 1
                result.total_analyzed += 1
                if evaluation.draft_finding:
                    result.draft_findings.append(evaluation.draft_finding)
            elif evaluation.status == "missing_authz":
                result.missing_authz_count += 1
                result.total_analyzed += 1
                if evaluation.draft_finding:
                    result.draft_findings.append(evaluation.draft_finding)
            elif evaluation.status == "public_exempt":
                result.public_exempt_count += 1
                result.total_analyzed += 1
            elif evaluation.status == "not_analyzed":
                result.unsupported_count += 1
                result.unsupported_routes.append(
                    {
                        "route": f"{route.http_method} {route.http_route}",
                        "file": route.file_path,
                        "reason": evaluation.reason,
                    }
                )

        return result

    async def analyze_project(
        self,
        session: AsyncSession,
        project_id: UUID,
        ctx: AuthContext | SystemContext,
    ) -> RouteAnalysisResult:
        """Fetch project symbols and relationships from database and analyze routes."""
        repo = BrainRepository(session)
        symbols = await repo.list_current_symbols(ctx, project_id, limit=2000)
        relationships = await repo.list_relationships(ctx, project_id, limit=5000)
        return self.analyze_routes(symbols=symbols, relationships=relationships)

    def _matches_authn(self, text: str) -> bool:
        low = text.lower()
        if any(pat.lower() in low for pat in self.config.custom_authn_patterns):
            return True
        return any(kw in low for kw in AUTHN_KEYWORDS)

    def _matches_authz(self, text: str) -> bool:
        low = text.lower()
        if any(pat.lower() in low for pat in self.config.custom_authz_patterns):
            return True
        return any(kw in low for kw in AUTHZ_KEYWORDS)
