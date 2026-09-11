"""
TRACE — Documents Router (Milestone 2: Ingestion)
Upload and list case documents. Files are parsed to paragraph-anchored
content, stored on disk, and registered in PostgreSQL with provenance-ready
structure (file + page + paragraph) for every downstream extraction.
"""

import os
import uuid
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from app.auth.dependencies import get_current_user, require_case_access
from app.db.postgres import get_pool
from app.ingestion.parsers import parse_document
from app.ingestion.provenance import write_extraction_rows
from app.config import settings

router = APIRouter(prefix="/api/cases", tags=["documents"])

ALLOWED_EXTENSIONS = {"pdf", "txt", "csv", "json"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _ext_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.get("/{case_id}/documents")
async def list_documents(case_id: str, current_user: dict = Depends(get_current_user)):
    """List all documents uploaded to a case. Enforces case access."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    rows = await pool.fetch(
        """SELECT d.id, d.filename, d.filetype, d.uploaded_by, d.uploaded_at,
              d.page_count, d.extracted, u.full_name AS uploader_name
           FROM documents d
           LEFT JOIN users u ON u.id = d.uploaded_by
           WHERE d.case_id = $1
           ORDER BY d.uploaded_at DESC""",
        case_id,
    )

    # Counts of provenance rows per document (cheap grouped aggregate)
    counts = {
        str(r["document_id"]): r["n"]
        for r in await pool.fetch(
            "SELECT document_id, COUNT(*) AS n FROM extraction_log GROUP BY document_id"
        )
    }

    return [
        {
            "id": str(r["id"]),
            "filename": r["filename"],
            "filetype": r["filetype"],
            "uploaded_by": str(r["uploaded_by"]),
            "uploader_name": r["uploader_name"],
            "uploaded_at": r["uploaded_at"].isoformat(),
            "page_count": r["page_count"] or 0,
            "extracted": r["extracted"],
            "extraction_count": counts.get(str(r["id"]), 0),
        }
        for r in rows
    ]


@router.post("/{case_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a document (PDF/TXT/CSV/JSON, max 50MB) to a case.
    Parses to paragraph-anchored content, stores the raw file on disk plus the
    normalized text in PostgreSQL, and enforces case access.
    """
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    # Case existence check (require_case_access passes for admins even if case is absent)
    case = await pool.fetchrow("SELECT id FROM cases WHERE id = $1", case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    filename = os.path.basename(file.filename or "unnamed")
    ext = _ext_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 50MB limit")

    # Parse into paragraph-anchored content
    try:
        full_text, pages = parse_document(ext, data, filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Could not parse file — it may be corrupted")

    # Honest failure for scanned/image-only PDFs: PyPDF2 reads text layers only,
    # so such files parse to pages with zero paragraphs. Refuse them explicitly
    # instead of silently ingesting a document nothing can ever be extracted
    # from (OCR is out of scope — fail clearly, don't pretend it worked).
    if ext == "pdf" and sum(len(p["paragraphs"]) for p in pages) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF contains no extractable text — it may be a scanned/image-only document. OCR is not supported; provide a text-based PDF.",
        )

    document_id = str(uuid.uuid4())
    storage_dir = settings.upload_dir
    os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, f"{case_id}_{document_id}_{filename}")
    with open(storage_path, "wb") as f:
        f.write(data)

    now = datetime.now(timezone.utc)
    page_count = len(pages)

    await pool.execute(
        """INSERT INTO documents
               (id, case_id, filename, filetype, uploaded_by, uploaded_at, storage_path, extracted_text, page_count, parsed_content)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)""",
        document_id,
        case_id,
        filename,
        ext,
        str(current_user["id"]),
        now,
        storage_path,
        full_text,
        page_count,
        json.dumps({"pages": pages}),
    )

    await pool.execute(
        """INSERT INTO audit_log (id, user_id, action, target_type, target_id, metadata, timestamp)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)""",
        str(uuid.uuid4()),
        str(current_user["id"]),
        "DOCUMENT_UPLOADED",
        "document",
        document_id,
        json.dumps({"filename": filename, "case_id": case_id, "bytes": len(data), "pages": page_count}),
        now,
    )

    return {
        "id": document_id,
        "filename": filename,
        "filetype": ext,
        "page_count": page_count,
        "paragraph_count": sum(len(p["paragraphs"]) for p in pages),
        "uploaded_at": now.isoformat(),
        "message": "Document uploaded and parsed",
    }


@router.get("/{case_id}/documents/{document_id}")
async def get_document(
    case_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Document metadata + paragraph-anchored parsed content (used by the evidentiary drawer)."""
    await require_case_access(case_id, current_user)
    pool = await get_pool()

    row = await pool.fetchrow(
        """SELECT id, case_id, filename, filetype, uploaded_by, uploaded_at,
                  storage_path, extracted_text, page_count, parsed_content
           FROM documents WHERE id = $1 AND case_id = $2""",
        document_id,
        case_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    parsed = row["parsed_content"] if isinstance(row["parsed_content"], dict) else json.loads(row["parsed_content"] or "{}")

    return {
        "id": str(row["id"]),
        "case_id": str(row["case_id"]),
        "filename": row["filename"],
        "filetype": row["filetype"],
        "uploaded_by": str(row["uploaded_by"]),
        "uploaded_at": row["uploaded_at"].isoformat(),
        "page_count": row["page_count"] or 0,
        "extracted_text": row["extracted_text"] or "",
        "pages": parsed.get("pages", []),
    }
