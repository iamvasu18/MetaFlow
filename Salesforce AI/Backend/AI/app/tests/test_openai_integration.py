from dotenv import load_dotenv

from Backend.AI.app.providers.ai_provider import (
    AnthropicProvider,
)


load_dotenv()


def test_anthropic_connection():

    provider = AnthropicProvider()

    response = provider.generate(
        system_prompt=(
            "You are a test assistant. "
            "Respond with exactly: "
            "ANTHROPIC_CONNECTION_SUCCESS"
        ),
        user_prompt="Test the connection.",
    )

    assert (
        response.strip()
        == "ANTHROPIC_CONNECTION_SUCCESS"
    )