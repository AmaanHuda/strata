"""Authentication & token service."""
from datetime import datetime, timezone, timedelta
from typing import Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.models.user import User, UserRole
from app.db.repositories.user import UserRepository
from app.schemas.user import LoginRequest, TokenResponse, UserCreate


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)
        self.db = db

    async def register(self, data: UserCreate) -> User:
        if await self.repo.get_by_email(data.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        if await self.repo.get_by_username(data.username):
            raise HTTPException(status_code=400, detail="Username already taken")
        return await self.repo.create({
            "email": data.email,
            "username": data.username,
            "hashed_password": hash_password(data.password),
            "full_name": data.full_name,
            "role": data.role,
        })

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_email(data.username) or await self.repo.get_by_username(data.username)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account deactivated")
        # Check lockout
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail=f"Account locked. Try after {user.locked_until.isoformat()}")
        if not verify_password(data.password, user.hashed_password):
            new_attempts = user.failed_login_attempts + 1
            update_data: dict = {"failed_login_attempts": new_attempts}
            if new_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                update_data["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)
            await self.repo.update(user, update_data)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Reset on success
        await self.repo.update(user, {
            "failed_login_attempts": 0,
            "locked_until": None,
            "last_login_at": datetime.now(timezone.utc),
        })
        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    async def get_current_user(self, token: str) -> User:
        from jose import JWTError
        try:
            payload = decode_token(token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user = await self.repo.get(UUID(payload["sub"]))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
