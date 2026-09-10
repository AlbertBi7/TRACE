"""
TRACE — Extraction Router (Milestone 3)
Trigger NLP extraction on an uploaded document and inspect extraction status.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.auth.dependencies import get_current_user, require_case_access
from app.db.postgres import get_pool
from app.nlp.pipeline import run_extraction

router = APIRouter(prefix="/api/cases", tags=["extraction"])


class ExtractionRequest(BaseModel):
    use_llm_fallback: bool = True


@router.post("/{case_id}/documents/{document_id}/extract")
async def extract_document(
    case_id: str,
    document_id: str,
    body: ExtractionRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    """Run entity + relation extraction on an uploaded document."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    doc = await pool.fetchrow(
        "SELECT id, case_id, extracted FROM documents WHERE id = $1 AND case_id = $2",
        document_id,
        case_id,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    use_llm = bool(body.use_llm_fallback) if body else True
    try:
        result = await run_extraction(document_id, use_llm_fallback=use_llm)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Extraction failed: {e}")

    return result


@router.get("/{case_id}/documents/{document_id}/extract")
async def extraction_status(
    case_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Extraction status + summary counts for one document."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    doc = await pool.fetchrow(
        "SELECT id, filename, extracted FROM documents WHERE id = $1 AND case_id = $2",
        document_id,
        case_id,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    counts = await pool.fetch(
        """SELECT entity_type, COUNT(*) AS n FROM extraction_log
           WHERE document_id = $1 AND head_entity_id = ''
           GROUP BY entity_type ORDER BY n DESC""",
        document_id,
    )
    rel_count = await pool.fetchval(
        "SELECT COUNT(*) FROM extraction_log WHERE document_id = $1 AND head_entity_id <> ''",
        document_id,
    )

    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "extracted": doc["extracted"],
        "entity_counts": {r["entity_type"]: r["n"] for r in counts},
        "relation_count": rel_count,
    }
