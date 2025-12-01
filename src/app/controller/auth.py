from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.security.deps import CurrentUser, get_current_user, require_roles
from app.security.jwt_tokens import create_access_token
from app.utils.tbconstants import ROLE
from app.repository.user_repository import UserRepository
from app.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/api", tags=["auth"])

@router.get("/users/me")
async def read_users_me(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "message": f"Chào user {current_user.username}!",
        "user_id": current_user.id,
        "roles": current_user.roles,
    }

@router.get("/admin/dashboard")
async def read_admin_dashboard(
    admin: CurrentUser = Depends(require_roles([ROLE.ADMIN]))
):
    return {"message": f"Chào mừng Admin {admin.username} đến dashboard!"}


@router.get("/pro-feature/chat")
async def use_pro_chat_feature(
    pro_user: CurrentUser = Depends(require_roles([ROLE.ADMIN, ROLE.USER_PRO]))
):
    return {"message": f"Cảm ơn {pro_user.username} đã dùng tính năng PRO!"}

# response_model, 
@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    username = form_data.username
    password = form_data.password

    user_repo = UserRepository(db)
    # use repository.authenticate which verifies hashed password correctly
    user = await user_repo.authenticate(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    roles = [r.name for r in getattr(user, "roles", [])]

    access_token = create_access_token(sub=str(user.id), roles=roles)
    return {"access_token": access_token, "token_type": "bearer", "user_name": user.username}



