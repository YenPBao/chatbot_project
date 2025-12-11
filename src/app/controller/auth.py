from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.security.jwt_tokens import create_access_token
from app.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.dto.user import UserLogin
from app.services.user_services import UserService


router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db=db)
    user = await service.authenticate_user(
        UserLogin(username=form_data.username, password=form_data.password)
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    roles: list[str] = []
    if hasattr(user, "roles") and user.roles:
        roles = [str(r.name if hasattr(r, "name") else r) for r in user.roles]
    elif hasattr(user, "role") and user.role:
        roles = [str(user.role)]

    access_token = create_access_token(
        sub=str(user.id),  # <<< sub = user.id (string)
        roles=roles,  # <<< list role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_name": user.username,
        "roles": roles,
    }
