"""
TRACE — Audit Log Router
Admin-only paginated audit log with filtering.
"""

from fastapi import APIRouter, Depends, Query
from app.auth.dependencies import require_role
from app.db.postgres import get_pool
from typing import Optional

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    current_user: dict = Depends(require_role("admin")),
):
    """
    Paginated audit log (admin only).
    Supports filtering by action, user_id, and target_type.
    """
    pool = await get_pool()

    conditions = []
    params = []
    param_idx = 1

    if action:
        conditions.append(f"a.action = ${param_idx}")
        params.append(action)
        param_idx += 1

    if user_id:
        conditions.append(f"a.user_id = ${param_idx}")
        params.append(user_id)
        param_idx += 1

    if target_type:
        conditions.append(f"a.target_type = ${param_idx}")
        params.append(target_type)
        param_idx += 1

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Count total
    count_query = f"SELECT COUNT(*) FROM audit_log a {where_clause}"
    total = await pool.fetchval(count_query, *params)

    # Fetch page
    offset = (page - 1) * page_size
    data_query = f"""
        SELECT a.id, a.user_id, u.email as user_email, u.full_name as user_name,
               a.action, a.target_type, a.target_id, a.metadata, a.ip_address, a.timestamp
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.user_id
        {where_clause}
        ORDER BY a.timestamp DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([page_size, offset])

    rows = await pool.fetch(data_query, *params)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "data": [
            {
                "id": str(r["id"]),
                "user_id": str(r["user_id"]) if r["user_id"] else None,
                "user_email": r["user_email"],
                "user_name": r["user_name"],
                "action": r["action"],
                "target_type": r["target_type"],
                "target_id": r["target_id"],
                "metadata": r["metadata"],
                "ip_address": r["ip_address"],
                "timestamp": r["timestamp"].isoformat(),
            }
            for r in rows
        ],
    }
