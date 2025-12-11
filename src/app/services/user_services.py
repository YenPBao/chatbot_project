from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import rds
from app.dto.user import UserLogin, UserRegister, UserOut
from app.model.user import User
from app.repository.user_repository import UserRepository
from app.security.password import PasswordHandler
from fastapi import HTTPException


class UserService:
    def __init__(
        self,
        db: AsyncSession,
        pwd_handler: Optional[PasswordHandler] = None,
    ):
        self.db = db
        self.repo = UserRepository(db)
        self.pwd_handler = pwd_handler or PasswordHandler()

    def _decode(self, v):
        return v.decode() if isinstance(v, (bytes, bytearray)) else v

    def _extract_role(self, user: User) -> str | None:
        role = getattr(user, "role", None)
        if role:
            return str(role)
        roles = getattr(user, "roles", None)
        if roles:
            r0 = roles[0]
            return getattr(r0, "name", str(r0))
        return None

    async def cache_user(self, user: User, *, ttl: int = 3600) -> None:
        dto = UserOut.model_validate(user, from_attributes=True)

        user_key = f"user:{dto.id}"
        username_key = f"user:username:{dto.username}"
        email_key = f"user:email:{dto.email}"

        await rds.set(user_key, dto.model_dump_json(), ex=ttl)
        await rds.set(username_key, str(dto.id), ex=ttl)
        await rds.set(email_key, str(dto.id), ex=ttl)

    async def get_user_by_id_cached(self, user_id: int) -> Optional[User]:
        cache_key = f"user:{user_id}"
        cached = await rds.get(cache_key)
        if cached:
            dto = UserOut.model_validate_json(self._decode(cached))
            return User(**dto.model_dump())

        user = await self.repo.get_by_id(user_id)
        if user:
            await self.cache_user(user)
        return user

    async def get_user_by_username_cached(self, username: str) -> Optional[User]:
        username_key = f"user:username:{username}"
        user_id_str = await rds.get(username_key)
        if user_id_str:
            try:
                user_id = int(self._decode(user_id_str))
                return await self.get_user_by_id_cached(user_id)
            except ValueError:
                pass

        user = await self.repo.get_by_username(username)
        if user:
            await self.cache_user(user)
        return user

    async def get_user_by_email_cached(self, email: str) -> Optional[User]:
        email_key = f"user:email:{email}"
        user_id_str = await rds.get(email_key)
        if user_id_str:
            try:
                user_id = int(self._decode(user_id_str))
                return await self.get_user_by_id_cached(user_id)
            except ValueError:
                pass

        user = await self.repo.get_by_email(email)
        if user:
            await self.cache_user(user)
        return user

    async def authenticate_user(self, login_data: UserLogin) -> Optional[User]:
        user = await self.repo.get_by_username(login_data.username)
        if not user or not user.is_active:
            return None

        if not self.pwd_handler.verify_password(
            login_data.password, user.password_hash
        ):
            return None

        await self.cache_user(user)
        return user

    async def register(self, dto: UserRegister) -> User:
        if await self.repo.exists_username(
            dto.username
        ) or await self.repo.exists_email(dto.email):
            raise HTTPException(409, "Username/Email exists")

        user = await self.repo.create_basic_user(
            username=dto.username,
            email=dto.email,
            password_hash=self.pwd_handler.hash_password(dto.password),
            first_name=dto.first_name,
            last_name=dto.last_name,
        )

        await self.db.commit()
        await self.db.refresh(user)
        await self.cache_user(user)
        return user
