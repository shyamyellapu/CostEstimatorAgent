"""AI provider factory with fallback support."""
import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.ai.ai_provider import (
    AIProvider, ExtractedDataResponse, MemberClassification,
    CoverLetterDraft, ChatResponse
)

logger = logging.getLogger(__name__)


class FallbackProvider(AIProvider):
    """Wraps a primary and fallback provider. On any error from primary, retries with fallback."""

    def __init__(self, primary: AIProvider, fallback: AIProvider):
        self._primary = primary
        self._fallback = fallback

    @property
    def provider_name(self) -> str:
        return f"{self._primary.provider_name}(fallback:{self._fallback.provider_name})"

    async def _call_with_fallback(self, method_name: str, *args, **kwargs):
        try:
            print(f"[AI] Using PRIMARY model: {self._primary.provider_name} | operation: {method_name}")
            return await getattr(self._primary, method_name)(*args, **kwargs)
        except Exception as primary_err:
            print(
                f"[AI] PRIMARY ({self._primary.provider_name}) failed for '{method_name}' "
                f"— {type(primary_err).__name__}: {primary_err}. "
                f"Switching to FALLBACK: {self._fallback.provider_name}"
            )
            logger.warning(
                f"{self._primary.provider_name} failed for {method_name} "
                f"({type(primary_err).__name__}: {primary_err}). "
                f"Retrying with {self._fallback.provider_name}..."
            )
            result = await getattr(self._fallback, method_name)(*args, **kwargs)
            print(f"[AI] FALLBACK model ({self._fallback.provider_name}) succeeded for '{method_name}'")
            return result

    async def extract_from_document(self, file_bytes, file_type, filename, additional_context=None):
        return await self._call_with_fallback(
            "extract_from_document", file_bytes, file_type, filename, additional_context
        )

    async def extract_from_image(self, image_bytes, filename, additional_context=None):
        return await self._call_with_fallback(
            "extract_from_image", image_bytes, filename, additional_context
        )

    async def parse_boq(self, text, additional_context=None):
        return await self._call_with_fallback("parse_boq", text, additional_context)

    async def classify_member(self, description):
        return await self._call_with_fallback("classify_member", description)

    async def parse_quotation(self, text):
        return await self._call_with_fallback("parse_quotation", text)

    async def draft_cover_letter(self, quotation_data, template_clauses, company_info):
        return await self._call_with_fallback(
            "draft_cover_letter", quotation_data, template_clauses, company_info
        )

    async def chat(self, messages, context=None):
        return await self._call_with_fallback("chat", messages, context)

    async def complete(self, prompt, max_tokens=4000, temperature=0.1):
        return await self._call_with_fallback("complete", prompt, max_tokens=max_tokens, temperature=temperature)


def get_ai_provider() -> AIProvider:
    provider = settings.ai_provider.lower()

    if provider == "openai":
        from app.ai.openai_provider import OpenAIProvider
        from app.ai.claude_provider import ClaudeProvider
        primary = OpenAIProvider()
        fallback = ClaudeProvider()
        print(
            f"[AI] Provider configured: PRIMARY={primary.provider_name} "
            f"({settings.openai_model}) | FALLBACK={fallback.provider_name} "
            f"({settings.claude_model})"
        )
        return FallbackProvider(primary=primary, fallback=fallback)

    if provider == "claude":
        from app.ai.claude_provider import ClaudeProvider
        p = ClaudeProvider()
        print(f"[AI] Provider configured: {p.provider_name} ({settings.claude_model})")
        return p

    # Default: groq (no fallback)
    from app.ai.groq_provider import GroqProvider
    p = GroqProvider()
    print(f"[AI] Provider configured: {p.provider_name} ({settings.groq_model_large})")
    return p
