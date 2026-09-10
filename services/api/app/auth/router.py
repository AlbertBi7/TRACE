"""
TRACE — Auth Router
Login, token refresh, logout, and current-user endpoints.
Every auth event is written to the audit_log.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from app.auth.models import LoginRequest, TokenResponse, RefreshRequest, UserOut
from app.auth.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_token,
)
from app.auth.dependencies import get_current_user
from app.db.postgres import get_pool
from datetime import datetime, timezone, timedelta
from app.config import settings
import json
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _write_audit(user_id: str | None, action: str, target_type: str = "auth", target_id: str = "", metadata: dict = {}, ip: str = ""):
    """Helper to write audit log entries."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, metadata, ip_address, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)""",
        str(uuid.uuid4()),
        user_id,
        action,
        target_type,
        target_id,
        json.dumps(metadata, default=str) if metadata else "{}",
        ip,
        datetime.now(timezone.utc),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    """Authenticate with email + password, receive JWT access + refresh tokens."""
    pool = await get_pool()
    client_ip = request.client.host if request.client else ""

    user = await pool.fetchrow(
        "SELECT id, email, password_hash, full_name, role, is_active, created_at, last_login FROM users WHERE email = $1",
        body.email,
    )

    if not user:
        await _write_audit(None, "LOGIN_FAILED", "auth", "", {"email": body.email, "reason": "user_not_found"}, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user["is_active"]:
        await _write_audit(str(user["id"]), "LOGIN_FAILED", "auth", str(user["id"]), {"reason": "account_deactivated"}, client_ip)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    if not verify_password(body.password, user["password_hash"]):
        await _write_audit(str(user["id"]), "LOGIN_FAILED", "auth", str(user["id"]), {"reason": "wrong_password"}, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Create tokens
    token_data = {"sub": str(user["id"]), "email": user["email"], "role": user["role"]}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token hash for tracking/revocation
    await pool.execute(
        """INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
           VALUES ($1, $2, $3, $4, $5)""",
        str(uuid.uuid4()),
        str(user["id"]),
        hash_token(refresh_token),
        datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expiry_days),
        datetime.now(timezone.utc),
    )

    # Update last_login
    await pool.execute(
        "UPDATE users SET last_login = $1 WHERE id = $2",
        datetime.now(timezone.utc),
        user["id"],
    )

    await _write_audit(str(user["id"]), "LOGIN_SUCCESS", "auth", str(user["id"]), {}, client_ip)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut(
            id=str(user["id"]),
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"],
            last_login=datetime.now(timezone.utc),
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(body: RefreshRequest):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    pool = await get_pool()
    payload = decode_refresh_token(body.refresh_token)

    if payload is None:
        await _write_audit(None, "REFRESH_FAILED", "auth", "", {"reason": "invalid_or_expired_token"}, "")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # Check the refresh token isn't revoked
    token_hash = hash_token(body.refresh_token)
    stored = await pool.fetchrow(
        "SELECT id, revoked FROM refresh_tokens WHERE token_hash = $1",
        token_hash,
    )

    if not stored or stored["revoked"]:
        await _write_audit(
            payload.get("sub"), "REFRESH_FAILED", "auth", str(payload.get("sub") or ""),
            {"reason": "revoked_or_unknown_token"}, "",
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    # Revoke the old refresh token (rotation)
    await pool.execute("UPDATE refresh_tokens SET revoked = true WHERE id = $1", stored["id"])

    user_id = payload.get("sub")
    user = await pool.fetchrow(
        "SELECT id, email, full_name, role, is_active, created_at, last_login FROM users WHERE id = $1",
        user_id,
    )

    if not user or not user["is_active"]:
        await _write_audit(user_id, "REFRESH_FAILED", "auth", str(user_id or ""), {"reason": "user_missing_or_deactivated"}, "")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    # Issue new tokens
    token_data = {"sub": str(user["id"]), "email": user["email"], "role": user["role"]}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    await pool.execute(
        """INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
           VALUES ($1, $2, $3, $4, $5)""",
        str(uuid.uuid4()),
        str(user["id"]),
        hash_token(new_refresh),
        datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expiry_days),
        datetime.now(timezone.utc),
    )

    await _write_audit(str(user["id"]), "REFRESH_SUCCESS", "auth", str(user["id"]), {}, "")

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=UserOut(
            id=str(user["id"]),
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"],
            last_login=user["last_login"],
        ),
    )


@router.post("/logout")
async def logout(body: RefreshRequest, current_user: dict = Depends(get_current_user)):
    """Revoke the refresh token and log the event."""
    pool = await get_pool()
    token_hash = hash_token(body.refresh_token)

    revoked = await pool.execute("UPDATE refresh_tokens SET revoked = true WHERE token_hash = $1", token_hash)
    await _write_audit(
        str(current_user["id"]), "LOGOUT", "auth", str(current_user["id"]),
        {"token_revoked": bool(revoked and revoked.endswith("1"))},
    )

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return UserOut(
        id=str(current_user["id"]),
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
        last_login=current_user["last_login"],
    )
