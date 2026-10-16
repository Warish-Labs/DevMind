"""Base repository with mandatory AuthContext/SystemContext validation (docs/03 §4)."""

from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext

T = TypeVar("T")


class BaseRepository:
    """Base class for all persistence repositories.

    Enforces that every data access operation is passed an explicit AuthContext
    or SystemContext, preventing cross-tenant leakage and unauthorized access.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _validate_context(ctx: AuthContext | SystemContext) -> None:
        """Validate that the context is a legitimate AuthContext or SystemContext."""
        if not isinstance(ctx, (AuthContext, SystemContext)):
            raise TypeError(
                "Repository operations require an AuthContext or SystemContext; "
                f"received {type(ctx).__name__}"
            )

    @classmethod
    def _scope_workspace_query(
        cls,
        stmt: Select[tuple[T]],
        model_workspace_col: object,
        ctx: AuthContext | SystemContext,
        target_workspace_id: UUID | None = None,
    ) -> Select[tuple[T]]:
        """Apply workspace isolation predicate to query.

        - If AuthContext: strictly constrains to ctx.workspace_id.
        - If target_workspace_id is provided and differs from ctx.workspace_id,
          access is denied (empty query).
        - If SystemContext: uses target_workspace_id or ctx.workspace_id if specified.
        """
        cls._validate_context(ctx)

        if isinstance(ctx, AuthContext):
            if target_workspace_id is not None and target_workspace_id != ctx.workspace_id:
                # Caller requested a different workspace than their authenticated context
                # Constrain to an impossible match to return empty result
                return stmt.where(
                    model_workspace_col == UUID("00000000-0000-0000-0000-000000000000")
                )
            return stmt.where(model_workspace_col == ctx.workspace_id)

        # SystemContext
        ws_id = target_workspace_id or ctx.workspace_id
        if ws_id is not None:
            return stmt.where(model_workspace_col == ws_id)
        return stmt
