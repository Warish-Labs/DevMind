"""GitHub permissions specification, degradation handling, and error classification (docs/12 ADR-015, docs/03 §10.1).

Defines:
- Granular permission matrix for GitHub App installations and OAuth scopes.
- Strict rejection of forbidden / over-privileged scopes (least privilege).
- Permission degradation evaluation when tokens expire, are revoked, or lack scopes.
- RFC 9457 error mapping for GitHub API error responses (401, 403, 404, 429).
- Mandatory human approval gate check for any mutating GitHub action (no auto-comment/merge).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.core.errors import DevMindError

# ---------------------------------------------------------------------------
# Scope Definitions (ADR-015)
# ---------------------------------------------------------------------------

# Minimal required GitHub App repository permissions
GITHUB_APP_REQUIRED_PERMISSIONS: dict[str, str] = {
    "pull_requests": "read",
    "contents": "read",
    "metadata": "read",
}

# Optional GitHub App permissions (v1.2+, human approval gated)
GITHUB_APP_OPTIONAL_PERMISSIONS: dict[str, str] = {
    "issues": "write",
    "checks": "write",
}

# Standard GitHub OAuth user identity scopes
GITHUB_OAUTH_SCOPES: list[str] = [
    "read:user",
    "user:email",
    "repo",  # Fallback for OAuth-only personal repositories
]

# Forbidden scopes that DevMind must NEVER request or require
FORBIDDEN_SCOPES: frozenset[str] = frozenset({
    "delete_repo",
    "admin:org",
    "admin:repo_hook",
    "admin:org_hook",
    "admin:public_key",
    "admin:gpg_key",
    "site_admin",
})

# Actions that strictly require human approval (zero unapproved side effects)
MUTATING_GITHUB_ACTIONS: frozenset[str] = frozenset({
    "post_pr_comment",
    "create_review_comment",
    "merge_pull_request",
    "close_pull_request",
    "update_branch",
    "create_check_run",
})


class GitHubPermissionStatus(StrEnum):
    """Lifecycle status of a GitHub credential grant."""

    ACTIVE = "active"
    DEGRADED = "degraded"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class PermissionEvaluationResult:
    """Outcome of evaluating granted GitHub permissions against requirements."""

    status: GitHubPermissionStatus
    granted_permissions: list[str]
    missing_permissions: list[str]
    can_perform_analysis: bool
    reason: str | None = None
    resolution_hint: str | None = None


# ---------------------------------------------------------------------------
# Evaluation & Policy Enforcement
# ---------------------------------------------------------------------------


def evaluate_app_permissions(
    granted: dict[str, str] | list[str],
) -> PermissionEvaluationResult:
    """Evaluate GitHub App installation permissions against required matrix."""
    granted_map: dict[str, str] = {}
    if isinstance(granted, list):
        for item in granted:
            if ":" in item:
                k, v = item.split(":", 1)
                granted_map[k.strip()] = v.strip()
            else:
                granted_map[item.strip()] = "read"
    else:
        granted_map = dict(granted)

    missing: list[str] = []
    for perm, required_level in GITHUB_APP_REQUIRED_PERMISSIONS.items():
        granted_level = granted_map.get(perm)
        if not granted_level:
            missing.append(f"{perm}:{required_level}")
        elif required_level == "write" and granted_level != "write":
            missing.append(f"{perm}:{required_level}")

    granted_list = [f"{k}:{v}" for k, v in granted_map.items()]

    if not missing:
        return PermissionEvaluationResult(
            status=GitHubPermissionStatus.ACTIVE,
            granted_permissions=granted_list,
            missing_permissions=[],
            can_perform_analysis=True,
            reason=None,
            resolution_hint=None,
        )

    return PermissionEvaluationResult(
        status=GitHubPermissionStatus.DEGRADED,
        granted_permissions=granted_list,
        missing_permissions=missing,
        can_perform_analysis=False,
        reason=f"GitHub App installation lacks required permissions: {', '.join(missing)}",
        resolution_hint="Update GitHub App installation permissions in repository settings.",
    )


def evaluate_oauth_permissions(
    granted_scopes: list[str],
) -> PermissionEvaluationResult:
    """Evaluate OAuth granted scopes against basic identity and repo read requirements."""
    scopes_set = set(granted_scopes)
    has_identity = "read:user" in scopes_set or "user:email" in scopes_set or "user" in scopes_set
    has_repo = "repo" in scopes_set or "public_repo" in scopes_set

    missing: list[str] = []
    if not has_identity:
        missing.append("read:user")
    if not has_repo:
        missing.append("repo")

    if not missing:
        return PermissionEvaluationResult(
            status=GitHubPermissionStatus.ACTIVE,
            granted_permissions=list(granted_scopes),
            missing_permissions=[],
            can_perform_analysis=True,
            reason=None,
            resolution_hint=None,
        )

    return PermissionEvaluationResult(
        status=GitHubPermissionStatus.DEGRADED,
        granted_permissions=list(granted_scopes),
        missing_permissions=missing,
        can_perform_analysis=False,
        reason=f"GitHub OAuth token lacks required scopes: {', '.join(missing)}",
        resolution_hint="Re-authenticate with GitHub and authorize the requested scopes.",
    )


def requires_human_approval(action: str) -> bool:
    """Check if a GitHub mutation action requires a human approval gate per ADR-015."""
    return action in MUTATING_GITHUB_ACTIONS


# ---------------------------------------------------------------------------
# Error Classification (RFC 9457)
# ---------------------------------------------------------------------------


class GitHubPermissionDeniedError(DevMindError):
    """GitHub API returned 403 Forbidden or scope insufficient."""

    def __init__(
        self,
        detail: str = "GitHub integration permission denied",
        missing_permissions: list[str] | None = None,
    ) -> None:
        errors = (
            [{"field": "permissions", "message": f"Missing: {', '.join(missing_permissions)}"}]
            if missing_permissions
            else None
        )
        super().__init__(
            detail=detail,
            code="integration.github.permission_denied",
            status_code=403,
            title="GitHub Permission Denied",
            errors=errors,
        )


class GitHubTokenRevokedError(DevMindError):
    """GitHub token expired, invalid, or revoked (401)."""

    def __init__(
        self,
        detail: str = "GitHub credential revoked or expired. Please re-authenticate.",
    ) -> None:
        super().__init__(
            detail=detail,
            code="integration.github.token_revoked",
            status_code=401,
            title="GitHub Credential Revoked",
        )


class GitHubRateLimitError(DevMindError):
    """GitHub API rate limit exhausted (429 or 403 rate limit)."""

    def __init__(
        self,
        detail: str = "GitHub API rate limit exceeded. Please retry later.",
        retry_after: int | None = None,
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            detail=detail,
            code="integration.github.rate_limited",
            status_code=429,
            title="GitHub Rate Limit Exceeded",
            headers=headers,
        )


def classify_github_api_error(
    status_code: int,
    response_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> DevMindError:
    """Convert raw GitHub REST API errors to RFC 9457 Problem Details errors."""
    body = response_body or {}
    message = body.get("message", "GitHub API error")

    if status_code == 401:
        return GitHubTokenRevokedError(
            detail=f"GitHub authentication failed: {message}",
        )

    if status_code == 403:
        if "rate limit" in message.lower():
            retry_after = None
            if headers and "x-ratelimit-reset" in headers:
                try:
                    retry_after = max(0, int(headers["x-ratelimit-reset"]))
                except ValueError:
                    pass
            return GitHubRateLimitError(
                detail=f"GitHub API rate limit exceeded: {message}",
                retry_after=retry_after,
            )
        return GitHubPermissionDeniedError(
            detail=f"GitHub permission denied: {message}",
        )

    if status_code == 404:
        from app.core.errors import NotFoundError

        return NotFoundError(
            detail=f"GitHub resource not found: {message}",
            code="resource.not_found",
        )

    if status_code == 429:
        retry_after = None
        if headers and "retry-after" in headers:
            try:
                retry_after = int(headers["retry-after"])
            except ValueError:
                pass
        return GitHubRateLimitError(
            detail=f"GitHub API rate limit reached: {message}",
            retry_after=retry_after,
        )

    return DevMindError(
        detail=f"GitHub upstream error ({status_code}): {message}",
        code="server.internal_error",
        status_code=502,
        title="Bad Gateway",
    )
