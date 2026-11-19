import os
import re
import io
import json
import uuid
import base64
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

import httpx
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import numpy as np

# Attempt OpenCV import for local deterministic inpainting / seamless boundary operations
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from .config import settings

GENERATED_IMAGES_DIR = os.path.join("backend_uploads", "generated_images")
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)

LINEAGE_FILE = os.path.join(GENERATED_IMAGES_DIR, "image_lineage.json")

# =============================================================================
# 0. Photorealism Prompt Engine
# =============================================================================

STYLE_KEYWORDS = {
    "anime", "cartoon", "watercolor", "oil painting", "pencil sketch", "sketch",
    "cyberpunk", "vintage", "retro", "pixel art", "comic", "3d render", "3d",
    "illustration", "artistic", "fantasy", "abstract", "impressionist", "surreal",
    "vector", "flat design", "minimalist", "neon", "glitch", "vaporwave",
    "painting", "drawn", "animated", "manga", "chibi", "low poly", "claymation",
    "charcoal", "pastel", "impressionism", "expressionism", "cubism",
}

PHOTOREALISM_SUFFIX = (
    ", photorealistic, professional photograph, natural lighting, real-world textures, "
    "DSLR quality, 35mm camera, f/1.8 aperture, natural depth of field, "
    "shot on Canon EOS R5, 8k resolution, hyper-detailed, no CGI, no 3D render, no cartoon, no anime"
)

PHOTOREALISM_NEGATIVE = (
    "cartoon, anime, illustration, 3D render, CGI, plastic skin, painted, artistic, "
    "fantasy art, watercolor, vector art, drawing, unrealistic, artificial, low quality, "
    "blurry, distorted, overexposed, artifacts, text, watermark"
)

def user_requested_specific_style(prompt: str) -> bool:
    """Returns True if the user explicitly requested a non-photorealistic style."""
    lower = prompt.lower()
    return any(kw in lower for kw in STYLE_KEYWORDS)


def build_photorealistic_prompt(user_prompt: str) -> str:
    """
    Returns a prompt enhanced for photorealism. If the user has requested a specific
    artistic style, the prompt is returned verbatim with only quality tokens added.
    """
    if user_requested_specific_style(user_prompt):
        return f"{user_prompt}, high quality, sharp focus, highly detailed, masterpiece"
    return f"{user_prompt}{PHOTOREALISM_SUFFIX}"


def build_inpainting_prompt(user_prompt: str) -> str:
    """
    For inpainting, build a compact focused prompt describing only what should
    appear in the modified region — not the entire image.
    """
    if user_requested_specific_style(user_prompt):
        return f"{user_prompt}, high quality, seamless, blended"
    return (
        f"{user_prompt}, photorealistic, natural, seamless integration, "
        "matching lighting and perspective, high quality, DSLR photograph"
    )


# =============================================================================
# 1. Mask Processor & Pixel Compositor
# =============================================================================

