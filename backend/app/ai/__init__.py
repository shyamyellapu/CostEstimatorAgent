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
        total = len(self._providers)

        for idx, provider in enumerate(self._providers, start=1):
            role = "PRIMARY" if idx == 1 else f"FALLBACK-{idx - 1}"
            print(
                f"[AI] Using {role} model: {provider.provider_name} "
                f"({idx}/{total}) | operation: {method_name}"
            )
            try:
                result = await getattr(provider, method_name)(*args, **kwargs)
                if method_name == "parse_quotation" and isinstance(result, dict) and result.get("error"):
                    raise RuntimeError(f"parse_quotation returned error payload: {result.get('error')}")
                if idx > 1:
                    print(f"[AI] {role} model ({provider.provider_name}) succeeded for '{method_name}'")
                return result
            except Exception as err:
                err_msg = f"{provider.provider_name}: {type(err).__name__}: {err}"
                errors.append(err_msg)
                logger.warning("%s failed for %s: %s", provider.provider_name, method_name, err)
                if idx < total:
                    next_provider = self._providers[idx].provider_name
                    print(
                        f"[AI] {role} ({provider.provider_name}) failed for '{method_name}' "
                        f"— switching to {next_provider}"
                    )

        joined = " | ".join(errors)
        raise RuntimeError(f"All AI providers failed for '{method_name}'. Details: {joined}")

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


def _has_openai_key() -> bool:
    return bool((settings.openai_api_key or "").strip())


def _has_claude_key() -> bool:
    return bool((settings.anthropic_api_key or "").strip())


def _has_groq_key() -> bool:
    return bool((settings.groq_api_key or "").strip())


def _build_provider_chain(preferred: str) -> List[AIProvider]:
    chain_order = {
        "openai": ["openai", "claude", "groq"],
        "claude": ["claude", "openai", "groq"],
        "groq": ["groq", "openai", "claude"],
    }.get(preferred, ["openai", "claude", "groq"])

    providers: List[AIProvider] = []
    configured_names: List[str] = []

    for name in chain_order:
        if name == "openai":
            if not _has_openai_key():
                logger.info("Skipping openai in provider chain: OPENAI_API_KEY is not set")
                continue
            from app.ai.openai_provider import OpenAIProvider
            providers.append(OpenAIProvider())
            configured_names.append(f"openai({settings.openai_model})")
        elif name == "claude":
            if not _has_claude_key():
                logger.info("Skipping claude in provider chain: ANTHROPIC_API_KEY is not set")
                continue
            from app.ai.claude_provider import ClaudeProvider
            providers.append(ClaudeProvider())
            configured_names.append(f"claude({settings.claude_model})")
        elif name == "groq":
            if not _has_groq_key():
                logger.info("Skipping groq in provider chain: GROQ_API_KEY is not set")
                continue
            from app.ai.groq_provider import GroqProvider
            providers.append(GroqProvider())
            configured_names.append(f"groq({settings.groq_model_large})")

    if not providers:
        raise RuntimeError(
            "No AI provider is configured with a valid API key. "
            "Set at least one of OPENAI_API_KEY, ANTHROPIC_API_KEY, or GROQ_API_KEY in backend/.env"
        )

    print(f"[AI] Provider chain configured: {' -> '.join(configured_names)}")
    return providers


def get_ai_provider() -> AIProvider:
    provider = settings.ai_provider.lower()
    providers = _build_provider_chain(provider)
    if len(providers) == 1:
        return providers[0]
    return FallbackProvider(providers=providers)
