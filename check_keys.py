import sqlite3
import httpx
import asyncio

conn = sqlite3.connect('chatgpt_platform.db')
c = conn.cursor()
c.execute("SELECT provider, api_key FROM user_settings WHERE length(api_key) > 10")
rows = c.fetchall()

async def main():
    for prov, key in rows:
        print(f"Provider: {prov}, Key prefix: {key[:8]}...")
        if prov == 'groq':
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get('https://api.groq.com/openai/v1/models', headers={'Authorization': f'Bearer {key}'})
                if resp.status_code == 200:
                    models = [m['id'] for m in resp.json().get('data', [])]
                    print(f"Groq models count: {len(models)}")
                    print("Sample models:", models[:8])
                    vision = [m for m in models if any(k in m for k in ['vision', 'vl', 'llava', 'image'])]
                    print("Groq vision:", vision)
        elif prov == 'gemini':
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f'https://generativelanguage.googleapis.com/v1beta/models?key={key}')
                if resp.status_code == 200:
                    models = [m['name'] for m in resp.json().get('models', [])]
                    print("Exact Gemini models:")
                    for m in models:
                        print(m)

asyncio.run(main())
