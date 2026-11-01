"""Unit tests for Environment Variable Name Checker (docs/01 CAP-07, docs/07 §6)."""

from __future__ import annotations

from app.analysis.env_checker import EnvVarChecker, EnvVarCheckResult


def test_env_var_checker_parse_env_example() -> None:
    """Verify parsing variable names from .env.example with comments and export prefixes."""
    content = """
# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0

# Authentication (Clerk)
export CLERK_SECRET_KEY=mock_clerk_sec_12345
CLERK_PUBLISHABLE_KEY=mock_clerk_pub_12345

# Feature Flags
ENABLE_ANALYTICS=true
DEBUG

# Trailing comments
DEVMIND_RUN_MODE=all # mode of operation
"""
    names = EnvVarChecker.parse_env_example(content)

    assert "DATABASE_URL" in names
    assert "REDIS_URL" in names
    assert "CLERK_SECRET_KEY" in names
    assert "CLERK_PUBLISHABLE_KEY" in names
    assert "ENABLE_ANALYTICS" in names
    assert "DEBUG" in names
    assert "DEVMIND_RUN_MODE" in names

    # Values must not be parsed or included as keys
    assert "true" not in names
    assert "postgresql" not in names
    assert len(names) == 7


def test_env_var_checker_detects_missing_configured_variables() -> None:
    """Verify detecting referenced variables missing from deployment environment configuration."""
    referenced = ["DATABASE_URL", "CLERK_SECRET_KEY", "DEVMIND_LLM_KEY"]
    configured = ["DATABASE_URL", "PORT"]

    res: EnvVarCheckResult = EnvVarChecker.verify_environment_variables(
        referenced_names=referenced,
        configured_names=configured,
    )

    assert res.has_issues is True
    assert "CLERK_SECRET_KEY" in res.referenced_missing
    assert "DEVMIND_LLM_KEY" in res.referenced_missing
    assert "DATABASE_URL" in res.valid_configured
    assert "DATABASE_URL" not in res.referenced_missing


def test_env_var_checker_detects_suspected_typos_and_casing() -> None:
    """Verify detecting suspected typos, prefix variations, and casing mismatches."""
    referenced = ["DATABASE_URL", "CLERK_API_KEY"]
    configured = ["database_url", "CLERK_SECRET_KEY", "PORT"]

    res = EnvVarChecker.verify_environment_variables(
        referenced_names=referenced,
        configured_names=configured,
    )

    assert res.has_issues is True
    # Casing mismatch detection for database_url
    typo_targets = {t.expected_name: t.found_name for t in res.suspected_typos}
    assert typo_targets.get("DATABASE_URL") == "database_url"
    # Similar key detection for CLERK_API_KEY vs CLERK_SECRET_KEY
    assert any(
        t.expected_name == "CLERK_API_KEY" and t.found_name == "CLERK_SECRET_KEY"
        for t in res.suspected_typos
    )


def test_env_var_checker_cross_checks_against_example_template() -> None:
    """Verify detecting missing required keys defined in .env.example when configured list is provided."""
    example_content = """
DATABASE_URL=
REDIS_URL=
SESSION_SECRET=
"""
    configured = ["DATABASE_URL"]

    res = EnvVarChecker.verify_environment_variables(
        referenced_names=["DATABASE_URL"],
        configured_names=configured,
        example_env_content=example_content,
    )

    assert res.has_issues is True
    assert "REDIS_URL" in res.missing_required
    assert "SESSION_SECRET" in res.missing_required
    assert "DATABASE_URL" not in res.missing_required


def test_env_var_checker_clean_configuration() -> None:
    """Verify that fully matching configuration reports no issues."""
    referenced = ["DATABASE_URL", "REDIS_URL"]
    configured = ["DATABASE_URL", "REDIS_URL", "PORT"]

    res = EnvVarChecker.verify_environment_variables(
        referenced_names=referenced,
        configured_names=configured,
        example_env_content="DATABASE_URL=\nREDIS_URL=\n",
    )

    assert res.has_issues is False
    assert len(res.missing_required) == 0
    assert len(res.referenced_missing) == 0
    assert len(res.suspected_typos) == 0
    assert set(res.valid_configured) == {"DATABASE_URL", "REDIS_URL"}
