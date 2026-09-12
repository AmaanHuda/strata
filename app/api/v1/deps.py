"""FastAPI dependency providers: Authentication, RBAC, DB session."""
from typing import Callable, List
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, AuthorizationError
from app.core.security import decode_token
from app.db.models.user import User, UserRole
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extracts and validates user from JWT bearer token."""
    if not auth:
        raise AuthenticationError("Authorization header missing")

    token = auth.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise AuthenticationError("Invalid or expired access token")

    if payload.get("type") != "access":
        raise AuthenticationError("Token is not an access token")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token subject")

    user = await db.get(User, UUID(user_id))
    if not user:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return user


def require_roles(*roles: UserRole) -> Callable:
    """RBAC dependency to ensure current user holds required role."""
    async def _role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AuthorizationError(
                f"Role '{user.role.value}' does not have sufficient permissions. Required: {[r.value for r in roles]}"
            )
        return user
    return _role_checker
