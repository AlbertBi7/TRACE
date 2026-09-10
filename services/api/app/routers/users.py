"""
TRACE — Users Router
Admin-only CRUD for user management: create investigators, deactivate, reset passwords.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from app.auth.models import UserCreate, UserOut, UserUpdate, PasswordReset
from app.auth.security import hash_password
from app.auth.dependencies import get_current_user, require_role
from app.db.postgres import get_pool
from datetime import datetime, timezone
import json
import uuid

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(current_user: dict = Depends(require_role("admin"))):
    """List all users (admin only)."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, email, full_name, role, is_active, created_at, last_login FROM users ORDER BY created_at DESC"
    )
    return [
        UserOut(
            id=str(r["id"]),
            email=r["email"],
            full_name=r["full_name"],
            role=r["role"],
            is_active=r["is_active"],
            created_at=r["created_at"],
            last_login=r["last_login"],
        )
        for r in rows
    ]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, current_user: dict = Depends(require_role("admin"))):
    """Create a new user (admin only)."""
    pool = await get_pool()

    # Check for duplicate email
    existing = await pool.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await pool.execute(
        """INSERT INTO users (id, email, password_hash, full_name, role, is_active, created_at)
           VALUES ($1, $2, $3, $4, $5, true, $6)""",
        user_id,
        body.email,
        hash_password(body.password),
        body.full_name,
        body.role.value,
        now,
    )

    # Audit log
    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "USER_CREATED",
        "user",
        user_id,
        now,
    )

    return UserOut(
        id=user_id,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        is_active=True,
        created_at=now,
    )


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: str, current_user: dict = Depends(require_role("admin"))):
    """Get a specific user's details (admin only)."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, email, full_name, role, is_active, created_at, last_login FROM users WHERE id = $1",
        user_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserOut(
        id=str(row["id"]),
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        last_login=row["last_login"],
    )


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: str, body: UserUpdate, current_user: dict = Depends(require_role("admin"))):
    """Update user fields (admin only). Supports partial updates."""
    pool = await get_pool()

    row = await pool.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = {}
    if body.full_name is not None:
        updates["full_name"] = body.full_name
    if body.role is not None:
        updates["role"] = body.role.value
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [user_id] + list(updates.values())
    await pool.execute(f"UPDATE users SET {set_clauses} WHERE id = $1", *values)

    # Audit log
    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, metadata, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "USER_UPDATED",
        "user",
        user_id,
        json.dumps(updates, default=str),
        datetime.now(timezone.utc),
    )

    updated = await pool.fetchrow(
        "SELECT id, email, full_name, role, is_active, created_at, last_login FROM users WHERE id = $1",
        user_id,
    )
    return UserOut(
        id=str(updated["id"]),
        email=updated["email"],
        full_name=updated["full_name"],
        role=updated["role"],
        is_active=updated["is_active"],
        created_at=updated["created_at"],
        last_login=updated["last_login"],
    )


@router.delete("/{user_id}")
async def deactivate_user(user_id: str, current_user: dict = Depends(require_role("admin"))):
    """Soft-deactivate a user (admin only). Does not delete data."""
    pool = await get_pool()

    if str(current_user["id"]) == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    row = await pool.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await pool.execute("UPDATE users SET is_active = false WHERE id = $1", user_id)

    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "USER_DEACTIVATED",
        "user",
        user_id,
        datetime.now(timezone.utc),
    )

    return {"message": "User deactivated"}


@router.post("/{user_id}/reset-password")
async def reset_password(user_id: str, body: PasswordReset, current_user: dict = Depends(require_role("admin"))):
    """Reset a user's password (admin only)."""
    pool = await get_pool()

    row = await pool.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await pool.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2",
        hash_password(body.new_password),
        user_id,
    )

    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "PASSWORD_RESET",
        "user",
        user_id,
        datetime.now(timezone.utc),
    )

    return {"message": "Password reset successfully"}
