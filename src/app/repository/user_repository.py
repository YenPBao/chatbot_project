from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.user import User
from app.model.role import Role
from app.utils.tbconstants import ROLE


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        res = await self.db.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        res = await self.db.execute(select(User).where(User.username == username))
        return res.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        res = await self.db.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    async def exists_username(self, username: str) -> bool:
        stmt = select(select(User.id).where(User.username == username).exists())
        return bool((await self.db.execute(stmt)).scalar())

    async def exists_email(self, email: str) -> bool:
        stmt = select(select(User.id).where(User.email == email).exists())
        return bool((await self.db.execute(stmt)).scalar())

    async def create_basic_user(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        user = User(
            username=username.strip(),
            email=email.lower().strip(),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            password_hash=password_hash,
        )

        if hasattr(user, "roles"):
            res = await self.db.execute(
                select(Role).where(Role.name == ROLE.USER.value)
            )
            role = res.scalar_one_or_none()
            if role:
                user.roles.append(role)

        self.db.add(user)
        await self.db.flush()
        return user

    async def update_user(
        self,
        user_id: int,
        *,
        username: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_active: bool | None = None,
        password_hash: str | None = None,
    ) -> Optional[User]:
        user = await self.db.get(User, user_id)
        if not user:
            return None

        if username is not None:
            user.username = username.strip()
        if email is not None:
            user.email = email.lower().strip()
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if is_active is not None:
            user.is_active = is_active
        if password_hash is not None:
            user.password_hash = password_hash

        await self.db.flush()
        return user

    async def delete_user(self, user_id: int) -> bool:
        user = await self.db.get(User, user_id)
        if not user:
            return False
        await self.db.delete(user)
        await self.db.flush()
        return True
