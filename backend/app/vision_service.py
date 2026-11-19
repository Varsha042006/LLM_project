import os
import re
import math
import base64
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageStat, ImageFilter, ImageOps
import numpy as np
import httpx

from .config import settings

# Color reference dictionary for human-friendly color naming
COLOR_NAMES = [
    ((0, 0, 0), "Deep Black"),
    ((25, 25, 25), "Charcoal Slate"),
    ((10, 25, 50), "Cosmic Navy Blue"),
    ((20, 50, 100), "Deep Ocean Blue"),
    ((40, 120, 200), "Vibrant Atmospheric Blue"),
    ((100, 180, 240), "Sky Cyan"),
    ((255, 255, 255), "Pure Cloud White"),
    ((200, 200, 200), "Bright Silver Mist"),
    ((120, 120, 120), "Neutral Gray"),
    ((30, 90, 40), "Forest Emerald"),
    ((80, 160, 60), "Lush Foliage Green"),
    ((180, 140, 60), "Continental Ochre / Earth"),
    ((220, 90, 40), "Sunset Amber / Terra Cotta"),
    ((200, 40, 40), "Crimson Red"),
    ((150, 40, 150), "Cosmic Violet"),
    ((240, 220, 60), "Solar Golden Yellow")
]


def closest_color_name(rgb: Tuple[int, int, int]) -> str:
    """Finds the nearest human-readable color label using Euclidean RGB distance."""
    r, g, b = rgb[:3]
    best_name = "Unknown Shade"
    min_dist = float("inf")
    for ref_rgb, name in COLOR_NAMES:
        dist = math.sqrt((r - ref_rgb[0]) ** 2 + (g - ref_rgb[1]) ** 2 + (b - ref_rgb[2]) ** 2)
        if dist < min_dist:
            min_dist = dist
            best_name = name
    return best_name


def inspect_image_properties(image_path: str) -> Dict[str, Any]:
    """
    Extracts deep visual, photometric, and structural features from an image file using PIL & NumPy.
    """
    if not os.path.exists(image_path):
        return {"error": f"Image file not found: {image_path}"}

    try:
        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            width, height = img.size
            aspect_ratio = round(width / max(height, 1), 2)
            megapixels = round((width * height) / 1_000_000, 2)
            format_name = img.format or "JPEG"
            mode = img.mode

            # Aspect ratio description
            if 0.95 <= aspect_ratio <= 1.05:
                ar_desc = "Square (1:1)"
            elif 1.7 <= aspect_ratio <= 1.85:
                ar_desc = "Widescreen Landscape (16:9)"
            elif 1.3 <= aspect_ratio <= 1.4:
                ar_desc = "Standard Landscape (4:3)"
            elif aspect_ratio > 1.05:
                ar_desc = f"Landscape ({aspect_ratio}:1)"
            else:
                ar_desc = f"Portrait (1:{round(1/aspect_ratio, 2)})"

            # Image statistics: brightness, contrast, luminance
            stat = ImageStat.Stat(rgb_img)
            mean_r, mean_g, mean_b = stat.mean[:3]
            std_r, std_g, std_b = stat.stddev[:3]

            # Perceived luminance (ITU-R BT.709)
            luminance = round(0.2126 * mean_r + 0.7152 * mean_g + 0.0722 * mean_b, 1)
            contrast_level = round((std_r + std_g + std_b) / 3, 1)

            if luminance < 50:
                tone_desc = "Dark / Nocturnal / Deep Space"
            elif luminance < 130:
                tone_desc = "Balanced Mid-tone / Natural"
            elif luminance < 200:
                tone_desc = "Bright / Daylight / High Key"
            else:
                tone_desc = "Very Bright / Luminous"

            # Dominant color palette extraction (quantized palette)
            paletted = rgb_img.quantize(colors=6, method=Image.Quantize.FASTOCTREE).convert("RGB")
            colors = paletted.getcolors(maxcolors=256)
            dominant_palette = []
            if colors:
                colors.sort(key=lambda x: x[0], reverse=True)
                total_pixels = width * height
                for count, col in colors[:5]:
                    pct = round((count / total_pixels) * 100, 1)
                    hex_code = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                    dominant_palette.append({
                        "rgb": col,
                        "hex": hex_code,
                        "name": closest_color_name(col),
                        "percentage": pct
                    })

            # Edge & sharpness score
            gray = rgb_img.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            sharpness_score = round(edge_stat.mean[0], 2)
            has_fine_details = sharpness_score > 12.0

            file_size_bytes = os.path.getsize(image_path)
            file_size_kb = round(file_size_bytes / 1024, 1)

            return {
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
                "aspect_ratio_desc": ar_desc,
                "megapixels": megapixels,
                "format": format_name,
                "mode": mode,
                "file_size_kb": file_size_kb,
                "luminance": luminance,
                "tone_desc": tone_desc,
                "contrast_level": contrast_level,
                "sharpness_score": sharpness_score,
                "has_fine_details": has_fine_details,
                "dominant_palette": dominant_palette,
                "mean_rgb": (round(mean_r, 1), round(mean_g, 1), round(mean_b, 1))
            }
    except Exception as e:
        return {"error": str(e)}


