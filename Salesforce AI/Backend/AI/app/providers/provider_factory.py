import os

from dotenv import load_dotenv

from Backend.AI.app.providers.base import AIProvider
from Backend.AI.app.providers.mock_provider import MockProvider
from Backend.AI.app.providers.ai_provider import AnthropicProvider


load_dotenv()


def get_ai_provider() -> AIProvider:
    """
    Return the configured AI provider.

    Supported providers:
        mock
        anthropic
    """

    provider_name = os.getenv(
        "AI_PROVIDER",
        "mock",
    ).lower()

    if provider_name == "mock":
        return MockProvider()

    if provider_name == "anthropic":
        return AnthropicProvider()

    raise ValueError(
        f"Unsupported AI provider: {provider_name}"
    )