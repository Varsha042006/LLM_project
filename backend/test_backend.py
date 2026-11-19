import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import SessionLocal, init_db
from backend.app.models import User, Chat, Document

client = TestClient(app)


class TestBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_health_and_models(self):
        res = client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

        res_models = client.get("/api/models")
        self.assertEqual(res_models.status_code, 200)
        models = res_models.json()
        self.assertGreater(len(models), 0)
        self.assertTrue(any("groq" in m.get("provider", "") for m in models))

    def test_02_guest_auth(self):
        res = client.post("/api/auth/guest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("user", data)
        self.assertTrue(data["user"]["display_name"].startswith("Guest User"))
        
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res_me = client.get("/api/auth/me", headers=headers)
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.json()["id"], data["user"]["id"])

    def test_03_email_signup_and_login(self):
        email = "phase3_tester@localgpt.dev"
        password = "SecurePassword2026!"
        
        # Register
        res_reg = client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "display_name": "Phase 3 Tester"
        })
        # If exists from previous run, ignore 400
        if res_reg.status_code != 200:
            self.assertEqual(res_reg.status_code, 400)
        else:
            self.assertEqual(res_reg.status_code, 200)

        # Login
        res_login = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        self.assertEqual(res_login.status_code, 200)
        token = res_login.json()["access_token"]

        # User settings
        headers = {"Authorization": f"Bearer {token}"}
        res_set = client.get("/api/settings", headers=headers)
        self.assertEqual(res_set.status_code, 200)
        self.assertIn("provider", res_set.json())

    def test_04_chat_lifecycle(self):
        # Guest login for clean chat tests
        res = client.post("/api/auth/guest")
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create chat
        res_c = client.post("/api/chats", json={"title": "First Conversation"}, headers=headers)
        self.assertEqual(res_c.status_code, 200)
        chat_id = res_c.json()["id"]
        self.assertEqual(res_c.json()["title"], "First Conversation")

        # List chats
        res_list = client.get("/api/chats", headers=headers)
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(c["id"] == chat_id for c in res_list.json()))

        # Rename chat
        res_ren = client.patch(f"/api/chats/{chat_id}", json={"title": "Renamed Topic"}, headers=headers)
        self.assertEqual(res_ren.status_code, 200)
        self.assertEqual(res_ren.json()["title"], "Renamed Topic")

        # Chat details
        res_det = client.get(f"/api/chats/{chat_id}", headers=headers)
        self.assertEqual(res_det.status_code, 200)
        self.assertEqual(res_det.json()["title"], "Renamed Topic")

        # Delete chat
        res_del = client.delete(f"/api/chats/{chat_id}", headers=headers)
        self.assertEqual(res_del.status_code, 200)


if __name__ == "__main__":
    unittest.main()

