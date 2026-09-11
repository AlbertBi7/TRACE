"""
TRACE — Resolution Router (Milestone 4)
Suggest / accept / undo entity merges. Investigator-in-the-loop: suggestions
are never applied to the graph until accepted; undo restores prior state
without deleting the decision history (audit trail).
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.dependencies import get_current_user, require_case_access
from app.db.postgres import get_pool
from app.resolution.matcher import suggest_merges

router = APIRouter(prefix="/api/cases", tags=["resolution"])


@router.post("/{case_id}/resolution/suggest")
async def suggest_case_merges(case_id: str, current_user: dict = Depends(get_current_user)):
    """Run deterministic matching and return new merge suggestions for the case."""
    await require_case_access(case_id, current_user)
    suggestions = await suggest_merges(case_id)
    return {"suggested": len(suggestions), "suggestions": suggestions}


@router.get("/{case_id}/resolution/merges")
async def list_merges(case_id: str, current_user: dict = Depends(get_current_user)):
    """All merge decisions for the case, grouped by status."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    rows = await pool.fetch(
        """SELECT m.id, m.primary_entity_id, m.merged_entity_id, m.method,
                  m.confidence, m.status, m.suggested_at, m.decided_by, m.decided_at,
                  pe.value AS primary_value, me.value AS merged_value
           FROM entity_merges m
           LEFT JOIN LATERAL (
               SELECT value FROM extraction_log
               WHERE entity_or_edge_id = m.primary_entity_id AND value <> ''
               LIMIT 1
           ) pe ON true
           LEFT JOIN LATERAL (
               SELECT value FROM extraction_log
               WHERE entity_or_edge_id = m.merged_entity_id AND value <> ''
               LIMIT 1
           ) me ON true
           WHERE m.case_id = $1
           ORDER BY m.confidence DESC, m.suggested_at DESC""",
        case_id,
    )

    grouped = {"suggested": [], "accepted": [], "undone": []}
    for r in rows:
        grouped.setdefault(r["status"], []).append({
            "id": str(r["id"]),
            "primary_entity_id": r["primary_entity_id"],
            "merged_entity_id": r["merged_entity_id"],
            "primary_value": r["primary_value"],
            "merged_value": r["merged_value"],
            "method": r["method"],
            "confidence": r["confidence"],
            "suggested_at": r["suggested_at"].isoformat(),
            "decided_at": r["decided_at"].isoformat() if r["decided_at"] else None,
        })
    return grouped


@router.post("/{case_id}/resolution/merges/{merge_id}/accept")
async def accept_merge(case_id: str, merge_id: str, current_user: dict = Depends(get_current_user)):
    """Accept a suggested merge (investigator decision). Audited."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    result = await pool.execute(
        """UPDATE entity_merges
           SET status = 'accepted', decided_by = $1, decided_at = $2
           WHERE id = $3 AND case_id = $4 AND status = 'suggested'""",
        str(current_user["id"]),
        datetime.now(timezone.utc),
        uuid.UUID(merge_id) if _is_uuid(merge_id) else merge_id,
        case_id,
    )
    if not result or not result.endswith("1"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merge not found or already decided")

    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, metadata, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "MERGE_ACCEPTED",
        "entity_merge",
        merge_id,
        json.dumps({"case_id": case_id}),
        datetime.now(timezone.utc),
    )
    return {"message": "Merge accepted"}


@router.post("/{case_id}/resolution/merges/{merge_id}/dismiss")
async def dismiss_merge(case_id: str, merge_id: str, current_user: dict = Depends(get_current_user)):
    """Dismiss a suggested merge — marks as undone without ever affecting the graph."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    result = await pool.execute(
        """UPDATE entity_merges
           SET status = 'undone', decided_by = $1, decided_at = $2
           WHERE id = $3 AND case_id = $4 AND status = 'suggested'""",
        str(current_user["id"]),
        datetime.now(timezone.utc),
        uuid.UUID(merge_id) if _is_uuid(merge_id) else merge_id,
        case_id,
    )
    if not result or not result.endswith("1"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merge not found or not in suggested state")

    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, metadata, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "MERGE_DISMISSED",
        "entity_merge",
        merge_id,
        json.dumps({"case_id": case_id}),
        datetime.now(timezone.utc),
    )
    return {"message": "Merge dismissed"}


@router.post("/{case_id}/resolution/merges/{merge_id}/undo")
async def undo_merge(case_id: str, merge_id: str, current_user: dict = Depends(get_current_user)):
    """Undo an accepted merge — restores 'suggested' history, audited."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    result = await pool.execute(
        """UPDATE entity_merges
           SET status = 'undone', decided_by = $1, decided_at = $2
           WHERE id = $3 AND case_id = $4 AND status = 'accepted'""",
        str(current_user["id"]),
        datetime.now(timezone.utc),
        uuid.UUID(merge_id) if _is_uuid(merge_id) else merge_id,
        case_id,
    )
    if not result or not result.endswith("1"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merge not found or not in accepted state")

    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, metadata, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "MERGE_UNDONE",
        "entity_merge",
        merge_id,
        json.dumps({"case_id": case_id}),
        datetime.now(timezone.utc),
    )
    return {"message": "Merge undone"}


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
