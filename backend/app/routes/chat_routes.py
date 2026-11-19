import os
import re
import json
import uuid
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from PIL import Image
from ..database import get_db
from ..models import User, Chat, Message, UserSettings
from ..schemas import (
    ChatCreateRequest,
    ChatUpdateRequest,
    ChatResponse,
    ChatDetailResponse,
    MessageResponse,
    ChatStreamRequest,
    ImageUploadResponse,
    ImageEditRequest,
    ImageEditResponse,
    MessageFeedbackRequest
)
from ..auth import get_current_user
from ..llm_service import stream_chat_completion, AVAILABLE_HOSTED_MODELS, resolve_conversational_intent
from ..rag_service import retrieve_relevant_chunks, build_rag_context
from ..image_router import (
    ImageEditRouter,
    ImageLineageManager,
    MaskProcessor,
    PixelCompositor
)
from ..image_service import (
    detect_image_prompt,
    generate_image_asset,
    detect_image_modification,
    is_explicit_image_edit,
    apply_image_filter,
    GENERATED_IMAGES_DIR
)
from ..vision_service import (
    inspect_image_properties,
    call_cloud_vision_api,
    generate_synthesized_vision_report,
    execute_visual_qa,
    classify_vision_task
)
from ..gemini_service import (
    get_gemini_api_key,
    is_gemini_configured,
    describe_image_with_gemini,
    synthesize_modification_prompt,
    generate_image_with_imagen
)

router = APIRouter(prefix="/api", tags=["Chat"])


@router.post("/upload/image", response_model=ImageUploadResponse)
async def upload_chat_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    """
    Accepts and stores user-uploaded images for visual question answering and modifications.
    """
    filename = file.filename or "upload.jpg"
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type '{ext}'. Allowed types: {', '.join(allowed_exts)}"
        )

    clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
    saved_filename = f"user_{uuid.uuid4().hex[:8]}_{clean_name}"
    save_path = os.path.join(GENERATED_IMAGES_DIR, saved_filename)

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    try:
        with Image.open(save_path) as img:
            width, height = img.size
            format_name = img.format or "JPEG"
    except Exception:
        width, height = 1024, 1024
        format_name = "JPEG"

    return ImageUploadResponse(
        url=f"/api/images/{saved_filename}",
        filename=saved_filename,
        width=width,
        height=height,
        format=format_name,
        size=len(contents)
    )


