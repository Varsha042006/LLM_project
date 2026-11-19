import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class Settings(BaseModel):
    # App
    APP_NAME: str = "ChatGPT Platform API"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Database: Supports PostgreSQL (e.g. postgresql://user:pass@host:5432/dbname) or SQLite fallback
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chatgpt_platform.db")
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "chatgpt_platform_super_secret_jwt_key_2026_at_least_32_bytes_long")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # Uploads
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "backend_uploads")
    
    # Provider-Specific API Keys & Models
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY") or os.getenv("HOSTED_LLM_API_KEY") or ""
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    HOSTED_LLM_API_KEY: str = os.getenv("HOSTED_LLM_API_KEY") or os.getenv("GROQ_API_KEY") or ""
    HOSTED_LLM_BASE_URL: str = os.getenv("HOSTED_LLM_BASE_URL", "https://api.groq.com/openai/v1")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # HuggingFace Inference API token (free tier) for SDXL inpainting / img2img
    HF_API_TOKEN: str = os.getenv("HF_API_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN") or ""
    
    # Global Defaults
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "local") # local, groq, gemini, huggingface, custom
    DEFAULT_MODEL_NAME: str = os.getenv("DEFAULT_MODEL_NAME", "qwen-2.5-local")
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]

settings = Settings()

