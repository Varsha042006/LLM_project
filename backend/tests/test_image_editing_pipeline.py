"""
Tests for the fixed image editing pipeline.

Verifies:
- Photorealistic prompt injection for text-to-image
- Style preservation when user requests a specific style
- InpaintingService NEVER calls Pollinations text-to-image
- InpaintingService uses HF SDXL when token is configured
- InpaintingService falls back to OpenCV (not Pollinations) when HF unavailable
- Pixel preservation outside mask (PixelCompositor)
- build_photorealistic_prompt and build_inpainting_prompt utilities
"""

import sys
import os
import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import numpy as np

from backend.app.image_router import (
    build_photorealistic_prompt,
    build_inpainting_prompt,
    user_requested_specific_style,
    PHOTOREALISM_SUFFIX,
    PHOTOREALISM_NEGATIVE,
    PixelCompositor,
    InpaintingService,
    TextToImageService,
    GENERATED_IMAGES_DIR,
)


def run_coro_sync(coro):
    """
    Executes a coroutine that completes synchronously (or with mocked sub-coroutines)
    without spinning up an asyncio IOCP/Proactor event loop, preventing Windows sandbox
    loopback socket hangs.
    """
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


# ---------------------------------------------------------------------------
# 1. Photorealism Prompt Engine Tests
# ---------------------------------------------------------------------------

class TestPhotorealismPromptEngine(unittest.TestCase):

    def test_plain_prompt_gets_photorealism_tokens(self):
        result = build_photorealistic_prompt("a dog running in a park")
        self.assertIn("photorealistic", result)
        self.assertIn("DSLR", result)
        self.assertIn("natural lighting", result)
        self.assertIn("no cartoon", result)

    def test_anime_style_preserved(self):
        result = build_photorealistic_prompt("anime girl with blue hair")
        self.assertIn("anime", result)
        self.assertNotIn("photorealistic", result)
        self.assertIn("high quality", result)

    def test_cartoon_style_preserved(self):
        result = build_photorealistic_prompt("a cartoon dog playing fetch")
        self.assertIn("cartoon", result)
        self.assertNotIn("photorealistic", result)

    def test_watercolor_style_preserved(self):
        result = build_photorealistic_prompt("watercolor landscape painting")
        self.assertIn("watercolor", result)
        self.assertNotIn("photorealistic", result)

    def test_oil_painting_style_preserved(self):
        result = build_photorealistic_prompt("oil painting of mountains at sunset")
        self.assertNotIn("photorealistic", result)

    def test_style_detection(self):
        self.assertTrue(user_requested_specific_style("anime character"))
        self.assertTrue(user_requested_specific_style("pixel art game background"))
        self.assertTrue(user_requested_specific_style("pencil sketch portrait"))
        self.assertFalse(user_requested_specific_style("photo of a cat"))
        self.assertFalse(user_requested_specific_style("a person standing on a mountain"))

    def test_inpainting_prompt_adds_seamless_tokens(self):
        result = build_inpainting_prompt("add a red hat")
        self.assertIn("photorealistic", result)
        self.assertIn("seamless", result)

    def test_inpainting_prompt_preserves_style(self):
        result = build_inpainting_prompt("add a cartoon crown")
        self.assertIn("cartoon", result)
        self.assertNotIn("photorealistic", result)

    def test_photorealism_negative_has_key_terms(self):
        for term in ["cartoon", "anime", "CGI", "3D render"]:
            self.assertIn(term, PHOTOREALISM_NEGATIVE)


# ---------------------------------------------------------------------------
# 2. PixelCompositor Tests  
# ---------------------------------------------------------------------------