@router.post("/image/edit", response_model=ImageEditResponse)
async def edit_image_endpoint(
    req: ImageEditRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dedicated endpoint for universal mask-based inpainting, object removal,
    background modification, style transformation, and deterministic filters.
    """
    filename = os.path.basename(req.image_url)
    local_path = os.path.join(GENERATED_IMAGES_DIR, filename)
    if not os.path.exists(local_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source image '{filename}' not found on server."
        )

    res = await ImageEditRouter.route_and_execute(
        instruction=req.instruction,
        image_path=local_path,
        mask_data=req.mask_data,
        chat_id=req.chat_id,
        user_id=user.id
    )

    if res.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("markdown") or res.get("error") or "Image edit failed."
        )

    # Persist assistant message in chat if chat_id provided
    if req.chat_id:
        ast_msg = Message(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            chat_id=req.chat_id,
            user_id=user.id,
            role="assistant",
            content=(
                f"✨ **AI Image Edit Completed**\n\n"
                f"![{req.instruction}]({res['image_url']})\n\n"
                f"**Instruction:** *{req.instruction}*\n"
                f"**Operation:** `{res.get('operation', 'edit')}`\n"
                f"**Original:** [{filename}]({req.image_url})\n\n"
                f"[📥 Download Modified Image]({res['image_url']})"
            )
        )
        db.add(ast_msg)
        db.commit()

    return ImageEditResponse(
        status=res.get("status", "success"),
        image_url=res["image_url"],
        original_url=req.image_url,
        operation=res.get("operation", "edit"),
        instruction=req.instruction,
        version=len(ImageLineageManager.get_versions(req.chat_id)) if req.chat_id else 1,
        filename=res.get("filename", filename),
        dimensions=res.get("dimensions", {"width": 1024, "height": 1024}),
        pixel_preservation=res.get("pixel_preservation", "100% outside mask")
    )


@router.get("/image/lineage/{chat_id}")
def get_image_lineage(
    chat_id: str,
    user: User = Depends(get_current_user)
):
    """Returns the multi-turn editing lineage tree for a chat session."""
    versions = ImageLineageManager.get_versions(chat_id)
    return {"chat_id": chat_id, "versions": versions}


@router.get("/models")
def list_available_models():
    """Returns the list of selectable hosted models for the top navbar pill."""
    return AVAILABLE_HOSTED_MODELS


@router.get("/chats", response_model=List[ChatResponse])
def get_user_chats(
    search: Optional[str] = Query(None, description="Search term for chat titles or messages"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Chat).filter(Chat.user_id == user.id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(Chat.title.ilike(term))
    chats = query.order_by(Chat.updated_at.desc()).all()
    
    result = []
    for c in chats:
        msg_count = db.query(Message).filter(Message.chat_id == c.id).count()
        r = ChatResponse.from_orm(c)
        r.message_count = msg_count
        result.append(r)
    return result


@router.post("/chats", response_model=ChatResponse)
def create_chat(
    req: ChatCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = Chat(
        id=f"chat_{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        title=req.title or "New Chat",
        model_name=req.model_name or "llama-3.3-70b-versatile"
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return ChatResponse.from_orm(chat)


@router.get("/chats/{chat_id}", response_model=ChatDetailResponse)
def get_chat_detail(
    chat_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    
    messages = db.query(Message).filter(Message.chat_id == chat_id, Message.user_id == user.id).order_by(Message.created_at.asc()).all()
    return ChatDetailResponse(
        id=chat.id,
        title=chat.title,
        model_name=chat.model_name,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=len(messages),
        messages=[MessageResponse.from_orm(m) for m in messages]
    )


@router.patch("/chats/{chat_id}", response_model=ChatResponse)
def rename_chat(
    chat_id: str,
    req: ChatUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    chat.title = req.title.strip() or "Untitled Chat"
    db.commit()
    db.refresh(chat)
    return ChatResponse.from_orm(chat)


@router.delete("/chats/{chat_id}")
def delete_chat(
    chat_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    db.delete(chat)
    db.commit()
    return {"status": "ok", "message": "Chat deleted successfully."}


@router.post("/chat/stream")
async def chat_stream_endpoint(
    req: ChatStreamRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint.
    Retrieves RAG document chunks, loads conversation history, and streams tokens.
    """
    # Ensure or create chat
    chat = None
    if req.chat_id:
        chat = db.query(Chat).filter(Chat.id == req.chat_id, Chat.user_id == user.id).first()
    
    if not chat:
        # Create new chat automatically
        chat_title = req.message[:32].strip() + ("..." if len(req.message) > 32 else "")
        chat = Chat(
            id=f"chat_{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            title=chat_title or "New Chat",
            model_name=req.model_name or "llama-3.3-70b-versatile"
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # Save user message (with image thumbnail if attached)
    user_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    user_content = req.message
    if req.image_url and req.image_url not in user_content:
        user_content = f"![Attached Image]({req.image_url})\n\n{req.message}"

    user_msg = Message(
        id=user_msg_id,
        chat_id=chat.id,
        user_id=user.id,
        role="user",
        content=user_content
    )
    db.add(user_msg)
    db.commit()

    # Load existing conversation history for multi-turn context
    history_records = db.query(Message).filter(
        Message.chat_id == chat.id,
        Message.user_id == user.id
    ).order_by(Message.created_at.asc()).all()

    # Resolve attached document strictly for this turn or prior turn in this chat
    target_document = getattr(req, "document_name", None)
    if not target_document:
        doc_match = re.search(r'📄\s*\*\*Attached Document:\*\*\s*`([^`]+)`', req.message)
        if doc_match:
            target_document = doc_match.group(1).strip()

    if not target_document and chat.id:
        for h in reversed(history_records):
            if not h.content:
                continue
            h_doc_match = re.search(r'📄\s*\*\*Attached Document:\*\*\s*`([^`]+)`', h.content)
            if h_doc_match:
                target_document = h_doc_match.group(1).strip()
                break

    # RAG Retrieval: Only search when requested and query is not a casual greeting/conversational message
    sources_json = None
    prompt_for_llm = req.message
    retrieved_chunks = []
    
    is_conversational = resolve_conversational_intent(req.message) is not None

    if req.use_rag and not is_conversational:
        retrieved_chunks = retrieve_relevant_chunks(user.id, req.message, top_k=6, target_document=target_document)
        if retrieved_chunks:
            prompt_for_llm, citations = build_rag_context(req.message, retrieved_chunks)
            sources_json = json.dumps(citations)

    messages_payload = []
    for h in history_records[:-1]: # exclude the user message we just saved to avoid duplication
        messages_payload.append({"role": h.role, "content": h.content})
    messages_payload.append({"role": "user", "content": prompt_for_llm})

    # Prepare assistant message record and pre-fetch settings to prevent DetachedInstanceError
    assistant_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    user_id_val = user.id
    chat_id_val = chat.id
    user_settings_obj = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    model_name_val = req.model_name or chat.model_name
    temperature_val = req.temperature or 0.7
    top_p_val = req.top_p or 0.9
    system_prompt_val = req.system_prompt
    bind_engine = db.get_bind()

    has_explicit_image = bool(req.image_url)

    # -------------------------------------------------------------
    # 1. New Image Generation Request (e.g. "boy", "generate image of boy", "photo of a boy")
    # -------------------------------------------------------------
    new_img_prompt = detect_image_prompt(req.message)
    if new_img_prompt and not (has_explicit_image and is_explicit_image_edit(req.message)):
        async def sse_image_stream():
            meta_event = {
                "type": "meta",
                "chat_id": chat_id_val,
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_msg_id,
                "sources": []
            }
            yield f"data: {json.dumps(meta_event)}\n\n"

            intro_chunk = f"🎨 **Initializing AI Image Generation...**\n\n*Crafting high-resolution FLUX.1 Diffusion photograph for:* **\"{new_img_prompt}\"**\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': intro_chunk})}\n\n"

            # Execute photorealistic diffusion generation
            img_result = await generate_image_asset(new_img_prompt, user_id=user_id_val)

            if img_result.get("status") == "error" or not img_result.get("image_url"):
                image_card = f"\n\n{img_result.get('markdown', '⚠️ Image generation limit reached. Please wait a moment and try again.')}\n"
            else:
                # Record in lineage for multi-turn editing
                if chat_id_val:
                    ImageLineageManager.record_version(
                        chat_id=chat_id_val,
                        image_url=img_result['image_url'],
                        operation="text_to_image",
                        instruction=new_img_prompt
                    )

                image_card = (
                    f"\n\n![{new_img_prompt}]({img_result['image_url']})\n\n"
                    f"**Prompt:** *{new_img_prompt}*\n"
                    f"**Resolution:** 1024×1024 • **Model:** {img_result.get('model', 'Photorealistic Diffusion')}\n\n"
                    f"[📥 Download Full Resolution Image]({img_result['image_url']})"
                )
            yield f"data: {json.dumps({'type': 'token', 'content': image_card})}\n\n"

            full_content = intro_chunk + image_card
            with Session(bind_engine) as save_db:
                ast_msg = Message(
                    id=assistant_msg_id,
                    chat_id=chat_id_val,
                    user_id=user_id_val,
                    role="assistant",
                    content=full_content,
                    sources=None
                )
                save_db.add(ast_msg)
                c_update = save_db.query(Chat).filter(Chat.id == chat_id_val).first()
                if c_update and (c_update.title == "New Chat" or "generate image" in c_update.title.lower()):
                    c_update.title = f"🎨 {new_img_prompt[:26]}"
                save_db.commit()

            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg_id})}\n\n"

        return StreamingResponse(
            sse_image_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    # Resolve context image (either explicitly attached or recent image in conversation / lineage)
    target_image_url = req.image_url
    target_image_prompt = None

    if not target_image_url and chat_id_val:
        target_image_url = ImageLineageManager.get_latest_image_url(chat_id_val)

    if not target_image_url:
        for h in reversed(history_records):
            if not h.content:
                continue
            img_match = re.search(r'!\[(.*?)\]\((/api/images/[^\)]+)\)', h.content)
            if img_match:
                target_image_url = img_match.group(2)
                alt_txt = img_match.group(1)
                if alt_txt and alt_txt != "Attached Image":
                    target_image_prompt = alt_txt
                prompt_match = re.search(r'\*\*Prompt:\*\*\s*\*([^\*]+)\*', h.content)
                if prompt_match:
                    target_image_prompt = prompt_match.group(1).strip()
                break

    target_local_path = None
    if target_image_url:
        target_local_path = os.path.join(GENERATED_IMAGES_DIR, os.path.basename(target_image_url))

    # -------------------------------------------------------------
    # 2. Image Modification / Changes / Filters Check
    # -------------------------------------------------------------
    mod_intent = detect_image_modification(
        req.message,
        has_explicit_image=has_explicit_image,
        context_prompt=target_image_prompt
    )
    if mod_intent and target_image_url and target_local_path and os.path.exists(target_local_path):
        async def sse_image_mod_stream():
            meta_event = {
                "type": "meta",
                "chat_id": chat_id_val,
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_msg_id,
                "sources": []
            }
            yield f"data: {json.dumps(meta_event)}\n\n"

            desc = mod_intent.get('description', 'AI Image Edit')
            intro = f"✨ **Executing Image Edit with ImageEditRouter...**\n\n*Applying {desc}*\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': intro})}\n\n"

            # Execute via Universal ImageEditRouter
            edit_res = await ImageEditRouter.route_and_execute(
                instruction=req.message,
                image_path=target_local_path,
                chat_id=chat_id_val,
                user_id=user_id_val,
                context_prompt=target_image_prompt
            )

            if edit_res.get("status") == "error":
                result_card = f"\n\n{edit_res.get('markdown', '⚠️ The requested image modification could not be completed.')}\n"
            else:
                op_title = edit_res.get('operation', 'edit').replace('_', ' ').title()
                result_card = (
                    f"\n\n![{edit_res.get('prompt', req.message)}]({edit_res['image_url']})\n\n"
                    f"**Operation:** `{op_title}` • **Instruction:** *{req.message}*\n"
                    f"**Original Image:** [{os.path.basename(target_image_url)}]({target_image_url})\n"
                    f"**Engine:** LocalGPT Universal Router • **Pixel Preservation:** 100% Unmasked Pixels Preserved\n\n"
                    f"[📥 Download Modified Image]({edit_res['image_url']})"
                )

            yield f"data: {json.dumps({'type': 'token', 'content': result_card})}\n\n"

            full_content = intro + result_card
            with Session(bind_engine) as save_db:
                ast_msg = Message(
                    id=assistant_msg_id,
                    chat_id=chat_id_val,
                    user_id=user_id_val,
                    role="assistant",
                    content=full_content,
                    sources=None
                )
                save_db.add(ast_msg)
                c_update = save_db.query(Chat).filter(Chat.id == chat_id_val).first()
                if c_update and c_update.title == "New Chat":
                    c_update.title = f"🎨 Mod: {desc[:22]}"
                save_db.commit()

            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg_id})}\n\n"

        return StreamingResponse(
            sse_image_mod_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
        )

    # -------------------------------------------------------------
    # 2. Context-Aware Visual Question Answering (VQA)
    # -------------------------------------------------------------
    vision_keywords = [
        "what is", "what are", "describe", "explain", "look", "see", "color", "palette", "resolution",
        "dimension", "size", "in this image", "in this picture", "in the picture", "about the image",
        "about this image", "tell me about", "analyze", "inspect", "detail", "quality", "what do you see",
        "who is", "what breed", "identify", "how many", "count", "error", "code", "architecture",
        "workflow", "diagram", "flowchart", "summarize", "purpose", "why", "how", "component",
        "database", "frontend", "backend", "step", "fix", "output", "trace"
    ]
    # Check if message is a genuine vision query or empty attachment, including multi-turn follow-ups
    is_vision_query = (
        bool(req.image_url) or
        (bool(target_image_url) and (
            any(k in req.message.lower() for k in vision_keywords) or
            len(history_records) <= 6
        ))
    )

    if is_vision_query and target_image_url and target_local_path and os.path.exists(target_local_path):
        async def sse_vision_stream():
            meta_event = {
                "type": "meta",
                "chat_id": chat_id_val,
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_msg_id,
                "sources": []
            }
            yield f"data: {json.dumps(meta_event)}\n\n"

            # Execute context-aware visual question answering with exact user query & task
            clean_question = req.message.strip() if req.message.strip() else "Explain this image."
            vqa_res = await execute_visual_qa(
                image_path=target_local_path,
                question=clean_question,
                user_settings=user_settings_obj,
                requested_model=model_name_val,
                history_messages=messages_payload,
                context_prompt=target_image_prompt
            )
            report_text = vqa_res["answer"]

            # Stream report in natural word chunks
            accumulated_tokens = []
            words = report_text.split(" ")
            for i, word in enumerate(words):
                token_chunk = word + (" " if i < len(words) - 1 else "")
                accumulated_tokens.append(token_chunk)
                yield f"data: {json.dumps({'type': 'token', 'content': token_chunk})}\n\n"
                await asyncio.sleep(0.008)

            full_content = "".join(accumulated_tokens)
            with Session(bind_engine) as save_db:
                ast_msg = Message(
                    id=assistant_msg_id,
                    chat_id=chat_id_val,
                    user_id=user_id_val,
                    role="assistant",
                    content=full_content,
                    sources=None
                )
                save_db.add(ast_msg)
                c_update = save_db.query(Chat).filter(Chat.id == chat_id_val).first()
                if c_update and c_update.title == "New Chat":
                    c_update.title = f"👁️ Image: {req.message[:22]}"
                save_db.commit()

            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg_id})}\n\n"

        return StreamingResponse(
            sse_vision_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
        )


    async def sse_event_stream():
        accumulated_text = []

        # Yield metadata event with chat_id and sources first
        meta_event = {
            "type": "meta",
            "chat_id": chat_id_val,
            "user_message_id": user_msg_id,
            "assistant_message_id": assistant_msg_id,
            "sources": json.loads(sources_json) if sources_json else []
        }
        yield f"data: {json.dumps(meta_event)}\n\n"

        # Stream tokens from hosted LLM service
        async for token in stream_chat_completion(
            messages=messages_payload,
            user_settings=user_settings_obj,
            model_name=model_name_val,
            temperature=temperature_val,
            top_p=top_p_val,
            system_prompt=system_prompt_val,
            user_id=user_id_val,
            user_chunks=retrieved_chunks
        ):
            accumulated_text.append(token)
            chunk_event = {
                "type": "token",
                "content": token
            }
            yield f"data: {json.dumps(chunk_event)}\n\n"

        # Save assistant message in database
        full_assistant_content = "".join(accumulated_text).strip()
        with Session(bind_engine) as save_db:
            ast_msg = Message(
                id=assistant_msg_id,
                chat_id=chat_id_val,
                user_id=user_id_val,
                role="assistant",
                content=full_assistant_content,
                sources=sources_json
            )
            save_db.add(ast_msg)
            # Update chat timestamp
            c_update = save_db.query(Chat).filter(Chat.id == chat_id_val).first()
            if c_update and c_update.title == "New Chat":
                c_update.title = req.message[:30]
            save_db.commit()

        done_event = {
            "type": "done",
            "message_id": assistant_msg_id,
            "chat_id": chat_id_val
        }
        yield f"data: {json.dumps(done_event)}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/chat/feedback")
def set_message_feedback(
    req: MessageFeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msg = db.query(Message).filter(Message.id == req.message_id, Message.user_id == user.id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found.")
    msg.feedback = req.feedback
    db.commit()
    return {"status": "ok", "message_id": msg.id, "feedback": msg.feedback}
