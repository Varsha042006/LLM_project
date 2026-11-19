import os
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import httpx

from .config import settings

# Provider identifiers
PROVIDER_GROQ = "groq"
PROVIDER_GEMINI = "gemini"
PROVIDER_HUGGINGFACE = "huggingface"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_LOCAL = "local"
PROVIDER_CUSTOM = "custom"

# Provider Supported Models Registry
GROQ_SUPPORTED_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.2-1b-preview",
    "llama-3.2-3b-preview",
    "llama-3.2-11b-vision-preview",
    "qwen-2.5-32b-it",
    "deepseek-r1-distill-llama-70b",
    "mixtral-8x7b-32768",
    "gemma2-9b-it"
]

GEMINI_SUPPORTED_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-flash-latest",
    "gemini-pro-latest"
]

HUGGINGFACE_SUPPORTED_MODELS = [
    "meta-llama/Llama-3.2-3B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3"
]

OPENROUTER_SUPPORTED_MODELS = [
    "meta-llama/llama-3.3-70b-instruct",
    "google/gemini-3.5-flash",
    "deepseek/deepseek-r1"
]

PROVIDER_DEFAULT_MODELS = {
    PROVIDER_GROQ: settings.GROQ_MODEL or "openai/gpt-oss-120b",
    PROVIDER_GEMINI: settings.GEMINI_MODEL or "gemini-2.0-flash",
    PROVIDER_HUGGINGFACE: "meta-llama/Llama-3.2-3B-Instruct",
    PROVIDER_OPENROUTER: "meta-llama/llama-3.3-70b-instruct",
    PROVIDER_LOCAL: "qwen2.5-0.5b"
}

PROVIDER_DEFAULT_BASE_URLS = {
    PROVIDER_GROQ: "https://api.groq.com/openai/v1",
    PROVIDER_GEMINI: "https://generativelanguage.googleapis.com/v1beta/openai",
    PROVIDER_HUGGINGFACE: "https://api-inference.huggingface.co/v1",
    PROVIDER_OPENROUTER: "https://openrouter.ai/api/v1"
}


@dataclass
class LLMExecutionPlan:
    """Represents the strictly validated routing plan for an LLM query."""
    primary_provider: str
    primary_model: str
    primary_api_key: Optional[str]
    primary_base_url: str
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    fallback_api_key: Optional[str] = None
    fallback_base_url: Optional[str] = None
    routing_reason: str = "direct"


def classify_model_provider(model_name: Optional[str]) -> str:
    """
    Identifies the native provider for any model string.
    Ensures model names are never routed to the wrong provider.
    """
    if not model_name or not model_name.strip():
        return settings.DEFAULT_LLM_PROVIDER or PROVIDER_GROQ

    m = model_name.strip().lower()

    if "local" in m or "qwen-2.5-local" in m or "qwen2.5-0.5b" in m or "qwen2.5-1.5b" in m:
        return PROVIDER_LOCAL
    if m in [x.lower() for x in GEMINI_SUPPORTED_MODELS] or "gemini" in m:
        return PROVIDER_GEMINI
    if m in [x.lower() for x in GROQ_SUPPORTED_MODELS]:
        return PROVIDER_GROQ
    if any(k in m for k in ["llama", "qwen", "deepseek", "mixtral", "gemma"]) and "/" not in m:
        return PROVIDER_GROQ
    if "/" in m:
        return PROVIDER_HUGGINGFACE

    return settings.DEFAULT_LLM_PROVIDER or PROVIDER_GROQ


def get_provider_key(provider: str, user_settings: Optional[Any] = None) -> Optional[str]:
    """Retrieves the valid API key for a specific provider without cross-polluting."""
    # 1. Check user settings if the user's chosen provider matches
    if user_settings:
        user_p = getattr(user_settings, "provider", None)
        user_k = getattr(user_settings, "api_key", None)
        if user_k and str(user_k).strip() and not str(user_k).startswith("demo_"):
            clean_k = str(user_k).strip()
            # If provider matches explicitly
            if user_p == provider:
                return clean_k
            # If key format indicates Google Gemini (starts with AIza)
            if provider == PROVIDER_GEMINI and clean_k.startswith("AIza"):
                return clean_k
            # If key format indicates Groq (starts with gsk_)
            if provider == PROVIDER_GROQ and clean_k.startswith("gsk_"):
                return clean_k

    # 2. Check environment / global config for provider
    if provider == PROVIDER_GROQ:
        k = os.getenv("GROQ_API_KEY") or os.getenv("HOSTED_LLM_API_KEY") or settings.GROQ_API_KEY or settings.HOSTED_LLM_API_KEY
        if k and k.strip() and not k.startswith("demo_"):
            return k.strip()
    elif provider == PROVIDER_GEMINI:
        k = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or settings.GEMINI_API_KEY
        if k and k.strip() and not k.startswith("demo_"):
            return k.strip()
    elif provider == PROVIDER_HUGGINGFACE:
        k = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
        if k and k.strip() and not k.startswith("demo_"):
            return k.strip()

    return None


