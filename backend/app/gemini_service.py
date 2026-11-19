import os
import re
import base64
import json
import uuid
import httpx
from typing import Optional, Dict, Any, List
from PIL import Image

from .config import settings
GENERATED_IMAGES_DIR = os.path.join("backend_uploads", "generated_images")
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)

def get_gemini_api_key(user_settings: Optional[Any] = None) -> Optional[str]:
    """
    Resolves the Google Gemini API key from user settings, database, global config, or environment.
    """
    if user_settings:
        if getattr(user_settings, "provider", None) == "gemini" and getattr(user_settings, "api_key", None):
            k = str(user_settings.api_key).strip()
            if k and not k.startswith("demo_"):
                return k
        # Or if api_key starts with AIza or AQ (Google API key pattern)
        if getattr(user_settings, "api_key", None):
            raw_k = str(user_settings.api_key).strip()
            if (raw_k.startswith("AIza") or raw_k.startswith("AQ.")) and not raw_k.startswith("demo_"):
                return raw_k

    # Environment or Config
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or settings.GEMINI_API_KEY
    if env_key and env_key.strip() and not env_key.startswith("demo_"):
        return env_key.strip()

    # Check database persistence
    try:
        import sqlite3
        conn = sqlite3.connect("chatgpt_platform.db")
        c = conn.cursor()
        c.execute("SELECT api_key FROM user_settings WHERE provider='gemini' AND length(api_key) > 10")
        row = c.fetchone()
        conn.close()
        if row and row[0] and not row[0].startswith("demo_"):
            return row[0].strip()
    except Exception:
        pass

    return None


def get_gemini_model_name() -> str:
    """Returns the configured or default Google Gemini vision/text model."""
    return settings.GEMINI_MODEL or "gemini-3.1-flash-lite"


def is_gemini_configured(user_settings: Optional[Any] = None) -> bool:
    return bool(get_gemini_api_key(user_settings))


async def answer_visual_question_with_gemini(
    image_path: str,
    question: str,
    user_settings: Optional[Any] = None,
    history_messages: Optional[List[Dict[str, str]]] = None,
    task_prompt: Optional[str] = None
) -> Optional[str]:
    """
    Executes context-aware Visual Question Answering via Google Gemini Multimodal Vision API.
    Supports multi-turn follow-up questions and specialized task instructions.
    """
    key = get_gemini_api_key(user_settings)
    if not key or not os.path.exists(image_path):
        return None

    try:
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/png" if ext == ".png" else ("image/webp" if ext == ".webp" else "image/jpeg")

        # Active Gemini vision models in priority order
        candidate_models = [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-3.5-flash",
            "gemini-2.5-pro",
            "gemini-pro-latest"
        ]

        full_prompt = (task_prompt.strip() + "\n\n") if task_prompt else ""
        full_prompt += f"User Question: {question.strip()}"

        # Construct contents with conversation history for follow-ups
        contents = []
        if history_messages:
            # Include recent conversation turns (up to 6 messages) to provide multi-turn visual context
            recent_history = history_messages[-6:]
            # If the last message in history is a user message matching this turn, omit it to prevent consecutive user turns
            if recent_history and recent_history[-1].get("role") == "user":
                recent_history = recent_history[:-1]

            for msg in recent_history:
                role = "user" if msg.get("role") == "user" else "model"
                txt = msg.get("content", "").strip()
                # Clean out image markdown tags for history
                clean_txt = re.sub(r'!\[.*?\]\(.*?\)', '', txt).strip()
                if clean_txt:
                    if not contents or contents[-1]["role"] != role:
                        contents.append({
                            "role": role,
                            "parts": [{"text": clean_txt}]
                        })
                    else:
                        contents[-1]["parts"].append({"text": clean_txt})

        # Ensure strict alternating roles before appending final user turn
        while contents and contents[-1]["role"] == "user":
            contents.pop()

        # Append current user visual question with the image
        contents.append({
            "role": "user",
            "parts": [
                {"text": full_prompt},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": b64_data
                    }
                }
            ]
        })

        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.25,
                    "maxOutputTokens": 2048
                }
            }

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
                    else:
                        print(f"Gemini {model} returned HTTP {resp.status_code}: {resp.text[:140]}")
                        if resp.status_code == 429:
                            import asyncio
                            await asyncio.sleep(1.5)
                        continue
            except Exception as e:
                print(f"Gemini {model} VQA attempt notice: {type(e).__name__}: {e}")
                continue

    except Exception as e:
        print(f"Gemini VQA execution error: {e}")

    return None


