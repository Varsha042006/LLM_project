import sqlite3
import httpx
import asyncio
import base64

conn = sqlite3.connect('chatgpt_platform.db')
c = conn.cursor()
c.execute("SELECT api_key FROM user_settings WHERE provider='gemini' AND length(api_key) > 10")
key = c.fetchone()[0]

async def test_multiturn_vqa():
    with open("test_arch_diag.png", "rb") as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"
    
    # Turn 1: Explain diagram
    payload1 = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "Explain this architecture diagram."},
                    {"inline_data": {"mime_type": "image/png", "data": b64}}
                ]
            }
        ]
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r1 = await client.post(url, json=payload1)
        ans1 = r1.json()['candidates'][0]['content']['parts'][0]['text']
        print("=== Turn 1 (Explain this image) ===")
        print(ans1[:200])
        print()

        # Turn 2: Follow-up question about database
        payload2 = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "Explain this architecture diagram."},
                        {"inline_data": {"mime_type": "image/png", "data": b64}}
                    ]
                },
                {
                    "role": "model",
                    "parts": [{"text": ans1}]
                },
                {
                    "role": "user",
                    "parts": [
                        {"text": "What does the database component do?"},
                        {"inline_data": {"mime_type": "image/png", "data": b64}}
                    ]
                }
            ]
        }
        r2 = await client.post(url, json=payload2)
        ans2 = r2.json()['candidates'][0]['content']['parts'][0]['text']
        print("=== Turn 2 Follow-up (What does the database component do?) ===")
        print(ans2[:300])

asyncio.run(test_multiturn_vqa())