def resolve_llm_execution_plan(
    requested_model: Optional[str] = None,
    user_settings: Optional[Any] = None
) -> LLMExecutionPlan:
    """
    Central LLM Router:
    1. Analyzes requested model and user settings.
    2. Enforces strict provider-model pairing (never sends Groq model to Gemini or Gemini model to Groq).
    3. Selects primary provider based on available credentials and requested model.
    4. Sets up cross-provider fallback with valid fallback model name.
    """
    req_model = requested_model.strip() if requested_model else None
    native_provider = classify_model_provider(req_model) if req_model else None

    # Check available credentials
    groq_key = get_provider_key(PROVIDER_GROQ, user_settings)
    gemini_key = get_provider_key(PROVIDER_GEMINI, user_settings)
    hf_key = get_provider_key(PROVIDER_HUGGINGFACE, user_settings)

    # Determine user-selected provider in settings
    settings_provider = getattr(user_settings, "provider", None) if user_settings else None
    custom_base_url = getattr(user_settings, "base_url", None) if user_settings else None

    # Case Local Qwen Neural Model
    if native_provider == PROVIDER_LOCAL:
        return LLMExecutionPlan(
            primary_provider=PROVIDER_LOCAL,
            primary_model="qwen-2.5-local",
            primary_api_key=None,
            primary_base_url="local",
            fallback_provider=None,
            fallback_model=None,
            fallback_api_key=None,
            fallback_base_url=None,
            routing_reason="Local Qwen neural model requested"
        )

    # Case A: User explicitly requested a Gemini model
    if native_provider == PROVIDER_GEMINI:
        chosen_model = req_model if req_model in GEMINI_SUPPORTED_MODELS else (settings.GEMINI_MODEL or "gemini-3.5-flash")
        primary_p = PROVIDER_GEMINI
        primary_k = gemini_key
        primary_url = custom_base_url if (settings_provider == PROVIDER_GEMINI and custom_base_url) else PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GEMINI]

        # Fallback to Groq if Groq key exists
        fallback_p = PROVIDER_GROQ if groq_key else None
        fallback_m = (settings.GROQ_MODEL or "llama-3.3-70b-versatile") if fallback_p else None
        fallback_k = groq_key if fallback_p else None
        fallback_url = PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GROQ] if fallback_p else None

        return LLMExecutionPlan(
            primary_provider=primary_p,
            primary_model=chosen_model,
            primary_api_key=primary_k,
            primary_base_url=primary_url,
            fallback_provider=fallback_p,
            fallback_model=fallback_m,
            fallback_api_key=fallback_k,
            fallback_base_url=fallback_url,
            routing_reason="Gemini model requested"
        )

    # Case B: User requested a Groq model (e.g. llama-3.3-70b-versatile)
    if native_provider == PROVIDER_GROQ or (not native_provider and settings_provider == PROVIDER_GROQ):
        chosen_model = req_model if (req_model and req_model in GROQ_SUPPORTED_MODELS) else (settings.GROQ_MODEL or "llama-3.3-70b-versatile")

        # If Groq key is available, use Groq as primary
        if groq_key:
            primary_p = PROVIDER_GROQ
            primary_m = chosen_model
            primary_k = groq_key
            primary_url = custom_base_url if (settings_provider == PROVIDER_GROQ and custom_base_url) else PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GROQ]

            # Cross-fallback to Gemini if Gemini key exists
            fallback_p = PROVIDER_GEMINI if gemini_key else None
            fallback_m = (settings.GEMINI_MODEL or "gemini-3.5-flash") if fallback_p else None
            fallback_k = gemini_key if fallback_p else None
            fallback_url = PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GEMINI] if fallback_p else None

            return LLMExecutionPlan(
                primary_provider=primary_p,
                primary_model=primary_m,
                primary_api_key=primary_k,
                primary_base_url=primary_url,
                fallback_provider=fallback_p,
                fallback_model=fallback_m,
                fallback_api_key=fallback_k,
                fallback_base_url=fallback_url,
                routing_reason="Groq model with Groq credentials"
            )
        elif gemini_key:
            # CRITICAL FIX: User has Gemini key configured, but default model is llama-3.3-70b.
            # Do NOT send llama-3.3-70b to Gemini! Route to Gemini with Gemini's supported model.
            return LLMExecutionPlan(
                primary_provider=PROVIDER_GEMINI,
                primary_model=settings.GEMINI_MODEL or "gemini-3.5-flash",
                primary_api_key=gemini_key,
                primary_base_url=PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GEMINI],
                fallback_provider=None,
                fallback_model=None,
                fallback_api_key=None,
                fallback_base_url=None,
                routing_reason="Remapped to Gemini with Gemini model because only Gemini key is available"
            )

    # Case C: User explicitly configured settings provider as Gemini
    if settings_provider == PROVIDER_GEMINI:
        gemini_model = req_model if (req_model and "gemini" in req_model.lower()) else (settings.GEMINI_MODEL or "gemini-3.5-flash")
        return LLMExecutionPlan(
            primary_provider=PROVIDER_GEMINI,
            primary_model=gemini_model,
            primary_api_key=gemini_key,
            primary_base_url=custom_base_url or PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GEMINI],
            fallback_provider=PROVIDER_GROQ if groq_key else None,
            fallback_model=settings.GROQ_MODEL or "llama-3.3-70b-versatile" if groq_key else None,
            fallback_api_key=groq_key if groq_key else None,
            fallback_base_url=PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GROQ] if groq_key else None,
            routing_reason="Settings configured for Gemini"
        )

    # Case D: Default to Groq or local fallback
    chosen_groq_model = req_model if (req_model and req_model in GROQ_SUPPORTED_MODELS) else (settings.GROQ_MODEL or "llama-3.3-70b-versatile")
    return LLMExecutionPlan(
        primary_provider=PROVIDER_GROQ,
        primary_model=chosen_groq_model,
        primary_api_key=groq_key,
        primary_base_url=custom_base_url or PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GROQ],
        fallback_provider=PROVIDER_GEMINI if gemini_key else None,
        fallback_model=settings.GEMINI_MODEL or "gemini-3.5-flash" if gemini_key else None,
        fallback_api_key=gemini_key if gemini_key else None,
        fallback_base_url=PROVIDER_DEFAULT_BASE_URLS[PROVIDER_GEMINI] if gemini_key else None,
        routing_reason="Default routing"
    )


