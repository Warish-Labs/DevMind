"""Tests verifying LLM Gateway configuration loaders, Pydantic schemas, and startup validation (docs/05 §11, M6-03)."""

from pathlib import Path

import pytest

from app.llm.config import (
    ConfigValidationError,
    GatewayConfig,
    ModelCapabilitiesConfig,
    ModelEntry,
    ModelsConfig,
    ProviderDataPolicyConfig,
    ProviderEntry,
    ProvidersConfig,
    TaskDataConfig,
    TaskEntry,
    TasksConfig,
    load_gateway_config,
    validate_gateway_config,
)


def _make_minimal_valid_config() -> GatewayConfig:
    """Helper creating a minimal valid GatewayConfig in memory."""
    providers = ProvidersConfig(
        providers={
            "mock_prov": ProviderEntry(
                adapter="fake",
                enabled=True,
                terms_reviewed=True,
                data_policy=ProviderDataPolicyConfig(source_code_allowed=True),
            )
        }
    )
    models = ModelsConfig(
        models={
            "mock_model": ModelEntry(
                provider="mock_prov",
                model_id="mock-v1",
                capabilities=ModelCapabilitiesConfig(
                    tool_calling=True,
                    structured_output="native",
                    streaming=True,
                ),
            )
        }
    )
    tasks = TasksConfig(
        tasks={
            "mock_task": TaskEntry(
                model="mock_model",
                fallbacks=[],
                required_capabilities=["structured_output"],
                data=TaskDataConfig(may_contain_source=True),
            )
        }
    )
    return GatewayConfig(
        providers=providers,
        models=models,
        tasks=tasks,
        config_hash="testhash12345",
    )


def test_load_default_gateway_config() -> None:
    """Verify loading and validating the actual repository configs in server/configs/llm/."""
    cfg = load_gateway_config(environment="development")
    assert cfg.providers.version == 1
    assert "fake_provider" in cfg.providers.providers
    assert "primary_provider" in cfg.providers.providers
    assert "test_model" in cfg.models.models
    assert "code_answer" in cfg.tasks.tasks
    assert len(cfg.config_hash) == 64  # SHA-256 hex string


def test_missing_config_files_raises() -> None:
    """Verify error raised when config directory does not exist or lacks files."""
    with pytest.raises(ConfigValidationError) as exc_info:
        load_gateway_config(config_dir=Path("/non_existent_dir_12345"))
    assert "missing" in str(exc_info.value).lower()


def test_referential_integrity_model_missing_provider() -> None:
    """Verify error raised when a model references a missing provider."""
    cfg = _make_minimal_valid_config()
    cfg.models.models["broken_model"] = ModelEntry(
        provider="missing_provider_xyz",
        model_id="xyz",
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="development")
    assert "non-existent provider 'missing_provider_xyz'" in str(exc_info.value)


def test_referential_integrity_task_missing_model() -> None:
    """Verify error raised when a task references a missing model."""
    cfg = _make_minimal_valid_config()
    cfg.tasks.tasks["broken_task"] = TaskEntry(
        model="non_existent_model_xyz",
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="development")
    assert "non-existent primary model 'non_existent_model_xyz'" in str(exc_info.value)


def test_referential_integrity_task_missing_fallback() -> None:
    """Verify error raised when a task references a missing fallback model."""
    cfg = _make_minimal_valid_config()
    cfg.tasks.tasks["task_with_bad_fallback"] = TaskEntry(
        model="mock_model",
        fallbacks=["missing_fallback_model"],
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="development")
    assert "non-existent fallback model 'missing_fallback_model'" in str(exc_info.value)


def test_capability_check_missing_tool_calling() -> None:
    """Verify error raised when model lacks required tool_calling capability."""
    cfg = _make_minimal_valid_config()
    cfg.models.models["no_tool_model"] = ModelEntry(
        provider="mock_prov",
        model_id="no-tools",
        capabilities=ModelCapabilitiesConfig(tool_calling=False, structured_output="native"),
    )
    cfg.tasks.tasks["tool_task"] = TaskEntry(
        model="no_tool_model",
        required_capabilities=["tool_calling"],
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="development")
    assert "requires capability 'tool_calling'" in str(exc_info.value)


def test_capability_check_missing_structured_output() -> None:
    """Verify error raised when model lacks required structured_output capability."""
    cfg = _make_minimal_valid_config()
    cfg.models.models["no_struct_model"] = ModelEntry(
        provider="mock_prov",
        model_id="no-struct",
        capabilities=ModelCapabilitiesConfig(structured_output="none"),
    )
    cfg.tasks.tasks["struct_task"] = TaskEntry(
        model="no_struct_model",
        required_capabilities=["structured_output"],
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="development")
    assert "requires capability 'structured_output'" in str(exc_info.value)


def test_data_policy_source_code_disallowed() -> None:
    """Verify error raised when task with source code maps to provider where source_code_allowed=False."""
    cfg = _make_minimal_valid_config()
    cfg.providers.providers["private_prov"] = ProviderEntry(
        adapter="openai",
        data_policy=ProviderDataPolicyConfig(source_code_allowed=False),
    )
    cfg.models.models["private_model"] = ModelEntry(
        provider="private_prov",
        model_id="priv-v1",
        capabilities=ModelCapabilitiesConfig(streaming=True),
    )
    cfg.tasks.tasks["source_task"] = TaskEntry(
        model="private_model",
        data=TaskDataConfig(may_contain_source=True),
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="production")
    assert "source_code_allowed=False" in str(exc_info.value)


def test_production_environment_rejects_placeholder_url() -> None:
    """Verify production rejects placeholder hostnames like .invalid."""
    cfg = _make_minimal_valid_config()
    cfg.providers.providers["prod_prov"] = ProviderEntry(
        adapter="openai_compatible",
        base_url="https://api.provider.invalid/v1",
        enabled=True,
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="production")
    assert "Placeholder hostname '.invalid'" in str(exc_info.value)


def test_production_environment_rejects_placeholder_model_id() -> None:
    """Verify production rejects REPLACE_* placeholder model IDs for active tasks."""
    cfg = _make_minimal_valid_config()
    cfg.models.models["mock_model"].model_id = "REPLACE_WITH_EVALUATED_MODEL_ID"
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="production")
    assert "Placeholder model_id" in str(exc_info.value)


def test_production_environment_requires_terms_reviewed() -> None:
    """Verify production requires terms_reviewed=True for source code tasks."""
    cfg = _make_minimal_valid_config()
    cfg.providers.providers["mock_prov"].terms_reviewed = False
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_gateway_config(cfg, environment="production")
    assert "requires terms_reviewed=True" in str(exc_info.value)
