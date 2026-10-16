"""User domain service implementing user profile retrieval and management."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.persistence.models.user import User
from app.persistence.repositories.user_repo import UserRepository


class UserService:
    """Domain service managing user identity records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def get_user_by_id(
        self,
        ctx: AuthContext | SystemContext,
        user_id: UUID,
    ) -> User:
        """Find user by ID or raise NotFoundError."""
        user = await self.repo.get_by_id(ctx, user_id)
        if user is None:
            raise NotFoundError(detail=f"User '{user_id}' not found")
        return user
