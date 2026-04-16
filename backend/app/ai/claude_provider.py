"""
Claude AI Provider — future integration stub.
Implements the same AIProvider interface as GroqProvider.
Swap in by setting AI_PROVIDER=claude in .env
"""
from typing import Any, Dict, List, Optional
from app.ai.ai_provider import (
    AIProvider, ExtractedDataResponse, MemberClassification,
    CoverLetterDraft, ChatResponse
)


class ClaudeProvider(AIProvider):

    def __init__(self):
        # Import only when actually used
        try:
            import anthropic
            from app.config import settings
            self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.model = "claude-opus-4-5"
        except ImportError:
            raise ImportError("anthropic package required for ClaudeProvider")

    @property
    def provider_name(self) -> str:
        return "claude"

    async def extract_from_document(self, file_bytes, file_type, filename, additional_context=None):
        raise NotImplementedError("ClaudeProvider.extract_from_document not yet implemented")

    async def extract_from_image(self, image_bytes, filename, additional_context=None):
        raise NotImplementedError("ClaudeProvider.extract_from_image not yet implemented")

    async def parse_boq(self, text, additional_context=None):
        raise NotImplementedError("ClaudeProvider.parse_boq not yet implemented")

    async def classify_member(self, description):
        raise NotImplementedError("ClaudeProvider.classify_member not yet implemented")

    async def parse_quotation(self, text):
        raise NotImplementedError("ClaudeProvider.parse_quotation not yet implemented")

    async def draft_cover_letter(self, quotation_data, template_clauses, company_info):
        raise NotImplementedError("ClaudeProvider.draft_cover_letter not yet implemented")

    async def chat(self, messages, context=None):
        raise NotImplementedError("ClaudeProvider.chat not yet implemented")
