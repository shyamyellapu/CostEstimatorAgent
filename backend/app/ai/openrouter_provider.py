"""
OpenRouter AI Provider — uses OpenAI-compatible API via OpenRouter.

Set AI_PROVIDER=openrouter in .env to use.
OpenRouter is OpenAI-API-compatible, so we inherit OpenAIProvider and
just swap the base_url and API key.

Free model: openai/gpt-oss-20b:free (no TPM limits on free tier)
"""
from app.ai.openai_provider import OpenAIProvider
from app.config import settings

import logging
logger = logging.getLogger(__name__)


class OpenRouterProvider(OpenAIProvider):

    def __init__(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required for OpenRouterProvider. Install with: pip install openai"
            )

        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://costestimatoragent.local",
                "X-Title": "Cost Estimator Agent",
            },
        )
        self.model = settings.openrouter_model
        self.model_fast = settings.openrouter_model_fast
        self.model_vision = settings.openrouter_model_vision

    @property
    def provider_name(self) -> str:
        return "openrouter"
