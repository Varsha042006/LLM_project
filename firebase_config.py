"""
Firebase Configuration Manager for LocalGPT Pro.
Loads Firebase Web App configuration and Firebase Admin credentials
from Streamlit secrets (.streamlit/secrets.toml) or Environment variables.
"""

import os
from typing import Dict, Any, Optional

try:
    import streamlit as st
except ImportError:
    st = None


def get_firebase_web_config() -> Dict[str, str]:
    """
    Retrieves the client-side Firebase Web App configuration.
    Priority:
    1. Streamlit secrets (.streamlit/secrets.toml under [firebase])
    2. Environment variables (FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, etc.)
    3. Default configuration for LocalGPT-Pro
    """
    config = {
        "apiKey": "AIzaSyAvalzQ3T-XfG5wT45hV3se6EvsM9PjPzU",
        "authDomain": "localgpt-pro-45558.firebaseapp.com",
        "projectId": "localgpt-pro-45558",
        "storageBucket": "localgpt-pro-45558.firebasestorage.app",
        "messagingSenderId": "428746563248",
        "appId": "1:428746563248:web:09a472d6ca0035ac652575",
        "measurementId": ""
    }

    # 1. Try Streamlit secrets
    if st is not None:
        try:
            if hasattr(st, "secrets") and "firebase" in st.secrets:
                fb_sec = st.secrets["firebase"]
                for k in ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId", "measurementId"]:
                    if k in fb_sec and fb_sec[k]:
                        config[k] = str(fb_sec[k]).strip()
                    # Also support snake_case variant in secrets.toml (e.g. api_key)
                    snake_k = "".join(["_" + c.lower() if c.isupper() else c for c in k]).lstrip("_")
                    if snake_k in fb_sec and fb_sec[snake_k]:
                        config[k] = str(fb_sec[snake_k]).strip()
        except Exception:
            pass

    # 2. Try Environment variables (overrides or fills in blanks)
    env_map = {
        "apiKey": "FIREBASE_API_KEY",
        "authDomain": "FIREBASE_AUTH_DOMAIN",
        "projectId": "FIREBASE_PROJECT_ID",
        "storageBucket": "FIREBASE_STORAGE_BUCKET",
        "messagingSenderId": "FIREBASE_MESSAGING_SENDER_ID",
        "appId": "FIREBASE_APP_ID",
        "measurementId": "FIREBASE_MEASUREMENT_ID"
    }

    for cfg_key, env_var in env_map.items():
        val = os.getenv(env_var)
        if val and val.strip():
            config[cfg_key] = val.strip()

    return config


def is_firebase_configured() -> bool:
    """
    Checks if Firebase Web App has been properly configured with a real API key.
    """
    cfg = get_firebase_web_config()
    api_key = cfg.get("apiKey", "")
    project_id = cfg.get("projectId", "")
    return bool(api_key and len(api_key) > 10 and not api_key.startswith("YOUR_") and project_id)


def get_firebase_admin_credentials_path() -> Optional[str]:
    """
    Locates the Firebase Admin Service Account JSON credentials file.
    Searches:
    1. st.secrets["firebase"]["service_account_path"]
    2. FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_KEY env var
    3. GOOGLE_APPLICATION_CREDENTIALS env var
    4. Local project root: 'firebase-service-account.json', 'firebase-credentials.json', 'serviceAccountKey.json'
    """
    # 1. Streamlit secrets
    if st is not None:
        try:
            if hasattr(st, "secrets") and "firebase" in st.secrets:
                fb_sec = st.secrets["firebase"]
                p = fb_sec.get("service_account_path") or fb_sec.get("serviceAccountPath")
                if p and os.path.exists(str(p)):
                    return str(p)
        except Exception:
            pass

    # 2. Environment variables
    for env_var in ["FIREBASE_SERVICE_ACCOUNT_PATH", "FIREBASE_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS"]:
        val = os.getenv(env_var)
        if val and os.path.exists(val):
            return val

    # 3. Known local files in project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        "firebase-service-account.json",
        "firebase-credentials.json",
        "serviceAccountKey.json",
        "localgpt-pro-firebase-adminsdk.json"
    ]
    for c in candidates:
        full_path = os.path.join(project_root, c)
        if os.path.exists(full_path):
            return full_path

    return None