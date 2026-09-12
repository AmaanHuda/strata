"""
Authentication & Authorization service:
- Registration, Login, Token generation
- Refresh token rotation & revocation strategy
- Password hashing & secure verification
"""
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.core.errors import AuthenticationError, ConflictError, NotFoundError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.user import RefreshToken, User, UserRole
from app.db.repositories.user import UserRepository
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserOut


class AuthService:
    """Handles user identity, JWT lifecycle, and role-based permissions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def register(self, data: UserCreate) -> User:
        """Registers a new user."""
        existing_email = await self.user_repo.get_by_email(data.email)
        if existing_email:
            raise ConflictError("User with this email already exists")

        existing_username = await self.user_repo.get_by_username(data.username)
        if existing_username:
            raise ConflictError("Username is already taken")

        hashed_pw = hash_password(data.password)
        user = await self.user_repo.create({
            "email": data.email,
            "username": data.username,
            "hashed_password": hashed_pw,
            "full_name": data.full_name,
            "role": data.role,
            "is_active": True,
            "is_verified": False,
        })
        return user

    async def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticates user and issues access + refresh tokens."""
        user = await self.user_repo.get_by_email(data.username)
        if not user:
            user = await self.user_repo.get_by_username(data.username)

        if not user or not verify_password(data.password, user.hashed_password):
            raise AuthenticationError("Invalid username or password")

        if not user.is_active:
            raise AuthenticationError("User account is disabled")

        # Update last login
        await self.user_repo.update(user, {"last_login_at": datetime.now(timezone.utc)})

        # Issue tokens
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token = create_refresh_token(subject=str(user.id))

        # Store refresh token hash for rotation & revocation tracking
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        rt_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.db.add(rt_record)
        await self.db.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Rotates refresh token and returns a new access token."""
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise AuthenticationError("Invalid or expired refresh token")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Provided token is not a refresh token")

        user_id = payload.get("sub")
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Check in DB if revoked
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
            )
        )
        rt_record = result.scalar_one_or_none()
        if not rt_record:
            raise AuthenticationError("Refresh token has been revoked or is invalid")

        # Revoke the used refresh token (Token Rotation)
        rt_record.is_revoked = True

        user = await self.user_repo.get(UUID(user_id))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or disabled")

        # Create new tokens
        new_access = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        new_refresh = create_refresh_token(subject=str(user.id))
        new_token_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        new_rt = RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.db.add(new_rt)
        await self.db.flush()

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, refresh_token: Optional[str]) -> bool:
        """Revokes the refresh token."""
        if refresh_token:
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            await self.db.execute(
                update(RefreshToken)
                .where(RefreshToken.token_hash == token_hash)
                .values(is_revoked=True)
            )
            await self.db.flush()
        return True
