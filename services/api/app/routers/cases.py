"""
TRACE — Cases Router
Case CRUD with role-based access control and case assignments.
Investigators see only their assigned cases. Admins see all.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from app.auth.models import CaseCreate, CaseUpdate, CaseOut, CaseAssignment
from app.auth.dependencies import get_current_user, require_role, require_case_access
from app.db.postgres import get_pool
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=list[CaseOut])
async def list_cases(current_user: dict = Depends(get_current_user)):
    """
    List cases. Admins see all; investigators see only assigned cases.
    """
    pool = await get_pool()

    if current_user["role"] == "admin":
        rows = await pool.fetch(
            "SELECT id, name, description, created_by, created_at, status FROM cases ORDER BY created_at DESC"
        )
    else:
        rows = await pool.fetch(
            """SELECT c.id, c.name, c.description, c.created_by, c.created_at, c.status
               FROM cases c
               JOIN case_assignments ca ON ca.case_id = c.id
               WHERE ca.user_id = $1
               ORDER BY c.created_at DESC""",
            str(current_user["id"]),
        )

    return [
        CaseOut(
            id=str(r["id"]),
            name=r["name"],
            description=r["description"],
            created_by=str(r["created_by"]),
            created_at=r["created_at"],
            status=r["status"],
        )
        for r in rows
    ]


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(body: CaseCreate, current_user: dict = Depends(get_current_user)):
    """Create a new case. The creator is auto-assigned."""
    pool = await get_pool()
    case_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await pool.execute(
        """INSERT INTO cases (id, name, description, created_by, created_at, status)
           VALUES ($1, $2, $3, $4, $5, 'open')""",
        case_id,
        body.name,
        body.description,
        str(current_user["id"]),
        now,
    )

    # Auto-assign the creator
    await pool.execute(
        "INSERT INTO case_assignments (case_id, user_id, assigned_at) VALUES ($1, $2, $3)",
        case_id,
        str(current_user["id"]),
        now,
    )

    # Audit log
    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "CASE_CREATED",
        "case",
        case_id,
        now,
    )

    return CaseOut(
        id=case_id,
        name=body.name,
        description=body.description,
        created_by=str(current_user["id"]),
        created_at=now,
        status="open",
    )


@router.get("/{case_id}", response_model=CaseOut)
async def get_case(case_id: str, current_user: dict = Depends(get_current_user)):
    """Get case details. Enforces case access."""
    # Check access
    await require_case_access(case_id, current_user)

    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, description, created_by, created_at, status FROM cases WHERE id = $1",
        case_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return CaseOut(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        created_by=str(row["created_by"]),
        created_at=row["created_at"],
        status=row["status"],
    )


@router.patch("/{case_id}", response_model=CaseOut)
async def update_case(case_id: str, body: CaseUpdate, current_user: dict = Depends(get_current_user)):
    """Update case fields. Enforces case access."""
    await require_case_access(case_id, current_user)

    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM cases WHERE id = $1", case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.status is not None:
        if body.status not in ("open", "closed", "archived"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        updates["status"] = body.status

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [case_id] + list(updates.values())
    await pool.execute(f"UPDATE cases SET {set_clauses} WHERE id = $1", *values)

    # Audit
    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "CASE_UPDATED",
        "case",
        case_id,
        datetime.now(timezone.utc),
    )

    updated = await pool.fetchrow(
        "SELECT id, name, description, created_by, created_at, status FROM cases WHERE id = $1",
        case_id,
    )
    return CaseOut(
        id=str(updated["id"]),
        name=updated["name"],
        description=updated["description"],
        created_by=str(updated["created_by"]),
        created_at=updated["created_at"],
        status=updated["status"],
    )


@router.post("/{case_id}/assign")
async def assign_investigator(case_id: str, body: CaseAssignment, current_user: dict = Depends(require_role("admin"))):
    """Assign an investigator to a case (admin only)."""
    pool = await get_pool()

    # Verify case exists
    case = await pool.fetchrow("SELECT id FROM cases WHERE id = $1", case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    # Verify user exists and has the investigator role
    user = await pool.fetchrow("SELECT id, role FROM users WHERE id = $1", body.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user["role"] != "investigator":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only users with the investigator role can be assigned to a case",
        )

    # Check if already assigned
    existing = await pool.fetchrow(
        "SELECT 1 FROM case_assignments WHERE case_id = $1 AND user_id = $2",
        case_id,
        body.user_id,
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already assigned to this case")

    await pool.execute(
        "INSERT INTO case_assignments (case_id, user_id, assigned_at) VALUES ($1, $2, $3)",
        case_id,
        body.user_id,
        datetime.now(timezone.utc),
    )

    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, metadata, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "CASE_ASSIGNMENT",
        "case",
        case_id,
        f'{{"assigned_user": "{body.user_id}"}}',
        datetime.now(timezone.utc),
    )

    return {"message": "Investigator assigned to case"}


@router.get("/{case_id}/assignments")
async def list_assignments(case_id: str, current_user: dict = Depends(get_current_user)):
    """List all users assigned to a case."""
    await require_case_access(case_id, current_user)

    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT u.id, u.email, u.full_name, u.role, ca.assigned_at
           FROM case_assignments ca
           JOIN users u ON u.id = ca.user_id
           WHERE ca.case_id = $1
           ORDER BY ca.assigned_at""",
        case_id,
    )

    return [
        {
            "id": str(r["id"]),
            "email": r["email"],
            "full_name": r["full_name"],
            "role": r["role"],
            "assigned_at": r["assigned_at"].isoformat(),
        }
        for r in rows
    ]
