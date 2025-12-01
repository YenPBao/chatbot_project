from app.repository.user_repository import UserRepository
from app.dto.user import UserRegister
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from config.db import get_db
from app.config.settings import settings
from app.model.user import User
from app.security.password import PasswordHandler
from typing import Optional
from fastapi import Depends
from datetime import datetime, timezone, timedelta
from app.dto.user import UserLogin
import jwt

class UserService:
    def __init__(self, 
                 db: AsyncSession = Depends(get_db),
                 pwd_handler: PasswordHandler = Depends(PasswordHandler)):
        self.db = db
        self.user_repo = UserRepository(db) 
        self.pwd_handler = pwd_handler

    async def authenticate_user(self, login_data: UserLogin) -> Optional[User]:

        db_user = await self.user_repo.get_user_by_username(login_data.username)
        if not db_user:
            return None

        if not self.pwd_handler.verify_password(login_data.password, db_user.hashed_password):
            return None 
        return db_user

    def create_access_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(seconds=settings.access_expire_seconds)
        to_encode = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role,
            "exp": expire
        }
        
        secret_key = settings.require_jwt_secret()
        
        encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.jwt_alg)
        return encoded_jwt

    async def register(self, dto: UserRegister):
        if await self.repo.exists_username(dto.username) or await self.repo.exists_email(dto.email):
            raise HTTPException(409, "Username/Email exists")
        return await self.repo.create_basic_user(
            username=dto.username, email=dto.email, password=dto.password,
            first_name=dto.first_name, last_name=dto.last_name,
        )