import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Document
from ..schemas import DocumentResponse
from ..auth import get_current_user
from ..rag_service import (
    get_user_upload_dir,
    extract_text_from_file,
    chunk_text,
    save_user_chunks,
    remove_document_chunks
)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    docs = db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).all()
    return [DocumentResponse.from_orm(d) for d in docs]


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accepts and parses PDF, DOCX, TXT, CSV, and JSON files.
    Chunks text and stores passages in the user's isolated RAG knowledge base.
    """
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".pdf", ".docx", ".txt", ".csv", ".json", ".md"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed types: {', '.join(allowed_exts)}"
        )

    user_dir = get_user_upload_dir(user.id)
    save_path = os.path.join(user_dir, filename)

    # Read content
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    # Check if documents with this filename already exist for the user; if so, replace them
    existing_docs = db.query(Document).filter(Document.user_id == user.id, Document.filename == filename).all()
    if existing_docs:
        for ex in existing_docs:
            db.delete(ex)
        remove_document_chunks(user.id, filename)
        db.commit()

    # Extract text and chunk
    pages_data = extract_text_from_file(save_path, filename)
    chunks = chunk_text(pages_data, filename)

    # Save to user's RAG chunk store
    if chunks:
        save_user_chunks(user.id, chunks)

    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        filename=filename,
        file_type=ext,
        file_path=save_path,
        file_size=len(contents),
        num_chunks=len(chunks)
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return DocumentResponse.from_orm(doc)


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    remove_document_chunks(user.id, doc.filename)
    db.delete(doc)
    db.commit()
    return {"status": "ok", "message": f"Document '{doc.filename}' deleted."}


@router.delete("")
def clear_all_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    docs = db.query(Document).filter(Document.user_id == user.id).all()
    for d in docs:
        if os.path.exists(d.file_path):
            try:
                os.remove(d.file_path)
            except Exception:
                pass
        remove_document_chunks(user.id, d.filename)
        db.delete(d)
    db.commit()
    return {"status": "ok", "message": "All documents cleared from knowledge base."}

