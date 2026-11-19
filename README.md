# LocalGPT Pro — Private Local AI & Neural X-Ray with Google Sign-In

LocalGPT Pro is a private, multi-user AI intelligence platform featuring local LLM inference (Qwen 2.5), deep Transformer Neural X-Ray introspection, per-user document RAG indexing (FAISS), and secure **Firebase Google Sign-In** authentication.

---

## 🔐 Google Sign-In Authentication Architecture

The Google Sign-In system is engineered with a strict two-way security architecture separating client-side authentication from server-side cryptographic token verification:

1. **Frontend Authentication Component (`components/firebase_auth/index.html`)**:
   - Implemented as a genuine Streamlit custom component using `streamlit.components.v1.declare_component`.
   - Uses the official Firebase JavaScript SDK (`firebase-app-compat.js` and `firebase-auth-compat.js`).
   - Renders a clean, centered "Continue with Google" button with official Google branding and interactive loading states.
   - Triggers `firebase.auth().signInWithPopup(new firebase.auth.GoogleAuthProvider())` with `{ prompt: 'select_account' }` to ensure account selection.
   - Retrieves the signed Firebase ID Token (JWT) from `user.getIdToken(true)` and dispatches it via `window.parent.postMessage` to Streamlit.

2. **Backend Cryptographic Verification (`auth_service.py`)**:
   - Validates the Firebase ID token signature, expiration (`exp`), audience (`aud`), and revocation status using the **Firebase Admin SDK** (`firebase_admin.auth.verify_id_token`).
   - Zero-trust architecture: **Never trusts client-supplied UIDs or emails**. The authenticated user identity is extracted strictly from the cryptographically verified JWT claims (`uid`, `email`, `name`, `picture`).
   - Fallback verification: Uses Google's public OAuth2 certificate endpoints (`google.oauth2.id_token.verify_firebase_token`) if service account keys are pending.

3. **Per-User Data Isolation (`database.py` & `rag.py`)**:
   - Maps the verified Google UID to an isolated user record (`google_<uid>`).
   - Scopes all database queries (conversations, messages, uploaded documents) strictly by `user_id`.
   - Isolates vector search indexes in `indexes/<user_id>/` and uploads in `uploads/<user_id>/`.
   - Prevents cross-account data leakage across multiple users.

---

## 🚀 Quick Setup & Installation

### 1. Install Dependencies
Run the following in your Python environment:
```bash
pip install -r requirements.txt
```
Key authentication libraries installed:
- `firebase-admin>=6.0.0`
- `google-auth>=2.0.0`
- `pyjwt>=2.8.0`
- `streamlit>=1.30.0`

---

## ⚙️ Firebase Configuration

### Step 1: Obtain Firebase Web App Credentials
1. Open the [Firebase Console](https://console.firebase.google.com/) and navigate to your project (`LocalGPT-Pro`).
2. Go to **Project Settings** > **General** > **Your apps** > **LocalGPT-Web**.
3. Under **Authentication** > **Sign-in method**, ensure **Google** is enabled.
4. Under **Authentication** > **Settings** > **Authorized domains**, ensure `localhost` is listed.

### Step 2: Configure Streamlit Secrets
Open or create `.streamlit/secrets.toml` (protected by `.gitignore`):
```toml
[firebase]
apiKey = "AIzaSy..."                # Your Firebase Web API key
authDomain = "localgpt-pro.firebaseapp.com"
projectId = "localgpt-pro"
storageBucket = "localgpt-pro.appspot.com"
messagingSenderId = "123456789012"
appId = "1:123456789012:web:abcdef1234567890"

# Optional: Path to Firebase Admin service account key for token revocation checks
# service_account_path = "firebase-service-account.json"
```

*Alternatively, you can export these as environment variables:*
```bash
export FIREBASE_API_KEY="AIzaSy..."
export FIREBASE_PROJECT_ID="localgpt-pro"
export FIREBASE_AUTH_DOMAIN="localgpt-pro.firebaseapp.com"
```

### Step 3 (Optional): Configure Firebase Admin Service Account
For token revocation checks and server administration:
1. In Firebase Console, go to **Project settings** > **Service accounts**.
2. Click **Generate new private key** and save the JSON file as `firebase-service-account.json` in the project root.
3. The `.gitignore` file already protects all `*-service-account.json` and credentials files from being committed.

---

## 🏃 Running the Application

Launch the Streamlit app:
```bash
streamlit run app.py
```
Or specify the port:
```bash
streamlit run app.py --server.port 8501
```

1. Open `http://localhost:8501` in your browser.
2. Click **Continue with Google**.
3. Select your Google account in the popup.
4. On successful login, the app cryptographically verifies your token, creates your isolated workspace, and loads the LocalGPT Pro dashboard with your Google name and avatar!

---

## 📁 Authentication Module Structure

| File | Purpose |
|------|---------|
| `components/firebase_auth/index.html` | Streamlit custom component iframe implementing the Firebase JS SDK, Google popup login, and postMessage event handlers. |
| `auth_component.py` | Python wrapper declaring the custom component using `streamlit.components.v1.declare_component`. |
| `auth_service.py` | Backend security service for Firebase Admin SDK initialization, token verification, and revocation checks. |
| `firebase_config.py` | Centralized configuration manager loading Web App config and service account paths from `.streamlit/secrets.toml` and environment variables. |
| `auth.py` | Core authentication module preserving Email/Password hashing and delegating token verification to `auth_service`. |
| `database.py` | SQLite database manager managing user records, Google avatar URLs, and per-user data isolation. |
| `app.py` | Main Streamlit application with modern centered login card, Google avatar display, and protected dashboard. |
| `.streamlit/secrets.toml.example` | Template for configuring Firebase credentials. |
| `.gitignore` | Security rules ensuring secrets, credentials, and private databases are never committed. |

