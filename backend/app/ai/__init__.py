"""AI provider factory."""
from app.config import settings
from app.ai.ai_provider import AIProvider


def get_ai_provider() -> AIProvider:
    if settings.ai_provider.lower() == "claude":
        from app.ai.claude_provider import ClaudeProvider
        return ClaudeProvider()
    else:
        from app.ai.groq_provider import GroqProvider
        return GroqProvider()
