"""Tests validating unified launcher, free profile, advisory lock, and startup sweep."""

from unittest.mock import MagicMock, patch

import redis

from app.core.lifecycle import (
    MIGRATION_ADVISORY_LOCK_KEY,
    run_migrations_with_advisory_lock,
    run_startup_sweep,
)
from app.core.settings import Settings
from app.launcher import launch
from app.workers.celery_app import create_celery_app


def test_celery_app_prefix_isolation() -> None:
    """Verify that Celery broker and queues respect DEVMIND_REDIS_KEY_PREFIX."""
    settings = Settings(
        redis_key_prefix="devmind_test:",
        redis_url="redis://localhost:6379/1",
    )
    app = create_celery_app(settings)

    assert app.conf.broker_url == "redis://localhost:6379/1"
    assert app.conf.broker_transport_options["global_keyprefix"] == "devmind_test:"
    assert app.conf.result_backend_transport_options["global_keyprefix"] == "devmind_test:"
    assert app.conf.task_default_queue == "devmind_test:default"
    assert app.conf.task_acks_late is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.timezone == "UTC"


def test_advisory_lock_migration_baseline() -> None:
    """Verify pre-M2 baseline migration check under advisory lock."""
    settings = Settings()
    result = run_migrations_with_advisory_lock(settings)
    assert result is True


def test_advisory_lock_contention_handling() -> None:
    """Verify that migration check handles lock contention when another instance holds lock."""
    settings = Settings()
    lock_acquirer = MagicMock(return_value=False)
    migration_runner = MagicMock()
    lock_releaser = MagicMock()

    result = run_migrations_with_advisory_lock(
        settings,
        migration_runner=migration_runner,
        lock_acquirer=lock_acquirer,
        lock_releaser=lock_releaser,
    )

    assert result is False
    lock_acquirer.assert_called_once_with(MIGRATION_ADVISORY_LOCK_KEY)
    migration_runner.assert_not_called()
    lock_releaser.assert_not_called()


def test_advisory_lock_successful_execution() -> None:
    """Verify advisory lock acquisition, runner execution, and release."""
    settings = Settings()
    lock_acquirer = MagicMock(return_value=True)
    migration_runner = MagicMock(return_value=True)
    lock_releaser = MagicMock(return_value=True)

    result = run_migrations_with_advisory_lock(
        settings,
        migration_runner=migration_runner,
        lock_acquirer=lock_acquirer,
        lock_releaser=lock_releaser,
    )

    assert result is True
    lock_acquirer.assert_called_once_with(MIGRATION_ADVISORY_LOCK_KEY)
    migration_runner.assert_called_once()
    lock_releaser.assert_called_once_with(MIGRATION_ADVISORY_LOCK_KEY)


def test_startup_sweep_cleans_stale_keys() -> None:
    """Verify startup sweep scans prefix and purges stale lock keys."""
    settings = Settings(redis_key_prefix="dm_sweep:")

    mock_client = MagicMock()
    mock_client.scan_iter.return_value = [
        "dm_sweep:celery_task_1",
        "dm_sweep:lock:project_123",
        "dm_sweep:tmp:buffer_456",
    ]
    # lock key has no TTL (survived crash), tmp key has no TTL
    mock_client.ttl.side_effect = lambda k: -1 if ":lock:" in k or ":tmp:" in k else 300

    with patch("redis.Redis.from_url", return_value=mock_client):
        res = run_startup_sweep(settings)

    assert res["status"] == "ok"
    assert res["key_prefix"] == "dm_sweep:"
    assert res["total_keys"] == 3
    assert res["swept_keys"] == 2
    mock_client.delete.assert_any_call("dm_sweep:lock:project_123")
    mock_client.delete.assert_any_call("dm_sweep:tmp:buffer_456")


def test_startup_sweep_degraded_when_redis_offline() -> None:
    """Verify startup sweep handles Redis unavailability gracefully without raising."""
    settings = Settings(redis_key_prefix="dm:")

    with patch("redis.Redis.from_url", side_effect=redis.exceptions.ConnectionError("Offline")):
        res = run_startup_sweep(settings)

    assert res["status"] == "degraded"
    assert res["key_prefix"] == "dm:"
    assert "Offline" in res["reason"]
    assert res["swept_keys"] == 0


def test_launcher_dispatch_api() -> None:
    """Verify launcher dispatches to API server runner."""
    settings = Settings(run_mode="api")
    runner = MagicMock()

    code = launch(settings, server_runner=runner)
    assert code == 0
    runner.assert_called_once()


def test_launcher_dispatch_worker() -> None:
    """Verify launcher dispatches to Celery worker process runner."""
    settings = Settings(run_mode="worker")
    runner = MagicMock()

    code = launch(settings, proc_runner=runner)
    assert code == 0
    runner.assert_called_once()
    cmd = runner.call_args[0][0]
    assert "celery" in cmd
    assert "worker" in cmd


def test_launcher_dispatch_scheduler() -> None:
    """Verify launcher dispatches to Celery scheduler process runner."""
    settings = Settings(run_mode="scheduler")
    runner = MagicMock()

    code = launch(settings, proc_runner=runner)
    assert code == 0
    runner.assert_called_once()
    cmd = runner.call_args[0][0]
    assert "celery" in cmd
    assert "beat" in cmd


def test_launcher_dispatch_all_free_profile() -> None:
    """Verify launcher starts embedded Celery worker with beat and solo pool in free profile."""
    settings = Settings(run_mode="all")
    server_runner = MagicMock()
    celery_launcher = MagicMock()
    mock_proc = MagicMock()
    celery_launcher.return_value = mock_proc

    code = launch(
        settings,
        server_runner=server_runner,
        celery_launcher=celery_launcher,
    )
    assert code == 0
    server_runner.assert_called_once()
    celery_launcher.assert_called_once()

    celery_cmd = celery_launcher.call_args[0][0]
    assert "celery" in celery_cmd
    assert "worker" in celery_cmd
    assert "--beat" in celery_cmd
    assert "--pool=solo" in celery_cmd
    assert "--concurrency=1" in celery_cmd
    mock_proc.terminate.assert_called_once()


def test_launcher_invalid_mode() -> None:
    """Verify launcher returns error code on unknown mode."""
    settings = MagicMock(spec=Settings)
    settings.run_mode = "invalid_mode"
    settings.env = "local"
    settings.log_level = "INFO"
    settings.redis_key_prefix = "dm:"
    settings.redis_url = "redis://localhost:6379/0"
    settings.database_url = "postgresql://localhost/devmind"

    code = launch(settings)
    assert code == 1
