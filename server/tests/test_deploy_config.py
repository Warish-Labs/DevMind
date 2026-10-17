"""Tests validating deployment configuration and Render Blueprint."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_render_blueprint_structure() -> None:
    """Verify that render.yaml satisfies free tier constraints and has no hardcoded secrets."""
    render_file = REPO_ROOT / "render.yaml"
    assert render_file.exists(), "render.yaml must exist at repository root"

    with render_file.open("r", encoding="utf-8") as f:
        blueprint = yaml.safe_load(f)

    services = blueprint.get("services", [])
    assert len(services) >= 1, "render.yaml must define web service"

    # Find web service
    web_services = [
        s for s in services if s.get("type") == "web" and s.get("name") == "devmind-api"
    ]
    assert len(web_services) == 1, "Must define web service devmind-api"
    api = web_services[0]
    assert api.get("plan") == "free", "API service must use free plan (ADR-046)"
    assert api.get("runtime") == "docker", "API must use docker runtime"
    assert api.get("dockerfilePath") == "server/Dockerfile"
    assert api.get("healthCheckPath") == "/healthz"

    # Verify no plaintext secrets in envVars
    env_vars = api.get("envVars", [])
    env_dict = {item.get("key"): item for item in env_vars}
    sensitive_keys = [
        "DEVMIND_DATABASE_URL",
        "DEVMIND_DATABASE_URL_DIRECT",
        "DEVMIND_REDIS_URL",
        "CLERK_SECRET_KEY",
        "CLERK_PUBLISHABLE_KEY",
        "CLERK_WEBHOOK_SECRET",
        "DEVMIND_ENCRYPTION_KEYS",
        "DEVMIND_EXT_TOKEN_PEPPER",
        "DEVMIND_TURNSTILE_SECRET_KEY",
        "DEVMIND_GITHUB_CLIENT_ID",
        "DEVMIND_GITHUB_CLIENT_SECRET",
        "DEVMIND_GITHUB_WEBHOOK_SECRET",
        "DEVMIND_LLM_PRIMARY_API_KEY",
        "DEVMIND_EMBED_API_KEY",
    ]
    for key in sensitive_keys:
        if key in env_dict:
            assert env_dict[key].get("sync") is False, (
                f"Sensitive env var {key} must have sync: false"
            )
            assert "value" not in env_dict[key], (
                f"Sensitive env var {key} must not have plaintext value"
            )


def test_deployment_runbook_exists() -> None:
    """Verify deploy-render-vercel.md exists."""
    runbook = REPO_ROOT / "docs" / "runbooks" / "deploy-render-vercel.md"
    assert runbook.exists(), "docs/runbooks/deploy-render-vercel.md must exist"


def test_free_quotas_configuration() -> None:
    """Verify server/configs/quotas.free.yaml satisfies free-tier ceilings (ADR-046)."""
    quotas_file = REPO_ROOT / "server" / "configs" / "quotas.free.yaml"
    assert quotas_file.exists(), "server/configs/quotas.free.yaml must exist"

    with quotas_file.open("r", encoding="utf-8") as f:
        quotas = yaml.safe_load(f)

    assert quotas["profile"] == "free"
    storage = quotas["storage"]
    assert storage["database_storage_cap_bytes"] <= 536870912  # 512 MB Neon Free limit
    assert (
        storage["max_chunks_per_project"] * storage["bytes_per_chunk"]["total_estimated_per_chunk"]
        <= storage["chunk_storage_budget_bytes"]
    )

    memory = quotas["memory"]
    assert memory["container_ram_cap_bytes"] <= 536870912  # 512 MB Render Free limit
    assert memory["worker_concurrency"] == 1  # Solo pool concurrency 1
    assert memory["measured_idle_memory_bytes"] < memory["container_ram_cap_bytes"]
