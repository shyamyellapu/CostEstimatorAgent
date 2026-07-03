"""AI provider factory with fallback support."""
import logging
from typing import List

from app.config import settings
from app.ai.ai_provider import (
    AIProvider, ExtractedDataResponse, MemberClassification,
    CoverLetterDraft, ChatResponse
)

logger = logging.getLogger(__name__)


class FallbackProvider(AIProvider):
    """Wraps multiple providers and retries in order until one succeeds."""

    def __init__(self, providers: List[AIProvider]):
        if not providers:
            raise ValueError("At least one AI provider is required")
        self._providers = providers

    @property
    def provider_name(self) -> str:
        names = [p.provider_name for p in self._providers]
        return "fallback:" + "->".join(names)

    async def _call_with_fallback(self, method_name: str, *args, **kwargs):
        errors: List[str] = []
        for provider in self._providers:
            try:
                result = await getattr(provider, method_name)(*args, **kwargs)
                if method_name == "parse_quotation" and isinstance(result, dict) and result.get("error"):
                    raise RuntimeError(f"parse_quotation returned error: {result.get('error')}")
                return result
            except Exception as err:
                errors.append(f"{provider.provider_name}: {type(err).__name__}: {err}")
                logger.warning("%s failed for %s: %s", provider.provider_name, method_name, err)

        raise RuntimeError(f"All providers failed for '{method_name}': {' | '.join(errors)}")

    async def extract_from_document(self, file_bytes, file_type, filename, additional_context=None):
        return await self._call_with_fallback(
            "extract_from_document", file_bytes, file_type, filename, additional_context
        )

    async def extract_from_image(self, image_bytes, filename, additional_context=None):
        return await self._call_with_fallback(
            "extract_from_image", image_bytes, filename, additional_context
        )

    async def extract_from_multiple_files(self, files, additional_context=None):
        return await self._call_with_fallback(
            "extract_from_multiple_files", files, additional_context
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


def _has_openai_key() -> bool:
    return bool((settings.openai_api_key or "").strip())


def _has_claude_key() -> bool:
    return bool((settings.anthropic_api_key or "").strip())


def _has_groq_key() -> bool:
    return bool((settings.groq_api_key or "").strip())


def _has_openrouter_key() -> bool:
    return bool((settings.openrouter_api_key or "").strip())


def _has_gemini_key() -> bool:
    return bool((settings.gemini_api_key or "").strip())


def _make_provider(name: str) -> "AIProvider | None":
    if name == "openai":
        if not _has_openai_key():
            return None
        from app.ai.openai_provider import OpenAIProvider
        return OpenAIProvider()
    if name == "claude":
        if not _has_claude_key():
            return None
        from app.ai.claude_provider import ClaudeProvider
        return ClaudeProvider()
    if name == "groq":
        if not _has_groq_key():
            return None
        from app.ai.groq_provider import GroqProvider
        return GroqProvider()
    if name == "openrouter":
        if not _has_openrouter_key():
            return None
        from app.ai.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider()
    if name == "gemini":
        if not _has_gemini_key():
            return None
        from app.ai.gemini_provider import GeminiProvider
        return GeminiProvider()
    return None


def get_ai_provider() -> AIProvider:
    """
    Return a provider based strictly on AI_PROVIDER in .env.
    Only the declared provider is used — no silent fallback to other providers.
    """
    preferred = settings.ai_provider.strip().lower()
    provider = _make_provider(preferred)

    if provider is None:
        raise RuntimeError(
            f"AI_PROVIDER is set to '{preferred}' but its API key is missing. "
            f"Set the corresponding key in backend/.env:\n"
            f"  groq       → GROQ_API_KEY\n"
            f"  openai     → OPENAI_API_KEY\n"
            f"  claude     → ANTHROPIC_API_KEY\n"
            f"  openrouter → OPENROUTER_API_KEY\n"
            f"  gemini     → GEMINI_API_KEY"
        )

    logger.info("AI provider: %s (%s)", preferred, getattr(provider, 'provider_name', preferred))
    return provider