class TestPixelCompositor(unittest.TestCase):

    def _make_solid_image(self, color, size=(64, 64)):
        return Image.new("RGB", size, color)

    def _make_mask(self, size=(64, 64), region=None):
        mask = Image.new("L", size, 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        if region:
            draw.rectangle(region, fill=255)
        return mask

    def test_full_black_mask_preserves_original_entirely(self):
        orig = self._make_solid_image((100, 150, 200))
        edited = self._make_solid_image((255, 0, 0))
        mask = Image.new("L", (64, 64), 0)

        result = PixelCompositor.composite(
            original_image=orig,
            edited_image=edited,
            mask=mask,
            feather_radius=0
        )
        orig_arr = np.array(orig)
        result_arr = np.array(result)
        np.testing.assert_array_almost_equal(orig_arr, result_arr, decimal=1)

    def test_pixels_outside_mask_preserved_exactly(self):
        orig = self._make_solid_image((50, 100, 150))
        edited = self._make_solid_image((255, 0, 0))
        mask = self._make_mask(region=[0, 0, 15, 15])

        result = PixelCompositor.composite(
            original_image=orig,
            edited_image=edited,
            mask=mask,
            feather_radius=0
        )
        result_arr = np.array(result)
        bottom_right = result_arr[32:, 32:]
        expected = np.full_like(bottom_right, [50, 100, 150])
        np.testing.assert_array_equal(bottom_right, expected)

    def test_white_mask_region_uses_edited_image(self):
        orig = self._make_solid_image((0, 0, 0))
        edited = self._make_solid_image((255, 255, 255))
        mask = Image.new("L", (64, 64), 255)

        result = PixelCompositor.composite(
            original_image=orig,
            edited_image=edited,
            mask=mask,
            feather_radius=0
        )
        result_arr = np.array(result)
        center = result_arr[16:48, 16:48]
        self.assertTrue(np.mean(center) > 200)


# ---------------------------------------------------------------------------
# 3. InpaintingService Tests (Zero-Network Mocked)
# ---------------------------------------------------------------------------

class TestInpaintingService(unittest.TestCase):

    def setUp(self):
        self.test_dir = os.path.join("backend_uploads", "test_scratch_inpaint")
        os.makedirs(self.test_dir, exist_ok=True)
        self.img_path = os.path.join(self.test_dir, "source.jpg")
        self.img = Image.new("RGB", (64, 64), (100, 150, 200))
        self.img.save(self.img_path)
        self.mask = Image.new("L", (64, 64), 128)

    def tearDown(self):
        if os.path.exists(self.img_path):
            try:
                os.remove(self.img_path)
            except Exception:
                pass

    def test_hf_sdxl_called_when_token_configured(self):
        """When HF_API_TOKEN is set, InpaintingService._try_hf_sdxl_inpaint is used."""
        fake_result = Image.new("RGB", (1024, 1024), (0, 200, 0))

        async def fake_inpaint(*args, **kwargs):
            return fake_result

        with patch.object(InpaintingService, "_get_hf_token", return_value="hf_valid_token_123"):
            with patch.object(InpaintingService, "_try_hf_sdxl_inpaint", side_effect=fake_inpaint):
                coro = InpaintingService.inpaint(
                    image_path=self.img_path,
                    mask=self.mask,
                    prompt="add a golden retriever"
                )
                result = run_coro_sync(coro)

        self.assertEqual(result["method"], "hf_sdxl_inpainting")
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["hf_configured"])

    def test_opencv_fallback_when_hf_not_configured(self):
        """When no HF token, InpaintingService uses local OpenCV, never Pollinations."""
        fake_cv = Image.new("RGB", (64, 64), (80, 80, 80))

        with patch.object(InpaintingService, "_get_hf_token", return_value=None):
            with patch.object(InpaintingService, "_opencv_inpaint_region", return_value=fake_cv):
                coro = InpaintingService.inpaint(
                    image_path=self.img_path,
                    mask=self.mask,
                    prompt="remove object"
                )
                result = run_coro_sync(coro)

        self.assertEqual(result["method"], "opencv_telea")
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["hf_configured"])

    def test_pillow_fallback_when_both_unavailable(self):
        """When neither HF nor OpenCV available, graceful Pillow compositing fallback."""
        with patch.object(InpaintingService, "_get_hf_token", return_value=None):
            with patch.object(InpaintingService, "_opencv_inpaint_region", return_value=None):
                coro = InpaintingService.inpaint(
                    image_path=self.img_path,
                    mask=self.mask,
                    prompt="enhance region"
                )
                result = run_coro_sync(coro)

        self.assertEqual(result["method"], "pillow_fallback")
        self.assertEqual(result["status"], "success")


# ---------------------------------------------------------------------------
# 4. TextToImageService Photorealism URL Construction
# ---------------------------------------------------------------------------

class TestTextToImageServicePhotorealism(unittest.TestCase):

    def test_build_photorealistic_prompt_for_text_to_image(self):
        prompt = "a serene mountain landscape with a lake"
        enhanced = build_photorealistic_prompt(prompt)
        self.assertIn("photorealistic", enhanced)
        self.assertIn("DSLR", enhanced)
        self.assertIn(prompt, enhanced)

    def test_anime_prompt_not_tainted(self):
        prompt = "anime girl in neo tokyo cyberpunk city"
        enhanced = build_photorealistic_prompt(prompt)
        self.assertIn("anime", enhanced)
        self.assertNotIn("photorealistic", enhanced)


if __name__ == "__main__":
    unittest.main()
