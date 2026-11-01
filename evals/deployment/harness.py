"""Benchmark harness and evaluation runner for Deployment Diagnosis (docs/01 CAP-07, docs/09 §9, M12-17)."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SERVER_DIR = ROOT_DIR / "server"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.analysis.env_checker import EnvVarChecker  # noqa: E402
from app.analysis.log_parser import LogParser  # noqa: E402
from app.core.auth_context import AuthContext  # noqa: E402
from app.core.errors import ForbiddenError  # noqa: E402
from app.persistence.models.deployment import DeploymentIncident  # noqa: E402
from app.persistence.repositories.incident_repo import (  # noqa: E402
    DeploymentIncidentRepository,
)
from evals.deployment.metrics import (  # noqa: E402
    DeploymentBenchmarkSummary,
    compute_classification_metrics,
    compute_env_var_metrics,
    compute_retrieval_metrics,
    compute_sanitization_metrics,
)

DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"
RESULTS_DIR = ROOT_DIR / "evals" / "results" / "deployment"


def get_git_commit_hash() -> str:
    """Resolve current short git commit hash for benchmark tracking."""
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return output.strip()
    except Exception:
        return "unknown"


def evaluate_sanitization_and_parser(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate LogParser sanitization, category classification, and line citations."""
    raw_log = case["raw_log"]
    parsed = LogParser.redact_and_parse(
        raw_log,
        environment=case.get("environment", "production"),
        service_name=case.get("service_name"),
    )

    # 1. Secret redaction verification
    secrets_leaked = 0
    for secret in case.get("secret_tokens", []):
        if (
            secret in parsed.redacted_text
            or secret in parsed.error_signature
            or secret in parsed.probable_cause
        ):
            secrets_leaked += 1

    # 2. ANSI stripping verification
    has_ansi = "\x1b[" in parsed.redacted_text or "\x1b[" in parsed.error_signature

    # 3. Category classification
    expected_cat = case["expected_category"]
    category_match = parsed.failure_category == expected_cat

    # 4. Primary line citation
    expected_line = case.get("expected_primary_line_index")
    primary_line_match = parsed.primary_log_line == expected_line

    # 5. Insufficient log detection
    expected_insuff = case.get("expected_insufficient_log", False)
    is_insufficient = (
        (parsed.failure_category in ("unknown", "unhandled_exception") and parsed.confidence <= 0.50)
        or not parsed.redacted_text.strip()
    )
    insufficient_log_match = is_insufficient == expected_insuff

    return {
        "case_id": case["id"],
        "secrets_leaked": secrets_leaked,
        "has_ansi": has_ansi,
        "category_match": category_match,
        "primary_line_match": primary_line_match,
        "insufficient_log_match": insufficient_log_match,
        "parsed": parsed,
    }


def evaluate_env_var_analysis(case: dict[str, Any], parsed: Any) -> dict[str, Any]:
    """Evaluate EnvVarChecker missing variable extraction and typo recommendations."""
    example_env = case.get("example_env", "")
    configured = case.get("configured_env_vars", [])
    expected_missing = set(case.get("expected_missing_vars", []))

    if not example_env:
        return {
            "case_id": case["id"],
            "missing_tp": 0,
            "missing_fp": 0,
            "missing_fn": 0,
            "typo_match": True,
        }

    check_result = EnvVarChecker.verify_environment_variables(
        referenced_names=parsed.referenced_env_vars,
        configured_names=configured,
        example_env_content=example_env,
    )

    detected_missing = set(check_result.missing_required)
    tp = len(detected_missing & expected_missing)
    fp = len(detected_missing - expected_missing)
    fn = len(expected_missing - detected_missing)

    # Check expected typo suggestions
    typo_match = True
    for expected_typo in case.get("expected_typos", []):
        ref_name = expected_typo["referenced_name"]
        exp_tmpl = expected_typo["expected_template_name"]
        min_sim = expected_typo.get("min_similarity", 0.70)

        found = False
        for typo_cand in check_result.suspected_typos:
            candidate_names = {typo_cand.expected_name, typo_cand.found_name}
            if (
                ref_name in candidate_names
                and exp_tmpl in candidate_names
                and typo_cand.similarity >= min_sim
            ):
                found = True
                break
        if not found:
            typo_match = False

    return {
        "case_id": case["id"],
        "missing_tp": tp,
        "missing_fp": fp,
        "missing_fn": fn,
        "typo_match": typo_match,
    }


