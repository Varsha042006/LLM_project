"""
Comprehensive Verification and Test Suite for LocalGPT Pro Firebase Google Sign-In.
Tests:
- Token verification security (rejecting invalid/tampered tokens)
- Identity derivation strictly from verified claims
- User data isolation between distinct Google accounts
- Database creation & avatar persistence
- Component file integrity
- Preserving existing LocalGPT functionality
"""

import os
import sys
import unittest
import time
import uuid

import database as db
import auth
import firebase_config
import auth_service
import auth_component


class TestFirebaseAuthIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.google_uid_1 = f"test_google_{uuid.uuid4().hex[:8]}"
        cls.google_uid_2 = f"test_google_{uuid.uuid4().hex[:8]}"
        cls.email_1 = f"{cls.google_uid_1}@gmail.com"
        cls.email_2 = f"{cls.google_uid_2}@gmail.com"

    def test_01_component_files_exist(self):
        """Test 1: Verify Streamlit custom component index.html exists and is well-formed."""
        component_dir = auth_component._COMPONENT_DIR
        self.assertTrue(os.path.exists(component_dir), "Component directory missing")
        index_html = os.path.join(component_dir, "index.html")
        self.assertTrue(os.path.exists(index_html), "Component index.html missing")
        with open(index_html, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("firebase.auth.GoogleAuthProvider", content)
        self.assertIn("streamlit:setComponentValue", content)
        self.assertIn("Continue with Google", content)
        print("✓ Test 1 Passed: Streamlit custom component index.html is verified and well-formed.")

    def test_02_firebase_config_loader(self):
        """Test 2: Verify Firebase config loading from secrets/env with project defaults."""
        cfg = firebase_config.get_firebase_web_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("projectId", cfg)
        self.assertIn("authDomain", cfg)
        self.assertEqual(cfg["projectId"], "localgpt-pro-45558")
        self.assertEqual(cfg["authDomain"], "localgpt-pro-45558.firebaseapp.com")
        print("✓ Test 2 Passed: Firebase Web configuration loaded correctly.")

    def test_03_invalid_token_rejection(self):
        """Test 3: Backend Security - Verify empty, malformed, or fake tokens are rejected."""
        # Empty token
        ok, msg, user = auth_service.verify_firebase_id_token("")
        self.assertFalse(ok)
        self.assertIsNone(user)

        # Malformed JWT
        ok, msg, user = auth_service.verify_firebase_id_token("invalid.jwt.token.string")
        self.assertFalse(ok)
        self.assertIsNone(user)

        # Tampered signature token
        fake_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkZha2UgVXNlciIsImlhdCI6MTUxNjIzOTAyMn0.invalidSignature"
        ok, msg, user = auth_service.verify_firebase_id_token(fake_token)
        self.assertFalse(ok)
        self.assertIsNone(user)
        print("✓ Test 3 Passed: Invalid, empty, and tampered tokens are rejected securely.")

    def test_04_google_user_creation_and_avatar(self):
        """Test 4: Verify Google user creation, photo_url storage, and database persistence."""
        user = db.get_or_create_google_user(
            uid=self.google_uid_1,
            email=self.email_1,
            display_name="Google Tester One",
            photo_url="https://lh3.googleusercontent.com/a/test_avatar_1"
        )
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], f"google_{self.google_uid_1}")
        self.assertEqual(user["email"], self.email_1)
        self.assertEqual(user["display_name"], "Google Tester One")
        self.assertEqual(user["photo_url"], "https://lh3.googleusercontent.com/a/test_avatar_1")
        self.assertEqual(user["auth_provider"], "google_firebase")
        self.assertEqual(user["is_verified"], 1)
        print("✓ Test 4 Passed: Google user and profile picture persisted correctly in SQLite.")

    def test_05_multi_user_data_isolation(self):
        """Test 5: Verify strict data isolation between two distinct Google accounts."""
        # Create User 1 and User 2
        user_1 = db.get_or_create_google_user(
            uid=self.google_uid_1,
            email=self.email_1,
            display_name="User Alpha"
        )
        user_2 = db.get_or_create_google_user(
            uid=self.google_uid_2,
            email=self.email_2,
            display_name="User Beta"
        )

        u1_id = user_1["id"]
        u2_id = user_2["id"]

        c1_id = f"chat_u1_{uuid.uuid4().hex[:6]}"
        c2_id = f"chat_u2_{uuid.uuid4().hex[:6]}"
        d1_id = f"doc_u1_{uuid.uuid4().hex[:6]}"
        d2_id = f"doc_u2_{uuid.uuid4().hex[:6]}"

        # Create Chat for User 1
        chat_1 = db.create_chat(c1_id, u1_id, "User 1 Confidential Strategy")
        db.add_message(f"msg_{uuid.uuid4().hex[:6]}", chat_1["id"], u1_id, "user", "Private financial roadmap")

        # Create Chat for User 2
        chat_2 = db.create_chat(c2_id, u2_id, "User 2 Project Plan")
        db.add_message(f"msg_{uuid.uuid4().hex[:6]}", chat_2["id"], u2_id, "user", "Private engineering notes")

        # Verify User 1 cannot see User 2's chats
        u1_chats = db.get_user_chats(u1_id)
        u1_chat_ids = [c["id"] for c in u1_chats]
        self.assertIn(c1_id, u1_chat_ids)
        self.assertNotIn(c2_id, u1_chat_ids)

        # Verify User 2 cannot see User 1's chats
        u2_chats = db.get_user_chats(u2_id)
        u2_chat_ids = [c["id"] for c in u2_chats]
        self.assertIn(c2_id, u2_chat_ids)
        self.assertNotIn(c1_id, u2_chat_ids)

        # Verify Messages are isolated
        u1_msgs = db.get_chat_messages(c1_id, u1_id)
        self.assertEqual(len(u1_msgs), 1)
        self.assertEqual(u1_msgs[0]["content"], "Private financial roadmap")

        # User 2 attempting to query User 1's chat messages receives empty/forbidden
        cross_msgs = db.get_chat_messages(c1_id, u2_id)
        self.assertEqual(len(cross_msgs), 0)

        # Create Documents for User 1 & User 2
        db.add_document(d1_id, u1_id, "Quarterly_Results.pdf", "pdf", "uploads/Quarterly_Results.pdf", 4)
        db.add_document(d2_id, u2_id, "Marketing_Budget.docx", "docx", "uploads/Marketing_Budget.docx", 2)

        u1_docs = [d["id"] for d in db.get_user_documents(u1_id)]
        u2_docs = [d["id"] for d in db.get_user_documents(u2_id)]

        self.assertIn(d1_id, u1_docs)
        self.assertNotIn(d2_id, u1_docs)
        self.assertIn(d2_id, u2_docs)
        self.assertNotIn(d1_id, u2_docs)

        print("✓ Test 5 Passed: Strict multi-user conversation and document isolation verified.")

    def test_06_session_validation_and_logout(self):
        """Test 6: Verify session validation logic and logout cleanup."""
        # Unauthenticated session state
        empty_session = {}
        self.assertFalse(auth_service.validate_session(empty_session))

        # Authenticated session state
        auth_session = {
            "user": {"id": "google_12345", "email": "test@gmail.com", "display_name": "Tester"},
            "id_token": "valid_mock_token",
            "token_verified_at": time.time()
        }
        self.assertTrue(auth_service.validate_session(auth_session))

        # Simulate Logout
        auth_session.clear()
        self.assertFalse(auth_service.validate_session(auth_session))
        print("✓ Test 6 Passed: Session validation and logout cleanup verified.")

    def test_07_existing_email_auth_preserved(self):
        """Test 7: Verify existing Email/Password signup and login are preserved."""
        test_email = f"standard_{uuid.uuid4().hex[:6]}@localgpt.dev"
        ok, msg, user = auth.signup_user(test_email, "StrongPass789!", "Standard User")
        self.assertTrue(ok)
        self.assertIsNotNone(user)

        log_ok, log_msg, log_user = auth.login_user(test_email, "StrongPass789!")
        self.assertTrue(log_ok)
        self.assertEqual(log_user["email"], test_email)
        print("✓ Test 7 Passed: Existing email/password authentication functions without regression.")


if __name__ == "__main__":
    unittest.main()

