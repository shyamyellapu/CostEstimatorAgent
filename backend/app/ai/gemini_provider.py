"""
Google Gemini AI Provider — uses Google's OpenAI-compatible endpoint.

Set AI_PROVIDER=gemini in .env to use.
Google AI Studio exposes an OpenAI-compatible REST API at:
  https://generativelanguage.googleapis.com/v1beta/openai/

Get your free API key at: https://aistudio.google.com/apikey
"""
from app.ai.openai_provider import OpenAIProvider
from app.config import settings

import logging
logger = logging.getLogger(__name__)


class GeminiProvider(OpenAIProvider):

    def __init__(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required for GeminiProvider. Install with: pip install openai"
            )

        self.client = AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.model = settings.gemini_model
        self.model_fast = settings.gemini_model_fast
        self.model_vision = settings.gemini_model_vision

    @property
    def provider_name(self) -> str:
        return "gemini"
