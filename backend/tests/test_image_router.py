import os
import unittest
import numpy as np
from PIL import Image

from backend.app.image_router import (
    ImageEditRouter,
    UniversalIntentParser,
    MaskProcessor,
    PixelCompositor,
    ImageLineageManager,
    PillowFilterService,
    ObjectRemovalService
)
from backend.app.image_service import detect_image_prompt


class TestImageEditRouter(unittest.TestCase):
    """
    Comprehensive test suite for Universal ImageEditRouter, Mask Processing,
    Pixel Preservation, Dimension Preservation, and Multi-Turn Lineage.
    """

    def setUp(self):
        self.test_dir = os.path.join("backend_uploads", "test_scratch")
        os.makedirs(self.test_dir, exist_ok=True)

        # Create a synthetic 200x200 test RGB image
        self.img_path = os.path.join(self.test_dir, "test_source.jpg")
        self.test_img = Image.new("RGB", (200, 200), color=(70, 130, 180)) # Steel blue
        self.test_img.save(self.img_path)

    def tearDown(self):
        # Clean up test scratch files
        if os.path.exists(self.img_path):
            try:
                os.remove(self.img_path)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 1. Routing & Universal Intent Parser Tests
    # -------------------------------------------------------------------------
    def test_text_to_image_routing(self):
        plan = UniversalIntentParser.parse_intent("generate a picture of a cyberpunk cityscape at midnight", has_image=False)
        self.assertEqual(plan["operation"], "text_to_image")
        self.assertEqual(plan["action"], "generate")
        self.assertIn("cityscape", plan["prompt"])

    def test_pillow_filter_routing(self):
        filters = [
            ("make it black and white", "grayscale"),
            ("high contrast dynamic pop", "contrast"),
            ("make it night time", "night"),
            ("turn into a pencil sketch", "sketch"),
            ("flip horizontal mirror", "flip_h"),
            ("rotate 90 degrees", "rotate_90"),
        ]
        for instruction, expected_filter in filters:
            plan = UniversalIntentParser.parse_intent(instruction, has_image=True)
            self.assertEqual(plan["operation"], "pillow_filter")
            self.assertEqual(plan["filter_type"], expected_filter)

    def test_object_addition_routing(self):
        plan = UniversalIntentParser.parse_intent("add a stylish leather jacket to the person", has_image=True)
        self.assertEqual(plan["operation"], "inpainting")
        self.assertEqual(plan["action"], "add")
        self.assertTrue(plan["mask_required"])

    def test_object_removal_routing(self):
        plan = UniversalIntentParser.parse_intent("remove the red coffee cup from the desk", has_image=True)
        self.assertEqual(plan["operation"], "object_removal")
        self.assertEqual(plan["action"], "remove")
        self.assertTrue(plan["mask_required"])

    def test_background_editing_routing(self):
        plan = UniversalIntentParser.parse_intent("change background to a tropical sandy beach", has_image=True)
        self.assertEqual(plan["operation"], "background_editing")
        self.assertEqual(plan["action"], "replace_background")
        self.assertEqual(plan["mask_source"], "background")

    def test_style_transformation_routing(self):
        plan = UniversalIntentParser.parse_intent("transform this into anime studio ghibli style", has_image=True)
        self.assertEqual(plan["operation"], "style_transformation")
        self.assertEqual(plan["action"], "stylize")

    def test_outpainting_routing(self):
        plan = UniversalIntentParser.parse_intent("expand canvas borders and outpaint surroundings", has_image=True)
        self.assertEqual(plan["operation"], "outpainting")
        self.assertEqual(plan["action"], "expand")

    # -------------------------------------------------------------------------
    # 2. Mask Processing Tests
    # -------------------------------------------------------------------------
    def test_mask_processing_and_feathering(self):
        raw_mask = Image.new("L", (100, 100), 0)
        raw_mask.paste(255, (20, 20, 80, 80))

        # Test decode & resize
        resized = MaskProcessor.decode_mask(raw_mask, target_size=(200, 200))
        self.assertEqual(resized.size, (200, 200))

        # Test feathering
        feathered = MaskProcessor.feather_mask(resized, radius=5)
        self.assertEqual(feathered.size, (200, 200))
        # Boundary pixels should have transitional alpha values between 0 and 255
        feathered_arr = np.array(feathered)
        has_intermediate = np.any((feathered_arr > 10) & (feathered_arr < 240))
        self.assertTrue(has_intermediate, "Feathering must produce smooth gradient transitions")

        # Test inversion
        inverted = MaskProcessor.invert_mask(resized)
        self.assertEqual(inverted.size, (200, 200))
        self.assertEqual(inverted.getpixel((0, 0)), 255)
        self.assertEqual(inverted.getpixel((100, 100)), 0)

    def test_auto_masks(self):
        img = Image.new("RGB", (300, 300), (255, 255, 255))
        for m_type in ["subject", "background", "sky", "ground", "border"]:
            mask = MaskProcessor.generate_auto_mask(img, mask_type=m_type)
            self.assertEqual(mask.size, (300, 300))
            self.assertEqual(mask.mode, "L")

    # -------------------------------------------------------------------------
    # 3. Pixel Preservation Tests (Critical Requirement)
    # -------------------------------------------------------------------------
    def test_pixel_preservation_strict(self):
        """
        Guarantees that unmasked pixels in the composited result are
        mathematically identical (100% byte-for-byte) to the original image.
        """
        orig_img = Image.new("RGB", (100, 100), color=(50, 100, 150))
        edited_patch = Image.new("RGB", (100, 100), color=(255, 20, 147)) # Deep pink

        # Strict binary mask: Left half 0 (unmasked/preserved), Right half 255 (edited)
        mask = Image.new("L", (100, 100), 0)
        mask.paste(255, (50, 0, 100, 100))

        composited = PixelCompositor.composite(
            original_image=orig_img,
            edited_image=edited_patch,
            mask=mask,
            feather_radius=0
        )

        orig_arr = np.array(orig_img)
        comp_arr = np.array(composited)

        # Unmasked region (left columns 0 to 49) MUST BE 100% IDENTICAL
        left_orig = orig_arr[:, :50]
        left_comp = comp_arr[:, :50]
        self.assertTrue(
            np.array_equal(left_comp, left_orig),
            "Unmasked pixels outside editable area must match original image 100%!"
        )

        # Edited region (right columns 50 to 99) MUST BE edited color
        right_comp = comp_arr[:, 50:]
        self.assertTrue(
            np.all(right_comp == [255, 20, 147]),
            "Edited pixels inside mask must match edited patch!"
        )

    # -------------------------------------------------------------------------
    # 4. Dimension Preservation Tests
    # -------------------------------------------------------------------------
    def test_dimension_preservation(self):
        """
        Ensures that non-square, custom-aspect-ratio images preserve their
        exact native dimensions after processing.
        """
        orig_w, orig_h = 373, 219
        odd_img = Image.new("RGB", (orig_w, orig_h), color=(80, 80, 80))
        odd_path = os.path.join(self.test_dir, "odd_dim.jpg")
        odd_img.save(odd_path)

        res = PillowFilterService.apply_filter(odd_path, "grayscale")
        self.assertEqual(res["dimensions"]["width"], orig_w)
        self.assertEqual(res["dimensions"]["height"], orig_h)

        with Image.open(res["local_path"]) as out_img:
            self.assertEqual(out_img.size, (orig_w, orig_h))

        if os.path.exists(odd_path):
            os.remove(odd_path)

    # -------------------------------------------------------------------------
    # 5. Multi-Turn Image Lineage & Version History Tests
    # -------------------------------------------------------------------------
    def test_multi_turn_lineage(self):
        import uuid
        chat_id = f"test_chat_unit_lineage_{uuid.uuid4().hex[:8]}"

        # Turn 1: Initial edit
        v1 = ImageLineageManager.record_version(
            chat_id=chat_id,
            image_url="/api/images/test_v1.jpg",
            operation="pillow_filter",
            instruction="make it black and white"
        )
        self.assertEqual(v1["version"], 1)

        latest_1 = ImageLineageManager.get_latest_image_url(chat_id)
        self.assertEqual(latest_1, "/api/images/test_v1.jpg")

        # Turn 2: Follow-up edit on v1
        v2 = ImageLineageManager.record_version(
            chat_id=chat_id,
            image_url="/api/images/test_v2.jpg",
            operation="inpainting",
            instruction="add sunglasses",
            parent_url=latest_1
        )
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["parent_url"], "/api/images/test_v1.jpg")

        latest_2 = ImageLineageManager.get_latest_image_url(chat_id)
        self.assertEqual(latest_2, "/api/images/test_v2.jpg")

        # Verify lineage tree
        all_versions = ImageLineageManager.get_versions(chat_id)
        self.assertEqual(len(all_versions), 2)
        self.assertEqual(all_versions[0]["version"], 1)
        self.assertEqual(all_versions[1]["version"], 2)

    # -------------------------------------------------------------------------
    # 6. Deterministic Pillow Operations Tests
    # -------------------------------------------------------------------------
    def test_all_pillow_filters_execute(self):
        filters = ["grayscale", "contrast", "night", "sketch", "invert", "rotate_90", "rotate_180", "flip_h", "flip_v", "blur"]
        for f in filters:
            res = PillowFilterService.apply_filter(self.img_path, f)
            self.assertEqual(res["status"], "success")
            self.assertTrue(os.path.exists(res["local_path"]))

    def test_detect_image_prompt_variations(self):
        """Verifies universal detection of image generation intents."""
        cases = {
            "generate llm worflow image": "llm workflow",
            "create a futuristic city photo": "futuristic city",
            "make a red sports car picture": "red sports car",
            "draw a cute puppy playing in garden": "cute puppy playing in garden",
            "generate an image of a snow mountain": "snow mountain",
            "generate workflow diagram image": "workflow diagram",
        }
        for prompt, expected_sub in cases.items():
            detected = detect_image_prompt(prompt)
            self.assertIsNotNone(detected, f"Failed to detect image intent for: {prompt}")
            self.assertIn(expected_sub, detected.lower())


if __name__ == "__main__":
    unittest.main()

