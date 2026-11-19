"""
Document processor module for LocalGPT Pro.
Supports PDF, TXT, and DOCX parsing and text chunking with metadata.
"""

import os
from typing import List, Dict, Any


def extract_text_from_txt(file_path: str) -> str:
    """Extracts text from a plaintext file with multiple encoding fallbacks."""
    for enc in ["utf-8", "latin-1", "utf-16", "cp1252"]:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ""


def extract_text_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Extracts text per page from a PDF file using pypdf."""
    from pypdf import PdfReader
    pages_text = []
    reader = PdfReader(file_path)
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append({"page": idx + 1, "text": text.strip()})
    return pages_text


def extract_text_from_docx(file_path: str) -> str:
    """Extracts text from a DOCX file using python-docx."""
    from docx import Document
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                full_text.append(row_text)
    return "\n\n".join(full_text)


def process_document_file(file_path: str, filename: str) -> List[Dict[str, Any]]:
    """
    Parses a document file based on extension and returns a list of chunks with source metadata.
    Supported extensions: .pdf, .txt, .docx, .md, .csv
    """
    ext = os.path.splitext(filename)[1].lower()
    raw_pages: List[Dict[str, Any]] = []

    if ext == ".pdf":
        raw_pages = extract_text_from_pdf(file_path)
    elif ext == ".docx":
        text = extract_text_from_docx(file_path)
        raw_pages = [{"page": 1, "text": text}]
    elif ext in [".txt", ".md", ".csv", ".json", ".py"]:
        text = extract_text_from_txt(file_path)
        raw_pages = [{"page": 1, "text": text}]
    else:
        # Generic text attempt
        text = extract_text_from_txt(file_path)
        raw_pages = [{"page": 1, "text": text}]

    # Chunk text
    return chunk_document_pages(raw_pages, filename=filename)


def chunk_document_pages(
    pages: List[Dict[str, Any]],
    filename: str,
    chunk_size: int = 450,
    chunk_overlap: int = 80
) -> List[Dict[str, Any]]:
    """
    Splits page texts into overlapping chunks, tracking document filename and page numbers.
    """
    chunks = []
    chunk_idx = 0

    for p in pages:
        page_num = p.get("page", 1)
        text = p.get("text", "")
        if not text:
            continue

        # Split into words/paragraphs
        words = text.split()
        if not words:
            continue

        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_content = " ".join(chunk_words)

            chunks.append({
                "chunk_id": f"{filename}_chunk_{chunk_idx}",
                "chunk_index": chunk_idx,
                "filename": filename,
                "page": page_num,
                "content": chunk_content,
                "char_length": len(chunk_content),
                "word_count": len(chunk_words)
            })
            chunk_idx += 1

            if end >= len(words):
                break
            start += max(1, chunk_size - chunk_overlap)

    return chunks

