from Backend.AI.app.services.observability import timed_ai_call
import os
import logging
from math import isfinite
from Backend.AI.app.services.observability import log_event

import anthropic
from dotenv import load_dotenv

from Backend.AI.app.providers.base import AIProvider
from Backend.AI.app.providers.errors import AIOutputLimitError


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
        timeout=float(os.getenv('AI_REQUEST_TIMEOUT_SECONDS','90'))
        if not isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError('AI_REQUEST_TIMEOUT_SECONDS must be between 0 and 300 seconds.')
        self.client = anthropic.Anthropic(api_key=self.api_key,timeout=timeout,max_retries=0)

    @timed_ai_call
    def generate(self, system_prompt, user_prompt):
        try:
            return self._generate(system_prompt,user_prompt)
        except anthropic.AuthenticationError:
            raise RuntimeError('AI provider rejected the API key. Review Settings → AI provider.') from None
        except anthropic.RateLimitError:
            raise RuntimeError('AI provider rate limit or quota reached. Check billing/quota before retrying.') from None
        except anthropic.APIConnectionError:
            raise RuntimeError('AI provider request timed out or failed. Check connectivity and retry explicitly.') from None
        except anthropic.APIStatusError:
            raise RuntimeError('AI provider request failed. Check model access and provider availability.') from None

    def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        self.generation_attempts += 1
        messages = [{"role": "user", "content": user_prompt}]
        # Count the actual assembled request, not a characters/4 estimate.
        count = self.client.messages.count_tokens(
            model=self.model, system=system_prompt + "\nReturn the exact requested JSON only. Do not wrap JSON in Markdown code fences.", messages=messages,
        ).input_tokens
        log_event(logging.getLogger(__name__), 'ai_input_counted', operation='generate', phase='token_count', input_tokens=count)
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
            system=system_prompt + "\nReturn the exact requested JSON only. Do not wrap JSON in Markdown code fences.",
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
            log_event(
                logging.getLogger(__name__), "ai_output_limit_reached",
                operation="generate", phase="output",
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                output_budget=self.max_tokens,
            )
            raise AIOutputLimitError(
                "AI response reached its output limit (output-token limit) before completing valid JSON. "
                "Generation must be retried with a smaller, complete plan or decomposed "
                "into validated stages; no partial response was accepted."
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