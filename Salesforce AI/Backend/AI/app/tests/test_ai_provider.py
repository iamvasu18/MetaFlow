import pytest

from Backend.AI.app.providers.ai_provider import (
    AnthropicProvider,
)


def test_provider_requires_api_key(monkeypatch):

    monkeypatch.delenv(
        "ANTHROPIC_API_KEY",
        raising=False,
    )

    monkeypatch.setenv(
        "ANTHROPIC_MODEL",
        "test-model",
    )

    with pytest.raises(
        ValueError,
        match="ANTHROPIC_API_KEY",
    ):
        AnthropicProvider()


def test_provider_requires_model(monkeypatch):

    monkeypatch.setenv(
        "ANTHROPIC_API_KEY",
        "test-key",
    )

    monkeypatch.delenv(
        "ANTHROPIC_MODEL",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="ANTHROPIC_MODEL",
    ):
        AnthropicProvider()


def test_provider_accepts_configuration():

    provider = AnthropicProvider(
        api_key="test-key",
        model="test-model",
    )

    assert provider.api_key == "test-key"
    assert provider.model == "test-model"