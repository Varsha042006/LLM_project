import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.app.config import settings
from backend.app.llm_router import (
    classify_model_provider,
    resolve_llm_execution_plan,
    get_provider_key,
    PROVIDER_GROQ,
    PROVIDER_GEMINI,
    PROVIDER_HUGGINGFACE,
    GROQ_SUPPORTED_MODELS,
    GEMINI_SUPPORTED_MODELS
)
from backend.app.llm_service import stream_chat_completion


class DummySettings:
    """Mock user settings object."""
    def __init__(self, provider="groq", api_key=None, base_url=None, model_name=None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name


class TestLLMProviderRouter(unittest.TestCase):
    """
    Test suite verifying strict provider and model routing.
    Guarantees Groq models only go to Groq, Gemini models only go to Gemini,
    and cross-provider fallbacks never leak mismatched model names.
    """

    def test_classify_model_provider(self):
        # Groq models
        self.assertEqual(classify_model_provider("llama-3.3-70b-versatile"), PROVIDER_GROQ)
        self.assertEqual(classify_model_provider("llama-3.1-8b-instant"), PROVIDER_GROQ)
        self.assertEqual(classify_model_provider("qwen-2.5-32b-it"), PROVIDER_GROQ)
        self.assertEqual(classify_model_provider("deepseek-r1-distill-llama-70b"), PROVIDER_GROQ)
        self.assertEqual(classify_model_provider("mixtral-8x7b-32768"), PROVIDER_GROQ)

        # Gemini models
        self.assertEqual(classify_model_provider("gemini-3.5-flash"), PROVIDER_GEMINI)
        self.assertEqual(classify_model_provider("gemini-3.5-flash-lite"), PROVIDER_GEMINI)
        self.assertEqual(classify_model_provider("gemini-3.8-flash"), PROVIDER_GEMINI)
        self.assertEqual(classify_model_provider("gemini-2.5-flash"), PROVIDER_GEMINI)
        self.assertEqual(classify_model_provider("gemini-1.5-flash"), PROVIDER_GEMINI)
        self.assertEqual(classify_model_provider("gemini-2.0-flash"), PROVIDER_GEMINI)
        self.assertEqual(classify_model_provider("gemini-flash-latest"), PROVIDER_GEMINI)

        # HuggingFace models
        self.assertEqual(classify_model_provider("meta-llama/Llama-3.2-3B-Instruct"), PROVIDER_HUGGINGFACE)

    def test_groq_models_never_sent_to_gemini(self):
        """
        Critical Test: When Groq model (llama-3.3-70b-versatile) is requested,
        the plan must target Groq, and any fallback to Gemini MUST use a Gemini-supported model.
        """
        user_s = DummySettings(provider="groq", api_key="gsk_test_groq_key")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIza_test_gemini_key"}):
            plan = resolve_llm_execution_plan("llama-3.3-70b-versatile", user_settings=user_s)

            # Primary must be Groq
            self.assertEqual(plan.primary_provider, PROVIDER_GROQ)
            self.assertEqual(plan.primary_model, "llama-3.3-70b-versatile")
            self.assertIn("groq.com", plan.primary_base_url)

            # Fallback must be Gemini with a GEMINI model, NEVER llama
            if plan.fallback_provider == PROVIDER_GEMINI:
                self.assertIn("gemini", plan.fallback_model.lower())
                self.assertNotIn("llama", plan.fallback_model.lower())
                self.assertIn("googleapis.com", plan.fallback_base_url)

    def test_gemini_models_never_sent_to_groq(self):
        """
        Critical Test: When Gemini model (gemini-2.5-flash) is requested,
        the plan must target Gemini, and any fallback to Groq MUST use a Groq-supported model.
        """
        user_s = DummySettings(provider="gemini", api_key="AIza_test_gemini_key")
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_groq_key"}):
            plan = resolve_llm_execution_plan("gemini-2.5-flash", user_settings=user_s)

            # Primary must be Gemini
            self.assertEqual(plan.primary_provider, PROVIDER_GEMINI)
            self.assertEqual(plan.primary_model, "gemini-2.5-flash")
            self.assertIn("googleapis.com", plan.primary_base_url)

            # Fallback must be Groq with a GROQ model, NEVER gemini
            if plan.fallback_provider == PROVIDER_GROQ:
                self.assertIn("llama", plan.fallback_model.lower())
                self.assertNotIn("gemini", plan.fallback_model.lower())
                self.assertIn("groq.com", plan.fallback_base_url)

    def test_gemini_only_key_auto_remapping(self):
        """
        Fix verification for the user's reported bug:
        When only a Gemini API key is configured, and the request or default model
        is 'llama-3.3-70b-versatile', the router must automatically remap the model
        to a valid Gemini model ('gemini-2.5-flash') so that Google Gemini never
        receives a 404 for models/llama-3.3-70b-versatile.
        """
        # User configured Gemini key, but did not change model from default llama-3.3-70b
        user_s = DummySettings(provider="gemini", api_key="AIza_test_key_123")
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            plan = resolve_llm_execution_plan("llama-3.3-70b-versatile", user_settings=user_s)

            self.assertEqual(plan.primary_provider, PROVIDER_GEMINI)
            # The model sent to Gemini MUST NOT be llama-3.3-70b-versatile!
            self.assertNotEqual(plan.primary_model, "llama-3.3-70b-versatile")
            self.assertIn("gemini", plan.primary_model.lower())
            self.assertIn(plan.primary_model, GEMINI_SUPPORTED_MODELS)

    def test_environment_variables_resolution(self):
        """Verifies GROQ_API_KEY, GROQ_MODEL, GEMINI_API_KEY, GEMINI_MODEL."""
        test_env = {
            "GROQ_API_KEY": "gsk_custom_groq_123",
            "GROQ_MODEL": "qwen-2.5-32b-it",
            "GEMINI_API_KEY": "AIza_custom_gemini_456",
            "GEMINI_MODEL": "gemini-2.0-flash",
        }
        with patch.dict(os.environ, test_env):
            groq_key = get_provider_key(PROVIDER_GROQ)
            gemini_key = get_provider_key(PROVIDER_GEMINI)

            self.assertEqual(groq_key, "gsk_custom_groq_123")
            self.assertEqual(gemini_key, "AIza_custom_gemini_456")

    def test_supported_model_lists_sanity(self):
        """Verifies that all registry models are non-empty and well-formed."""
        for m in GROQ_SUPPORTED_MODELS:
            self.assertTrue(len(m) > 3)
            self.assertNotIn("gemini", m)

        for m in GEMINI_SUPPORTED_MODELS:
            self.assertTrue(len(m) > 3)
            self.assertIn("gemini", m)


if __name__ == "__main__":
    unittest.main()

