import os
import re
import urllib.parse
import uuid
import httpx
from typing import Optional, Dict, Any, List, Union
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter

from .image_router import (
    ImageEditRouter,
    UniversalIntentParser,
    MaskProcessor,
    PixelCompositor,
    ImageLineageManager,
    TextToImageService,
    InpaintingService,
    ObjectRemovalService,
    PillowFilterService,
    build_photorealistic_prompt,
    PHOTOREALISM_NEGATIVE,
)

GENERATED_IMAGES_DIR = os.path.join("backend_uploads", "generated_images")
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)

IMAGE_INTENT_PATTERNS = [
    # 1. "generate/create/render/produce/show me [a] [image/picture/photo of] <prompt>"
    r'(?:please\s+)?(?:generate|create|render|produce|show\s+me)\s+(?:an?\s+)?(?:image|picture|photo|drawing|illustration|painting|visual|graphic|artwork|diagram|portrait)?\s*(?:of|for|about|depicting)?\s*(.+)',
    # 2. "make/draw/paint/illustrate/render/sketch [an] [image/picture/photo of] <prompt>"
    r'(?:please\s+)?(?:make|draw|paint|illustrate|render|sketch)\s+(?:an?\s+)?(?:image|picture|photo|drawing|illustration|painting|visual|graphic|artwork|diagram|portrait)\s*(?:of|for|about|depicting)?\s*(.+)',
    # 3. "[an] image/picture/photo/portrait of <prompt>"
    r'(?:an?\s+)?(?:image|picture|photo|illustration|drawing|diagram|portrait|photograph)\s+of\s+(.+)',
    # 4. "draw/paint/illustrate/render/sketch [me] [a] <prompt>"
    r'(?:please\s+)?(?:draw|paint|illustrate|render|sketch)\s+(?:me\s+)?(?:an?\s+)?(.+)',
    # 5. "<prompt> image/picture/photo/wallpaper/artwork"
    r'(.+?)\s+(?:image|picture|photo|drawing|illustration|painting|artwork|wallpaper|portrait)$',
    # 6. Direct standalone single-word/short subject prompts like "boy", "a boy", "cute puppy", "young boy in park"
    r'^(?:a\s+)?(?:young\s+|little\s+|cute\s+)?(?:boy|girl|man|woman|child|baby|puppy|dog|cat|kitten|supercar|sunset|landscape|portrait)(?:[\s,].*)?$',
]

# Patterns specifically requesting changes / modifications / variations to an existing or attached image
IMAGE_MODIFICATION_PATTERNS = [
    r'^(?:modify|change|edit|alter|transform|turn|convert|replace|swap)\b',
    r'^(?:remove|delete|erase|take\s+out|clear|get\s+rid\s+of)\b',
    r'^(?:add|put|give|insert)\b',
    r'^(?:make|turn)\s+(?:it|the\s+image|her|him|them|the\s+[\w]+)\b',
    r'^(?:apply|use)\s+(?:a\s+)?(?:filter|effect|style|mode)\b',
    r'\b(?:black\s+and\s+white|grayscale|monochrome|b&w|blur|invert|flip|rotate)\b',
    r'\b(?:in\s+this\s+image|to\s+this\s+image|on\s+this\s+image|in\s+the\s+photo)\b',
]


def is_explicit_image_edit(text: str) -> bool:
    """Returns True if the user prompt explicitly requests a change, edit, or filter on an image."""
    if not text or not text.strip():
        return False
    clean = text.strip().lower()
    for pat in IMAGE_MODIFICATION_PATTERNS:
        if re.search(pat, clean, re.IGNORECASE):
            return True
    return False