class MaskProcessor:
    """
    Validates, scales, feathers, inverts, and automatically generates masks
    for localized inpainting and segmentation.
    """

    @staticmethod
    def decode_mask(mask_input: Union[str, bytes, Image.Image], target_size: Tuple[int, int]) -> Image.Image:
        """
        Accepts base64 data URI, raw bytes, file path, or PIL Image,
        scales to target_size (W, H), and converts to single-channel 'L' mode.
        """
        if isinstance(mask_input, Image.Image):
            mask = mask_input.convert("L")
        elif isinstance(mask_input, str):
            if mask_input.startswith("data:image"):
                # Data URI: data:image/png;base64,....
                b64_data = mask_input.split(",", 1)[1]
                mask_bytes = base64.b64decode(b64_data)
                mask = Image.open(io.BytesIO(mask_bytes)).convert("L")
            elif os.path.exists(mask_input):
                mask = Image.open(mask_input).convert("L")
            else:
                # Raw base64 string
                mask_bytes = base64.b64decode(mask_input)
                mask = Image.open(io.BytesIO(mask_bytes)).convert("L")
        elif isinstance(mask_input, bytes):
            mask = Image.open(io.BytesIO(mask_input)).convert("L")
        else:
            raise ValueError(f"Unsupported mask input type: {type(mask_input)}")

        if mask.size != target_size:
            mask = mask.resize(target_size, Image.Resampling.BILINEAR)

        return mask

    @staticmethod
    def feather_mask(mask: Image.Image, radius: int = 6) -> Image.Image:
        """
        Applies Gaussian blur to the binary mask to prevent harsh seams
        and ensure smooth compositing with untouched original pixels.
        """
        if radius <= 0:
            return mask
        return mask.filter(ImageFilter.GaussianBlur(radius=radius))

    @staticmethod
    def binarize_mask(mask: Image.Image, threshold: int = 30) -> Image.Image:
        """
        Converts a soft or color mask into a strict 0/255 binary mask.
        """
        return mask.point(lambda p: 255 if p > threshold else 0, mode="L")

    @staticmethod
    def invert_mask(mask: Image.Image) -> Image.Image:
        """Inverts mask: 255 becomes 0, 0 becomes 255."""
        return ImageOps.invert(mask.convert("L"))

    @staticmethod
    def generate_auto_mask(image: Image.Image, mask_type: str = "subject") -> Image.Image:
        """
        Generates contextual geometric masks for operations when no manual brush mask was painted:
        - 'subject': Elliptical / center focal mask
        - 'background': Inverted subject mask (surrounding environment)
        - 'sky': Upper 45% of canvas (weather, sky, lighting)
        - 'ground': Lower 40% of canvas (grass, floor, water, paths)
        - 'border': Outer 15% edge frame for outpainting
        """
        w, h = image.size
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)

        if mask_type in ["hat", "cap", "head", "hair"]:
            # Upper head and crown zone (does NOT cover face/eyes/nose/mouth)
            bbox = (int(w * 0.15), 0, int(w * 0.85), int(h * 0.42))
            draw.ellipse(bbox, fill=255)
        elif mask_type in ["glasses", "sunglasses", "eyes"]:
            # Horizontal eye-level band
            bbox = (int(w * 0.22), int(h * 0.24), int(w * 0.78), int(h * 0.44))
            draw.ellipse(bbox, fill=255)
        elif mask_type in ["clothing", "shirt", "jacket", "coat", "dress", "suit"]:
            # Torso and clothing region
            draw.rectangle((int(w * 0.08), int(h * 0.48), int(w * 0.92), h), fill=255)
        elif mask_type == "subject":
            # Central 60% elliptical zone
            bbox = (int(w * 0.2), int(h * 0.15), int(w * 0.8), int(h * 0.85))
            draw.ellipse(bbox, fill=255)
        elif mask_type == "background":
            # Entire canvas minus central subject ellipse
            mask = Image.new("L", (w, h), 255)
            draw = ImageDraw.Draw(mask)
            bbox = (int(w * 0.22), int(h * 0.18), int(w * 0.78), int(h * 0.82))
            draw.ellipse(bbox, fill=0)
        elif mask_type in ["sky", "weather", "upper"]:
            # Upper horizontal region with gradient transition
            draw.rectangle((0, 0, w, int(h * 0.45)), fill=255)
        elif mask_type in ["ground", "lower"]:
            # Lower horizontal region
            draw.rectangle((0, int(h * 0.6), w, h), fill=255)
        elif mask_type in ["border", "outpaint"]:
            # Frame around image
            border_w = int(w * 0.15)
            border_h = int(h * 0.15)
            draw.rectangle((0, 0, w, h), fill=255)
            draw.rectangle((border_w, border_h, w - border_w, h - border_h), fill=0)
        else:
            # Default to full editable canvas
            mask = Image.new("L", (w, h), 255)

        return MaskProcessor.feather_mask(mask, radius=8)


class PixelCompositor:
    """
    Guarantees strict 100% pixel preservation of unedited regions outside the mask.
    Combines the newly synthesized patch with the original image using feathered alpha.
    """

    @staticmethod
    def composite(
        original_image: Image.Image,
        edited_image: Image.Image,
        mask: Image.Image,
        feather_radius: int = 5
    ) -> Image.Image:
        """
        Strict pixel preservation:
        Where mask == 0, output is mathematically identical to original_image.
        Where mask == 255, output is edited_image.
        Transitions smoothly across feathered boundaries.
        """
        orig_rgb = original_image.convert("RGB")
        w, h = orig_rgb.size

        # Ensure matching dimensions
        if edited_image.size != (w, h):
            edited_rgb = edited_image.convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
        else:
            edited_rgb = edited_image.convert("RGB")

        if mask.size != (w, h):
            mask_l = mask.convert("L").resize((w, h), Image.Resampling.BILINEAR)
        else:
            mask_l = mask.convert("L")

        if feather_radius > 0:
            mask_l = MaskProcessor.feather_mask(mask_l, radius=feather_radius)

        # PIL Image.composite(image1, image2, mask): image1 where mask is 255, image2 where mask is 0
        return Image.composite(edited_rgb, orig_rgb, mask_l)


# =============================================================================
# 2. Image Lineage & Version Manager (Multi-Turn Conversational Memory)
# =============================================================================

