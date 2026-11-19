"""
SQLite Database module for LocalGPT Pro.
Provides strict user-ownership filtering, chat persistence, document metadata, and account deletion cleanup.
"""

import sqlite3
import os
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = "localgpt.db"
UPLOAD_DIR = "uploads"
INDEX_DIR = "indexes"


def get_connection() -> sqlite3.Connection:
    """Get SQLite database connection with row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes SQLite tables for users, chats, messages, and documents."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(INDEX_DIR, exist_ok=True)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                display_name TEXT,
                photo_url TEXT,
                is_verified INTEGER DEFAULT 0,
                verification_code TEXT,
                auth_provider TEXT DEFAULT 'email',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Safely migrate existing databases if photo_url is missing
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN photo_url TEXT")
        except Exception:
            pass
        
        # Chats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                num_chunks INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()


# -----------------------------------------------------------------------------
# User CRUD & Isolation
# -----------------------------------------------------------------------------
def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_user(
    user_id: str,
    email: str,
    password_hash: Optional[str] = None,
    display_name: Optional[str] = None,
    is_verified: bool = False,
    verification_code: Optional[str] = None,
    auth_provider: str = "email",
    photo_url: Optional[str] = None
) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, email, password_hash, display_name, is_verified, verification_code, auth_provider, photo_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email.strip().lower(), password_hash, display_name or email.split("@")[0], 1 if is_verified else 0, verification_code, auth_provider, photo_url))
        conn.commit()
    return get_user_by_id(user_id)


def get_or_create_google_user(
    uid: str,
    email: str,
    display_name: Optional[str] = None,
    photo_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves or creates a user authenticated via Google Firebase.
    Ensures existing users with matching email or UID are linked and updated with fresh profile data.
    """
    user_id = f"google_{uid}"
    email_clean = email.strip().lower()

    with get_connection() as conn:
        cursor = conn.cursor()
        # First check by exact user_id
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                UPDATE users
                SET display_name = COALESCE(?, display_name),
                    photo_url = COALESCE(?, photo_url),
                    is_verified = 1
                WHERE id = ?
            """, (display_name, photo_url, user_id))
            conn.commit()
            return get_user_by_id(user_id)

        # Check by email
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email_clean,))
        row = cursor.fetchone()
        if row:
            existing = dict(row)
            cursor.execute("""
                UPDATE users
                SET display_name = COALESCE(?, display_name),
                    photo_url = COALESCE(?, photo_url),
                    is_verified = 1,
                    auth_provider = 'google_firebase'
                WHERE id = ?
            """, (display_name, photo_url, existing["id"]))
            conn.commit()
            return get_user_by_id(existing["id"])

        # Create new user
        cursor.execute("""
            INSERT INTO users (id, email, password_hash, display_name, photo_url, is_verified, verification_code, auth_provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            email_clean,
            None,
            display_name or email_clean.split("@")[0],
            photo_url,
            1,
            None,
            "google_firebase"
        ))
        conn.commit()
    return get_user_by_id(user_id)


def verify_user_email(user_id: str, code: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT verification_code FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["verification_code"] == code:
            cursor.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))
            conn.commit()
            return True
    return False


def delete_user_account(user_id: str) -> bool:
    """
    Completely deletes user account, database records, uploaded files, and FAISS index.
    Enforces multi-user cleanup.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM documents WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

    # Clean up user uploads directory
    user_upload_dir = os.path.join(UPLOAD_DIR, user_id)
    if os.path.exists(user_upload_dir):
        shutil.rmtree(user_upload_dir, ignore_errors=True)

    # Clean up user FAISS index directory
    user_index_dir = os.path.join(INDEX_DIR, user_id)
    if os.path.exists(user_index_dir):
        shutil.rmtree(user_index_dir, ignore_errors=True)

    return True


# -----------------------------------------------------------------------------
# Chat CRUD (strictly scoped to user_id)
# -----------------------------------------------------------------------------
def get_user_chats(user_id: str, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns chats belonging only to the specified user, optionally filtered by title or content search."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if search_query and search_query.strip():
            query_str = f"%{search_query.strip()}%"
            cursor.execute("""
                SELECT DISTINCT c.* FROM chats c
                LEFT JOIN messages m ON c.id = m.chat_id
                WHERE c.user_id = ? AND (c.title LIKE ? OR m.content LIKE ?)
                ORDER BY c.updated_at DESC
            """, (user_id, query_str, query_str))
        else:
            cursor.execute("""
                SELECT * FROM chats
                WHERE user_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]


def create_chat(chat_id: str, user_id: str, title: str = "New Chat") -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chats (id, user_id, title)
            VALUES (?, ?, ?)
        """, (chat_id, user_id, title))
        conn.commit()
    return {"id": chat_id, "user_id": user_id, "title": title}


def update_chat_title(chat_id: str, user_id: str, new_title: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (new_title, chat_id, user_id))
        conn.commit()


def delete_chat(chat_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        cursor.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
        conn.commit()
    return True


# -----------------------------------------------------------------------------
# Message CRUD (strictly scoped to user_id)
# -----------------------------------------------------------------------------
def get_chat_messages(chat_id: str, user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE chat_id = ? AND user_id = ?
            ORDER BY created_at ASC
        """, (chat_id, user_id))
        return [dict(row) for row in cursor.fetchall()]


def add_message(message_id: str, chat_id: str, user_id: str, role: str, content: str, sources: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (id, chat_id, user_id, role, content, sources)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (message_id, chat_id, user_id, role, content, sources))
        cursor.execute("""
            UPDATE chats SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (chat_id, user_id))
        conn.commit()


# -----------------------------------------------------------------------------
# Documents CRUD (strictly scoped to user_id)
# -----------------------------------------------------------------------------
def get_user_documents(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM documents
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        seen = set()
        deduped = []
        for r in rows:
            if r["filename"] not in seen:
                seen.add(r["filename"])
                deduped.append(r)
        return deduped


def add_document(doc_id: str, user_id: str, filename: str, file_type: str, file_path: str, num_chunks: int = 0):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE user_id = ? AND filename = ?", (user_id, filename))
        cursor.execute("""
            INSERT INTO documents (id, user_id, filename, file_type, file_path, num_chunks)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (doc_id, user_id, filename, file_type, file_path, num_chunks))
        conn.commit()


def delete_document(doc_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
        row = cursor.fetchone()
        if row and os.path.exists(row["file_path"]):
            try:
                os.remove(row["file_path"])
            except Exception:
                pass
        cursor.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
        conn.commit()
    return True

