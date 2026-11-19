"""
Streamlit Custom Component for Firebase Google Authentication.
Provides true two-way communication between Streamlit and Firebase Web SDK.
"""

import os
from typing import Optional, Dict, Any
import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "firebase_auth")

if not os.path.exists(_COMPONENT_DIR):
    raise FileNotFoundError(f"Firebase auth component directory not found at: {_COMPONENT_DIR}")

# Declare the custom component using Streamlit's official declare_component API
_google_sign_in_component = components.declare_component(
    "firebase_google_sign_in",
    path=_COMPONENT_DIR
)


def google_sign_in_button(
    firebase_config: Dict[str, str],
    theme: str = "dark",
    action: Optional[str] = None,
    key: str = "google_auth_button"
) -> Optional[Dict[str, Any]]:
    """
    Renders the professional Google Sign-In button custom component.

    Args:
        firebase_config: Dict containing Firebase web configuration parameters
        theme: 'dark' or 'light'
        action: Optional action string (e.g. 'sign_out')
        key: Streamlit component key

    Returns:
        Dict returned from client with keys: status, idToken, uid, email, displayName, photoURL, or None
    """
    return _google_sign_in_component(
        firebaseConfig=firebase_config,
        theme=theme,
        action=action,
        key=key,
        default=None
    )

