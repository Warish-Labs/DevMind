"""Persistence repositories enforcing tenant isolation via AuthContext."""

from app.persistence.repositories.audit_repo import AuditEventRepository
from app.persistence.repositories.base import BaseRepository
from app.persistence.repositories.brain_repo import BrainRepository
from app.persistence.repositories.bug_record_repo import BugRecordRepository
from app.persistence.repositories.consent_repo import ConsentRepository
from app.persistence.repositories.extension_repo import ExtensionRepository
from app.persistence.repositories.github_repo import GitHubRepository
from app.persistence.repositories.incident_repo import DeploymentIncidentRepository
from app.persistence.repositories.living_doc_repo import LivingDocRepository
from app.persistence.repositories.project_eval_repo import ProjectEvaluationRepository
from app.persistence.repositories.project_repo import ProjectRepository
from app.persistence.repositories.project_task_repo import ProjectTaskRepository
from app.persistence.repositories.retention_repo import RetentionRepository
from app.persistence.repositories.usage_repo import (
    UsageRecordRepository,
    create_database_usage_sink,
)
from app.persistence.repositories.user_repo import UserRepository
from app.persistence.repositories.workspace_repo import WorkspaceRepository

__all__ = [
    "AuditEventRepository",
    "BaseRepository",
    "BrainRepository",
    "BugRecordRepository",
    "ConsentRepository",
    "DeploymentIncidentRepository",
    "ExtensionRepository",
    "GitHubRepository",
    "LivingDocRepository",
    "ProjectEvaluationRepository",
    "ProjectRepository",
    "ProjectTaskRepository",
    "RetentionRepository",
    "UsageRecordRepository",
    "create_database_usage_sink",
    "UserRepository",
    "WorkspaceRepository",
]
