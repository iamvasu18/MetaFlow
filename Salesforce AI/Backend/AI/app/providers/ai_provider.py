import os
import logging

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

        try:
            self.max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))
        except ValueError as exc:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be an integer.") from exc
        if self.max_tokens < 256:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be at least 256.")

        try:
            self.max_input_tokens = int(os.getenv("ANTHROPIC_MAX_INPUT_TOKENS", "180000"))
        except ValueError as exc:
            raise ValueError("ANTHROPIC_MAX_INPUT_TOKENS must be an integer.") from exc
        if self.max_input_tokens <= 0:
            raise ValueError("ANTHROPIC_MAX_INPUT_TOKENS must be positive.")

        self.usage_events = []
        self.generation_attempts = 0
        self.client = anthropic.Anthropic(
            api_key=self.api_key
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        self.generation_attempts += 1
        messages = [{"role": "user", "content": user_prompt}]
        # Count the actual assembled request, not a characters/4 estimate.
        count = self.client.messages.count_tokens(
            model=self.model, system=system_prompt, messages=messages,
        ).input_tokens
        logging.getLogger(__name__).info(
            "AI input_tokens=%d configured_input_budget=%d output_limit=%d",
            count, self.max_input_tokens, self.max_tokens,
        )
        if count > self.max_input_tokens:
            raise ValueError(
                f"AI planning input is too large: {count} tokens exceeds the configured "
                f"input budget of {self.max_input_tokens}. No generation request was sent. "
                "Reduce the selected Salesforce context or split the implementation scope. "
                "Increasing ANTHROPIC_MAX_TOKENS does not reduce input size."
            )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        usage = getattr(response, "usage", None)
        self.usage_events.append({"model": getattr(response, "model", self.model), **{
            key: (getattr(usage, key, 0) or 0) for key in
            ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        }} if usage is not None else None)

        if getattr(response, "stop_reason", None) == "max_tokens":
            raise RuntimeError(
                "AI response reached its output limit. Increase ANTHROPIC_MAX_TOKENS "
                "within your selected model's supported limit and generate a fresh plan."
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