async def describe_image_with_gemini(
    image_path: str,
    user_settings: Optional[Any] = None
) -> Optional[str]:
    """
    Uses Gemini Multimodal Vision via Google REST API to inspect an image and return a rich semantic description.
    Tries configured GEMINI_MODEL with fallback across active Google Gemini vision models.
    """
    key = get_gemini_api_key(user_settings)
    if not key or not os.path.exists(image_path):
        return None

    try:
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/png" if ext == ".png" else "image/jpeg"

        candidate_models = ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]

        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": "Analyze this image and describe its subject, context, and key details concisely."},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64_data
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 600
                }
            }

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
                    elif resp.status_code in [404, 503]:
                        continue
                    else:
                        break
            except Exception:
                continue
    except Exception as e:
        print(f"Gemini describe_image notice: {e}")
    return None


async def synthesize_modification_prompt(
    image_path: Optional[str],
    user_instruction: str,
    user_settings: Optional[Any] = None,
    context_prompt: Optional[str] = None
) -> str:
    """
    Synthesizes a high-fidelity image generation prompt based on an existing image and
    the user's edit instruction. Uses Gemini Vision if configured, or intelligent heuristic.
    """
    key = get_gemini_api_key(user_settings)
    
    # 1. Try Google Gemini Multimodal Vision if key is available
    if key and image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")

            ext = os.path.splitext(image_path)[1].lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"

            prompt_text = (
                "You are an expert image editing assistant for an AI inpainting system. "
                "The user has uploaded an image and wants to make a specific change. "
                f"User's edit instruction: '{user_instruction}'. "
                "Analyze the image carefully. Then write a concise inpainting prompt describing ONLY what "
                "should appear in the region being modified — not the entire image. "
                "Preserve the original subject's identity, pose, lighting and composition unless explicitly asked to change them. "
                "Focus on the specific modification requested. "
                "Output ONLY the inpainting prompt (1-3 sentences), no commentary, no quotes."
            )

            candidate_models = [get_gemini_model_name(), "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-lite"]
            candidate_models = list(dict.fromkeys(candidate_models))

            for model in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt_text},
                                {
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": b64_data
                                    }
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.5,
                        "maxOutputTokens": 200
                    }
                }

                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post(url, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts and "text" in parts[0]:
                                    res_text = parts[0]["text"].strip().replace('"', '').replace('\n', ' ')
                                    if len(res_text) > 10:
                                        return res_text
                        elif resp.status_code == 404:
                            continue
                        else:
                            break
                except Exception:
                    continue
        except Exception as e:
            print(f"Gemini prompt synthesis notice: {e}")

    # 2. Intelligent Subject & Action Heuristic Fallback
    instruction_clean = user_instruction.strip()
    clean_lower = instruction_clean.lower()
    
    # Strip user command prefixes
    command_prefixes = [
        "i told to modify image by", "i told you to modify image by", "i asked you to modify image by",
        "i told to modify the image by", "i asked you to modify the image by", "modify the image by",
        "modify this image by", "modify image by", "modify photo by", "change the image by",
        "change image by", "edit the image by", "edit image by", "it generated like this, i want",
        "it generated like this", "i want more", "i want", "can you make it", "can you",
        "please make it", "please", "make it look like", "make it", "modify the image as",
        "modify this image so", "modify the image so", "modify image to", "modify to",
        "generate image as", "make the image as", "make them", "show them", "depict them",
        "as they are", "as those"
    ]
    for p in sorted(command_prefixes, key=len, reverse=True):
        if clean_lower.startswith(p):
            instruction_clean = instruction_clean[len(p):].strip()
            clean_lower = instruction_clean.lower()
            break

    # Determine base subjects generically (works for ANY subject, person, object, or environment)
    base_subject = "the subjects in the image"
    if context_prompt and len(context_prompt.strip()) > 2:
        base_subject = context_prompt.strip()
    elif image_path:
        base_name = os.path.splitext(os.path.basename(image_path))[0].lower()
        base_name = re.sub(r'^(?:user|gen|filt|mod|inpaint|removed)_[a-f0-9]+_', '', base_name)
        base_name = re.sub(r'[_\-]+', ' ', base_name).strip()
        if len(base_name) > 2 and not base_name.isdigit():
            base_subject = base_name

    # 1. Object Addition
    if clean_lower.startswith("add ") or clean_lower.startswith("adding ") or " with a " in clean_lower:
        added_item = instruction_clean
        if clean_lower.startswith("add ") or clean_lower.startswith("adding "):
            added_item = instruction_clean.split(" ", 1)[1].strip()
        return (
            f"A realistic, authentic photograph of {base_subject} with {added_item}, "
            f"natural daylight, authentic textures, matching depth-of-field, sharp focus, taken with a DSLR camera, no CGI, no 3D render"
        )

    # 2. Object Removal
    if any(k in clean_lower for k in ["remove ", "removing ", "delete ", "erase ", "take away ", "get rid of "]):
        return (
            f"A realistic, authentic photograph of {base_subject} with seamless background reconstruction, "
            f"natural lighting, clean unblemished surfaces, sharp focus, taken with a DSLR camera"
        )

    # 3. Background Modification
    if any(k in clean_lower for k in ["background", "backdrop", "setting", "environment", "put in ", "place in "]):
        return (
            f"A realistic photograph of {base_subject} in {instruction_clean}, "
            f"natural environmental lighting, authentic atmospheric perspective, sharp focus, DSLR camera"
        )

    # 4. Natural / Realistic Photography Request
    if any(k in clean_lower for k in ["natural", "naturally", "realistic", "real", "lifelike", "authentic", "photo", "dslr"]):
        return (
            f"A realistic, authentic candid photograph of {base_subject}, "
            f"natural lighting, authentic textures and surface detail, taken with a DSLR camera, "
            f"Canon EOS R5 85mm f/1.4 lens, sharp focus, candid real life photography, no CGI, no 3D render, no plastic look"
        )

    # 5. General Action / Modification
    return (
        f"A realistic photograph of {base_subject} {instruction_clean}, "
        f"authentic textures, natural lighting, sharp focus, DSLR quality, no CGI, no 3D render"
    )


async def generate_image_with_imagen(
    prompt: str,
    user_settings: Optional[Any] = None,
    user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Attempts to generate an image using Google's Imagen 3 API if a Gemini API key is configured.
    Falls back gracefully if not available.
    """
    key = get_gemini_api_key(user_settings)
    if not key:
        return None

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={key}"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1",
            "outputMimeType": "image/jpeg"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                predictions = data.get("predictions", [])
                if predictions and "bytesBase64Encoded" in predictions[0]:
                    b64_img = predictions[0]["bytesBase64Encoded"]
                    img_bytes = base64.b64decode(b64_img)
                    
                    filename = f"imagen_{uuid.uuid4().hex[:10]}.jpg"
                    local_path = os.path.join(GENERATED_IMAGES_DIR, filename)
                    with open(local_path, "wb") as f:
                        f.write(img_bytes)

                    return {
                        "image_url": f"/api/images/{filename}",
                        "local_path": local_path,
                        "filename": filename,
                        "model": "Google Imagen 3 (imagen-3.0-generate-002)",
                        "markdown": (
                            f"\n\n![{prompt}](/api/images/{filename})\n\n"
                            f"**Prompt:** *{prompt}*\n"
                            f"**Resolution:** 1024×1024 • **Model:** Google Imagen 3\n\n"
                            f"[📥 Download Image](/api/images/{filename})"
                        )
                    }
    except Exception as e:
        print(f"Imagen 3 API invocation notice: {e}")

    return None
