
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.user import User
from app.security.password import PasswordHandler
from app.model.role import Role
from app.dto.user import UserOut        
from app.utils.tbconstants import ROLE
from app.core.redis_client import rds

logger = logging.getLogger(__name__)
handle = PasswordHandler()


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def cache_user(self, user: User) -> None:
        # ORM -> UserOut
        dto = UserOut.model_validate(user, from_attributes=True)
        user_key = f"user:{dto.id}"
        username_key = f"user:username:{dto.username}"
        email_key = f"user:email:{dto.email}"
        # Lưu JSON của UserOut
        await rds.set(user_key, dto.model_dump_json(), ex=3600)
        await rds.set(username_key, str(dto.id), ex=3600)
        await rds.set(email_key, str(dto.id), ex=3600)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        # 1. Thử cache
        cache_key = f"user:{user_id}"
        cached = await rds.get(cache_key)
        if cached is None:
            return None

        # JSON -> UserOut
        dto = UserOut.model_validate_json(cached)
        user = User(**dto.model_dump())
        if user is not None:
            return user

        res = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user: Optional[User] = res.scalar_one_or_none()

        if user is not None:
            await self.cache_user(user)
        return user

    async def get_by_username(self, username: str) -> Optional[User]:
        username_key = f"user:username:{username}"
        user_id_str = await rds.get(username_key)
        if user_id_str is not None:
            try:
                user_id = int(user_id_str)
                return await self.get_by_id(user_id)
            except ValueError:
                pass  

        res = await self.db.execute(
            select(User).where(User.username == username)
        )
        user: Optional[User] = res.scalar_one_or_none()

        if user is not None:
            await self.cache_user(user)

        return user

    async def get_by_email(self, email: str) -> Optional[User]:
        email_key = f"user:email:{email}"

        user_id_str = await rds.get(email_key)
        if user_id_str is not None:
            try:
                user_id = int(user_id_str)
                return await self.get_by_id(user_id)
            except ValueError:
                pass

        res = await self.db.execute(
            select(User).where(User.email == email)
        )
        user: Optional[User] = res.scalar_one_or_none()

        if user is not None:
            await self._cache_user(user)

        return user

    async def exists_username(self, username: str) -> bool:
        username_key = f"user:username:{username}"
        if await rds.get(username_key) is not None:
            return True

        res = await self.db.execute(
            select(func.exists(select(User.id).where(User.username == username)))
        )
        exists = bool(res.scalar())
        if exists:
            await self.get_by_username(username)
        return exists

    async def exists_email(self, email: str) -> bool:
        email_key = f"user:email:{email}"
        if await rds.get(email_key) is not None:
            return True

        res = await self.db.execute(
            select(func.exists(select(User.id).where(User.email == email)))
        )
        exists = bool(res.scalar())
        if exists:
            await self.get_by_email(email)
        return exists
    
    async def create_basic_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        user = User(
            username=username.strip(),
            email=email.lower().strip(),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            password_hash=handle.hash_password(password),
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

        await self.cache_user(user)
        return user

   
    async def authenticate(self, username: str, password: str) -> Optional[User]:
        res = await self.db.execute(
            select(User).where(User.username == username)
        )
        user: Optional[User] = res.scalar_one_or_none()

        if not user:
            logger.info("authenticate: user not found username=%s", username)
            return None
        if not user.is_active:
            logger.info("authenticate: user inactive username=%s", username)
            return None

        ok = handle.verify_password(password, user.password_hash)
        logger.info("authenticate: verify result for username=%s -> %s", username, ok)
        if not ok:
            return None
        await self.cache_user(user)
        return user
