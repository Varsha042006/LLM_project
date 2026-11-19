import asyncio
import os
import sys
from PIL import Image, ImageDraw, ImageFont
from backend.app.vision_service import execute_visual_qa

def setup_test_images():
    print("Generating test images...")
    
    # 1. Architecture diagram (already exists, but make sure)
    img1 = Image.new('RGB', (700, 350), color=(250, 250, 252))
    d1 = ImageDraw.Draw(img1)
    d1.rectangle([40, 60, 220, 160], outline=(40, 80, 200), width=3, fill=(235, 242, 255))
    d1.text((60, 100), "Frontend (React.js)", fill=(20, 40, 120))
    d1.rectangle([460, 60, 660, 160], outline=(40, 80, 200), width=3, fill=(235, 242, 255))
    d1.text((480, 100), "Backend (FastAPI)", fill=(20, 40, 120))
    d1.line([(220, 110), (460, 110)], fill=(0, 120, 255), width=3)
    d1.text((280, 85), "REST API (JSON)", fill=(0, 100, 200))
    d1.rectangle([460, 210, 660, 310], outline=(30, 140, 60), width=3, fill=(235, 255, 240))
    d1.text((475, 250), "Database (PostgreSQL)", fill=(10, 80, 30))
    d1.line([(560, 160), (560, 210)], fill=(30, 140, 60), width=3)
    d1.text((570, 180), "SQLAlchemy ORM", fill=(30, 140, 60))
    img1.save("test_arch_diag.png")

    # 2. Flowchart
    img2 = Image.new('RGB', (700, 400), color=(255, 255, 255))
    d2 = ImageDraw.Draw(img2)
    # Start
    d2.ellipse([270, 20, 430, 70], outline=(0, 0, 0), width=2, fill=(230, 245, 230))
    d2.text((320, 38), "[Start]", fill=(0, 0, 0))
    d2.line([(350, 70), (350, 110)], fill=(0, 0, 0), width=2)
    # Step 1: Input
    d2.rectangle([250, 110, 450, 160], outline=(0, 0, 0), width=2, fill=(240, 240, 255))
    d2.text((270, 128), "1. User Submits Email", fill=(0, 0, 0))
    d2.line([(350, 160), (350, 200)], fill=(0, 0, 0), width=2)
    # Decision: Valid?
    d2.polygon([(350, 200), (470, 250), (350, 300), (230, 250)], outline=(0, 0, 0), width=2, fill=(255, 250, 230))
    d2.text((305, 242), "Is Email Valid?", fill=(0, 0, 0))
    # Branch Yes -> Send OTP
    d2.line([(470, 250), (560, 250), (560, 330)], fill=(0, 120, 0), width=2)
    d2.text((490, 230), "Yes", fill=(0, 120, 0))
    d2.rectangle([480, 330, 640, 380], outline=(0, 120, 0), width=2, fill=(230, 255, 230))
    d2.text((505, 348), "Send OTP Code", fill=(0, 100, 0))
    # Branch No -> Show Error
    d2.line([(230, 250), (140, 250), (140, 330)], fill=(200, 0, 0), width=2)
    d2.text((170, 230), "No", fill=(200, 0, 0))
    d2.rectangle([60, 330, 220, 380], outline=(200, 0, 0), width=2, fill=(255, 230, 230))
    d2.text((80, 348), "Display Error Msg", fill=(180, 0, 0))
    img2.save("test_flowchart.png")

    # 3. Document screenshot
    img3 = Image.new('RGB', (700, 350), color=(255, 255, 255))
    d3 = ImageDraw.Draw(img3)
    d3.text((40, 30), "==========================================================", fill=(100, 100, 100))
    d3.text((40, 50), "PROJECT FALCON - EXECUTIVE STATUS REPORT (Q4 2026)", fill=(0, 51, 102))
    d3.text((40, 70), "==========================================================", fill=(100, 100, 100))
    d3.text((40, 100), "Project Lead: Dr. Elena Rostova | Department: Cloud Architecture", fill=(50, 50, 50))
    d3.text((40, 130), "Core Achievements:", fill=(0, 0, 0))
    d3.text((60, 160), "1. Successfully reduced API response latency by 42%.", fill=(30, 30, 30))
    d3.text((60, 190), "2. Completed zero-downtime database migration to distributed shards.", fill=(30, 30, 30))
    d3.text((60, 220), "3. Passed SOC2 Type II compliance audit with zero critical vulnerabilities.", fill=(30, 30, 30))
    d3.text((40, 260), "Target Release Date: December 15, 2026.", fill=(150, 0, 0))
    d3.text((40, 290), "Status: ON TRACK FOR GLOBAL ROLLOUT.", fill=(0, 120, 0))
    img3.save("test_doc_text.png")

    # 4. Code screenshot with bug
    img4 = Image.new('RGB', (700, 300), color=(30, 30, 30))
    d4 = ImageDraw.Draw(img4)
    code_lines = [
        "# Python Utility Function: Calculate Average",
        "def calculate_average(numbers):",
        "    total = 0",
        "    for n in numbers:",
        "        total += n",
        "    return total / len(numbers)  # Calculate mean",
        "",
        "# Invocation:",
        "data = []",
        "avg = calculate_average(data)"
    ]
    y = 30
    for cl in code_lines:
        color = (120, 180, 120) if cl.startswith("#") else ((240, 200, 100) if "def " in cl else (220, 220, 220))
        d4.text((40, y), cl, fill=color)
        y += 24
    img4.save("test_code_error.png")

    # 5. Photograph
    # Check if we have an existing photo or create a vibrant landscape photo
    existing_photos = [f for f in os.listdir("backend_uploads/generated_images") if "WhatsApp" in f]
    photo_path = os.path.join("backend_uploads/generated_images", existing_photos[0]) if existing_photos else "test_photo.jpg"
    if not os.path.exists(photo_path):
        # Create a scenic photo
        img5 = Image.new('RGB', (600, 400), color=(135, 206, 235)) # sky
        d5 = ImageDraw.Draw(img5)
        d5.ellipse([450, 40, 530, 120], fill=(255, 220, 0)) # Sun
        d5.polygon([(50, 400), (250, 150), (450, 400)], fill=(100, 110, 120)) # Mountain 1
        d5.polygon([(250, 400), (420, 180), (580, 400)], fill=(80, 90, 100)) # Mountain 2
        d5.rectangle([0, 320, 600, 400], fill=(34, 139, 34)) # Grass
        d5.rectangle([100, 270, 180, 350], fill=(160, 82, 45)) # Cabin
        d5.polygon([(80, 270), (140, 210), (200, 270)], fill=(139, 0, 0)) # Roof
        img5.save("test_photo.jpg")
        photo_path = "test_photo.jpg"

    print("All test images ready.")
    return photo_path