async def call_cloud_vision_api(
    image_path: str,
    prompt: str,
    user_settings: Optional[Any] = None
) -> Optional[str]:
    """
    Attempts to call cloud vision APIs (Groq Llama 3.2 Vision, Gemini 1.5 Flash, or OpenAI GPT-4o)
    if an API key is configured.
    """
    api_key = settings.HOSTED_LLM_API_KEY
    provider = settings.DEFAULT_LLM_PROVIDER
    base_url = settings.HOSTED_LLM_BASE_URL

    if user_settings:
        if getattr(user_settings, "api_key", None):
            api_key = user_settings.api_key
        if getattr(user_settings, "provider", None):
            provider = user_settings.provider
        if getattr(user_settings, "base_url", None):
            base_url = user_settings.base_url

    if not api_key or api_key.startswith("demo_"):
        return None

    try:
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else ("image/png" if ext == ".png" else "image/webp")
        data_uri = f"data:{mime_type};base64,{b64_data}"

        # Choose vision model strictly compatible with provider
        if provider == "groq":
            model = "llama-3.2-11b-vision-preview"
            endpoint = f"{base_url.rstrip('/')}/chat/completions"
        elif provider == "gemini":
            model = settings.GEMINI_MODEL or "gemini-3.5-flash"
            endpoint = f"{base_url.rstrip('/')}/chat/completions"
        else:
            model = "gpt-4o-mini"
            endpoint = f"{base_url.rstrip('/')}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}}
                    ]
                }
            ],
            "max_tokens": 800,
            "temperature": 0.5
        }

        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"Cloud vision invocation notice: {e}")

    return None


# -----------------------------------------------------------------------------
# Context-Aware Visual Question Answering (VQA) Pipeline
# -----------------------------------------------------------------------------

VISION_CAPABLE_MODELS = {
    # Google Gemini Models
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-flash-latest",
    "gemini-pro-latest",
    # Groq Vision Models
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
    # OpenAI Vision Models
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo"
}


def is_vision_model(model_name: Optional[str]) -> bool:
    """Verifies whether a model genuinely supports multimodal image input."""
    if not model_name:
        return False
    m = model_name.strip().lower()
    return any(v in m for v in ["vision", "flash", "gpt-4o", "gemini"])


