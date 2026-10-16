"""User repository for identity mapping and user record operations (docs/03 §3.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.user import User
from app.persistence.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Repository handling User persistence and identity lookup."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        user_id: UUID,
        include_deleted: bool = False,
    ) -> User | None:
        """Find user by UUID identifier."""
        self._validate_context(ctx)
        stmt = select(User).where(User.id == user_id)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_clerk_user_id(
        self,
        ctx: AuthContext | SystemContext,
        clerk_user_id: str,
        include_deleted: bool = False,
    ) -> User | None:
        """Find user by external Clerk user ID."""
        self._validate_context(ctx)
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email(
        self,
        ctx: AuthContext | SystemContext,
        email: str,
        include_deleted: bool = False,
    ) -> User | None:
        """Find user by email address."""
        self._validate_context(ctx)
        stmt = select(User).where(User.email == email)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(
        self,
        ctx: AuthContext | SystemContext,
        *,
        clerk_user_id: str,
        email: str,
        display_name: str | None = None,
    ) -> User:
        """Create a new user record."""
        self._validate_context(ctx)
        user = User(
            clerk_user_id=clerk_user_id,
            email=email,
            display_name=display_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_last_seen(
        self,
        ctx: AuthContext | SystemContext,
        user_id: UUID,
    ) -> None:
        """Update last_seen_at timestamp for a user."""
        self._validate_context(ctx)
        user = await self.get_by_id(ctx, user_id)
        if user:
            user.last_seen_at = datetime.now(UTC)
            await self.session.flush()

    async def soft_delete(
        self,
        ctx: AuthContext | SystemContext,
        user_id: UUID,
    ) -> None:
        """Soft delete a user record by stamping deleted_at."""
        self._validate_context(ctx)
        user = await self.get_by_id(ctx, user_id)
        if user:
            user.deleted_at = datetime.now(UTC)
            await self.session.flush()
