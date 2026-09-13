"""
TRACE — Document Parsers (Milestone 2: Ingestion)
Normalize PDF / TXT / CSV / JSON / Image uploads into:
  full_text : str                — flat text (stored in documents.extracted_text)
  pages     : list[dict]         — [{page: int, paragraphs: [str, ...]}, ...]
                                   stored in documents.parsed_content so every
                                   extraction can cite (file, page, paragraph).
All logic is local and deterministic — no external calls (except OCR which is
local transcription only). Native PyPDF2 path is tried first; OCR is fallback
only when PyPDF2 yields zero extractable characters.
"""

import csv
import io
import json
import re
import logging

MAX_PARA_CHARS = 600

logger = logging.getLogger("trace.parsers")

# Tracks whether the last parse_document call used OCR (for provenance flagging
# and extractor labeling in documents router / extraction pipeline). Simple
# module-level flag is sufficient because FastAPI handles requests sequentially
# per worker for this path; for concurrent workers the flag is per-process.
_LAST_OCR = False


def get_last_ocr_flag() -> bool:
    return _LAST_OCR


def _set_last_ocr(flag: bool) -> None:
    global _LAST_OCR
    _LAST_OCR = flag


def _split_paragraphs(text: str, split_lines: bool = False) -> list[str]:
    """
    Split text into paragraph-sized chunks on blank lines / sentence runs.

    split_lines=True (used for PDF text, where line breaks are extraction
    artifacts rather than author intent): also break after lines ending in
    sentence punctuation, so each sentence-terminated line is its own
    paragraph — giving page+paragraph provenance real granularity.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_parts = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        if split_lines:
            buf = ""
            for line in (ln.strip() for ln in part.split("\n")):
                if not line:
                    continue
                buf = f"{buf} {line}".strip() if buf else line
                if len(buf) >= MAX_PARA_CHARS or re.search(r"[.!?]\s*$", line):
                    out.append(buf)
                    buf = ""
            if buf:
                out.append(buf)
            continue
        if len(part) <= MAX_PARA_CHARS:
            out.append(part)
            continue
        # Long run: chunk on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", part)
        buf = ""
        for s in sentences:
            if buf and len(buf) + len(s) + 1 > MAX_PARA_CHARS:
                out.append(buf)
                buf = s
            else:
                buf = f"{buf} {s}".strip()
        if buf:
            out.append(buf)
    return out


def _ocr_image_to_paragraphs(image) -> list[str]:
    """
    Run tesseract on a single PIL Image, reconstruct logical paragraphs via
    block/paragraph grouping (image_to_data), and chunk to MAX_PARA_CHARS.
    Deterministic, grounded transcription only.
    """
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as e:
        logger.warning(f"pytesseract not available ({e}) — OCR paragraph reconstruction unavailable")
        return []

    # Try structured data first for block/paragraph reconstruction
    try:
        data = pytesseract.image_to_data(image, lang="eng+hin", output_type=Output.DICT, config="--psm 6")
    except Exception as e:
        logger.warning(f"image_to_data failed ({e}), falling back to image_to_string")
        try:
            text = pytesseract.image_to_string(image, lang="eng+hin", config="--psm 6")
            if not (text or "").strip():
                return []
            return _split_paragraphs(text, split_lines=True)
        except Exception as e2:
            logger.warning(f"image_to_string fallback failed ({e2})")
            return []

    n = len(data.get("text", []))
    if n == 0 or all(not (t or "").strip() for t in data["text"]):
        try:
            text = pytesseract.image_to_string(image, lang="eng+hin", config="--psm 6")
            if not (text or "").strip():
                return []
            return _split_paragraphs(text, split_lines=True)
        except Exception:
            return []

    from collections import defaultdict

    lines_dict: dict[tuple, list[str]] = defaultdict(list)
    for i in range(n):
        # level 5 = word
        if data["level"][i] != 5:
            continue
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines_dict[key].append(txt)

    if not lines_dict:
        try:
            text = pytesseract.image_to_string(image, lang="eng+hin", config="--psm 6")
            if not (text or "").strip():
                return []
            return _split_paragraphs(text, split_lines=True)
        except Exception:
            return []

    # Group lines by paragraph (block, par)
    par_dict: dict[tuple, list[str]] = defaultdict(list)
    for (block, par, line), words in sorted(lines_dict.items()):
        line_text = " ".join(words).strip()
        if line_text:
            par_dict[(block, par)].append(line_text)

    raw_paras: list[str] = []
    for key in sorted(par_dict.keys()):
        para_text = " ".join(par_dict[key]).strip()
        if para_text:
            raw_paras.append(para_text)

    if not raw_paras:
        try:
            text = pytesseract.image_to_string(image, lang="eng+hin", config="--psm 6")
            if not (text or "").strip():
                return []
            return _split_paragraphs(text, split_lines=True)
        except Exception:
            return []

    # Chunk long paragraphs exceeding MAX_PARA_CHARS using existing logic
    final: list[str] = []
    for rp in raw_paras:
        rp = rp.strip()
        if not rp:
            continue
        if len(rp) <= MAX_PARA_CHARS:
            final.append(rp)
        else:
            chunks = _split_paragraphs(rp)
            final.extend(chunks)
    return final


def _parse_scanned_pdf_ocr(data: bytes) -> tuple[str, list[dict]]:
    """
    OCR fallback for scanned PDFs: convert PDF pages to PIL images via
    pdf2image (dpi=200), then OCR each page with paragraph/block segmentation.
    Returns (full_text, pages) matching TRACE's exact schema.
    """
    _set_last_ocr(True)
    try:
        from pdf2image import convert_from_bytes
    except ImportError as e:
        logger.warning(f"pdf2image not available ({e}) — cannot OCR scanned PDF")
        raise ValueError(f"OCR dependencies missing (pdf2image): {e}")

    try:
        images = convert_from_bytes(data, dpi=200)
    except Exception as e:
        logger.warning(f"pdf2image convert_from_bytes failed ({e})")
        raise ValueError(f"Failed to render PDF for OCR: {e}")

    if not images:
        return "", [{"page": 1, "paragraphs": []}]

    pages: list[dict] = []
    full: list[str] = []
    for idx, img in enumerate(images, start=1):
        try:
            paragraphs = _ocr_image_to_paragraphs(img)
        except Exception as e:
            logger.warning(f"OCR failed on page {idx} ({e})")
            paragraphs = []
        pages.append({"page": idx, "paragraphs": paragraphs})
        full.extend(paragraphs)

    return "\n\n".join(full), pages


def parse_image(data: bytes) -> tuple[str, list[dict]]:
    """
    Direct image parser for png/jpg/jpeg: OCR single image as page 1.
    Returns (full_text, pages) with single-page schema.
    """
    _set_last_ocr(True)
    try:
        from PIL import Image
    except ImportError as e:
        logger.warning(f"Pillow not available ({e}) — cannot OCR image")
        raise ValueError(f"OCR dependencies missing (Pillow): {e}")

    try:
        img = Image.open(io.BytesIO(data))
        # Ensure image is in a mode tesseract handles well
        if img.mode not in ("RGB", "L"):
            try:
                img = img.convert("RGB")
            except Exception:
                pass
    except Exception as e:
        raise ValueError(f"Failed to open image for OCR: {e}")

    paragraphs = _ocr_image_to_paragraphs(img)
    pages = [{"page": 1, "paragraphs": paragraphs}]
    full = "\n\n".join(paragraphs)
    return full, pages


def parse_pdf(data: bytes) -> tuple[str, list[dict]]:
    from PyPDF2 import PdfReader

    # Attempt fast PyPDF2 text layer extraction first
    reader = PdfReader(io.BytesIO(data))
    pages: list[dict] = []
    full: list[str] = []
    has_text = False
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            has_text = True
        paragraphs = _split_paragraphs(text, split_lines=True)
        if paragraphs:
            has_text = True
        pages.append({"page": i, "paragraphs": paragraphs})
        full.extend(paragraphs)

    # Graceful fallback: if zero extractable characters across all pages,
    # route to OCR instead of returning empty. Digital PDFs bypass OCR.
    total_paras = sum(len(p["paragraphs"]) for p in pages)
    total_chars = len("\n\n".join(full).strip())
    if (not has_text or total_paras == 0 or total_chars == 0) and len(reader.pages) > 0:
        logger.info("PDF has no extractable text — routing to OCR fallback (scanned PDF)")
        try:
            ocr_text, ocr_pages = _parse_scanned_pdf_ocr(data)
            _set_last_ocr(True)
            # If OCR produced content, return it; otherwise fall through to
            # empty result so caller can raise honest 422 (even OCR found nothing)
            if sum(len(p["paragraphs"]) for p in ocr_pages) > 0:
                return ocr_text, ocr_pages
            # OCR produced nothing — keep OCR flag true so caller knows OCR
            # was attempted, but return OCR empty pages for accurate provenance
            return ocr_text, ocr_pages
        except Exception as e:
            logger.warning(f"OCR fallback failed ({e}) — returning empty PyPDF2 result")
            _set_last_ocr(False)
            return "\n\n".join(full), pages

    _set_last_ocr(False)
    return "\n\n".join(full), pages


def parse_txt(data: bytes) -> tuple[str, list[dict]]:
    _set_last_ocr(False)
    text = data.decode("utf-8", errors="replace")
    paragraphs = _split_paragraphs(text)
    return "\n\n".join(paragraphs), [{"page": 1, "paragraphs": paragraphs}]


def parse_csv(data: bytes) -> tuple[str, list[dict]]:
    _set_last_ocr(False)
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return "", [{"page": 1, "paragraphs": []}]

    header = [(c or "").strip() for c in rows[0]]
    paragraphs: list[str] = []
    for r in rows[1:]:
        pairs = []
        for j, cell in enumerate(r):
            col = header[j] if j < len(header) and header[j] else f"field_{j+1}"
            if (cell or "").strip():
                pairs.append(f"{col}: {(cell or '').strip()}")
        if pairs:
            paragraphs.append("; ".join(pairs))

    header_para = ", ".join(h for h in header if h)
    if header_para:
        paragraphs.insert(0, f"Columns: {header_para}")
    return "\n\n".join(paragraphs), [{"page": 1, "paragraphs": paragraphs}]


def parse_json(data: bytes) -> tuple[str, list[dict]]:
    _set_last_ocr(False)
    obj = json.loads(data.decode("utf-8", errors="replace"))

    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict) and isinstance(obj.get("records"), list):
        items = obj["records"]
    else:
        items = [obj]

    paragraphs: list[str] = []
    for item in items:
        if isinstance(item, dict):
            parts = "; ".join(f"{k}: {v}" for k, v in item.items() if v is not None)
            paragraphs.append(parts if parts else json.dumps(item))
        else:
            paragraphs.append(str(item))
    return "\n\n".join(paragraphs), [{"page": 1, "paragraphs": paragraphs}]


def parse_document(ext: str, data: bytes, filename: str = "") -> tuple[str, list[dict]]:
    """Dispatch on file extension. Returns (full_text, pages). Raises ValueError for unknown types."""
    ext = ext.lower().lstrip(".")
    parsers = {"pdf": parse_pdf, "txt": parse_txt, "csv": parse_csv, "json": parse_json, "png": parse_image, "jpg": parse_image, "jpeg": parse_image}
    parser = parsers.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported file type: .{ext}")
    return parser(data)
