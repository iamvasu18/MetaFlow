import os

import anthropic
from dotenv import load_dotenv

from Backend.AI.app.providers.base import AIProvider


load_dotenv()


class AnthropicProvider(AIProvider):
    """
    Anthropic Claude implementation of the AIProvider interface.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = (
            api_key
            or os.getenv("ANTHROPIC_API_KEY")
        )

        self.model = (
            model
            or os.getenv("ANTHROPIC_MODEL")
        )

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not configured."
            )

        if not self.model:
            raise ValueError(
                "ANTHROPIC_MODEL is not configured."
            )

        self.client = anthropic.Anthropic(
            api_key=self.api_key
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        if not response.content:
            raise ValueError(
                "Claude returned an empty response."
            )

        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]

        result = "\n".join(text_blocks).strip()

        if not result:
            raise ValueError(
                "Claude returned an empty text response."
            )

        return result