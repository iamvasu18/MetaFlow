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

    from Backend.AI.app.account_api import current_account
    from Backend.AI.app.services.integration_service import ai_settings
    settings=ai_settings(current_account.get())
    provider_name = settings.get('provider') or os.getenv(
        "AI_PROVIDER",
        "mock",
    ).lower()

    if provider_name == "mock":
        return MockProvider()

    if provider_name == "anthropic":
        return AnthropicProvider(api_key=settings.get('api_key'),model=settings.get('model'))

    raise ValueError(
        f"Unsupported AI provider: {provider_name}"
    )