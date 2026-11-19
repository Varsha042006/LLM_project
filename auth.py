"""
Authentication module for LocalGPT Pro.
Supports Email/Password with PBKDF2 hashing, email verification codes,
and Firebase Google OAuth / ID token verification.
"""

import hashlib
import os
import random
import uuid
from typing import Dict, Any, Optional, Tuple
import database as db


def hash_password(password: str) -> str:
    """Hashes a password with a random 16-byte salt using PBKDF2 HMAC-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + "$" + key.hex()


def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies a password against the stored salt$key hash."""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt_hex, key_hex = stored_hash.split("$", 1)
    salt = bytes.fromhex(salt_hex)
    expected_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return expected_key.hex() == key_hex


def signup_user(email: str, password: str, display_name: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Registers a new user and generates a 6-digit email verification code."""
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Invalid email address format.", None
    if len(password) < 6:
        return False, "Password must be at least 6 characters.", None
        
    existing = db.get_user_by_email(email)
    if existing:
        return False, "An account with this email already exists.", None

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    code = f"{random.randint(100000, 999999)}"
    
    user = db.create_user(
        user_id=user_id,
        email=email,
        password_hash=pw_hash,
        display_name=display_name or email.split("@")[0],
        is_verified=False,
        verification_code=code,
        auth_provider="email"
    )
    return True, f"Account created! Your verification code is: {code}", user


def login_user(email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Authenticates user with email and password."""
    email = email.strip().lower()
    user = db.get_user_by_email(email)
    if not user:
        return False, "Invalid email or password.", None
    
    if not verify_password(user["password_hash"], password):
        return False, "Invalid email or password.", None
        
    return True, "Login successful.", user


def verify_email_code(user_id: str, code: str) -> Tuple[bool, str]:
    """Verifies a user's email using the 6-digit code."""
    success = db.verify_user_email(user_id, code.strip())
    if success:
        return True, "Email successfully verified!"
    return False, "Invalid verification code. Please check and try again."


def verify_firebase_id_token(id_token: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Verifies a Firebase ID token (JWT) using the backend auth_service.
    Extracts identity strictly from cryptographically verified claims.
    """
    import auth_service
    return auth_service.verify_firebase_id_token(id_token)

