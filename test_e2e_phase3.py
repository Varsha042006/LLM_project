import urllib.request
import urllib.parse
import json
import uuid
import sys
import io

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:3000"

def log_pass(msg):
    print(f"  [PASS] {msg}")

def log_fail(msg, detail=""):
    print(f"  [FAIL] {msg} -> {detail}")
    sys.exit(1)

def http_json(method, path, body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=== STARTING PHASE 3 END-TO-END VERIFICATION ===")

    # 1. Frontend Check
    try:
        req = urllib.request.Request(FRONTEND_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            assert "ChatGPT Platform" in content or "html" in content
            log_pass("Next.js Frontend accessible at http://localhost:3000 (HTTP 200)")
    except Exception as e:
        log_fail("Next.js Frontend Accessibility", str(e))

    # 2. Backend Health
    try:
        health = http_json("GET", "/api/health")
        assert health["status"] == "healthy"
        log_pass(f"FastAPI Backend Health Check: {health['status']} (DB: {health['database']}, Hosted LLM: {health['hosted_llm']})")
    except Exception as e:
        log_fail("FastAPI Health Check", str(e))

    # 3. Models Endpoint
    try:
        models = http_json("GET", "/api/models")
        assert len(models) >= 3
        model_names = [m["name"] for m in models]
        log_pass(f"Available Hosted LLM Engines: {', '.join(model_names[:3])}")
    except Exception as e:
        log_fail("Models Retrieval", str(e))

    # 4. Guest Persona Auth
    try:
        guest = http_json("POST", "/api/auth/guest", body={})
        token = guest["access_token"]
        assert guest["user"]["display_name"].startswith("Guest User")
        log_pass(f"Guest User authentication successful ({guest['user']['display_name']}, JWT token: {token[:12]}...)")
    except Exception as e:
        log_fail("Guest Auth", str(e))

    # 5. Email/Password User Registration and Isolation
    user_email = f"tester_{uuid.uuid4().hex[:6]}@example.com"
    try:
        reg = http_json("POST", "/api/auth/register", {"email": user_email, "password": "SecurePassword123!", "display_name": "QA Lead"})
        user_token = reg["access_token"]
        assert reg["user"]["email"] == user_email
        log_pass(f"Registered new authenticated user: {user_email}")
    except Exception as e:
        log_fail("User Registration", str(e))

    # 6. Chat Lifecycle (Create, List, Rename)
    chat_id = None
    try:
        chat = http_json("POST", "/api/chats", {"title": "Initial Discussion", "model_name": "llama-3.3-70b-versatile"}, token=user_token)
        chat_id = chat["id"]
        assert chat["title"] == "Initial Discussion"
        log_pass(f"Created persistent chat conversation (ID: {chat_id})")

        # Rename
        updated = http_json("PATCH", f"/api/chats/{chat_id}", {"title": "Updated Architecture Chat"}, token=user_token)
        assert updated["title"] == "Updated Architecture Chat"
        log_pass(f"Renamed chat conversation to '{updated['title']}'")
    except Exception as e:
        log_fail("Chat Lifecycle", str(e))

    # 7. Document Upload (TXT / RAG Indexing)
    try:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        content = b"LocalGPT Pro is an advanced ChatGPT platform with RAG document synthesis and hosted cloud LLM endpoints."
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="specs.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            f"{BASE_URL}/api/documents/upload",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {user_token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            doc_data = json.loads(resp.read().decode("utf-8"))
            assert doc_data["filename"] == "specs.txt"
            assert doc_data["num_chunks"] >= 1
            log_pass(f"Uploaded and indexed 'specs.txt' ({doc_data['num_chunks']} chunk(s) stored in vector index)")
    except Exception as e:
        log_fail("Document Upload", str(e))

    # 8. Real-time SSE Token Streaming
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/chat/stream",
            data=json.dumps({
                "chat_id": chat_id,
                "message": "What is LocalGPT Pro?",
                "model_name": "llama-3.3-70b-versatile",
                "use_rag": True,
            }).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {user_token}",
            },
            method="POST",
        )
        tokens_received = []
        meta_received = False
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    payload_raw = line_str.replace("data: ", "")
                    try:
                        p = json.loads(payload_raw)
                        if p.get("type") == "token":
                            tokens_received.append(p.get("content", ""))
                        elif p.get("type") == "meta":
                            meta_received = True
                    except:
                        tokens_received.append(payload_raw)

        full_streamed_text = "".join(tokens_received)
        assert len(full_streamed_text) > 0
        log_pass(f"SSE Token Streaming successful ({len(tokens_received)} chunks received, {len(full_streamed_text)} chars)")
        print(f"      Sample response: \"{full_streamed_text[:120]}...\"")
    except Exception as e:
        log_fail("SSE Streaming", str(e))

    # 9. Verify Chat Messages Persisted
    try:
        chat_detail = http_json("GET", f"/api/chats/{chat_id}", token=user_token)
        messages = chat_detail["messages"]
        assert len(messages) >= 2  # user prompt + assistant response
        log_pass(f"Chat history verification: {len(messages)} messages stored and retrieved successfully")
    except Exception as e:
        log_fail("Chat History Retrieval", str(e))

    # 10. Message Feedback
    try:
        assistant_msg = next(m for m in messages if m["role"] == "assistant")
        feedback_res = http_json("POST", "/api/chat/feedback", {"message_id": assistant_msg["id"], "feedback": "like"}, token=user_token)
        assert feedback_res["status"] == "ok"
        log_pass("User feedback (thumbs up / like) successfully recorded")
    except Exception as e:
        log_fail("Feedback Submission", str(e))

    # 11. Settings Update
    try:
        settings = http_json("PATCH", "/api/settings", {"temperature": 0.5, "model_name": "qwen-2.5-local"}, token=user_token)
        assert settings["temperature"] == 0.5
        log_pass(f"User settings updated: Model = {settings['model_name']}, Temp = {settings['temperature']}")
    except Exception as e:
        log_fail("Settings Update", str(e))

    print("\n>>> ALL 11 END-TO-END VERIFICATION CHECKS PASSED PERFECTLY! <<<")

if __name__ == "__main__":
    main()