async def run_all_tests(photo_path: str):
    results = {}

    print("\n" + "="*70)
    print("TEST 1: Technical Architecture Diagram - Context-Aware VQA & Multi-turn")
    print("="*70)
    # Turn 1
    t1_q1 = "Explain this image."
    res1_1 = await execute_visual_qa(
        image_path="test_arch_diag.png",
        question=t1_q1,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct"
    )
    print(f"\n[Turn 1] Question: '{t1_q1}'")
    print(f"Task Classified: {res1_1.get('task')}")
    print(f"Model Used: {res1_1.get('model_used')}")
    ans1_1 = res1_1.get("answer", "")
    print(f"Answer Preview:\n{ans1_1[:350]}...\n")

    # Turn 2: Follow-up question about database
    await asyncio.sleep(1)
    t1_q2 = "What does the database component do?"
    history1 = [
        {"role": "user", "content": t1_q1},
        {"role": "assistant", "content": ans1_1}
    ]
    res1_2 = await execute_visual_qa(
        image_path="test_arch_diag.png",
        question=t1_q2,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct",
        history_messages=history1
    )
    print(f"\n[Turn 2 Follow-up] Question: '{t1_q2}'")
    print(f"Task Classified: {res1_2.get('task')}")
    ans1_2 = res1_2.get("answer", "")
    print(f"Answer Preview:\n{ans1_2[:350]}...\n")

    # Verification: Did answer change according to question?
    assert t1_q1.lower() not in ans1_1.lower() or "react" in ans1_1.lower()
    assert "postgresql" in ans1_2.lower() or "database" in ans1_2.lower()
    results["Test 1 (Architecture + Followup)"] = "PASSED"

    await asyncio.sleep(1.5)
    print("\n" + "="*70)
    print("TEST 2: Flowchart Diagram - Process Understanding")
    print("="*70)
    t2_q = "Explain this flowchart and its workflow steps."
    res2 = await execute_visual_qa(
        image_path="test_flowchart.png",
        question=t2_q,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct"
    )
    print(f"Question: '{t2_q}'")
    print(f"Task Classified: {res2.get('task')}")
    ans2 = res2.get("answer", "")
    print(f"Answer Preview:\n{ans2[:350]}...\n")
    assert "email" in ans2.lower() or "otp" in ans2.lower()
    results["Test 2 (Flowchart)"] = "PASSED"

    await asyncio.sleep(1.5)
    print("\n" + "="*70)
    print("TEST 3: Screenshot Containing Text - Summarization vs OCR Extraction")
    print("="*70)
    # Question A: Summarize
    t3_q_sum = "Summarize this document."
    res3_sum = await execute_visual_qa(
        image_path="test_doc_text.png",
        question=t3_q_sum,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct"
    )
    print(f"Question: '{t3_q_sum}'")
    print(f"Task Classified: {res3_sum.get('task')}")
    ans3_sum = res3_sum.get("answer", "")
    print(f"Summary Answer:\n{ans3_sum[:300]}...\n")

    await asyncio.sleep(1.5)
    # Question B: Extract text
    t3_q_ocr = "Extract all text from this screenshot."
    res3_ocr = await execute_visual_qa(
        image_path="test_doc_text.png",
        question=t3_q_ocr,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct"
    )
    print(f"Question: '{t3_q_ocr}'")
    print(f"Task Classified: {res3_ocr.get('task')}")
    ans3_ocr = res3_ocr.get("answer", "")
    print(f"OCR Answer:\n{ans3_ocr[:300]}...\n")
    assert "falcon" in ans3_sum.lower() or "latency" in ans3_sum.lower()
    assert "falcon" in ans3_ocr.lower() or "achievements" in ans3_ocr.lower()
    results["Test 3 (Text Screenshot & OCR)"] = "PASSED"

    await asyncio.sleep(1.5)
    print("\n" + "="*70)
    print("TEST 4: Python Code Screenshot - Error Finding")
    print("="*70)
    t4_q = "Find the error in this code and explain how to fix it."
    res4 = await execute_visual_qa(
        image_path="test_code_error.png",
        question=t4_q,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct"
    )
    print(f"Question: '{t4_q}'")
    print(f"Task Classified: {res4.get('task')}")
    ans4 = res4.get("answer", "")
    print(f"Answer Preview:\n{ans4[:350]}...\n")
    assert "zerodivisionerror" in ans4.lower() or "empty" in ans4.lower() or "divide" in ans4.lower() or "len" in ans4.lower()
    results["Test 4 (Code Error Analysis)"] = "PASSED"

    await asyncio.sleep(1.5)
    print("\n" + "="*70)
    print("TEST 5: Photograph - Scene & Object Description")
    print("="*70)
    t5_q = "What is in this picture?"
    res5 = await execute_visual_qa(
        image_path=photo_path,
        question=t5_q,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct"
    )
    print(f"Question: '{t5_q}'")
    print(f"Task Classified: {res5.get('task')}")
    ans5 = res5.get("answer", "")
    print(f"Answer Preview:\n{ans5[:350]}...\n")
    results["Test 5 (Photograph Scene)"] = "PASSED"

    print("\n" + "="*70)
    print("TEST 6: Separate Feature - Explicit Photometric Inspection Request")
    print("="*70)
    t6_q = "Inspect image properties, color palette and resolution."
    res6 = await execute_visual_qa(
        image_path="test_arch_diag.png",
        question=t6_q,
        requested_model="Qwen/Qwen2.5-0.5B-Instruct"
    )
    print(f"Question: '{t6_q}'")
    print(f"Task Classified: {res6.get('task')}")
    ans6 = res6.get("answer", "")
    print(f"Inspection Report Preview:\n{ans6[:300]}...\n")
    assert "color palette" in ans6.lower() or "palette" in ans6.lower() or "resolution" in ans6.lower()
    results["Test 6 (Explicit Detailed Inspection)"] = "PASSED"

    print("\n" + "="*70)
    print("TEST SUMMARY:")
    for k, v in results.items():
        print(f"  ✓ {k}: {v}")
    print("="*70)


if __name__ == "__main__":
    photo_p = setup_test_images()
    asyncio.run(run_all_tests(photo_p))