def detect_image_prompt(text: str) -> Optional[str]:
    """
    Detects if the user prompt is requesting a new image to be generated,
    and extracts the core subject prompt.
    """
    if not text or not text.strip():
        return None

    # If the user explicitly asks to edit, it is an edit, not a new generation
    if is_explicit_image_edit(text):
        return None

    clean = text.strip()
    for pat in IMAGE_INTENT_PATTERNS:
        m = re.match(pat, clean, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip() if m.groups() else clean
            # Clean trailing punctuation
            extracted = re.sub(r'[\.\?!,;:]+$', '', extracted).strip()
            # Clean leading articles like 'a ', 'an ', 'the '
            extracted = re.sub(r'^(?:an?|the)\s+', '', extracted, flags=re.IGNORECASE).strip()
            # Fix common typo 'worflow' -> 'workflow'
            extracted = re.sub(r'\bworflow\b', 'workflow', extracted, flags=re.IGNORECASE)
            if extracted and len(extracted) > 1:
                return extracted
            return clean
    return None


def detect_image_modification(
    text: str,
    has_explicit_image: bool = False,
    context_prompt: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Detects if the user query is asking to make changes, apply filters, or edit
    a current or attached image. Uses UniversalIntentParser for universal coverage.
    """
    if not text or not text.strip():
        return None

    clean = text.strip()

    # If this is detected as a new image prompt and NOT an explicit edit instruction,
    # it is a new generation — NEVER a modification.
    if detect_image_prompt(clean) is not None and not is_explicit_image_edit(clean):
        return None

    # If the user did NOT attach an image in this message, only allow modification
    # if the prompt explicitly contains image modification commands.
    if not has_explicit_image and not is_explicit_image_edit(clean):
        return None

    plan = UniversalIntentParser.parse_intent(
        instruction=clean,
        has_image=True,
        has_mask=False,
        context_description=context_prompt
    )

    op = plan.get("operation")

    # If it resolved to text_to_image, it's not a modification
    if op == "text_to_image":
        return None

    if op == "pillow_filter":
        return {
            "action": plan["filter_type"],
            "instruction": clean,
            "description": plan.get("description", f"Filter: {plan['filter_type']}"),
            "plan": plan
        }

    return {
        "action": "generative_variation",
        "operation": op,
        "instruction": clean,
        "enriched_prompt": plan.get("prompt", clean),
        "description": plan.get("description", f"AI Modification: {clean}"),
        "plan": plan
    }


def apply_image_filter(image_path: str, action: str) -> Dict[str, Any]:
    """
    Applies direct deterministic digital image transformations using PIL.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Source image not found: {image_path}")

    filename = f"mod_{action}_{uuid.uuid4().hex[:8]}.jpg"
    out_path = os.path.join(GENERATED_IMAGES_DIR, filename)

    with Image.open(image_path) as img:
        rgb_img = img.convert("RGB")

        if action == "grayscale":
            res = ImageOps.grayscale(rgb_img).convert("RGB")
            title = "Black & White Monochromatic Filter"
        elif action == "flip_h":
            res = rgb_img.transpose(Image.FLIP_LEFT_RIGHT)
            title = "Horizontally Mirrored"
        elif action == "flip_v":
            res = rgb_img.transpose(Image.FLIP_TOP_BOTTOM)
            title = "Vertically Inverted"
        elif action == "rotate_90":
            res = rgb_img.rotate(270, expand=True)
            title = "Rotated 90° Clockwise"
        elif action == "rotate_180":
            res = rgb_img.rotate(180, expand=True)
            title = "Rotated 180°"
        elif action == "invert":
            res = ImageOps.invert(rgb_img)
            title = "Color Inverted (Negative)"
        elif action == "contrast":
            enhancer = ImageEnhance.Contrast(rgb_img)
            res = enhancer.enhance(1.8)
            title = "High Contrast Enhanced"
        elif action == "blur":
            res = rgb_img.filter(ImageFilter.GaussianBlur(radius=6))
            title = "Gaussian Softened"
        elif action == "cyberpunk":
            # Stylized neon cyan/magenta shift
            r, g, b = rgb_img.split()
            r = ImageEnhance.Contrast(r).enhance(1.4)
            b = ImageEnhance.Brightness(b).enhance(1.3)
            res = Image.merge("RGB", (r, g, b))
            title = "Cyberpunk Neon Chromatic Shift"
        elif action == "night":
            # Darkened blue-shifted night filter
            darkened = ImageEnhance.Brightness(rgb_img).enhance(0.45)
            r, g, b = darkened.split()
            b = ImageEnhance.Brightness(b).enhance(1.4)
            r = ImageEnhance.Brightness(r).enhance(0.7)
            res = Image.merge("RGB", (r, g, b))
            title = "Nocturnal Atmospheric Night Filter"
        elif action == "sketch":
            gray = ImageOps.grayscale(rgb_img)
            inv = ImageOps.invert(gray)
            blurred = inv.filter(ImageFilter.GaussianBlur(radius=15))
            # Color dodge blend
            res = Image.blend(gray, ImageOps.invert(blurred), alpha=0.5).convert("RGB")
            title = "Pencil Sketch / Contours"
        else:
            res = rgb_img
            title = "Processed Image"

        res.save(out_path, "JPEG", quality=95)

    local_url = f"/api/images/{filename}"
    markdown = (
        f"🎨 **Applied Image Modification:** *{title}*\n\n"
        f"![{title}]({local_url})\n\n"
        f"*(Action: `{action}` • Dimensions: {res.width}×{res.height} • Click to view full)*"
    )

    return {
        "status": "success",
        "action": action,
        "title": title,
        "image_url": local_url,
        "local_path": out_path,
        "filename": filename,
        "markdown": markdown
    }


def generate_local_fallback_image(prompt: str, filepath: str) -> str:
    """
    Draws a sleek fallback graphic using PIL when offline or when external diffusion APIs are unreachable.
    """
    width, height = 1024, 1024
    img = Image.new("RGB", (width, height), color=(13, 16, 23))
    draw = ImageDraw.Draw(img)

    cx, cy = width // 2, height // 2
    lower_prompt = prompt.lower()

    if "earth" in lower_prompt or "planet" in lower_prompt:
        # Orbital planet render with atmosphere glow
        for glow_step in range(40):
            r = 300 + (40 - glow_step) * 3
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 140 + glow_step * 2, 255, 30), width=2)
        # Deep blue ocean sphere
        draw.ellipse([cx - 300, cy - 300, cx + 300, cy + 300], fill=(12, 54, 120), outline=(0, 210, 255), width=4)
        # Continents and cloud swirls
        draw.arc([cx - 240, cy - 240, cx + 200, cy + 200], start=30, end=160, fill=(40, 180, 110), width=35)
        draw.arc([cx - 180, cy - 100, cx + 250, cy + 220], start=200, end=320, fill=(255, 255, 255), width=20)
        draw.arc([cx - 120, cy - 220, cx + 180, cy + 80], start=80, end=240, fill=(255, 255, 255), width=24)
    elif "circle" in lower_prompt:
        radius = 320
        for step in range(30):
            glow_r = radius + (30 - step) * 4
            draw.ellipse([cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r], outline=(0, 180 + step * 2, 255, 20), width=2)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(0, 210, 255), outline=(255, 255, 255), width=6)
    else:
        # Abstract artistic cyber sphere
        for r in range(340, 60, -20):
            color = (int(0 + r * 0.4), int(160 + r * 0.2), int(255 - r * 0.3))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=3)

    try:
        font = ImageFont.load_default()
        label = f"LocalGPT AI Render: {prompt[:45]}"
        draw.text((40, height - 60), label, fill=(180, 195, 215), font=font)
    except Exception:
        pass

    img.save(filepath, "JPEG", quality=95)
    return filepath


