import sys
import os

# Prevent slow TensorFlow detection during Transformers import
if "tensorflow" not in sys.modules:
    sys.modules["tensorflow"] = None

os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

try:
    import transformers.utils.import_utils as _import_utils
    _import_utils.is_tf_available = lambda: False
    _import_utils.is_tf_text_available = lambda: False
except Exception:
    pass

import streamlit as st
import pandas as pd
import numpy as np
import torch
import time
import uuid
import plotly.express as px

import database as db
import auth
import firebase_config
import auth_service
import auth_component
import document_processor as doc_proc
import rag
import export_utils
from backend.app.image_service import (
    detect_image_prompt,
    generate_image_asset,
    detect_image_modification,
    apply_image_filter
)
from backend.app.vision_service import (
    inspect_image_properties,
    generate_synthesized_vision_report,
    execute_visual_qa
)
from tokenizer import load_tokenizer, tokenize_text, format_step4_flow
from model import (
    load_model,
    get_model_metadata,
    extract_embeddings,
    forward_xray,
    compute_logits_and_probs,
    generate_with_xray_trace
)
from visualization import (
    create_pca_embedding_plot,
    create_embedding_heatmap_matrix,
    create_attention_heatmap,
    create_hidden_states_pca_trajectory,
    create_logits_bar_chart,
    create_step_generation_flow
)

