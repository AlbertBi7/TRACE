"""
TRACE — Document Parsers (Milestone 2: Ingestion)
Normalize PDF / TXT / CSV / JSON uploads into:
  full_text : str                — flat text (stored in documents.extracted_text)
  pages     : list[dict]         — [{page: int, paragraphs: [str, ...]}, ...]
                                   stored in documents.parsed_content so every
                                   extraction can cite (file, page, paragraph).
All logic is local and deterministic — no external calls.
"""

import csv
import io
import json
import re

MAX_PARA_CHARS = 600


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


def parse_pdf(data: bytes) -> tuple[str, list[dict]]:
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages: list[dict] = []
    full: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        paragraphs = _split_paragraphs(text, split_lines=True)
        pages.append({"page": i, "paragraphs": paragraphs})
        full.extend(paragraphs)
    return "\n\n".join(full), pages


def parse_txt(data: bytes) -> tuple[str, list[dict]]:
    text = data.decode("utf-8", errors="replace")
    paragraphs = _split_paragraphs(text)
    return "\n\n".join(paragraphs), [{"page": 1, "paragraphs": paragraphs}]


def parse_csv(data: bytes) -> tuple[str, list[dict]]:
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
    parsers = {"pdf": parse_pdf, "txt": parse_txt, "csv": parse_csv, "json": parse_json}
    parser = parsers.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported file type: .{ext}")
    return parser(data)