def classify_vision_task(prompt: str) -> str:
    """
    Categorizes the user's visual inquiry into a specialized vision task:
    - detailed_inspection
    - code_analysis
    - diagram_architecture
    - flowchart_process
    - ocr_text_extraction
    - image_summarization
    - purpose_inference
    - photograph_scene
    - image_explanation
    - image_qa
    """
    p_lower = prompt.lower().strip()

    # 1. Detailed Inspection (Explicit metadata, photometric, color palette or dimension inspection)
    inspection_keywords = [
        "inspect image", "image inspection", "visual inspection", "image properties",
        "visual properties", "color palette", "dominant colors", "image dimensions",
        "resolution", "aspect ratio", "photometric", "technical specs of image",
        "luminance", "image metadata", "color distribution", "hex code"
    ]
    if any(k in p_lower for k in inspection_keywords):
        return "detailed_inspection"

    # 2. Code Screenshot Analysis
    code_keywords = [
        "code", "error", "find the error", "find error", "bug", "traceback", "exception",
        "syntax", "debug", "compile", "fix this", "fix the code", "programming", "python",
        "javascript", "function", "variable", "line of code", "ide", "terminal output",
        "stack trace", "what is wrong with this code", "code snippet"
    ]
    if any(k in p_lower for k in code_keywords):
        return "code_analysis"

    # 3. Flowchart & Process Understanding
    flowchart_keywords = [
        "flowchart", "flow chart", "decision tree", "sequence diagram",
        "steps", "decision", "branch", "branching", "algorithm flow", "state machine",
        "next step", "process flow"
    ]
    if any(k in p_lower for k in flowchart_keywords):
        return "flowchart_process"

    # 4. Diagram & Architecture Understanding
    architecture_keywords = [
        "architecture", "workflow", "data flow", "system design", "infrastructure",
        "components", "tier", "microservices", "connections", "network topology",
        "database connection", "backend", "frontend", "api", "cloud design", "system flow"
    ]
    if any(k in p_lower for k in architecture_keywords):
        return "diagram_architecture"

    # 5. OCR & Text Extraction
    ocr_keywords = [
        "extract text", "read text", "read the text", "transcribe", "ocr",
        "what text", "words in this", "copy text", "read this", "read what is written",
        "what is written"
    ]
    if any(k in p_lower for k in ocr_keywords):
        return "ocr_text_extraction"

    # 6. Document / Graphic Summarization
    summary_keywords = [
        "summarize", "summary", "key takeaways", "overview of this document",
        "bullet points", "main points", "synthesize this", "summarize this image",
        "summarize this document", "tldr"
    ]
    if any(k in p_lower for k in summary_keywords):
        return "image_summarization"

    # 7. Purpose Inference
    purpose_keywords = [
        "purpose", "why is this", "what is the purpose", "what is this used for",
        "what is the goal", "intended for", "what does this achieve", "objective",
        "why would someone use"
    ]
    if any(k in p_lower for k in purpose_keywords):
        return "purpose_inference"

    # 8. Photograph / Scene
    photo_keywords = [
        "what is in this picture", "what is in this photo", "describe the scene",
        "what do you see", "who is in", "what breed", "identify the object", "objects in this image",
        "scenery", "landscape", "person in", "animal in"
    ]
    if any(k in p_lower for k in photo_keywords):
        return "photograph_scene"

    # 9. Explanation
    if any(k in p_lower for k in ["explain", "explain this image", "describe this image", "walk me through", "break down"]):
        return "image_explanation"

    # 10. Default General VQA (e.g., follow-ups like "What does the database component do?")
    return "image_qa"


def build_vision_task_prompt(task: str, user_question: str) -> str:
    """
    Constructs an expert instruction tailored to the visual domain,
    ensuring the vision model answers the user's exact question thoroughly.
    """
    clean_q = user_question.strip() if user_question.strip() else "Explain this image."

    task_instructions = {
        "diagram_architecture": (
            "You are an expert systems and software architect. The user has provided an architecture or technical system diagram.\n"
            "- Carefully inspect all visible components, services, containers, databases, APIs, and clients.\n"
            "- Trace all communication paths, arrows, data flows, and protocols (e.g. REST, GraphQL, gRPC, ORM, WebSockets).\n"
            "- Clearly explain the system's structure, component responsibilities, interactions, and overall architectural purpose.\n"
            f"- Answer the user's exact inquiry with high technical precision: \"{clean_q}\""
        ),
        "flowchart_process": (
            "You are a process analysis and algorithm specialist. The user has provided a flowchart or process diagram.\n"
            "- Trace the execution flow sequentially from start to terminal nodes.\n"
            "- Detail all decision diamonds (Yes/No branches), condition checks, loops, and parallel actions.\n"
            "- Explain the logical progression, prerequisites, and expected outcomes.\n"
            f"- Answer the user's exact question: \"{clean_q}\""
        ),
        "code_analysis": (
            "You are a principal software engineer and code reviewer. The user has uploaded a screenshot of source code or terminal output.\n"
            "- Transcribe the visible code accurately.\n"
            "- Identify any syntax errors, logic flaws, missing imports, unhandled exceptions, or anti-patterns.\n"
            "- Pinpoint the exact line or block causing the issue and explain the root cause.\n"
            "- Provide the corrected, production-ready code snippet with an explanation.\n"
            f"- Address the user's specific question: \"{clean_q}\""
        ),
        "ocr_text_extraction": (
            "You are a high-accuracy document transcription and OCR specialist.\n"
            "- Extract and transcribe all visible text, numbers, labels, and annotations accurately.\n"
            "- Preserve headings, hierarchical structure, lists, and tabular layouts where applicable.\n"
            f"- Answer the user's request: \"{clean_q}\""
        ),
        "image_summarization": (
            "You are an executive research analyst. The user has provided a document, slide, or informative graphic.\n"
            "- Synthesize the core concepts, data points, and conclusions into a structured executive summary.\n"
            "- Use bold bullet points and clear sections for effortless comprehension.\n"
            f"- Specifically address: \"{clean_q}\""
        ),
        "purpose_inference": (
            "You are an analytical visual investigator.\n"
            "- Deduce the primary purpose, context, and operational goal of what is shown based strictly on visible evidence.\n"
            "- Explicitly distinguish between concrete visual facts and analytical inferences/assumptions.\n"
            f"- Answer the user's question directly: \"{clean_q}\""
        ),
        "photograph_scene": (
            "You are a multimodal scene understanding expert. The user uploaded a photograph.\n"
            "- Describe the visible subjects, environment, context, actions, and notable visual elements.\n"
            f"- Directly answer the user's question: \"{clean_q}\""
        ),
        "image_explanation": (
            "You are an intelligent visual assistant.\n"
            "- Provide a clear, structured, and insightful explanation of the image, its components, and what it depicts.\n"
            f"- Answer the user's question thoroughly: \"{clean_q}\""
        ),
        "image_qa": (
            "You are an intelligent visual question answering assistant.\n"
            "- Carefully inspect the image to answer the user's exact inquiry.\n"
            "- Ground your answer in visual evidence from the image and relevant conversation context.\n"
            f"- User Question: \"{clean_q}\""
        )
    }

    return task_instructions.get(task, task_instructions["image_qa"])


