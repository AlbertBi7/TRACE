"""
TRACE — Auth Dependencies
FastAPI Depends for extracting current user, role checks, and case access control.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.security import decode_access_token
from app.db.postgres import get_pool
from typing import Optional

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """
    Extract and validate the JWT access token from the Authorization header.
    Returns the user record from PostgreSQL.
    Raises 401 if token is invalid or user is inactive.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id, email, full_name, role, is_active, created_at, last_login FROM users WHERE id = $1",
        user_id,
    )

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    return dict(user)


def require_role(*roles: str):
    """
    Dependency factory: ensures the current user has one of the specified roles.
    Usage: Depends(require_role("admin"))
    """
    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return current_user
    return _check


async def require_case_access(case_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """
    Verify that the current user has access to the specified case.
    Admins can access all cases. Investigators must be assigned.
    """
    if current_user["role"] == "admin":
        return current_user

    pool = await get_pool()
    assignment = await pool.fetchrow(
        "SELECT 1 FROM case_assignments WHERE case_id = $1 AND user_id = $2",
        case_id,
        str(current_user["id"]),
    )

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this case",
        )

    return current_user