async def evaluate_incident_retrieval(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate DeploymentIncidentRepository similar incident search and tenant isolation."""
    workspace_id = UUID("018f0a00-0000-7000-8000-000000000001")
    project_id = UUID("018f0a00-0000-7000-8000-000000000101")
    alien_workspace_id = UUID("018f0a00-0000-7000-8000-000000000099")

    ctx = AuthContext(
        user_id=UUID("018f0a00-0000-7000-8000-000000000002"),
        clerk_user_id="user_test",
        email="test@devmind.local",
        workspace_id=workspace_id,
        project_id=project_id,
        workspace_role="admin",
        project_role="maintainer",
        permissions=frozenset({"project:read", "analysis:create"}),
    )
    alien_ctx = AuthContext(
        user_id=UUID("018f0a00-0000-7000-8000-000000000003"),
        clerk_user_id="user_alien",
        email="alien@devmind.local",
        workspace_id=alien_workspace_id,
        project_id=project_id,
        workspace_role="admin",
        project_role="maintainer",
        permissions=frozenset({"project:read", "analysis:create"}),
    )

    # Create mock session with past incidents
    now = datetime.now(UTC)
    mock_incident_1 = DeploymentIncident(
        id=UUID("0192e4a1-0000-7000-8000-000000000001"),
        workspace_id=workspace_id,
        project_id=project_id,
        fingerprint="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        summary="Alembic schema migration failed: revision not found",
        probable_cause="Can't locate revision identified by 0018 in alembic versions",
        resolution="Run alembic stamp head to clear failed revision marker",
        error_signature="alembic.util.exc.CommandError: Can't locate revision identified by '0018'",
        environment="production",
        service_name="migrator",
        failure_category="database_migration_failed",
        log_snippet="ERROR [alembic.util.exc] Can't locate revision identified by '0018'",
        occurrence_count=5,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )

    mock_incident_2 = DeploymentIncident(
        id=UUID("0192e4a1-0000-7000-8000-000000000002"),
        workspace_id=workspace_id,
        project_id=project_id,
        fingerprint="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        summary="Socket binding error: port 8000 in use",
        probable_cause="Address already in use",
        resolution="Kill orphaned process on port 8000",
        error_signature="OSError: [Errno 98] Address already in use",
        environment="production",
        service_name="devmind-api",
        failure_category="port_binding_failed",
        log_snippet="OSError: [Errno 98] Address already in use",
        occurrence_count=1,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )

    all_incidents = [mock_incident_1, mock_incident_2]

    # Mock execute return
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = all_incidents

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = DeploymentIncidentRepository(session=mock_session)

    # 1. Test search matching
    query_text = case.get("description", "")
    target_category = case["expected_category"]

    matches = await repo.search_similar_incidents(
        ctx,
        workspace_id=workspace_id,
        project_id=project_id,
        failure_category=target_category,
        error_signature=query_text,
        limit=5,
    )

    top_1_match = False
    reciprocal_rank = 0.0

    if case.get("expected_similar_incident"):
        exp_inc = case["expected_similar_incident"]
        for rank, (inc, _score, _match_type) in enumerate(matches, start=1):
            if (
                inc.failure_category == exp_inc["failure_category"]
                and exp_inc["expected_resolution_substring"] in (inc.resolution or "")
            ):
                reciprocal_rank = 1.0 / rank
                if rank == 1:
                    top_1_match = True
                break
    else:
        top_1_match = True
        reciprocal_rank = 1.0

    # 2. Test cross-tenant isolation enforcement
    tenant_isolated = False
    try:
        await repo.search_similar_incidents(
            alien_ctx,
            workspace_id=workspace_id,
            project_id=project_id,
            failure_category=target_category,
        )
    except ForbiddenError:
        tenant_isolated = True

    return {
        "case_id": case["id"],
        "top_1_match": top_1_match,
        "reciprocal_rank": reciprocal_rank,
        "tenant_isolated": tenant_isolated,
    }


def run_deployment_benchmark(
    dataset_path: Path = DATASET_PATH,
) -> DeploymentBenchmarkSummary:
    """Execute Deployment Diagnosis benchmark across all test cases."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Benchmark dataset not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    sanitization_results: list[dict[str, Any]] = []
    classification_results: list[dict[str, Any]] = []
    env_results: list[dict[str, Any]] = []
    retrieval_results: list[dict[str, Any]] = []

    for case in cases:
        # Sanitization & Classification
        parse_eval = evaluate_sanitization_and_parser(case)
        sanitization_results.append(parse_eval)
        classification_results.append(parse_eval)

        # Env Var Analysis
        env_eval = evaluate_env_var_analysis(case, parse_eval["parsed"])
        env_results.append(env_eval)

        # Incident Retrieval
        retrieval_eval = asyncio.run(evaluate_incident_retrieval(case))
        retrieval_results.append(retrieval_eval)

    sanitization_metrics = compute_sanitization_metrics(sanitization_results)
    classification_metrics = compute_classification_metrics(classification_results)
    env_var_metrics = compute_env_var_metrics(env_results)
    retrieval_metrics = compute_retrieval_metrics(retrieval_results)

    # Composite score calculation:
    # 25% secret redaction, 25% failure classification, 15% line citation, 15% env var F1, 10% typo match, 10% incident retrieval
    composite = (
        0.25 * sanitization_metrics.secret_redaction_rate
        + 0.25 * classification_metrics.category_accuracy
        + 0.15 * classification_metrics.primary_line_accuracy
        + 0.15 * env_var_metrics.missing_f1_score
        + 0.10 * env_var_metrics.typo_match_accuracy
        + 0.10 * retrieval_metrics.top_1_accuracy
    )

    passed = (
        composite >= 0.90
        and sanitization_metrics.secret_redaction_rate >= 1.00
        and classification_metrics.category_accuracy >= 0.90
        and env_var_metrics.missing_f1_score >= 0.90
        and retrieval_metrics.tenant_isolation_rate >= 1.00
    )

    status = "passed" if passed else "failed"
    git_commit = get_git_commit_hash()
    timestamp = datetime.now(UTC).isoformat()

    return DeploymentBenchmarkSummary(
        benchmark=data.get("benchmark", "devmind-deployment-diagnosis-eval-v1"),
        git_commit=git_commit,
        timestamp=timestamp,
        sanitization_metrics=sanitization_metrics,
        classification_metrics=classification_metrics,
        env_var_metrics=env_var_metrics,
        retrieval_metrics=retrieval_metrics,
        composite_score=round(composite, 4),
        status=status,
    )


def save_benchmark_results(summary: DeploymentBenchmarkSummary) -> tuple[Path, Path]:
    """Persist benchmark results to evals/results/deployment/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts_slug = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_file = RESULTS_DIR / f"{ts_slug}_{summary.git_commit}.json"
    latest_file = RESULTS_DIR / "latest.json"

    data = summary.to_dict()
    payload = json.dumps(data, indent=2) + "\n"

    with open(run_file, "w", encoding="utf-8") as f:
        f.write(payload)

    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(payload)

    return run_file, latest_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Deployment Diagnosis Evaluation Benchmark Runner")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Path to dataset.json",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=True,
        help="Persist benchmark results",
    )
    args = parser.parse_args()

    summary = run_deployment_benchmark(dataset_path=args.dataset)
    print(
        f"Deployment Diagnosis Benchmark: {summary.status.upper()} (Composite Score: {summary.composite_score:.2%})"
    )
    print(
        f"  Sanitization:   Redaction Rate={summary.sanitization_metrics.secret_redaction_rate:.2%}, "
        f"ANSI Strip={summary.sanitization_metrics.ansi_strip_rate:.2%}"
    )
    print(
        f"  Classification: Category Acc={summary.classification_metrics.category_accuracy:.2%}, "
        f"Line Acc={summary.classification_metrics.primary_line_accuracy:.2%}, "
        f"Truncated Acc={summary.classification_metrics.insufficient_log_accuracy:.2%}"
    )
    print(
        f"  Env Checker:    Missing F1={summary.env_var_metrics.missing_f1_score:.2%}, "
        f"Typo Acc={summary.env_var_metrics.typo_match_accuracy:.2%}"
    )
    print(
        f"  Past Incidents: Top-1 Acc={summary.retrieval_metrics.top_1_accuracy:.2%}, "
        f"MRR={summary.retrieval_metrics.mean_reciprocal_rank:.4f}, "
        f"Tenant Isolation={summary.retrieval_metrics.tenant_isolation_rate:.2%}"
    )

    if args.save:
        _, latest = save_benchmark_results(summary)
        print(f"  Persisted results to {latest}")

    if summary.status != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()
