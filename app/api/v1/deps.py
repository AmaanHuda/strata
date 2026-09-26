"""
FastAPI dependency providers.

Sign-in was intentionally **removed** from STRATA: there is no login, no token
and no role check. Every `/api/v1/*` endpoint is open.

This module survives as a thin compatibility layer. The routers all declare
`Depends(get_current_user)` / `Depends(require_roles(...))` and pass the result
around as an audit identity, so instead of rewriting twelve routers we keep the
two dependency names and give them a no-auth implementation.

What the caller gets back is an *anonymous principal*:
  * `role` is always `UserRole.ADMIN`, so role comparisons inside routers pass.
  * `id` is `None`. Audit columns fed from it (`async_jobs.created_by`,
    `ulpin_records.created_by`, `dataset_registry.created_by`) are nullable, so
    records are stored with no author — which is the honest answer when nobody
    signed in.
"""
from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

from app.db.models.user import UserRole


@dataclass(frozen=True)
class Principal:
    """Identity of an unauthenticated caller. Never persisted, never trusted."""

    id: Optional[UUID] = None
    role: UserRole = UserRole.ADMIN
    email: str = "anonymous@strata.local"
    username: str = "anonymous"
    is_active: bool = True


_ANONYMOUS = Principal()


async def get_current_user() -> Principal:
    """Returns the anonymous principal. No header, no token, no database lookup."""
    return _ANONYMOUS


def require_roles(*_roles: UserRole) -> Callable:
    """
    Signature-compatible stand-in for the old RBAC guard.

    With no accounts there is nobody to grant or deny a role to, so this always
    yields the anonymous principal. The role arguments are accepted and ignored
    purely so existing `Depends(require_roles(UserRole.ADMIN, ...))` declarations
    keep working.
    """

    async def _anonymous_caller() -> Principal:
        return _ANONYMOUS

    return _anonymous_caller