def clean_image_watermark(image_path: str) -> None:
    """
    Subtly in-paints the small bottom-right service logo using adjacent pixel texture.
    """
    try:
        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            if w > 200 and h > 100:
                patch = rgb_img.crop((w - 180, h - 65, w, h - 35))
                rgb_img.paste(patch, (w - 180, h - 35))
                rgb_img.save(image_path, "JPEG", quality=95)
    except Exception as e:
        print(f"Watermark cleanup note: {e}")


async def generate_image_asset(prompt: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates an image via high-resolution photorealistic diffusion,
    saves the image locally, cleans watermarks, and returns public URLs and Markdown formatted card.
    Automatically handles rate limits with auto-cooldown retry and multiple endpoints.
    Never returns fake geometric placeholder drawings.
    """
    clean_p = prompt.strip()
    # Enhance prompt for photorealism unless a specific style was requested
    enhanced_p = build_photorealistic_prompt(clean_p)
    filename = f"gen_{uuid.uuid4().hex[:10]}.jpg"
    local_path = os.path.join(GENERATED_IMAGES_DIR, filename)

    encoded = urllib.parse.quote(enhanced_p)
    neg_encoded = urllib.parse.quote(PHOTOREALISM_NEGATIVE)

    candidate_endpoints = [
        f"https://image.pollinations.ai/prompt/{encoded}?model=sana&negative_prompt={neg_encoded}&width=1024&height=1024&nologo=true",
        f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true",
        f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true",
        f"https://image.pollinations.ai/prompt/{encoded}?nologo=true"
    ]

    downloaded = False
    rate_limited_seconds = 0

    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        for cloud_url in candidate_endpoints:
            try:
                resp = await client.get(cloud_url, headers={"User-Agent": "Mozilla/5.0 LocalGPT-Pro/3.5"})
                if resp.status_code == 200 and len(resp.content) > 1000:
                    with open(local_path, "wb") as f:
                        f.write(resp.content)
                    clean_image_watermark(local_path)
                    downloaded = True
                    break
                elif resp.status_code == 402:
                    m = re.search(r'Retry after (\d+)s', resp.text)
                    cooldown = int(m.group(1)) if m else 15
                    rate_limited_seconds = max(rate_limited_seconds, cooldown)
                    if cooldown <= 25:
                        print(f"Rate limited by diffusion provider. Cooling down for {cooldown + 1}s...")
                        await asyncio.sleep(cooldown + 1)
                        retry_resp = await client.get(cloud_url, headers={"User-Agent": "Mozilla/5.0 LocalGPT-Pro/3.5"})
                        if retry_resp.status_code == 200 and len(retry_resp.content) > 1000:
                            with open(local_path, "wb") as f:
                                f.write(retry_resp.content)
                            clean_image_watermark(local_path)
                            downloaded = True
                            break
            except Exception as e:
                print(f"Diffusion generation attempt failed on {cloud_url[:50]}: {e}")
                continue

    if not downloaded:
        cooldown_msg = f"in {rate_limited_seconds} seconds" if rate_limited_seconds > 0 else "in 15–30 seconds"
        return {
            "status": "error",
            "error": f"The image diffusion service has a 45-second IP cooldown. Please retry {cooldown_msg}.",
            "image_url": None,
            "markdown": (
                f"⚠️ **Image Generation Limit:** The free AI diffusion provider enforces a 45-second rate limit between generations.\n\n"
                f"Please wait {cooldown_msg} and try your prompt `\"{clean_p}\"` again."
            )
        }

    local_url = f"/api/images/{filename}"
    markdown = (
        f"🎨 **Generated Image:** *\"{clean_p}\"*\n\n"
        f"![{clean_p}]({local_url})\n\n"
        f"*(Model: Photorealistic Diffusion • Resolution: 1024×1024 • Click image to view or download)*"
    )

    return {
        "status": "success",
        "prompt": clean_p,
        "enhanced_prompt": enhanced_p,
        "image_url": local_url,
        "local_path": local_path,
        "filename": filename,
        "model": "Photorealistic Diffusion (1024×1024)",
        "markdown": markdown
    }
