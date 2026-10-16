"""Tests validating Dockerfile and docker-compose configurations."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_dockerfile_multi_stage_and_non_root() -> None:
    """Assert server/Dockerfile uses multi-stage build and non-root execution."""
    dockerfile_path = REPO_ROOT / "server" / "Dockerfile"
    assert dockerfile_path.exists(), "server/Dockerfile must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "AS builder" in content, "Dockerfile must define builder stage"
    assert "AS runtime" in content, "Dockerfile must define runtime stage"
    assert "useradd" in content and "appuser" in content, "Dockerfile must create appuser"
    assert "USER appuser" in content, "Dockerfile must switch to non-root USER appuser"
    assert "HEALTHCHECK" in content, "Dockerfile must define HEALTHCHECK probe"


def test_docker_compose_services() -> None:
    """Assert infra/docker-compose.yml defines all required services with healthchecks."""
    compose_path = REPO_ROOT / "infra" / "docker-compose.yml"
    assert compose_path.exists(), "infra/docker-compose.yml must exist"

    with compose_path.open("r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})
    required_services = {"postgres", "redis", "api", "worker", "scheduler"}
    assert required_services.issubset(set(services.keys())), (
        f"Missing services: {required_services - set(services.keys())}"
    )

    # Verify postgres uses pgvector
    postgres = services["postgres"]
    assert "pgvector" in postgres.get("image", ""), "Postgres must use pgvector image"
    assert "healthcheck" in postgres, "Postgres must define healthcheck"

    # Verify redis/valkey
    redis = services["redis"]
    assert "redis" in redis.get("image", "") or "valkey" in redis.get("image", ""), (
        "Redis service must use redis or valkey image"
    )
    assert "healthcheck" in redis, "Redis must define healthcheck"

    # Verify API service depends on healthy DB and Redis
    api = services["api"]
    depends_on = api.get("depends_on", {})
    assert "postgres" in depends_on and "redis" in depends_on
    assert depends_on["postgres"]["condition"] == "service_healthy"
    assert depends_on["redis"]["condition"] == "service_healthy"