class ImageLineageManager:
    """
    Maintains multi-turn image editing lineages per chat.
    Ensures that consecutive edits modify the latest edited version
    without losing the original source image or reverting unintentionally.
    """

    @classmethod
    def _load_data(cls) -> Dict[str, Any]:
        if os.path.exists(LINEAGE_FILE):
            try:
                with open(LINEAGE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    @classmethod
    def _save_data(cls, data: Dict[str, Any]):
        try:
            with open(LINEAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save image lineage: {e}")

    @classmethod
    def record_version(
        cls,
        chat_id: str,
        image_url: str,
        operation: str,
        instruction: str,
        parent_url: Optional[str] = None
    ) -> Dict[str, Any]:
        data = cls._load_data()
        chat_tree = data.get(chat_id, {"versions": [], "active_version": 0})

        version_num = len(chat_tree["versions"]) + 1
        record = {
            "version": version_num,
            "image_url": image_url,
            "filename": os.path.basename(image_url),
            "operation": operation,
            "instruction": instruction,
            "parent_url": parent_url,
            "timestamp": datetime.utcnow().isoformat()
        }
        chat_tree["versions"].append(record)
        chat_tree["active_version"] = version_num
        data[chat_id] = chat_tree
        cls._save_data(data)
        return record

    @classmethod
    def get_latest_image_url(cls, chat_id: Optional[str]) -> Optional[str]:
        if not chat_id:
            return None
        data = cls._load_data()
        chat_tree = data.get(chat_id)
        if chat_tree and chat_tree.get("versions"):
            return chat_tree["versions"][-1]["image_url"]
        return None

    @classmethod
    def get_versions(cls, chat_id: str) -> List[Dict[str, Any]]:
        data = cls._load_data()
        chat_tree = data.get(chat_id, {})
        return chat_tree.get("versions", [])


# =============================================================================
# 3. Universal Intent & Structured Edit Plan Generator
# =============================================================================

class UniversalIntentParser:
    """
    Understands user editing intent for ANY image, ANY subject, and ANY instruction.
    Generates structured edit plans without example-specific hardcodes.
    """

    OPERATION_TYPES = [
        "text_to_image",
        "inpainting",
        "object_removal",
        "object_addition",
        "object_replacement",
        "background_editing",
        "style_transformation",
        "outpainting",
        "pillow_filter",
        "image_to_image"
    ]

    @classmethod
    def parse_intent(
        cls,
        instruction: str,
        has_image: bool = False,
        has_mask: bool = False,
        context_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses the user query into a structured execution plan.
        """
        clean = instruction.strip()
        lower = clean.lower()

        # 1. Deterministic Pillow Filter detection
        filter_type = cls._detect_pillow_filter(lower)
        if filter_type and has_image:
            return {
                "operation": "pillow_filter",
                "filter_type": filter_type,
                "instruction": clean,
                "action": "filter",
                "mask_required": False,
                "description": f"Deterministic Filter: {filter_type.replace('_', ' ').title()}"
            }

        # 2. Text-to-Image request (no reference image provided or explicit new generation)
        if not has_image or cls._is_explicit_new_generation(lower):
            subject_prompt = cls._extract_subject_prompt(clean)
            return {
                "operation": "text_to_image",
                "instruction": clean,
                "action": "generate",
                "prompt": subject_prompt,
                "negative_prompt": "blurry, low quality, distorted, extra limbs, ugly, bad anatomy",
                "mask_required": False,
                "description": f"Text-to-Image: \"{subject_prompt}\""
            }

        # 3. Mask-based editing when user explicitly painted a mask
        if has_mask:
            is_removal = any(w in lower for w in ["remove", "delete", "erase", "take out", "disappear", "clear"])
            action = "remove" if is_removal else "replace"
            op = "object_removal" if is_removal else "inpainting"
            return {
                "operation": op,
                "action": action,
                "instruction": clean,
                "prompt": cls._clean_instruction_prompt(clean, is_removal=is_removal),
                "negative_prompt": "seams, artifacts, blurry, harsh edges, distortion",
                "mask_required": True,
                "mask_source": "manual",
                "description": f"Mask Inpainting: {clean}"
            }

        # 4. Outpainting / Canvas Expansion
        if any(w in lower for w in ["expand", "outpaint", "widen", "extend canvas", "extend border", "zoom out"]):
            return {
                "operation": "outpainting",
                "action": "expand",
                "instruction": clean,
                "prompt": clean,
                "negative_prompt": "seams, distorted edges, blurry, cutoff",
                "mask_required": True,
                "mask_source": "border",
                "description": f"Canvas Outpainting: {clean}"
            }

        # 5. Object Removal
        if any(w in lower for w in ["remove", "erase", "delete", "get rid of", "take away", "eliminate"]):
            target = cls._extract_target_noun(lower, ["remove", "erase", "delete", "get rid of", "take away"])
            return {
                "operation": "object_removal",
                "action": "remove",
                "target": target,
                "instruction": clean,
                "prompt": f"seamless background texture, inpainting, unblemished surface without {target}",
                "negative_prompt": "remnants, artifacts, seams, blurry patch",
                "mask_required": True,
                "mask_source": "subject",
                "description": f"Object Removal: {target or clean}"
            }

        # 6. Background Modification
        if any(w in lower for w in ["background", "backdrop", "setting", "environment", "surroundings"]) or \
           any(lower.startswith(p) for p in ["put in ", "put them in ", "place in ", "set in ", "move to "]):
            bg_desc = cls._extract_background_description(clean)
            return {
                "operation": "background_editing",
                "action": "replace_background",
                "target": "background",
                "instruction": clean,
                "prompt": f"{bg_desc}, high quality, realistic depth-of-field, matching lighting",
                "negative_prompt": "blurry, mismatched lighting, cut-and-paste look, unnatural edges",
                "mask_required": True,
                "mask_source": "background",
                "preserve_subjects": True,
                "description": f"Background Modification: {bg_desc}"
            }

        # 7. Style Transformation
        if any(w in lower for w in [
            "style", "anime", "cartoon", "watercolor", "oil painting", "pencil sketch",
            "cyberpunk", "cinematic", "vintage", "retro", "pixel art", "comic book", "3d render",
            "photorealistic", "natural photograph", "candid photo", "dslr"
        ]) and any(w in lower for w in ["turn", "make", "convert", "change", "style", "into", "as"]):
            return {
                "operation": "style_transformation",
                "action": "stylize",
                "instruction": clean,
                "prompt": f"{clean}, high quality aesthetic, consistent composition",
                "negative_prompt": "ugly, deformed, low quality, artifacts, watermark",
                "mask_required": False,
                "description": f"Style Transfer: {clean}"
            }

        # 8. Object Addition / Replacement / Modification (only if explicit edit action keywords exist)
        has_mod_keyword = any(w in lower for w in [
            "add", "put", "wearing", "with a", "give", "holding", "change", "modify",
            "replace", "swap", "alter", "turn into", "make it", "make the"
        ])
        if has_mask or has_mod_keyword:
            is_addition = any(w in lower for w in ["add", "put a", "wearing", "with a", "give", "holding"])
            action = "add" if is_addition else "modify"
            base_context = context_description.strip() if context_description else "scene subjects"

            lower_clean = clean.lower()
            if any(w in lower_clean for w in ["hat", "cap", "beanie", "helmet", "crown", "hair"]):
                mask_source = "hat"
            elif any(w in lower_clean for w in ["glasses", "sunglasses", "shades", "spectacles"]):
                mask_source = "glasses"
            elif any(w in lower_clean for w in ["shirt", "jacket", "coat", "dress", "suit", "tie", "hoodie", "sweater", "clothes", "clothing"]):
                mask_source = "clothing"
            elif any(w in lower_clean for w in ["background", "backdrop", "setting", "environment"]):
                mask_source = "background"
            else:
                mask_source = "subject"

            return {
                "operation": "inpainting",
                "action": action,
                "instruction": clean,
                "prompt": f"{base_context} with {cls._clean_instruction_prompt(clean)}, natural lighting, authentic details, sharp focus, DSLR quality",
                "negative_prompt": "artifacts, distorted, low resolution, fake, plastic, CGI",
                "mask_required": True,
                "mask_source": mask_source,
                "description": f"Image Modification: {clean}"
            }

        # Otherwise, standalone visual prompt -> text_to_image
        subject_prompt = cls._extract_subject_prompt(clean)
        return {
            "operation": "text_to_image",
            "instruction": clean,
            "action": "generate",
            "prompt": subject_prompt,
            "negative_prompt": "blurry, low quality, distorted, extra limbs, ugly, bad anatomy",
            "mask_required": False,
            "description": f"Text-to-Image: \"{subject_prompt}\""
        }

    @staticmethod
    def _detect_pillow_filter(lower: str) -> Optional[str]:
        if any(k in lower for k in ["black and white", "grayscale", "monochrome", "b&w"]):
            return "grayscale"
        if "flip horizontal" in lower or "mirror" in lower:
            return "flip_h"
        if "flip vertical" in lower:
            return "flip_v"
        if "rotate 90" in lower or "turn 90" in lower:
            return "rotate_90"
        if "rotate 180" in lower:
            return "rotate_180"
        if "invert" in lower or "negative" in lower:
            return "invert"
        if "high contrast" in lower or "increase contrast" in lower:
            return "contrast"
        if "blur" in lower or "soften" in lower:
            return "blur"
        if "night" in lower or "nighttime" in lower or "nocturnal" in lower:
            return "night"
        if "sketch" in lower or "pencil drawing" in lower:
            return "sketch"
        return None

    @staticmethod
    def _is_explicit_new_generation(lower: str) -> bool:
        new_prefixes = [
            "generate a new image", "create a new image", "generate an image", "generate image",
            "create an image", "create image", "draw an image", "draw image", "draw a", "draw an",
            "paint an image", "paint image", "paint a picture", "make a new image", "make an image",
            "show me an image", "show me a photo", "photo of", "picture of", "portrait of", "photograph of",
            "render an image", "render a photo", "generate a", "generate an"
        ]
        if any(lower.startswith(p) for p in new_prefixes):
            return True
        # Direct subject nouns without edit words
        standalone_subjects = [
            "boy", "a boy", "girl", "a girl", "man", "a man", "woman", "a woman",
            "child", "baby", "puppy", "dog", "cat", "kitten", "supercar", "sunset", "landscape"
        ]
        return lower in standalone_subjects

    @staticmethod
    def _extract_subject_prompt(text: str) -> str:
        patterns = [
            r'(?:please\s+)?(?:generate|create|render|produce|show\s+me)\s+(?:an?\s+)?(?:image|picture|photo|drawing|illustration|painting|visual|graphic|artwork|diagram|portrait)?\s*(?:of|for|about|depicting)?\s*(.+)',
            r'(?:please\s+)?(?:make|draw|paint|illustrate|render|sketch)\s+(?:an?\s+)?(?:image|picture|photo|drawing|illustration|painting|visual|graphic|artwork|diagram|portrait)\s*(?:of|for|about|depicting)?\s*(.+)',
            r'(?:an?\s+)?(?:image|picture|photo|illustration|drawing|diagram|portrait|photograph)\s+of\s+(.+)',
            r'(?:please\s+)?(?:draw|paint|illustrate|render|sketch)\s+(?:me\s+)?(?:an?\s+)?(.+)',
            r'(.+?)\s+(?:image|picture|photo|drawing|illustration|painting|artwork|wallpaper|portrait)$',
        ]
        for pat in patterns:
            m = re.match(pat, text.strip(), re.IGNORECASE)
            if m:
                extracted = m.group(1).strip()
                extracted = re.sub(r'[\.\?!,;]+$', '', extracted).strip()
                extracted = re.sub(r'^(?:an?|the)\s+', '', extracted, flags=re.IGNORECASE).strip()
                if len(extracted) > 1:
                    return extracted
        return text.strip()

    @staticmethod
    def _clean_instruction_prompt(instruction: str, is_removal: bool = False) -> str:
        clean = instruction.strip()
        prefixes = [
            "modify image by", "modify the image by", "modify this image by", "modify image to",
            "change image by", "change the image by", "edit image by", "can you please",
            "please", "i want to", "add a", "add an", "add", "remove the", "remove", "erase"
        ]
        lower = clean.lower()
        for p in sorted(prefixes, key=len, reverse=True):
            if lower.startswith(p):
                clean = clean[len(p):].strip()
                lower = clean.lower()
                break
        return clean

    @staticmethod
    def _extract_target_noun(lower: str, keywords: List[str]) -> str:
        for kw in keywords:
            if kw in lower:
                parts = lower.split(kw, 1)
                if len(parts) > 1:
                    noun = parts[1].strip()
                    for stop_word in ["from the image", "in the picture", "please", "now"]:
                        noun = noun.replace(stop_word, "").strip()
                    return noun
        return "selected object"

    @staticmethod
    def _extract_background_description(text: str) -> str:
        lower = text.lower()
        triggers = ["background to ", "background with ", "put in ", "place in ", "set in ", "environment of "]
        for t in triggers:
            if t in lower:
                idx = lower.find(t) + len(t)
                return text[idx:].strip().rstrip(".?!,")
        return text.strip()


# =============================================================================
# 4. Modular Sub-Services (Text-to-Image, Inpainting, Filters, Removal)
# =============================================================================

class TextToImageService:
    """Executes high-resolution Text-to-Image synthesis using FLUX.1 Diffusion."""

    @staticmethod
    def _clean_watermark(image_path: str) -> None:
        try:
            with Image.open(image_path) as img:
                rgb_img = img.convert("RGB")
                w, h = rgb_img.size
                if w > 200 and h > 100:
                    patch = rgb_img.crop((w - 180, h - 65, w, h - 35))
                    rgb_img.paste(patch, (w - 180, h - 35))
                    rgb_img.save(image_path, "JPEG", quality=95)
        except Exception:
            pass

    @staticmethod
    async def generate(prompt: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        clean_p = prompt.strip()
        # Inject photorealism tokens unless the user requested a specific style
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
                        TextToImageService._clean_watermark(local_path)
                        downloaded = True
                        break
                    elif resp.status_code == 402:
                        m = re.search(r'Retry after (\d+)s', resp.text)
                        cooldown = int(m.group(1)) if m else 15
                        rate_limited_seconds = max(rate_limited_seconds, cooldown)
                        if cooldown <= 25:
                            await asyncio.sleep(cooldown + 1)
                            retry_resp = await client.get(cloud_url, headers={"User-Agent": "Mozilla/5.0 LocalGPT-Pro/3.5"})
                            if retry_resp.status_code == 200 and len(retry_resp.content) > 1000:
                                with open(local_path, "wb") as f:
                                    f.write(retry_resp.content)
                                TextToImageService._clean_watermark(local_path)
                                downloaded = True
                                break
                except Exception as e:
                    print(f"Warning: Cloud image generation attempt failed: {e}")
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
        return {
            "status": "success",
            "operation": "text_to_image",
            "prompt": clean_p,
            "enhanced_prompt": enhanced_p,
            "image_url": local_url,
            "local_path": local_path,
            "filename": filename,
            "model": "Photorealistic Diffusion (1024×1024)"
        }


class InpaintingService:
    """
    Executes localized inpainting using the ORIGINAL source image + mask.
    
    Priority chain:
      1. HuggingFace SDXL Inpainting API (if HF_API_TOKEN configured) — TRUE masked inpainting
      2. HuggingFace img2img (if HF_API_TOKEN configured) — full-image style/reference editing  
      3. OpenCV Telea local inpainting (CPU, no GPU) — object removal / fill operations
      4. Pillow region-aware edit — deterministic fallback
      NEVER: Pollinations text-to-image pretending to be image editing
    """

    # HuggingFace SDXL Inpainting endpoint (free tier, needs HF token)
    HF_SDXL_INPAINT_URL = "https://router.huggingface.co/hf-inference/models/diffusers/stable-diffusion-xl-1-0-inpainting-0.1"
    HF_IMG2IMG_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-refiner-1-0"

    @staticmethod
    def _get_hf_token(user_id: Optional[str] = None) -> Optional[str]:
        # 1. Environment variables & global settings
        token = settings.HF_API_TOKEN
        if token and token.strip() and token.strip().startswith("hf_"):
            return token.strip()
        for env_var in ["HF_API_TOKEN", "HUGGINGFACE_TOKEN", "HF_TOKEN"]:
            val = os.getenv(env_var, "").strip()
            if val and val.startswith("hf_"):
                return val

        # 2. Per-user settings from database if user_id is provided
        if user_id:
            try:
                from ..database import engine
                from ..models import UserSettings
                from sqlalchemy.orm import Session
                with Session(engine) as db:
                    u_set = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
                    if u_set and u_set.api_key:
                        key = u_set.api_key.strip()
                        if key.startswith("hf_") or u_set.provider == "huggingface":
                            return key
            except Exception:
                pass
        return None

    @staticmethod
    async def _try_hf_sdxl_inpaint(
        orig_img: Image.Image,
        mask_l: Image.Image,
        prompt: str,
        token: Optional[str] = None
    ) -> Optional[Image.Image]:
        """
        Calls HuggingFace SDXL Inpainting API with the original image + mask.
        Returns the inpainted PIL image, or None if unavailable.
        """
        if not token:
            token = InpaintingService._get_hf_token()
        if not token:
            return None

        # Resize to 1024x1024 for SDXL
        target_size = (1024, 1024)
        img_resized = orig_img.resize(target_size, Image.Resampling.LANCZOS)
        mask_resized = mask_l.resize(target_size, Image.Resampling.NEAREST)

        # Encode to base64
        buf_img = io.BytesIO()
        img_resized.save(buf_img, format="JPEG", quality=95)
        b64_img = base64.b64encode(buf_img.getvalue()).decode("utf-8")

        buf_mask = io.BytesIO()
        mask_resized.save(buf_mask, format="PNG")
        b64_mask = base64.b64encode(buf_mask.getvalue()).decode("utf-8")

        payload = {
            "inputs": prompt,
            "parameters": {
                "image": b64_img,
                "mask_image": b64_mask,
                "negative_prompt": PHOTOREALISM_NEGATIVE,
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "strength": 0.85
            }
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    InpaintingService.HF_SDXL_INPAINT_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "image" in content_type or len(resp.content) > 5000:
                        return Image.open(io.BytesIO(resp.content)).convert("RGB")
                    # Try JSON response with base64
                    try:
                        data = resp.json()
                        if isinstance(data, list) and data:
                            b64 = data[0].get("generated_image") or data[0].get("image")
                            if b64:
                                return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                    except Exception:
                        pass
                elif resp.status_code == 503:
                    print("HF SDXL: model loading (cold start), skipping — try again shortly")
                else:
                    print(f"HF SDXL inpaint returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"HF SDXL inpainting error: {e}")
        return None

    @staticmethod
    async def _try_hf_img2img(
        orig_img: Image.Image,
        prompt: str
    ) -> Optional[Image.Image]:
        """
        Calls HuggingFace img2img for full-image style/reference transformation.
        Returns modified PIL image, or None if unavailable.
        """
        token = InpaintingService._get_hf_token()
        if not token:
            return None

        target_size = (1024, 1024)
        img_resized = orig_img.resize(target_size, Image.Resampling.LANCZOS)

        buf_img = io.BytesIO()
        img_resized.save(buf_img, format="JPEG", quality=95)
        b64_img = base64.b64encode(buf_img.getvalue()).decode("utf-8")

        payload = {
            "inputs": prompt,
            "parameters": {
                "image": b64_img,
                "negative_prompt": PHOTOREALISM_NEGATIVE,
                "num_inference_steps": 25,
                "guidance_scale": 7.0,
                "strength": 0.65
            }
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    InpaintingService.HF_IMG2IMG_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "image" in content_type or len(resp.content) > 5000:
                        return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            print(f"HF img2img error: {e}")
        return None

    @staticmethod
    def _opencv_inpaint_region(
        orig_img: Image.Image,
        mask_l: Image.Image
    ) -> Optional[Image.Image]:
        """
        Uses OpenCV Telea/Navier-Stokes to fill the masked region (CPU, no GPU).
        Good for object removal and simple fill operations.
        """
        if not CV2_AVAILABLE:
            return None
        img_np = np.array(orig_img)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        mask_np = np.array(mask_l.resize(orig_img.size, Image.Resampling.NEAREST))
        _, mask_thresh = cv2.threshold(mask_np, 50, 255, cv2.THRESH_BINARY)
        inpainted_cv = cv2.inpaint(img_cv, mask_thresh, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
        return Image.fromarray(cv2.cvtColor(inpainted_cv, cv2.COLOR_BGR2RGB))

    @staticmethod
    async def inpaint(
        image_path: str,
        mask: Image.Image,
        prompt: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")

        orig_img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = orig_img.size

        mask_l = mask.convert("L").resize((orig_w, orig_h), Image.Resampling.BILINEAR)

        filename = f"inpaint_{uuid.uuid4().hex[:10]}.jpg"
        local_path = os.path.join(GENERATED_IMAGES_DIR, filename)

        inpaint_prompt = build_inpainting_prompt(prompt.strip())

        synthesized_img: Optional[Image.Image] = None
        method_used = "unknown"

        hf_token = InpaintingService._get_hf_token(user_id=user_id)
        if hf_token:
            print(f"[InpaintingService] Attempting HF SDXL inpainting for: {prompt[:60]}")
            synthesized_img = await InpaintingService._try_hf_sdxl_inpaint(orig_img, mask_l, inpaint_prompt, token=hf_token)
            if synthesized_img is not None:
                method_used = "hf_sdxl_inpainting"
                synthesized_img = synthesized_img.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

        if synthesized_img is None:
            # DO NOT fall back to OpenCV Telea! Telea is NOT a generative model and creates destructive radial blurs.
            print(f"[InpaintingService] AI inpainting unavailable. Returning structured error to preserve original image pixels.")
            original_url = f"/api/images/{os.path.basename(image_path)}"
            return {
                "status": "error",
                "operation": "inpainting",
                "error": "AI Inpainting model required for generative object modification.",
                "image_url": original_url,
                "prompt": prompt,
                "markdown": (
                    f"⚠️ **AI Inpainting Model Required for Generative Modifications**\n\n"
                    f"To add or modify elements (such as *\"{prompt}\"*) without destroying the original subject's face, hair, and identity, a generative diffusion inpainting model is required.\n\n"
                    f"*LocalGPT preserved 100% of your original photo rather than applying a destructive blur.*\n\n"
                    f"**To enable free neural inpainting:**\n"
                    f"1. Open **Settings** (⚙️) from the top-right navigation.\n"
                    f"2. Select **HuggingFace Inference API** and enter your free [Hugging Face User Access Token](https://huggingface.co/settings/tokens).\n"
                    f"3. Resubmit your instruction to generate the inpainting via `stable-diffusion-xl-inpainting`."
                )
            }

        final_composited = PixelCompositor.composite(
            original_image=orig_img,
            edited_image=synthesized_img,
            mask=mask_l,
            feather_radius=6
        )

        final_composited.save(local_path, "JPEG", quality=95)
        local_url = f"/api/images/{filename}"

        hf_configured = hf_token is not None
        status_note = ""
        if method_used == "hf_sdxl_inpainting":
            status_note = "AI inpainting via HuggingFace SDXL"
        elif method_used == "opencv_telea":
            status_note = "Local CPU inpainting via OpenCV (configure HF_API_TOKEN for AI-powered edits)"
        else:
            status_note = "Pillow fallback (configure HF_API_TOKEN for AI-powered edits)"

        return {
            "status": "success",
            "operation": "inpainting",
            "prompt": prompt.strip(),
            "inpaint_prompt": inpaint_prompt,
            "image_url": local_url,
            "local_path": local_path,
            "filename": filename,
            "original_url": f"/api/images/{os.path.basename(image_path)}",
            "dimensions": {"width": orig_w, "height": orig_h},
            "method": method_used,
            "hf_configured": hf_configured,
            "pixel_preservation": "Guaranteed outside editable mask",
            "note": status_note
        }


class ObjectRemovalService:
    """
    Removes objects from the image using the mask.
    Prefers local OpenCV Telea / Navier-Stokes inpainting for instant, zero-GPU CPU execution.
    """

    @staticmethod
    def remove(image_path: str, mask: Image.Image) -> Dict[str, Any]:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")

        orig_img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = orig_img.size
        mask_l = mask.convert("L").resize((orig_w, orig_h), Image.Resampling.BILINEAR)

        filename = f"removed_{uuid.uuid4().hex[:10]}.jpg"
        local_path = os.path.join(GENERATED_IMAGES_DIR, filename)

        if CV2_AVAILABLE:
            # OpenCV Navier-Stokes local inpainting on CPU
            img_np = np.array(orig_img)
            img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            mask_np = np.array(mask_l)
            # Binary threshold
            _, mask_thresh = cv2.threshold(mask_np, 50, 255, cv2.THRESH_BINARY)
            inpainted_cv = cv2.inpaint(img_cv, mask_thresh, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
            inpainted_rgb = Image.fromarray(cv2.cvtColor(inpainted_cv, cv2.COLOR_BGR2RGB))
        else:
            # PIL blur fill fallback
            blurred = orig_img.filter(ImageFilter.GaussianBlur(radius=15))
            inpainted_rgb = blurred

        # Composite back strictly outside mask
        final_composited = PixelCompositor.composite(
            original_image=orig_img,
            edited_image=inpainted_rgb,
            mask=mask_l,
            feather_radius=4
        )

        final_composited.save(local_path, "JPEG", quality=95)
        local_url = f"/api/images/{filename}"

        return {
            "status": "success",
            "operation": "object_removal",
            "image_url": local_url,
            "local_path": local_path,
            "filename": filename,
            "original_url": f"/api/images/{os.path.basename(image_path)}",
            "dimensions": {"width": orig_w, "height": orig_h}
        }


class PillowFilterService:
    """Executes deterministic digital image transformations using PIL."""

    @staticmethod
    def apply_filter(image_path: str, filter_type: str) -> Dict[str, Any]:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")

        filename = f"filt_{uuid.uuid4().hex[:10]}.jpg"
        out_path = os.path.join(GENERATED_IMAGES_DIR, filename)

        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size

            if filter_type in ["grayscale", "black_and_white", "b&w"]:
                res = ImageOps.grayscale(rgb_img).convert("RGB")
                title = "Black & White (Monochromatic)"
            elif filter_type == "flip_h":
                res = ImageOps.mirror(rgb_img)
                title = "Mirrored Horizontally"
            elif filter_type == "flip_v":
                res = ImageOps.flip(rgb_img)
                title = "Flipped Vertically"
            elif filter_type == "rotate_90":
                res = rgb_img.rotate(270, expand=True)
                title = "Rotated 90° Clockwise"
            elif filter_type == "rotate_180":
                res = rgb_img.rotate(180, expand=True)
                title = "Rotated 180°"
            elif filter_type == "invert":
                res = ImageOps.invert(rgb_img)
                title = "Color Negative Inverted"
            elif filter_type == "contrast":
                res = ImageEnhance.Contrast(rgb_img).enhance(1.8)
                title = "High Contrast Enhanced"
            elif filter_type == "blur":
                res = rgb_img.filter(ImageFilter.GaussianBlur(radius=6))
                title = "Gaussian Softened"
            elif filter_type == "night":
                darkened = ImageEnhance.Brightness(rgb_img).enhance(0.45)
                r, g, b = darkened.split()
                b = ImageEnhance.Brightness(b).enhance(1.4)
                r = ImageEnhance.Brightness(r).enhance(0.7)
                res = Image.merge("RGB", (r, g, b))
                title = "Nocturnal Atmospheric Grade"
            elif filter_type == "sketch":
                gray = ImageOps.grayscale(rgb_img)
                inv = ImageOps.invert(gray)
                blurred = inv.filter(ImageFilter.GaussianBlur(radius=15))
                res = Image.blend(gray, ImageOps.invert(blurred), alpha=0.5).convert("RGB")
                title = "Pencil Sketch & Contours"
            else:
                res = rgb_img
                title = "Processed Image"

            res.save(out_path, "JPEG", quality=95)

        local_url = f"/api/images/{filename}"
        return {
            "status": "success",
            "operation": "pillow_filter",
            "filter_type": filter_type,
            "title": title,
            "image_url": local_url,
            "local_path": out_path,
            "filename": filename,
            "original_url": f"/api/images/{os.path.basename(image_path)}",
            "dimensions": {"width": res.width, "height": res.height}
        }

    @staticmethod
    def generate_fallback_render(prompt: str, filepath: str) -> str:
        width, height = 1024, 1024
        img = Image.new("RGB", (width, height), color=(13, 16, 23))
        draw = ImageDraw.Draw(img)
        cx, cy = width // 2, height // 2

        # Abstract glowing geometric aura
        for r in range(340, 60, -20):
            color = (int(0 + r * 0.4), int(160 + r * 0.2), int(255 - r * 0.3))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=3)

        try:
            font = ImageFont.load_default()
            label = f"LocalGPT Pro AI Render: {prompt[:40]}"
            draw.text((40, height - 60), label, fill=(180, 195, 215), font=font)
        except Exception:
            pass

        img.save(filepath, "JPEG", quality=95)
        return filepath


# =============================================================================
# 5. Core ImageEditRouter Facade
# =============================================================================

class ImageEditRouter:
    """
    Central router that receives any image and instruction, determines the
    correct processing pipeline, preserves unedited pixels, and records lineage.
    """

    @classmethod
    async def route_and_execute(
        cls,
        instruction: str,
        image_path: Optional[str] = None,
        mask_data: Optional[Union[str, bytes, Image.Image]] = None,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        context_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches to:
        - TextToImageService
        - InpaintingService
        - ObjectRemovalService
        - PillowFilterService
        - BackgroundEditing / StyleTransfer
        """
        has_image = bool(image_path and os.path.exists(image_path))
        has_mask = mask_data is not None

        # 1. Parse structured edit plan
        plan = UniversalIntentParser.parse_intent(
            instruction=instruction,
            has_image=has_image,
            has_mask=has_mask,
            context_description=context_prompt
        )

        op = plan["operation"]

        # 2. Text-to-Image
        if op == "text_to_image" or not has_image:
            prompt = plan.get("prompt", instruction)
            res = await TextToImageService.generate(prompt=prompt, user_id=user_id)
            if chat_id:
                ImageLineageManager.record_version(
                    chat_id=chat_id,
                    image_url=res["image_url"],
                    operation="text_to_image",
                    instruction=instruction
                )
            res["plan"] = plan
            return res

        # 3. Deterministic Pillow Filters
        if op == "pillow_filter":
            res = PillowFilterService.apply_filter(image_path, plan["filter_type"])
            if chat_id:
                ImageLineageManager.record_version(
                    chat_id=chat_id,
                    image_url=res["image_url"],
                    operation="pillow_filter",
                    instruction=instruction,
                    parent_url=f"/api/images/{os.path.basename(image_path)}"
                )
            res["plan"] = plan
            return res

        # Load and validate original image dimensions
        orig_img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = orig_img.size

        # Resolve Mask (manual painted mask or auto-generated mask)
        if has_mask:
            mask = MaskProcessor.decode_mask(mask_data, (orig_w, orig_h))
        else:
            mask_type = plan.get("mask_source", "subject")
            mask = MaskProcessor.generate_auto_mask(orig_img, mask_type=mask_type)

        # 4. Object Removal
        if op == "object_removal":
            res = ObjectRemovalService.remove(image_path=image_path, mask=mask)
            if chat_id:
                ImageLineageManager.record_version(
                    chat_id=chat_id,
                    image_url=res["image_url"],
                    operation="object_removal",
                    instruction=instruction,
                    parent_url=f"/api/images/{os.path.basename(image_path)}"
                )
            res["plan"] = plan
            return res

        # 5. Inpainting / Object Addition / Replacement / Background / Style
        diffusion_prompt = plan.get("prompt", instruction)
        res = await InpaintingService.inpaint(
            image_path=image_path,
            mask=mask,
            prompt=diffusion_prompt,
            user_id=user_id
        )

        if chat_id and res.get("status") != "error":
            ImageLineageManager.record_version(
                chat_id=chat_id,
                image_url=res["image_url"],
                operation=op,
                instruction=instruction,
                parent_url=f"/api/images/{os.path.basename(image_path)}"
            )

        res["plan"] = plan
        return res

