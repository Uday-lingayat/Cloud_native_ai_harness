from collections.abc import Iterable

from app.config import LLMSettings

from .base import LLM, Reply
from .mock import MockLLM
from .openai_compatible import OpenAICompatibleLLM


def get_llm(
    *, script: Iterable[Reply] = (), settings: LLMSettings | None = None
) -> LLM:
    settings = settings or LLMSettings.load()
    if settings.provider == "mock":
        return MockLLM(script)
    if settings.provider == "openai_compatible":
        return OpenAICompatibleLLM(settings)
    raise ValueError("Unsupported LLM_PROVIDER. Choose mock or openai_compatible.")
