import sqlite3
import httpx
import asyncio
import base64
import os
from PIL import Image, ImageDraw

# Create a test architecture diagram image
img = Image.new('RGB', (600, 300), color=(255, 255, 255))
d = ImageDraw.Draw(img)
d.rectangle([50, 50, 200, 150], outline=(0, 0, 0), width=2)
d.text((70, 90), "Frontend (React)", fill=(0, 0, 0))
d.rectangle([350, 50, 500, 150], outline=(0, 0, 0), width=2)
d.text((370, 90), "Backend (FastAPI)", fill=(0, 0, 0))
d.line([(200, 100), (350, 100)], fill=(0, 0, 255), width=3)
d.text((230, 80), "REST API", fill=(0, 0, 255))
d.rectangle([350, 180, 500, 260], outline=(0, 0, 0), width=2)
d.text((370, 210), "Database (PostgreSQL)", fill=(0, 0, 0))
d.line([(425, 150), (425, 180)], fill=(0, 128, 0), width=3)
d.text((435, 160), "SQLAlchemy", fill=(0, 128, 0))
img.save("test_arch_diag.png")

conn = sqlite3.connect('chatgpt_platform.db')
c = conn.cursor()
c.execute("SELECT api_key FROM user_settings WHERE provider='gemini' AND length(api_key) > 10")
key = c.fetchone()[0]

async def test_vqa():
    with open("test_arch_diag.png", "rb") as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    
    question = "Explain the workflow and architecture in this image."
    for model_name in ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"You are a specialized visual intelligence and computer vision expert. The user uploaded an image and asked the following question:\n\nUser Question: {question}\n\nPlease analyze the image thoroughly and answer the user's question directly, clearly, and accurately based on the visual evidence in the image."},
                        {"inline_data": {"mime_type": "image/png", "data": b64}}
                    ]
                }
            ]
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload)
            print(f"Model {model_name}: status = {resp.status_code}")
            if resp.status_code == 200:
                print("Response:\n", resp.json()['candidates'][0]['content']['parts'][0]['text'])
                break
            else:
                print("Error:", resp.text[:200])

asyncio.run(test_vqa())