# =============================================================================
# Provider Execution Streamers
# =============================================================================

async def stream_openai_compatible_provider(
    provider_name: str,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    top_p: float = 0.9,
    timeout_sec: float = 60.0
) -> AsyncGenerator[Tuple[str, Optional[str]], None]:
    """
    Streams tokens from any standard OpenAI-compatible API endpoint (Groq, vLLM, HuggingFace, Gemini OpenAI endpoint).
    Yields tuple of (token, error_str). If error_str is set, stream should switch to fallback.
    Automatically handles 404 model_not_found by trying next supported candidate models.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    # Build model candidate list to handle retired or tiered models on Groq
    candidate_models = [model]
    if provider_name.lower() == "groq":
        for cand in ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
            if cand not in candidate_models:
                candidate_models.append(cand)

    last_error_msg = None
    streamed_any = False

    for cur_model in candidate_models:
        payload = {
            "model": cur_model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code == 404 and len(candidate_models) > 1 and cur_model != candidate_models[-1]:
                        # Model not found on this endpoint, try next candidate
                        continue
                    if response.status_code != 200:
                        err_bytes = await response.aread()
                        err_msg = f"{provider_name} API Error ({response.status_code}): {err_bytes.decode('utf-8', 'ignore')}"
                        last_error_msg = err_msg
                        break

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    streamed_any = True
                                    yield (content, None)
                        except Exception:
                            continue

            if streamed_any:
                return
        except Exception as e:
            last_error_msg = f"Connection to {provider_name} ({base_url}) failed: {str(e)}"
            break

    if not streamed_any and last_error_msg:
        yield ("", last_error_msg)


async def stream_gemini_native_rest(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    timeout_sec: float = 60.0
) -> AsyncGenerator[Tuple[str, Optional[str]], None]:
    """
    Streams tokens directly from Google Gemini's native generateContent / streamGenerateContent REST API.
    Bypasses OpenAI-compatible wrappers for direct Google AI Studio compatibility.
    """
    # Convert chat messages to Gemini contents structure
    gemini_contents = []
    system_instruction = None

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_instruction = {"parts": [{"text": content}]}
        else:
            g_role = "model" if role == "assistant" else "user"
            gemini_contents.append({"role": g_role, "parts": [{"text": content}]})

    if not gemini_contents:
        gemini_contents.append({"role": "user", "parts": [{"text": "Hello"}]})

    payload: Dict[str, Any] = {
        "contents": gemini_contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048
        }
    }
    if system_instruction:
        payload["system_instruction"] = system_instruction

    # Prepare model candidates starting with requested model, followed by verified available models
    candidate_models = [model]
    for m in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        if m not in candidate_models:
            candidate_models.append(m)

    last_error = None
    for cand_model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand_model}:streamGenerateContent?alt=sse&key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        err_bytes = await response.aread()
                        last_error = f"Google Gemini API Error ({response.status_code}): {err_bytes.decode('utf-8', 'ignore')}"
                        # If 404/503/429, try next candidate model
                        continue

                    # Stream succeeded
                    token_streamed = False
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        try:
                            chunk = json.loads(data_str)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    if "text" in p:
                                        token_streamed = True
                                        yield (p["text"], None)
                        except Exception:
                            continue
                    if token_streamed:
                        return
        except Exception as e:
            last_error = f"Connection to Google Gemini ({cand_model}) failed: {str(e)}"
            continue

    if last_error:
        yield ("", last_error)

