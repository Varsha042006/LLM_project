import re
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import io

from ..database import get_db
from ..models import User, Chat, Message
from ..auth import get_current_user
from ..document_export_service import (
    generate_pdf,
    generate_docx,
    generate_markdown,
    generate_txt,
    extract_document_title
)

router = APIRouter(prefix="/api/export", tags=["Document Export"])


class DocumentExportRequest(BaseModel):
    title: Optional[str] = "Document"
    content: str
    format: str = "pdf" # pdf, docx, md, txt


def sanitize_filename(name: str, fallback: str = "Document") -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', '', name).strip().replace(" ", "_")
    return cleaned[:60] if cleaned else fallback


@router.post("/document")
def export_document_content(
    req: DocumentExportRequest,
    user: User = Depends(get_current_user)
):
    """
    Dynamically generates and downloads a professional PDF, Word DOCX,
    Markdown, or Plain Text document from AI-generated content.
    """
    fmt = req.format.lower().strip()
    doc_title = extract_document_title(req.content, req.title or "VYNEXA_Document")
    safe_name = sanitize_filename(doc_title, "VYNEXA_Document")

    if fmt == "pdf":
        try:
            pdf_bytes = generate_pdf(doc_title, req.content)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}.pdf"',
                    "Access-Control-Expose-Headers": "Content-Disposition"
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    elif fmt == "docx":
        try:
            docx_bytes = generate_docx(doc_title, req.content)
            return Response(
                content=docx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}.docx"',
                    "Access-Control-Expose-Headers": "Content-Disposition"
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DOCX generation failed: {e}")

    elif fmt in ["md", "markdown"]:
        md_text = generate_markdown(doc_title, req.content)
        return Response(
            content=md_text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}.md"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    elif fmt in ["txt", "text"]:
        txt_text = generate_txt(doc_title, req.content)
        return Response(
            content=txt_text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}.txt"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{fmt}'. Choose from: pdf, docx, md, txt"
        )


@router.get("/chat/{chat_id}")
def export_full_chat_history(
    chat_id: str,
    format: str = Query("pdf", description="Format: pdf, docx, md, txt"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exports an entire chat thread with user and assistant dialogue into a compiled document.
    """
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    messages = db.query(Message).filter(Message.chat_id == chat_id, Message.user_id == user.id).order_by(Message.created_at.asc()).all()
    if not messages:
        raise HTTPException(status_code=400, detail="Chat has no messages to export.")

    # Compile chat into single structured document
    doc_title = chat.title or "VYNEXA_Chat_Export"
    compiled_parts = [f"# {doc_title}\n\n"]
    for m in messages:
        role_label = "**User**" if m.role == "user" else "**VYNEXA AI**"
        compiled_parts.append(f"### {role_label}\n{m.content}\n\n")

    compiled_content = "".join(compiled_parts)
    safe_name = sanitize_filename(doc_title, "Chat_Export")

    fmt = format.lower().strip()
    if fmt == "pdf":
        pdf_bytes = generate_pdf(doc_title, compiled_content)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'}
        )
    elif fmt == "docx":
        docx_bytes = generate_docx(doc_title, compiled_content)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.docx"'}
        )
    elif fmt in ["md", "markdown"]:
        md_text = generate_markdown(doc_title, compiled_content)
        return Response(
            content=md_text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.md"'}
        )
    else:
        txt_text = generate_txt(doc_title, compiled_content)
        return Response(
            content=txt_text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.txt"'}
        )
