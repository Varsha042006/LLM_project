import os
import sys
import unittest
import numpy as np
import torch
import shutil

os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
if "tensorflow" not in sys.modules:
    sys.modules["tensorflow"] = None

import database as db
import auth
import document_processor as doc_proc
import rag
import export_utils
from model import load_model
from tokenizer import load_tokenizer


class TestLocalGPTProFullStack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        # Clean test user if exists
        cls.user_a_email = "test_user_a@localgpt.dev"
        cls.user_b_email = "test_user_b@localgpt.dev"
        user_a = db.get_user_by_email(cls.user_a_email)
        if user_a:
            db.delete_user_account(user_a["id"])
        user_b = db.get_user_by_email(cls.user_b_email)
        if user_b:
            db.delete_user_account(user_b["id"])

        cls.model, cls.tokenizer, cls.device = load_model("Qwen/Qwen2.5-0.5B-Instruct", device="cpu")

    def test_01_user_signup_and_login(self):
        # Signup
        ok, msg, user = auth.signup_user(self.user_a_email, "SecurePassword123!", "Alice Test")
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], self.user_a_email)
        self.assertFalse(user["is_verified"])
        self.assertIsNotNone(user["verification_code"])

        # Login
        log_ok, log_msg, log_user = auth.login_user(self.user_a_email, "SecurePassword123!")
        self.assertTrue(log_ok)
        self.assertEqual(log_user["id"], user["id"])

        # Bad password
        bad_ok, bad_msg, _ = auth.login_user(self.user_a_email, "WrongPassword")
        self.assertFalse(bad_ok)

    def test_02_email_verification(self):
        user = db.get_user_by_email(self.user_a_email)
        code = user["verification_code"]
        ver_ok, ver_msg = auth.verify_email_code(user["id"], code)
        self.assertTrue(ver_ok)
        
        updated_user = db.get_user_by_id(user["id"])
        self.assertTrue(bool(updated_user["is_verified"]))

    def test_03_firebase_token_auth(self):
        # Synthetic Firebase token test (JWT structure)
        import jwt
        token_payload = {
            "sub": "firebase_alice_123",
            "email": "alice_firebase@example.com",
            "name": "Alice Firebase"
        }
        test_token = jwt.encode(token_payload, "localgpt_pro_jwt_secret_key_minimum_32_bytes_sha256", algorithm="HS256")
        fb_ok, fb_msg, fb_user = auth.verify_firebase_id_token(test_token)
        self.assertTrue(fb_ok)
        self.assertEqual(fb_user["email"], "alice_firebase@example.com")
        self.assertTrue(fb_user["is_verified"])

    def test_04_multi_user_data_isolation(self):
        # Create User B
        ok_b, _, user_b = auth.signup_user(self.user_b_email, "PasswordB456!", "Bob Test")
        self.assertTrue(ok_b)
        user_a = db.get_user_by_email(self.user_a_email)

        # Alice creates a chat
        chat_a = db.create_chat("chat_alice_1", user_a["id"], "Alice's Private Project")
        db.add_message("msg_a1", "chat_alice_1", user_a["id"], "user", "What is quantum computing?")
        db.add_message("msg_a2", "chat_alice_1", user_a["id"], "assistant", "Quantum computing uses qubits.")

        # Bob queries his chats
        bob_chats = db.get_user_chats(user_b["id"])
        bob_chat_ids = [c["id"] for c in bob_chats]
        self.assertNotIn("chat_alice_1", bob_chat_ids, "CRITICAL: Bob should NEVER see Alice's chat!")

        # Alice queries her chats
        alice_chats = db.get_user_chats(user_a["id"])
        alice_chat_ids = [c["id"] for c in alice_chats]
        self.assertIn("chat_alice_1", alice_chat_ids)

        # Bob attempts to read Alice's messages
        bob_intercepted_messages = db.get_chat_messages("chat_alice_1", user_b["id"])
        self.assertEqual(len(bob_intercepted_messages), 0, "CRITICAL: Bob cannot retrieve Alice's messages!")

    def test_05_document_processing_and_rag(self):
        user_a = db.get_user_by_email(self.user_a_email)
        user_b = db.get_user_by_email(self.user_b_email)

        # Create a sample document
        sample_doc_content = (
            "LocalGPT Pro architecture overview. "
            "LocalGPT Pro integrates high-throughput local Qwen models with FAISS vector indexing. "
            "The data isolation layer prevents cross-tenant data leakage by enforcing user_id keys on every query. "
            "Supported document formats are PDF, TXT, and DOCX."
        )
        sample_txt_path = "sample_test_doc.txt"
        with open(sample_txt_path, "w", encoding="utf-8") as f:
            f.write(sample_doc_content)

        # Process document
        chunks = doc_proc.process_document_file(sample_txt_path, "sample_test_doc.txt")
        self.assertGreater(len(chunks), 0)

        # Alice indexes the document into FAISS
        num_indexed = rag.index_user_document_chunks(user_a["id"], chunks, self.model, self.tokenizer)
        self.assertEqual(num_indexed, len(chunks))

        # Alice retrieves from her index
        retrieved_a = rag.retrieve_relevant_chunks(user_a["id"], "data isolation layer", self.model, self.tokenizer)
        self.assertGreater(len(retrieved_a), 0)
        self.assertIn("isolation", retrieved_a[0]["content"])

        # Bob searches his FAISS index -> MUST BE EMPTY
        retrieved_b = rag.retrieve_relevant_chunks(user_b["id"], "data isolation layer", self.model, self.tokenizer)
        self.assertEqual(len(retrieved_b), 0, "CRITICAL: Bob's vector index must be isolated from Alice's!")

        # Clean up temporary test file
        if os.path.exists(sample_txt_path):
            os.remove(sample_txt_path)

    def test_06_exports(self):
        user_a = db.get_user_by_email(self.user_a_email)
        messages = db.get_chat_messages("chat_alice_1", user_a["id"])
        
        md_text = export_utils.export_chat_to_markdown("Alice's Private Project", messages)
        self.assertIn("# Alice's Private Project", md_text)
        self.assertIn("quantum computing", md_text)

        pdf_bytes = export_utils.export_chat_to_pdf("Alice's Private Project", messages)
        self.assertTrue(len(pdf_bytes) > 500)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_07_account_deletion_and_cleanup(self):
        user_a = db.get_user_by_email(self.user_a_email)
        del_ok = db.delete_user_account(user_a["id"])
        self.assertTrue(del_ok)

        # Verify user is gone from DB
        self.assertIsNone(db.get_user_by_id(user_a["id"]))
        # Verify user's chats are gone
        self.assertEqual(len(db.get_user_chats(user_a["id"])), 0)
        # Verify user's index directory is purged
        user_a_index_dir = os.path.join(rag.INDEX_BASE_DIR, user_a["id"])
        self.assertFalse(os.path.exists(user_a_index_dir))


if __name__ == "__main__":
    unittest.main()