# Page configuration
st.set_page_config(
    page_title="LocalGPT Pro — Private Local AI & Neural X-Ray",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize SQLite database
db.init_db()

# Session State Initialization
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"
if "user" not in st.session_state:
    st.session_state["user"] = None
if "id_token" not in st.session_state:
    st.session_state["id_token"] = None
if "token_verified_at" not in st.session_state:
    st.session_state["token_verified_at"] = 0
if "current_chat_id" not in st.session_state:
    st.session_state["current_chat_id"] = None
if "active_mode" not in st.session_state:
    st.session_state["active_mode"] = "chat" # 'chat' or 'xray'

# Periodic token revalidation check across reruns (every 30 mins)
if st.session_state.get("user") and st.session_state.get("id_token"):
    verified_at = st.session_state.get("token_verified_at", 0)
    if time.time() - verified_at > 1800:
        is_valid, _, fresh_user = auth_service.verify_firebase_id_token(st.session_state["id_token"])
        if is_valid and fresh_user:
            st.session_state["user"] = fresh_user
            st.session_state["token_verified_at"] = time.time()
        else:
            st.session_state["user"] = None
            st.session_state["id_token"] = None
            st.warning("Your Google session has expired. Please sign in again.")
            st.rerun()

# -----------------------------------------------------------------------------
# Dynamic CSS (Dark Cyberpunk vs Light Modern)
# -----------------------------------------------------------------------------
if st.session_state["theme"] == "dark":
    st.markdown("""
    <style>
        .stApp {
            background-color: #0b0e14;
            color: #e6edf3;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        section[data-testid="stSidebar"] {
            background-color: #12161f !important;
            border-right: 1px solid #30363d !important;
        }
        .main-header {
            background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .main-title {
            font-size: 2.0rem;
            font-weight: 800;
            background: linear-gradient(90deg, #00f0ff, #7928ca, #ff007f);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }
        .token-chip {
            display: inline-block;
            background: rgba(0, 240, 255, 0.1);
            border: 1px solid rgba(0, 240, 255, 0.4);
            color: #00f0ff;
            border-radius: 6px;
            padding: 4px 8px;
            margin: 4px;
            font-family: monospace;
            font-size: 0.9rem;
        }
        .token-id-chip {
            color: #ff007f;
            font-size: 0.8rem;
            margin-left: 4px;
        }
        .source-card {
            background: #161b22;
            border-left: 3px solid #00f0ff;
            padding: 10px 14px;
            border-radius: 0 8px 8px 0;
            margin-top: 8px;
            margin-bottom: 8px;
            font-size: 0.88rem;
        }
        .xray-code-box {
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
            font-family: monospace;
            color: #7ee787;
            overflow-x: auto;
        }
        .stTabs [data-baseweb="tab-list"] {
            flex-wrap: wrap !important;
            gap: 6px !important;
            border-bottom: 1px solid #30363d !important;
            padding-bottom: 6px !important;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px !important;
            font-size: 0.86rem !important;
            border-radius: 8px !important;
            white-space: nowrap !important;
            margin-bottom: 4px !important;
        }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        .stApp {
            background-color: #f6f8fa;
            color: #24292f;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        section[data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #d0d7de !important;
        }
        .main-header {
            background: linear-gradient(135deg, #ffffff 0%, #f6f8fa 100%);
            border: 1px solid #d0d7de;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }
        .main-title {
            font-size: 2.0rem;
            font-weight: 800;
            color: #0969da;
            margin-bottom: 4px;
        }
        .token-chip {
            display: inline-block;
            background: #ddf4ff;
            border: 1px solid #54aeff;
            color: #0969da;
            border-radius: 6px;
            padding: 4px 8px;
            margin: 4px;
            font-family: monospace;
            font-size: 0.9rem;
        }
        .token-id-chip {
            color: #cf222e;
            font-size: 0.8rem;
            margin-left: 4px;
        }
        .source-card {
            background: #ffffff;
            border-left: 3px solid #0969da;
            border: 1px solid #d0d7de;
            border-left-width: 4px;
            padding: 10px 14px;
            border-radius: 0 8px 8px 0;
            margin-top: 8px;
            margin-bottom: 8px;
            font-size: 0.88rem;
        }
        .xray-code-box {
            background-color: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 8px;
            padding: 12px;
            font-family: monospace;
            color: #1a7f37;
            overflow-x: auto;
        }
        .stTabs [data-baseweb="tab-list"] {
            flex-wrap: wrap !important;
            gap: 6px !important;
            border-bottom: 1px solid #d0d7de !important;
            padding-bottom: 6px !important;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px !important;
            font-size: 0.86rem !important;
            border-radius: 8px !important;
            white-space: nowrap !important;
            margin-bottom: 4px !important;
        }
    </style>
    """, unsafe_allow_html=True)


# Cached Model & Tokenizer Loader
@st.cache_resource(show_spinner=False)
def load_llm_cached(model_name: str, device_choice: str):
    """Cached loader for Hugging Face CausalLM & Tokenizer."""
    device = "cuda" if (device_choice == "CUDA (GPU)" and torch.cuda.is_available()) else "cpu"
    model, tokenizer, actual_device = load_model(model_name=model_name, device=device)
    metadata = get_model_metadata(model)
    return model, tokenizer, metadata, actual_device


# -----------------------------------------------------------------------------
# AUTHENTICATION GATEWAY (Protected Pages)
# -----------------------------------------------------------------------------
user = st.session_state.get("user")

if user is None:
    # -------------------------------------------------------------
    # MODERN POPUP MODAL LOGIN INTERFACE (Matching Reference UI)
    # -------------------------------------------------------------
    if "auth_tab_mode" not in st.session_state:
        st.session_state["auth_tab_mode"] = "signin"

    # Inject UI styling for the white modal card & inputs
    st.markdown("""
    <style>
    /* Clean light mode backdrop */
    .stApp {
        background: #f1f5f9 !important;
    }
    [data-testid="stSidebar"] {
        display: none !important;
    }
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 520px !important;
    }

    /* Modal card styling */
    .auth-modal-card {
        background: #ffffff !important;
        border-radius: 28px !important;
        padding: 26px 28px 24px 28px !important;
        box-shadow: 0 20px 45px -10px rgba(0, 0, 0, 0.08), 0 0 1px rgba(0, 0, 0, 0.15) !important;
        border: 1px solid #e2e8f0 !important;
        position: relative !important;
        color: #0f172a !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }

    /* Close icon */
    .auth-close-btn {
        position: absolute;
        top: 20px;
        right: 24px;
        color: #64748b;
        font-size: 19px;
        font-weight: 300;
        cursor: pointer;
        line-height: 1;
        transition: color 0.15s ease;
    }
    .auth-close-btn:hover {
        color: #0f172a;
    }

    /* Glowing AI Orb */
    .auth-orb-container {
        display: flex;
        justify-content: center;
        margin-top: 2px;
        margin-bottom: 14px;
    }
    .auth-orb-box {
        width: 60px;
        height: 60px;
        border-radius: 18px;
        background: #000000;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 10px 25px rgba(0, 240, 255, 0.35), 0 4px 10px rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.15);
    }

    /* Typography */
    .auth-header-title {
        color: #0f172a !important;
        font-size: 25px !important;
        font-weight: 800 !important;
        text-align: center !important;
        margin: 0 0 5px 0 !important;
        letter-spacing: -0.5px !important;
    }
    .auth-header-subtitle {
        color: #64748b !important;
        font-size: 13.5px !important;
        text-align: center !important;
        margin: 0 0 18px 0 !important;
        line-height: 1.4 !important;
    }

    /* Divider */
    .auth-divider-wrap {
        display: flex;
        align-items: center;
        text-align: center;
        margin: 16px 0 14px 0;
    }
    .auth-divider-line {
        flex: 1;
        border-bottom: 1.5px solid #edf2f7;
    }
    .auth-divider-text {
        padding: 0 12px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #94a3b8;
    }

    /* Input styling */
    div[data-testid="stTextInput"] input {
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 10px 14px !important;
        font-size: 14px !important;
        height: 44px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
    }

    /* Segmented pill control */
    div[data-testid="stHorizontalBlock"]:has(button[key="seg_signin"]) {
        background: #f1f5f9 !important;
        border-radius: 12px !important;
        padding: 4px !important;
        margin-bottom: 12px !important;
        gap: 4px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(button[key="seg_signin"]) button {
        border: none !important;
        height: 38px !important;
        font-size: 13.5px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(button[key="seg_signin"]) button[kind="primary"] {
        background: #ffffff !important;
        color: #0f172a !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
    }
    div[data-testid="stHorizontalBlock"]:has(button[key="seg_signin"]) button[kind="secondary"] {
        background: transparent !important;
        color: #64748b !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }

    /* Primary blue button */
    div[data-testid="stButton"]:has(button[key="btn_auth_submit"]) button {
        background: #2563eb !important;
        color: #ffffff !important;
        border-radius: 12px !important;
        height: 46px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        border: none !important;
        margin-top: 10px !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"]:has(button[key="btn_auth_submit"]) button:hover {
        background: #1d4ed8 !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.45) !important;
        transform: translateY(-1px) !important;
    }
    </style>
    """, unsafe_allow_html=True)



    # 1. Continue with Google Button
    fb_cfg = firebase_config.get_firebase_web_config()
    auth_payload = auth_component.google_sign_in_button(
        firebase_config=fb_cfg,
        theme="light",
        key="firebase_google_auth_btn"
    )

    if auth_payload and isinstance(auth_payload, dict):
        p_status = auth_payload.get("status")
        if p_status == "success":
            received_token = auth_payload.get("idToken")
            with st.spinner("Cryptographically verifying Google credentials..."):
                ok, msg, verified_user = auth_service.verify_firebase_id_token(received_token)
                if ok and verified_user:
                    st.session_state["user"] = verified_user
                    st.session_state["id_token"] = received_token
                    st.session_state["token_verified_at"] = time.time()
                    st.session_state["auth_provider"] = "google_firebase"
                    st.success(f"✓ Welcome, {verified_user.get('display_name')}!")
                    time.sleep(0.3)
                    st.rerun()
                else:
                    st.error(f"Authentication verification failed: {msg}")
        elif p_status == "error":
            err_msg = auth_payload.get("message") or "Authentication failed."
            st.error(f"Google Sign-In Error: {err_msg}")

    # Divider: OR WITH EMAIL
    st.markdown("""
    <div class="auth-divider-wrap">
        <div class="auth-divider-line"></div>
        <span class="auth-divider-text">OR WITH EMAIL</span>
        <div class="auth-divider-line"></div>
    </div>
    """, unsafe_allow_html=True)

    # Segmented Control: [ Sign In ] [ Create Account ]
    seg_col1, seg_col2 = st.columns(2)
    with seg_col1:
        is_active_signin = (st.session_state["auth_tab_mode"] == "signin")
        if st.button("Sign In", key="seg_signin", type="primary" if is_active_signin else "secondary", use_container_width=True):
            st.session_state["auth_tab_mode"] = "signin"
            st.rerun()
    with seg_col2:
        is_active_signup = (st.session_state["auth_tab_mode"] == "signup")
        if st.button("Create Account", key="seg_signup", type="primary" if is_active_signup else "secondary", use_container_width=True):
            st.session_state["auth_tab_mode"] = "signup"
            st.rerun()

    # Form Fields
    if st.session_state["auth_tab_mode"] == "signin":
        st.markdown("""
        <div style="margin-top: 10px; margin-bottom: 4px;">
            <span style="font-weight: 600; font-size: 13.5px; color: #0f172a;">Email Address</span>
        </div>
        """, unsafe_allow_html=True)
        login_email = st.text_input("Email", placeholder="name@example.com", key="input_login_email", label_visibility="collapsed")

        st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; margin-bottom: 4px;">
            <span style="font-weight: 600; font-size: 13.5px; color: #0f172a;">Password</span>
            <span style="font-size: 12.5px; color: #10b981; font-weight: 500; cursor: pointer;">Forgot Password?</span>
        </div>
        """, unsafe_allow_html=True)
        login_password = st.text_input("Password", type="password", placeholder="••••••••", key="input_login_password", label_visibility="collapsed")

        if st.button("Sign In", key="btn_auth_submit", use_container_width=True):
            if not login_email or not login_password:
                st.error("Please enter your email and password.")
            else:
                ok, msg, u = auth.login_user(login_email, login_password)
                if ok:
                    st.session_state["user"] = u
                    st.session_state["auth_provider"] = "email"
                    st.success(f"Welcome back, {u['display_name']}!")
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.markdown("""
        <div style="margin-top: 10px; margin-bottom: 4px;">
            <span style="font-weight: 600; font-size: 13.5px; color: #0f172a;">Full Name</span>
        </div>
        """, unsafe_allow_html=True)
        signup_name = st.text_input("Full Name", placeholder="Jane Doe", key="input_signup_name", label_visibility="collapsed")

        st.markdown("""
        <div style="margin-top: 10px; margin-bottom: 4px;">
            <span style="font-weight: 600; font-size: 13.5px; color: #0f172a;">Email Address</span>
        </div>
        """, unsafe_allow_html=True)
        signup_email = st.text_input("Email Address", placeholder="name@example.com", key="input_signup_email", label_visibility="collapsed")

        st.markdown("""
        <div style="margin-top: 10px; margin-bottom: 4px;">
            <span style="font-weight: 600; font-size: 13.5px; color: #0f172a;">Password</span>
        </div>
        """, unsafe_allow_html=True)
        signup_password = st.text_input("Choose Password", type="password", placeholder="••••••••", key="input_signup_password", label_visibility="collapsed")

        if st.button("Create Account", key="btn_auth_submit", use_container_width=True):
            if not signup_email or not signup_password:
                st.error("Please provide an email and password.")
            else:
                ok, msg, u = auth.signup_user(signup_email, signup_password, signup_name)
                if ok:
                    st.success(msg)
                    st.session_state["user"] = u
                    st.session_state["auth_provider"] = "email"
                    st.rerun()
                else:
                    st.error(msg)

    # Skip Login Option
    st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
    if st.button("✕ Skip Login & Enter LocalGPT Directly", key="btn_skip_guest", use_container_width=True):
        guest_u = db.get_user_by_email("guest@localgpt.dev")
        if not guest_u:
            _, _, guest_u = auth.signup_user("guest@localgpt.dev", "GuestPass123!", "Guest User")
            db.verify_user_email(guest_u["id"], guest_u["verification_code"])
            guest_u = db.get_user_by_id(guest_u["id"])
        st.session_state["user"] = guest_u
        st.session_state["auth_provider"] = "guest"
        st.rerun()

    # Optional Multi-User Sandbox Test for Verification
    with st.expander("⚡ 1-Click Multi-User Sandbox Test", expanded=False):
        col_sb1, col_sb2 = st.columns(2)
        with col_sb1:
            if st.button("👤 Alice", key="demo_alice", use_container_width=True):
                u = db.get_user_by_email("alice@localgpt.dev")
                if not u:
                    _, _, u = auth.signup_user("alice@localgpt.dev", "AlicePass123!", "Alice")
                    db.verify_user_email(u["id"], u["verification_code"])
                    u = db.get_user_by_id(u["id"])
                st.session_state["user"] = u
                st.session_state["auth_provider"] = "test"
                st.rerun()
        with col_sb2:
            if st.button("👤 Bob", key="demo_bob", use_container_width=True):
                u = db.get_user_by_email("bob@localgpt.dev")
                if not u:
                    _, _, u = auth.signup_user("bob@localgpt.dev", "BobPass456!", "Bob")
                    db.verify_user_email(u["id"], u["verification_code"])
                    u = db.get_user_by_id(u["id"])
                st.session_state["user"] = u
                st.session_state["auth_provider"] = "test"
                st.rerun()

    st.stop()
    sys.exit(0)


# -----------------------------------------------------------------------------
# LOGGED IN WORKSPACE: SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
current_user_id = user["id"]

# User profile header in sidebar with Google avatar
st.sidebar.markdown("---")
user_avatar = user.get("photo_url")
display_name = user.get("display_name") or "User"
user_email = user.get("email") or ""
is_google_user = (user.get("auth_provider") == "google_firebase")

if user_avatar:
    st.sidebar.markdown(f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 10px; background: rgba(255,255,255,0.04); border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);">
        <img src="{user_avatar}" style="width: 44px; height: 44px; border-radius: 50%; object-fit: cover; border: 2px solid #00f0ff;" alt="Google Profile" />
        <div style="overflow: hidden;">
            <div style="font-weight: 700; font-size: 0.98rem; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; color: #f0f6fc;">{display_name}</div>
            <div style="font-size: 0.78rem; opacity: 0.75; white-space: nowrap; text-overflow: ellipsis; overflow: hidden;">{user_email}</div>
            <div style="font-size: 0.72rem; color: #10a37f; margin-top: 2px; font-weight: 500;">✓ Verified Google Account</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown(f"### 👤 {display_name}")
    st.sidebar.caption(f"📧 `{user_email}` | Verified: {'✅' if user.get('is_verified') else '⚠️ Unverified'}")

# Theme Switcher & Logout
col_th1, col_th2 = st.sidebar.columns(2)
with col_th1:
    new_theme = st.selectbox(
        "Theme",
        options=["dark", "light"],
        index=0 if st.session_state["theme"] == "dark" else 1,
        format_func=lambda x: "🌙 Dark" if x == "dark" else "☀️ Light"
    )
    if new_theme != st.session_state["theme"]:
        st.session_state["theme"] = new_theme
        st.rerun()
with col_th2:
    st.write("")
    st.write("")
    if st.button("🚪 Logout", use_container_width=True, type="secondary"):
        st.session_state["user"] = None
        st.session_state["id_token"] = None
        st.session_state["auth_provider"] = None
        st.session_state["current_chat_id"] = None
        st.session_state.pop("xray_data", None)
        st.session_state.pop("processed_upload_sigs", None)
        st.rerun()

# Account Deletion & Cleanup
with st.sidebar.expander("⚙️ Account Settings & Cleanup"):
    st.caption("Permanently delete your profile, chats, uploaded files, and vector index.")
    if st.button("🗑️ Delete Account & Purge Data", type="secondary"):
        db.delete_user_account(current_user_id)
        st.session_state["user"] = None
        st.session_state["current_chat_id"] = None
        st.session_state.pop("xray_data", None)
        st.warning("Account deleted and files purged.")
        st.rerun()

st.sidebar.markdown("---")

# Navigation Mode Switcher
st.sidebar.subheader("🚀 Mode")
mode_choice = st.sidebar.radio(
    "Active Workspace",
    options=["💬 Chat & RAG", "🔬 Neural LLM X-Ray"],
    index=0 if st.session_state["active_mode"] == "chat" else 1
)
st.session_state["active_mode"] = "chat" if mode_choice == "💬 Chat & RAG" else "xray"

# Model Selection
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Local Qwen Model")
model_options = [
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct"
]
selected_model_name = st.sidebar.selectbox("Model Variant", options=model_options, index=0)
device_choice = st.sidebar.radio("Hardware", options=["CPU (Local)", "CUDA (GPU)"], index=0 if not torch.cuda.is_available() else 1)

# Load Model
with st.spinner(f"Loading {selected_model_name}..."):
    try:
        model, tokenizer, metadata, actual_device = load_llm_cached(selected_model_name, device_choice)
        if not isinstance(metadata, dict):
            metadata = {}
        if "num_parameters_formatted" not in metadata:
            total_p = metadata.get("total_params", 494032768)
            p_b = round(total_p / 1e9, 2)
            metadata["num_parameters_formatted"] = f"{round(total_p / 1e6)}M ({p_b:.2f}B)" if p_b < 1.0 else f"{p_b:.2f}B"
        metadata.setdefault("num_layers", getattr(model.config, "num_hidden_layers", 24))
        metadata.setdefault("num_heads", getattr(model.config, "num_attention_heads", 14))
        metadata.setdefault("hidden_dim", getattr(model.config, "hidden_size", 896))
        metadata.setdefault("vocab_size", getattr(model.config, "vocab_size", 151643))
        metadata.setdefault("intermediate_dim", getattr(model.config, "intermediate_size", 4864))
        metadata.setdefault("num_kv_heads", getattr(model.config, "num_key_value_heads", 2))
        st.sidebar.success(f"✓ {selected_model_name.split('/')[-1]} Ready on {actual_device.type.upper()}")
    except Exception as e:
        st.error(f"Failed to load model: {e}")
        st.stop()

# Generation Hyperparameters
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Generation Controls")
temperature = st.sidebar.slider("Temperature", min_value=0.0, max_value=2.0, value=0.7, step=0.05)
top_k = st.sidebar.slider("Top-K", min_value=1, max_value=100, value=50, step=1)
top_p = st.sidebar.slider("Top-P", min_value=0.05, max_value=1.0, value=0.9, step=0.05)
max_new_tokens = st.sidebar.slider("Max New Tokens", min_value=50, max_value=1024, value=512, step=25)


# -----------------------------------------------------------------------------
# MODE 1: INTERACTIVE CHAT & RAG WORKSPACE
# -----------------------------------------------------------------------------
if st.session_state["active_mode"] == "chat":
    # Sidebar Chat Manager
    st.sidebar.markdown("---")
    st.sidebar.subheader("💬 Conversations")
    if st.sidebar.button("➕ New Chat", use_container_width=True, type="primary"):
        new_cid = f"chat_{uuid.uuid4().hex[:8]}"
        db.create_chat(new_cid, current_user_id, "New Chat")
        st.session_state["current_chat_id"] = new_cid
        st.session_state.pop("attached_image", None)
        st.session_state.pop("attached_image_path", None)
        st.session_state.pop("active_chat_image", None)
        st.rerun()

    # Chat Search
    search_query = st.sidebar.text_input("🔍 Search Chats...", placeholder="Filter by title or keyword")
    user_chats = db.get_user_chats(current_user_id, search_query=search_query)

    if not st.session_state["current_chat_id"] and user_chats:
        st.session_state["current_chat_id"] = user_chats[0]["id"]

    for c in user_chats:
        is_curr = (c["id"] == st.session_state["current_chat_id"])
        c_title = c["title"][:22] + "..." if len(c["title"]) > 22 else c["title"]
        col_c1, col_c2 = st.sidebar.columns([4, 1])
        with col_c1:
            if st.button(f"{'👉 ' if is_curr else '🗨️ '}{c_title}", key=f"chat_sel_{c['id']}", use_container_width=True):
                st.session_state["current_chat_id"] = c["id"]
                st.rerun()
        with col_c2:
            if st.button("✕", key=f"del_{c['id']}"):
                db.delete_chat(c["id"], current_user_id)
                if st.session_state["current_chat_id"] == c["id"]:
                    st.session_state["current_chat_id"] = None
                st.rerun()

    # Document Management & RAG Section in Sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("📎 Attached Documents (RAG)")
    user_docs = db.get_user_documents(current_user_id)
    if user_docs:
        for d in user_docs:
            col_d1, col_d2 = st.sidebar.columns([4, 1])
            with col_d1:
                st.caption(f"📄 **{d['filename']}** ({d['num_chunks']} chunks)")
            with col_d2:
                if st.button("🗑️", key=f"deldoc_{d['id']}"):
                    db.delete_document(d["id"], current_user_id)
                    rag.remove_document_from_user_faiss_index(current_user_id, d["filename"], model, tokenizer)
                    # Clear from processed uploads cache if present
                    if "processed_upload_sigs" in st.session_state:
                        st.session_state["processed_upload_sigs"] = {
                            s for s in st.session_state["processed_upload_sigs"] if d["filename"] not in s
                        }
                    st.rerun()

        if len(user_docs) > 1:
            if st.sidebar.button("🗑️ Clear All Documents", use_container_width=True):
                for d in user_docs:
                    db.delete_document(d["id"], current_user_id)
                rag.clear_user_faiss_index(current_user_id, model.config.hidden_size)
                st.session_state.pop("processed_upload_sigs", None)
                st.rerun()
    else:
        st.sidebar.info("No documents attached yet.")

    # Guard against infinite upload loops with session state tracking
    if "processed_upload_sigs" not in st.session_state:
        st.session_state["processed_upload_sigs"] = set()

    uploaded_file = st.sidebar.file_uploader(
        "Upload PDF, TXT, DOCX, or Image (PNG/JPG)",
        type=["pdf", "txt", "docx", "md", "png", "jpg", "jpeg", "webp"],
        key="doc_uploader"
    )
    if uploaded_file is not None:
        file_sig = f"{current_user_id}_{uploaded_file.name}_{uploaded_file.size}"
        if file_sig not in st.session_state["processed_upload_sigs"]:
            st.session_state["processed_upload_sigs"].add(file_sig)
            
            user_upload_dir = os.path.join(db.UPLOAD_DIR, current_user_id)
            os.makedirs(user_upload_dir, exist_ok=True)
            save_path = os.path.join(user_upload_dir, uploaded_file.name)

            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                st.session_state["attached_image"] = {
                    "filename": uploaded_file.name,
                    "path": save_path
                }
                st.sidebar.success(f"🖼️ Attached image '{uploaded_file.name}' for Visual Q&A & Editing!")
                st.rerun()
            else:
                # Replace previous documents if duplicate exists to avoid redundant chunks
                for d in user_docs:
                    if d["filename"] == uploaded_file.name:
                        db.delete_document(d["id"], current_user_id)
                rag.remove_document_from_user_faiss_index(current_user_id, uploaded_file.name, model, tokenizer)

                with st.sidebar.status(f"Indexing '{uploaded_file.name}'...", expanded=True) as status:
                    chunks = doc_proc.process_document_file(save_path, uploaded_file.name)
                    num_idx = rag.index_user_document_chunks(current_user_id, chunks, model, tokenizer)
                    db.add_document(
                        doc_id=str(uuid.uuid4()),
                        user_id=current_user_id,
                        filename=uploaded_file.name,
                        file_type=ext,
                        file_path=save_path,
                        num_chunks=len(chunks)
                    )
                    status.update(label=f"✓ Indexed {num_idx} chunks!", state="complete", expanded=False)
                st.sidebar.success(f"✓ '{uploaded_file.name}' ready for RAG!")
                st.rerun()

    if st.session_state.get("attached_image"):
        att = st.session_state["attached_image"]
        st.sidebar.markdown(f"**🖼️ Attached Image:** `{att['filename']}`")
        if os.path.exists(att["path"]):
            st.sidebar.image(att["path"], width=200)
        if st.sidebar.button("Detach Image", key="btn_detach_img"):
            st.session_state.pop("attached_image", None)
            st.session_state.pop("attached_image_path", None)
            st.session_state.pop("active_chat_image", None)
            st.rerun()

    # -------------------------------------------------------------------------
    # MAIN CHAT AREA
    # -------------------------------------------------------------------------
    current_chat_id = st.session_state.get("current_chat_id")
    if not current_chat_id:
        current_chat_id = f"chat_{uuid.uuid4().hex[:8]}"
        db.create_chat(current_chat_id, current_user_id, "New Chat")
        st.session_state["current_chat_id"] = current_chat_id

    # Chat Header with Title & Export Actions
    active_chat = next((c for c in user_chats if c["id"] == current_chat_id), None)
    chat_title = active_chat["title"] if active_chat else "Interactive Chat"

    col_h1, col_h2, col_h3 = st.columns([6, 2, 2])
    with col_h1:
        st.markdown(f"### 💬 {chat_title}")
    with col_h2:
        messages = db.get_chat_messages(current_chat_id, current_user_id)
        md_export = export_utils.export_chat_to_markdown(chat_title, messages)
        st.download_button(
            "📥 Export MD",
            data=md_export,
            file_name=f"{chat_title.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True
        )
    with col_h3:
        pdf_bytes = export_utils.export_chat_to_pdf(chat_title, messages)
        st.download_button(
            "📄 Export PDF",
            data=pdf_bytes,
            file_name=f"{chat_title.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # Render Chat History
    if not messages:
        doc_count = len(user_docs)
        if doc_count > 0:
            doc_names = ", ".join([f"`{d['filename']}`" for d in user_docs[:3]])
            st.markdown(f"""
            <div style="background: rgba(0, 240, 255, 0.05); border: 1px solid rgba(0, 240, 255, 0.3); border-radius: 12px; padding: 22px; text-align: center; margin: 20px 0;">
                <div style="font-size: 1.4rem; font-weight: 700; color: #00f0ff; margin-bottom: 6px;">📄 Document-Grounded RAG Ready</div>
                <div style="font-size: 0.98rem; opacity: 0.9; margin-bottom: 14px;">
                    Attached: {doc_names} ({doc_count} document{'s' if doc_count > 1 else ''} indexed into private FAISS).
                </div>
                <div style="font-size: 0.95rem; color: #7ee787;">
                    👇 <strong>Ask questions in the chat box at the bottom of the screen!</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("##### 💡 Example Questions You Can Ask:")
            cols_sug = st.columns(3)
            with cols_sug[0]:
                st.info(f"📋 **Summarize:**\n*'Provide a summary of {user_docs[0]['filename']}'*")
            with cols_sug[1]:
                st.info("🛠️ **Skills & Experience:**\n*'What work experience and key technical skills are listed?'*")
            with cols_sug[2]:
                st.info("📞 **Details & Contact:**\n*'What are the candidate’s education details and contact info?'*")
        else:
            st.markdown("""
            <div style="background: rgba(255, 255, 255, 0.02); border: 1px dashed #30363d; border-radius: 12px; padding: 22px; text-align: center; margin: 20px 0;">
                <div style="font-size: 1.3rem; font-weight: 600; margin-bottom: 6px;">👋 Welcome to LocalGPT Pro Chat</div>
                <div style="font-size: 0.95rem; opacity: 0.8; margin-bottom: 12px;">
                    Chat directly with the local Qwen model, or attach documents in the sidebar on the left for grounded RAG with source citations.
                </div>
                <div style="font-size: 0.9rem; color: #00f0ff;">
                    👇 Type a prompt in the input box below to start!
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        for m in messages:
            with st.chat_message(m["role"]):
                import re
                img_match = re.search(r'!\[(.*?)\]\((.*?)\)', m["content"])
                if img_match:
                    img_alt, img_url = img_match.group(1), img_match.group(2)
                    if img_url.startswith("/api/images/"):
                        fn = img_url.replace("/api/images/", "")
                        local_f = os.path.join("backend_uploads", "generated_images", fn)
                        if os.path.exists(local_f):
                            st.image(local_f, caption=f"Generated Image: '{img_alt}'", use_container_width=True)
                            with open(local_f, "rb") as f:
                                st.download_button("📥 Download Image", f.read(), file_name=fn, mime="image/jpeg", key=f"dl_{m['id']}")
                        else:
                            st.markdown(m["content"])
                    else:
                        st.markdown(m["content"])
                else:
                    st.markdown(m["content"])
                if m.get("sources"):
                    with st.expander("📚 View Cited Sources"):
                        st.markdown(m["sources"])

    # Chat Input Box
    user_prompt = st.chat_input("Ask a question, query your documents, or prompt the local model...")

    if user_prompt:
        # Save user message
        msg_id_u = f"msg_{uuid.uuid4().hex[:8]}"
        db.add_message(msg_id_u, current_chat_id, current_user_id, "user", user_prompt)
        
        # Update chat title if it's the first message
        if len(messages) == 0:
            db.update_chat_title(current_chat_id, current_user_id, user_prompt[:30])

        with st.chat_message("user"):
            st.markdown(user_prompt)

        # Attached image or context image
        attached_img = None
        att_obj = st.session_state.get("attached_image")
        if isinstance(att_obj, dict) and att_obj.get("path") and os.path.exists(att_obj["path"]):
            attached_img = att_obj["path"]
        elif st.session_state.get("attached_image_path") and os.path.exists(st.session_state["attached_image_path"]):
            attached_img = st.session_state["attached_image_path"]

        if not attached_img and st.session_state.get("active_chat_image"):
            if os.path.exists(st.session_state["active_chat_image"]):
                attached_img = st.session_state["active_chat_image"]

        # Check if user is requesting image modification / filter
        mod_intent = detect_image_modification(user_prompt)
        if mod_intent and (attached_img or os.path.exists("backend_uploads/generated_images")):
            # Resolve target image
            target_p = attached_img
            if not target_p and os.path.exists("backend_uploads/generated_images"):
                existing = [os.path.join("backend_uploads/generated_images", f) for f in os.listdir("backend_uploads/generated_images") if f.endswith((".jpg", ".png", ".webp"))]
                if existing:
                    target_p = max(existing, key=os.path.getctime)

            if target_p and os.path.exists(target_p):
                with st.chat_message("assistant"):
                    with st.spinner(f"✨ Executing Image Transformation: {mod_intent.get('description', 'Filter')}..."):
                        if mod_intent["action"] == "generative_variation":
                            import asyncio
                            enriched_p = mod_intent.get("enriched_prompt", user_prompt)
                            img_res = asyncio.run(generate_image_asset(enriched_p))
                            res_path = img_res["local_path"]
                        else:
                            f_res = apply_image_filter(target_p, mod_intent["action"])
                            res_path = f_res["output_path"]

                        if os.path.exists(res_path):
                            st.image(res_path, caption=f"Modified Image: {mod_intent.get('description', 'Result')}", use_container_width=True)
                            with open(res_path, "rb") as f:
                                st.download_button(
                                    label="📥 Download Modified Image",
                                    data=f.read(),
                                    file_name="modified_image.jpg",
                                    mime="image/jpeg"
                                )
                            msg_id_a = f"msg_{uuid.uuid4().hex[:8]}"
                            markdown_saved = f"![{mod_intent.get('description', 'Modified Image')}](/api/images/{os.path.basename(res_path)})\n\n**Action:** *{mod_intent.get('description', 'Transform')}*"
                            db.add_message(msg_id_a, current_chat_id, current_user_id, "assistant", markdown_saved)
                            st.rerun()

        # Check if user is asking a visual question or follow-up about an attached / active image
        vision_keywords = [
            "what is", "what are", "describe", "explain", "look", "see", "color", "palette", "resolution",
            "dimension", "size", "in this image", "in this picture", "in the picture", "about the image",
            "about this image", "tell me about", "analyze", "inspect", "detail", "quality", "what do you see",
            "who is", "what breed", "identify", "how many", "count", "error", "code", "architecture",
            "workflow", "diagram", "flowchart", "summarize", "purpose", "why", "how", "component",
            "database", "frontend", "backend", "step", "fix", "output", "trace", "find", "mean",
            "represent", "show", "where", "text", "ocr", "extract", "read", "picture", "photo"
        ]
        is_visual_turn = (
            attached_img is not None and
            os.path.exists(attached_img) and
            (
                any(k in user_prompt.lower() for k in vision_keywords) or
                st.session_state.get("attached_image") is not None or
                len(messages) <= 6
            )
        )

        if is_visual_turn:
            with st.chat_message("assistant"):
                with st.spinner("👁️ Analyzing visual content and formulating context-aware answer..."):
                    import asyncio
                    history_msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
                    vqa_res = asyncio.run(execute_visual_qa(
                        image_path=attached_img,
                        question=user_prompt,
                        requested_model=selected_model_name,
                        history_messages=history_msgs
                    ))
                    vision_ans = vqa_res.get("answer", "⚠️ No response generated.")
                    st.session_state["active_chat_image"] = attached_img
                    st.markdown(vision_ans)
                    msg_id_a = f"msg_{uuid.uuid4().hex[:8]}"
                    db.add_message(msg_id_a, current_chat_id, current_user_id, "assistant", vision_ans)
                    st.rerun()

        # Check if user is requesting image generation
        img_prompt = detect_image_prompt(user_prompt)
        if img_prompt:
            with st.chat_message("assistant"):
                with st.spinner(f"🎨 Generating image for '{img_prompt}' with FLUX.1 Diffusion..."):
                    import asyncio
                    img_res = asyncio.run(generate_image_asset(img_prompt))
                    if os.path.exists(img_res["local_path"]):
                        st.image(img_res["local_path"], caption=f"Generated Image: '{img_prompt}' (FLUX.1 Diffusion, 1024×1024)", use_container_width=True)
                        with open(img_res["local_path"], "rb") as f:
                            st.download_button(
                                label="📥 Download Image (1024×1024)",
                                data=f.read(),
                                file_name=f"{img_prompt.replace(' ', '_')}.jpg",
                                mime="image/jpeg"
                            )
                    else:
                        st.markdown(img_res["markdown"])

                    # Store assistant message
                    msg_id_a = f"msg_{uuid.uuid4().hex[:8]}"
                    db.add_message(msg_id_a, current_chat_id, current_user_id, "assistant", img_res["markdown"])
                    st.rerun()

        # RAG Retrieval Check
        with st.chat_message("assistant"):
            retrieved_chunks = []
            sources_summary = []
            rag_prompt = user_prompt

            if user_docs:
                with st.spinner("Searching user's private FAISS vector index..."):
                    retrieved_chunks = rag.retrieve_relevant_chunks(
                        user_id=current_user_id,
                        query=user_prompt,
                        model=model,
                        tokenizer=tokenizer,
                        top_k=3,
                        min_score=0.15
                    )
                    if retrieved_chunks:
                        rag_prompt, sources_summary = rag.build_rag_prompt(user_prompt, retrieved_chunks)

            # Live streaming response placeholder
            response_placeholder = st.empty()
            acc_response = ""

            def stream_callback(curr, total, tok, full_text):
                response_placeholder.markdown(full_text + "▌")

            gen_text, step_traces = generate_with_xray_trace(
                model=model,
                tokenizer=tokenizer,
                prompt=rag_prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                step_callback=stream_callback
            )

            response_placeholder.markdown(gen_text)

            # Format sources string for persistence
            sources_str = ""
            if sources_summary:
                sources_blocks = []
                for s in sources_summary:
                    sources_blocks.append(f"**[Source {s['ref']}]** `{s['filename']}` (Page {s['page']}) — *Relevance: {s['score']}*\n> {s['snippet']}")
                sources_str = "\n\n".join(sources_blocks)
                with st.expander("📚 View Cited Sources"):
                    st.markdown(sources_str)

            # Store assistant message
            msg_id_a = f"msg_{uuid.uuid4().hex[:8]}"
            db.add_message(msg_id_a, current_chat_id, current_user_id, "assistant", gen_text, sources=sources_str if sources_str else None)

            # Store last generation in session state for instant X-Ray inspection
            st.session_state["xray_prompt"] = user_prompt
            st.session_state["last_gen_text"] = gen_text
            st.session_state["last_step_traces"] = step_traces

            if st.button("🔬 Inspect this Response with Neural X-Ray", key=f"inspect_{msg_id_a}"):
                st.session_state["active_mode"] = "xray"
                st.session_state["pending_xray_prompt"] = user_prompt
                st.rerun()


# -----------------------------------------------------------------------------
# MODE 2: NEURAL LLM X-RAY WORKSTATION (Steps 4 through 10)
# -----------------------------------------------------------------------------
elif st.session_state["active_mode"] == "xray":
    st.markdown("""
    <div class="main-header">
        <div class="main-title">🔬 Neural LLM X-Ray Workstation</div>
        <div style="font-size: 1.05rem; opacity: 0.85;">
            Step-by-step neural mechanics inspection: Token IDs, Embeddings, Attention, Hidden States & Logits.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if "pending_xray_prompt" in st.session_state:
        st.session_state["xray_prompt_val"] = st.session_state.pop("pending_xray_prompt")
    elif "xray_prompt_val" not in st.session_state:
        st.session_state["xray_prompt_val"] = st.session_state.get("xray_prompt", "What is AI?")

    xray_prompt_input = st.text_input("X-Ray Target Prompt:", key="xray_prompt_val")

    run_xray_btn = st.button("🚀 Run Full Neural X-Ray Analysis", type="primary", use_container_width=True)

    # Layer & Head Selection Sliders
    col_s1, col_s2 = st.columns(2)
    max_layers = metadata.get('num_layers', 24)
    max_heads = metadata.get('num_heads', 14)
    with col_s1:
        if "pending_layer_slider" in st.session_state:
            st.session_state["selected_layer_slider"] = st.session_state.pop("pending_layer_slider")
        elif "selected_layer_slider" not in st.session_state:
            st.session_state["selected_layer_slider"] = min(12, max_layers)

        st.session_state["selected_layer_slider"] = min(max(1, st.session_state["selected_layer_slider"]), max_layers)

        selected_layer_num = st.slider(
            "Inspect Transformer Layer",
            min_value=1,
            max_value=max_layers,
            key="selected_layer_slider"
        )
        selected_layer_idx = selected_layer_num - 1
    with col_s2:
        if "pending_head_slider" in st.session_state:
            st.session_state["selected_head_slider"] = st.session_state.pop("pending_head_slider")
        elif "selected_head_slider" not in st.session_state:
            st.session_state["selected_head_slider"] = 1

        st.session_state["selected_head_slider"] = min(max(1, st.session_state["selected_head_slider"]), max_heads)

        selected_head_num = st.slider(
            "Inspect Attention Head",
            min_value=1,
            max_value=max_heads,
            key="selected_head_slider"
        )
        selected_head_idx = selected_head_num - 1

    curr_xdata = st.session_state.get("xray_data")
    needs_xray_run = (
        run_xray_btn
        or (curr_xdata is None)
        or (curr_xdata.get("prompt") != xray_prompt_input)
        or (curr_xdata.get("model_name") != selected_model_name)
    )

    if needs_xray_run and xray_prompt_input:
        tokens_info = tokenize_text(tokenizer, xray_prompt_input)
        input_ids = [t["token_id"] for t in tokens_info]

        with st.status("🔬 Executing Full Forward Pass & Capturing Tensors...", expanded=True) as status:
            st.write("⚡ Step 1/4 — Extracting input embedding matrix...")
            embeddings_data = extract_embeddings(model, input_ids)

            st.write("⚡ Step 2/4 — Computing multi-head attentions & layer hidden states...")
            forward_outputs = forward_xray(model, input_ids)

            st.write("⚡ Step 3/4 — Computing LM Head logits and softmax probabilities...")
            next_token_probs = compute_logits_and_probs(
                forward_outputs["last_logits"],
                tokenizer,
                top_k=top_k,
                temperature=temperature,
                top_p=top_p
            )

            st.write(f"⚡ Step 4/4 — Generating {max_new_tokens} autoregressive tokens with step trace...")
            gen_text, step_traces = generate_with_xray_trace(
                model=model,
                tokenizer=tokenizer,
                prompt=xray_prompt_input,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p
            )
            status.update(label="✅ Neural X-Ray Complete!", state="complete", expanded=False)

        st.session_state["xray_data"] = {
            "model_name": selected_model_name,
            "prompt": xray_prompt_input,
            "tokens_info": tokens_info,
            "input_ids": input_ids,
            "embeddings_data": embeddings_data,
            "forward_outputs": forward_outputs,
            "next_token_probs": next_token_probs,
            "generated_text": gen_text,
            "step_traces": step_traces
        }

    xdata = st.session_state.get("xray_data")

    if xdata and xdata.get("prompt") == xray_prompt_input and xdata.get("model_name") == selected_model_name:
        tokens_info = xdata["tokens_info"]
        embeddings_data = xdata["embeddings_data"]
        forward_outputs = xdata["forward_outputs"]
        next_token_probs = xdata["next_token_probs"]
        generated_text = xdata["generated_text"]
        step_traces = xdata["step_traces"]

        # Generated text preview
        st.markdown(f"""
        <div style="border: 1px solid #30363d; border-radius: 10px; padding: 16px; margin-bottom: 20px;">
            <div style="font-weight: bold; color: #00f0ff; margin-bottom: 6px;">🤖 Generated Response:</div>
            <div style="font-size: 1.05rem;">{generated_text}</div>
        </div>
        """, unsafe_allow_html=True)

        tabs = st.tabs([
            "1️⃣ Step 1: Prompt Input",
            "2️⃣ Step 2: BPE Tokens",
            "3️⃣ Step 3: Token IDs",
            "4️⃣ Step 4: Embeddings",
            "5️⃣ Step 5: Architecture",
            "6️⃣ Step 6: Self-Attention",
            "7️⃣ Step 7: Hidden States",
            "8️⃣ Step 8: LM Head Logits",
            "9️⃣ Step 9: Softmax Probs",
            "🔟 Step 10: Generation Rollout"
        ])

        # -------------------------------------------------------------
        # STEP 1: PROMPT INPUT
        # -------------------------------------------------------------
        with tabs[0]:
            st.markdown("### Step 1 — Raw Text Prompt Ingestion")
            st.markdown("Before neural computation can begin, the human prompt is ingested as a raw Unicode text string and wrapped into the model's instruction template.")
            
            st.markdown(f"""
            <div class="xray-code-box" style="font-size: 1.05rem; line-height: 1.6;">
                <strong>Raw Input Text:</strong><br>{xray_prompt_input}
            </div>
            """, unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Total Characters", len(xray_prompt_input))
            with m2:
                st.metric("Total Words", len(xray_prompt_input.split()))
            with m3:
                st.metric("Sub-Word Tokens", len(tokens_info))
            with m4:
                st.metric("Execution Device", actual_device.type.upper())

            st.markdown("#### ChatML / Instruct Template Boundary")
            chatml_sample = f"<|im_start|>user\n{xray_prompt_input}<|im_end|>\n<|im_start|>assistant\n"
            st.code(chatml_sample, language="text")
            st.caption("Instruct-tuned models delimit conversation turns with special tokens like `<|im_start|>` and `<|im_end|>` so the neural weights recognize speaker boundaries.")

        # -------------------------------------------------------------
        # STEP 2: BPE TOKENIZATION
        # -------------------------------------------------------------
        with tabs[1]:
            st.markdown("### Step 2 — Byte-Pair Encoding (BPE) Sub-Word Tokenization")
            st.markdown("The tokenizer decomposes raw text into sub-word tokens using Byte-Pair Encoding (BPE). Leading spaces are represented by prefix markers (e.g. ` ` or `Ġ`).")

            chip_html = "".join([f"<span class='token-chip'>{t['display_token']}</span>" for t in tokens_info])
            st.markdown(chip_html, unsafe_allow_html=True)

            st.markdown("#### Sub-Word Token Breakdown")
            token_rows = []
            for t in tokens_info:
                token_rows.append({
                    "Index": t["index"],
                    "Sub-word String": t["display_token"],
                    "Raw Token String": repr(t["raw_token"]),
                    "Character Span": t["char_length"],
                    "Starts With Space": t["display_token"].startswith(" ") or t["raw_token"].startswith("Ġ")
                })
            st.dataframe(pd.DataFrame(token_rows), use_container_width=True)
            st.info("💡 **Why Sub-words?** Sub-word tokenization avoids out-of-vocabulary issues by decomposing complex or rare words into frequent sub-word syllables or byte pieces.")

        # -------------------------------------------------------------
        # STEP 3: VOCABULARY TOKEN IDS
        # -------------------------------------------------------------
        with tabs[2]:
            st.markdown("### Step 3 — Vocabulary Token IDs & Embedding Indices")
            vocab_sz = metadata.get('vocab_size', 151643)
            st.markdown(f"Every sub-word token maps to an exact integer ID from Qwen's vocabulary table (**{vocab_sz:,}** tokens total). These integers form the initial tensor fed into the embedding lookup layer.")

            flow_info = format_step4_flow(tokens_info)
            st.markdown(f"""
            <div class="xray-code-box">
                Input Prompt:<br>{xray_prompt_input}<br><br>
                Tokens:<br>{flow_info['tokens_str']}<br><br>
                Token IDs (Input Tensor):<br>{flow_info['ids_str']}
            </div>
            """, unsafe_allow_html=True)

            chip_id_html = "".join([f"<span class='token-chip'>{t['display_token']} <span class='token-id-chip'>ID: {t['token_id']}</span></span>" for t in tokens_info])
            st.markdown(chip_id_html, unsafe_allow_html=True)

            st.markdown("#### Token ID Lookup Table")
            id_rows = []
            for t in tokens_info:
                id_rows.append({
                    "Index": t["index"],
                    "Display Token": t["display_token"],
                    "Token ID": t["token_id"],
                    "Hex Format": hex(t["token_id"]),
                    "Valid Range": f"0 to {vocab_sz - 1}"
                })
            st.dataframe(pd.DataFrame(id_rows), use_container_width=True)

        # -------------------------------------------------------------
        # STEP 4: INPUT EMBEDDINGS
        # -------------------------------------------------------------
        with tabs[3]:
            st.markdown("### Step 4 — Input Token Embeddings (Vector Space)")
            vocab_sz = metadata.get('vocab_size', 151643)
            h_dim = metadata.get('hidden_dim', 896)
            st.markdown(f"The input IDs index into the embedding matrix $W_{{emb}}$ of shape `({vocab_sz:,}, {h_dim})`. Each token becomes a dense continuous vector of dimension **{h_dim}**.")

            col_e1, col_e2 = st.columns(2)
            with col_e1:
                st.plotly_chart(create_pca_embedding_plot(embeddings_data["embedding_matrix"], tokens_info), use_container_width=True)
            with col_e2:
                st.plotly_chart(create_embedding_heatmap_matrix(embeddings_data["embedding_matrix"], tokens_info), use_container_width=True)

            st.markdown("#### Embedding Vector Summary Statistics")
            st.dataframe(pd.DataFrame(embeddings_data["stats"])[["token_index", "token_id", "norm", "mean", "std", "min", "max", "slice"]], use_container_width=True)

        # -------------------------------------------------------------
        # STEP 5: TRANSFORMER ARCHITECTURE
        # -------------------------------------------------------------
        with tabs[4]:
            st.markdown("### Step 5 — Transformer Layer Architecture & Structural Blueprint")
            n_layers = metadata.get('num_layers', 24)
            n_heads = metadata.get('num_heads', 14)
            h_dim = metadata.get('hidden_dim', 896)
            vocab_sz = metadata.get('vocab_size', 151643)
            param_display = metadata.get('num_parameters_formatted', f"{metadata.get('total_params_b', 0.49)}B")
            st.info(f"Selected: **Layer {selected_layer_idx + 1} of {n_layers}** | Heads: {n_heads} | Hidden Dim: {h_dim} | Parameters: {param_display}")

            st.markdown("#### Select Layer to Inspect:")
            layer_cols = st.columns(7)
            for l_idx in range(n_layers):
                with layer_cols[l_idx % 7]:
                    btn_type = "primary" if l_idx == selected_layer_idx else "secondary"
                    if st.button(f"L{l_idx + 1}", key=f"xray_btn_layer_{l_idx}", type=btn_type):
                        st.session_state["pending_layer_slider"] = l_idx + 1
                        st.rerun()

            st.markdown("---")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown(f"""
                <div class="source-card">
                    <strong>Layer {selected_layer_idx + 1} Internal Block Composition:</strong><br>
                    • <strong>Input RMSNorm:</strong> Normalizes incoming hidden states.<br>
                    • <strong>Q, K, V Projections:</strong> Linear maps to query, key, and value vectors.<br>
                    • <strong>RoPE (Rotary Position Embeddings):</strong> Encodes relative token distance.<br>
                    • <strong>Multi-Head / GQA Attention:</strong> {n_heads} Query heads, {metadata.get('num_kv_heads', 2)} KV heads.<br>
                    • <strong>Post-Attention RMSNorm:</strong> Normalizes attention output before MLP.<br>
                    • <strong>SwiGLU Feed-Forward Network:</strong> Intermediate dimension {metadata.get('intermediate_dim', 4864)}.<br>
                    • <strong>Residual Addition:</strong> $x_{{l}} = x_{{l-1}} + \\text{{Block}}(x_{{l-1}})$.
                </div>
                """, unsafe_allow_html=True)
            with col_b2:
                head_dim_calc = h_dim // n_heads if n_heads else 64
                st.markdown(f"""
                <div class="source-card">
                    <strong>Model Global Architecture Specifications:</strong><br>
                    • <strong>Architecture Type:</strong> Qwen2ForCausalLM<br>
                    • <strong>Total Transformer Layers:</strong> {n_layers}<br>
                    • <strong>Hidden Dimension ($d_{{model}}$):</strong> {h_dim}<br>
                    • <strong>Attention Heads:</strong> {n_heads}<br>
                    • <strong>Head Dimension ($d_{{head}}$):</strong> {head_dim_calc}<br>
                    • <strong>Vocabulary Size:</strong> {vocab_sz:,}
                </div>
                """, unsafe_allow_html=True)

        # -------------------------------------------------------------
        # STEP 6: MULTI-HEAD SELF-ATTENTION
        # -------------------------------------------------------------
        with tabs[5]:
            st.markdown(f"### Step 6 — Multi-Head Self-Attention (Layer {selected_layer_idx + 1}, Head {selected_head_idx + 1})")
            st.markdown(r"Self-attention computes inter-token dependency weights: $\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right) V$.")

            num_att_layers = len(forward_outputs["attentions"])
            safe_layer_idx = min(max(0, selected_layer_idx), num_att_layers - 1)
            att_layer = forward_outputs["attentions"][safe_layer_idx]
            safe_head_idx = min(max(0, selected_head_idx), att_layer.shape[0] - 1)
            att_head = att_layer[safe_head_idx]

            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.markdown(f"#### Head {safe_head_idx + 1} Attention Matrix")
                st.plotly_chart(create_attention_heatmap(att_head, tokens_info, safe_layer_idx, safe_head_idx), use_container_width=True)
            with col_a2:
                st.markdown("#### Layer-Averaged Attention (All Heads Combined)")
                st.plotly_chart(create_attention_heatmap(att_layer.mean(axis=0), tokens_info, safe_layer_idx, head_idx=0), use_container_width=True)

            st.caption("Note: The lower-triangular causal attention mask enforces that tokens only attend to past and current tokens, never future tokens.")

        # -------------------------------------------------------------
        # STEP 7: HIDDEN STATES TRAJECTORY
        # -------------------------------------------------------------
        with tabs[6]:
            st.markdown("### Step 7 — Hidden States Depth Evolution Trajectory")
            st.markdown("As tokens flow through all transformer layers, their hidden representations continuously shift and refine in high-dimensional vector space.")

            selected_token_idx = st.selectbox(
                "Select Token to Track through the Network Depth:",
                options=list(range(len(tokens_info))),
                format_func=lambda i: f"[{tokens_info[i]['index']}] '{tokens_info[i]['display_token']}'",
                index=len(tokens_info) - 1,
                key=f"token_select_box_{len(tokens_info)}_{abs(hash(xray_prompt_input))}"
            )

            st.plotly_chart(create_hidden_states_pca_trajectory(forward_outputs["hidden_states"], tokens_info, selected_token_idx=selected_token_idx), use_container_width=True)
            st.info(f"💡 The PCA trajectory traces the {metadata.get('hidden_dim', 896)}-dimensional vector for token `'{tokens_info[selected_token_idx]['display_token']}'` from Layer 0 (Embedding) through Layer {metadata.get('num_layers', 24)}.")

        # -------------------------------------------------------------
        # STEP 8: LM HEAD LOGITS
        # -------------------------------------------------------------
        with tabs[7]:
            st.markdown("### Step 8 — LM Head Unembedding Logits")
            vocab_sz = metadata.get('vocab_size', 151643)
            st.markdown(f"The final layer hidden state $h_L$ is linearly projected onto the vocabulary space via the unembedding matrix $W_U$: $z = h_L \cdot W_U^T \in \mathbb{{R}}^{{{vocab_sz:,}}}$.")

            st.plotly_chart(create_logits_bar_chart(next_token_probs, top_k=15), use_container_width=True)

            st.markdown("#### Top Candidate Unnormalized Logits")
            st.dataframe(pd.DataFrame(next_token_probs)[["rank", "token_str", "display_str", "token_id", "logit"]], use_container_width=True)

        # -------------------------------------------------------------
        # STEP 9: SOFTMAX PROBABILITIES
        # -------------------------------------------------------------
        with tabs[8]:
            st.markdown("### Step 9 — Softmax Normalization & Temperature-Scaled Probabilities")
            st.markdown(r"Softmax exponentiates and normalizes raw logits into a valid probability distribution: $P(w_i) = \frac{\exp(z_i / T)}{\sum_j \exp(z_j / T)}$.")

            prob_df = pd.DataFrame(next_token_probs)
            prob_fig = px.bar(
                prob_df.head(15),
                x="display_str",
                y="probability",
                text="percentage",
                labels={"display_str": "Token Candidate", "probability": "Softmax Probability"},
                title=f"Top-15 Next-Token Probabilities (Temperature = {temperature}, Top-P = {top_p}, Top-K = {top_k})",
                template="plotly_dark" if st.session_state["theme"] == "dark" else "plotly_white"
            )
            prob_fig.update_traces(marker_color="#00f0ff" if st.session_state["theme"] == "dark" else "#0969da", textposition="outside")
            prob_fig.update_layout(xaxis_tickangle=-45, height=420)
            st.plotly_chart(prob_fig, use_container_width=True)

            st.markdown("#### Softmax Probabilities & Sampling Table")
            st.dataframe(prob_df[["rank", "token_str", "display_str", "token_id", "probability", "percentage", "logit"]], use_container_width=True)

        # -------------------------------------------------------------
        # STEP 10: GENERATION ROLLOUT
        # -------------------------------------------------------------
        with tabs[9]:
            st.markdown("### Step 10 — Autoregressive Generation Rollout")
            st.markdown("The model appends the chosen token to the input sequence and repeats the forward pass autoregressively until maximum tokens or an end-of-sequence token is reached.")

            if step_traces:
                if len(step_traces) > 1:
                    step_slider = st.slider("Scrub Generation Step:", min_value=1, max_value=len(step_traces), value=1, key=f"rollout_step_slider_{len(step_traces)}")
                else:
                    step_slider = 1
                    st.info("Single step generated.")
                step_fig, step_info = create_step_generation_flow(step_traces, step_slider - 1)
                st.plotly_chart(step_fig, use_container_width=True)

                st.markdown("#### Step-by-Step Generation Rollout Log")
                st.dataframe(pd.DataFrame([{"Step": s["step"], "Chosen Token": f"'{s['chosen_display_str']}'", "Token ID": s["chosen_token_id"], "Accumulated Text": s["accumulated_text"]} for s in step_traces]), use_container_width=True)
            else:
                st.info("No generation traces recorded yet. Click 'Run Full Neural X-Ray Analysis' above.")
