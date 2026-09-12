"""Auth endpoints: register, login, refresh, logout, me."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import ApiResponse, MessageResponse
from app.schemas.user import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserOut,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[UserOut], status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    user = await svc.register(data)
    return ApiResponse(data=UserOut.model_validate(user), meta={"message": "User registered successfully"})


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    tokens = await svc.login(data)
    return ApiResponse(data=tokens, meta={"message": "Authentication successful"})


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_tokens(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    new_tokens = await svc.refresh(data.refresh_token)
    return ApiResponse(data=new_tokens, meta={"message": "Tokens refreshed"})


@router.post("/logout", response_model=ApiResponse[MessageResponse])
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = AuthService(db)
    await svc.logout(data.refresh_token)
    return ApiResponse(data=MessageResponse(message="Successfully logged out"))


@router.get("/me", response_model=ApiResponse[UserOut])
async def get_me(user: User = Depends(get_current_user)):
    return ApiResponse(data=UserOut.model_validate(user))