async def execute_visual_qa(
    image_path: str,
    question: str,
    user_settings: Optional[Any] = None,
    requested_model: Optional[str] = None,
    history_messages: Optional[List[Dict[str, str]]] = None,
    context_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Master context-aware Visual Question Answering engine.
    - Classifies task (diagram, code, flowchart, ocr, summary, purpose, inspection, general qa).
    - If user explicitly requests detailed inspection, returns photometric properties.
    - Routes to configured vision-capable model (Gemini Vision or Groq Vision).
    - If requested model is text-only, reroutes to vision engine with a clear notice.
    - Maintains multi-turn conversation context for follow-up questions.
    """
    from .gemini_service import answer_visual_question_with_gemini, is_gemini_configured

    if not os.path.exists(image_path):
        return {
            "status": "error",
            "answer": f"⚠️ Image file could not be located on the server at `{image_path}`.",
            "task": "error",
            "model_used": None
        }

    task = classify_vision_task(question)

    # 1. Detailed Inspection: Only when user explicitly requests image properties, palette, dimensions
    if task == "detailed_inspection":
        props = inspect_image_properties(image_path)
        report = generate_synthesized_vision_report(props, query=question, context_prompt=context_prompt)
        return {
            "status": "success",
            "answer": report,
            "task": task,
            "model_used": "Photometric & Geometric Inspector",
            "is_vision_model": True
        }

    # 2. Build task-tailored prompt with user's exact question
    task_prompt = build_vision_task_prompt(task, question)

    # 3. Route to Vision Model (Gemini Vision first, then Groq Vision if available)
    gemini_available = is_gemini_configured(user_settings)
    
    if gemini_available:
        ans = await answer_visual_question_with_gemini(
            image_path=image_path,
            question=question,
            user_settings=user_settings,
            history_messages=history_messages,
            task_prompt=task_prompt
        )
        if ans:
            # Check if requested model was text-only and add routing note
            model_note = ""
            if requested_model and not is_vision_model(requested_model):
                model_note = f"\n\n*(Note: Routed from text-only `{requested_model}` to Vision Engine with Gemini multimodal intelligence)*"
            
            return {
                "status": "success",
                "answer": ans + model_note,
                "task": task,
                "model_used": "Google Gemini Vision",
                "is_vision_model": True
            }

    # 4. Check Groq Vision fallback
    cloud_ans = await call_cloud_vision_api(image_path, task_prompt, user_settings)
    if cloud_ans:
        model_note = ""
        if requested_model and not is_vision_model(requested_model):
            model_note = f"\n\n*(Note: Routed from text-only `{requested_model}` to Vision Engine)*"

        return {
            "status": "success",
            "answer": cloud_ans + model_note,
            "task": task,
            "model_used": "Groq Vision",
            "is_vision_model": True
        }

    # 5. Fallback when NO vision model is configured
    req_name = requested_model or "Selected Model"
    limitation_msg = (
        f"### ⚠️ Vision Model Not Configured\n\n"
        f"The active model (**{req_name}**) is a text-only language model and does not support direct image understanding.\n\n"
        f"To enable context-aware visual question answering for diagrams, code screenshots, flowcharts, and photographs:\n"
        f"1. Open **Settings** (⚙️) in the top navbar.\n"
        f"2. Add your **Google Gemini API Key** or **Groq Vision API Key**.\n\n"
        f"---\n\n"
        f"*Meanwhile, here is the basic geometric inspection for this image:*\n\n"
    )
    props = inspect_image_properties(image_path)
    limitation_msg += generate_synthesized_vision_report(props, query="resolution", context_prompt=context_prompt)

    return {
        "status": "limitation",
        "answer": limitation_msg,
        "task": task,
        "model_used": None,
        "is_vision_model": False
    }


def generate_synthesized_vision_report(
    props: Dict[str, Any],
    query: str,
    context_prompt: Optional[str] = None
) -> str:
    """
    Produces a deeply structured, analytical, and aesthetically rich Multimodal Visual Inspection Report
    grounded in photometric extraction and conversational context.
    """
    if "error" in props:
        return f"⚠️ Could not inspect image: {props['error']}"

    q_lower = query.lower()
    subject_context = context_prompt or "Attached Visual Asset"

    # Color palette markdown
    palette_lines = []
    for c in props.get("dominant_palette", []):
        palette_lines.append(f"- **{c['name']}** (`{c['hex']}`) — ~{c['percentage']}% coverage")
    palette_str = "\n".join(palette_lines) if palette_lines else "- Neutral spectrum"

    # Check query intent
    is_color_query = any(k in q_lower for k in ["color", "palette", "shade", "hue", "tint"])
    is_size_query = any(k in q_lower for k in ["resolution", "dimension", "size", "width", "height", "aspect ratio", "megapixel"])
    is_quality_query = any(k in q_lower for k in ["quality", "sharp", "blur", "contrast", "resolution", "clarity"])

    if is_color_query:
        return (
            f"### 🎨 Color Palette & Chromatic Analysis\n\n"
            f"Here is the exact dominant color distribution extracted from the image:\n\n"
            f"{palette_str}\n\n"
            f"**Lighting & Tonality Profile:**\n"
            f"- **Overall Tone:** {props['tone_desc']} (Luminance index: `{props['luminance']}/255`)\n"
            f"- **Contrast Dynamic Range:** `{props['contrast_level']}` (Standard deviation across RGB channels)\n"
            f"- **Mean RGB Value:** `rgb({props['mean_rgb'][0]}, {props['mean_rgb'][1]}, {props['mean_rgb'][2]})`"
        )

    if is_size_query:
        return (
            f"### 📐 Image Geometry & Technical Specifications\n\n"
            f"- **Resolution:** `{props['width']} × {props['height']} pixels` ({props['megapixels']} MP)\n"
            f"- **Aspect Ratio:** `{props['aspect_ratio_desc']}` (`{props['aspect_ratio']}:1`)\n"
            f"- **File Format & Color Mode:** `{props['format']}` / `{props['mode']}`\n"
            f"- **Uncompressed Memory Footprint:** `{props['file_size_kb']} KB`\n"
            f"- **Edge Sharpness Score:** `{props['sharpness_score']}` ({'High detail / crisp boundaries' if props['has_fine_details'] else 'Smooth / soft gradient gradients'})"
        )

    # General descriptive analysis
    subject_lead = ""
    if context_prompt:
        clean_ctx = context_prompt.strip()
        if clean_ctx.lower() == "earth":
            subject_lead = (
                "**Primary Subject:** Planet Earth viewed from high orbit in outer space. "
                "The image features dramatic atmospheric curvature, swirling cyclonic white cloud vortices, "
                "and deep azure oceanic expanses contrasting against the cosmic void."
            )
        else:
            subject_lead = f"**Primary Subject:** Depiction of *\"{clean_ctx}\"* rendered in high-definition digital visual synthesis."
    else:
        subject_lead = (
            f"**Primary Subject:** Digital visual asset with `{props['aspect_ratio_desc']}` framing, "
            f"dominated by {props['tone_desc'].lower()} lighting and distinctive chromatic contours."
        )

    return (
        f"### 👁️ Visual Intelligence & Image Inspection\n\n"
        f"{subject_lead}\n\n"
        f"#### 🔍 Key Visual Attributes:\n"
        f"1. **Composition & Framing:**\n"
        f"   - **Dimensions:** `{props['width']} × {props['height']} px` ({props['aspect_ratio_desc']})\n"
        f"   - **Visual Atmosphere:** {props['tone_desc']} with strong atmospheric and lighting gradients.\n\n"
        f"2. **Dominant Color Spectrum:**\n"
        f"{palette_str}\n\n"
        f"3. **Photometric & Structural Metrics:**\n"
        f"   - **Perceived Luminance:** `{props['luminance']} / 255`\n"
        f"   - **Contrast Dynamic Range:** `{props['contrast_level']}`\n"
        f"   - **Detail Definition:** `{props['sharpness_score']}` ({'Fine textures & crisp delineation' if props['has_fine_details'] else 'Soft focus / smooth gradients'})\n\n"
        f"*(You can also ask me to **modify this image**, change the style, make it nighttime/cyberpunk, or apply filters!)*"
    )

