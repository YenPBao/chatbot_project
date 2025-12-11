from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.repository.user_repository import UserRepository
from app.security.jwt_tokens import decode_token
from app.utils.tbconstants import ROLE

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/login")


class CurrentUser:
    id: int
    roles: list[str]
    username: str


async def get_current_user(
    token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)
) -> CurrentUser:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad token payload")

    user = await UserRepository(db).get_by_id(int(user_id))
    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not active")

    cu = CurrentUser()
    cu.id = int(user_id)
    cu.username = user.username
    cu.roles = payload.get("roles", [])
    return cu


def require_roles(allowed: list[str]):
    allowed_set = {a.value if isinstance(a, ROLE) else a for a in allowed}

    async def _dep(user: CurrentUser = Depends(get_current_user)):
        if not any(r in allowed_set for r in user.roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return _dep
