from Backend.AI.app.providers.mock_provider import MockProvider
from Backend.AI.app.providers.provider_factory import get_ai_provider


def test_factory_returns_mock_provider(monkeypatch):

    monkeypatch.setenv(
        "AI_PROVIDER",
        "mock",
    )

    provider = get_ai_provider()

    assert isinstance(
        provider,
        MockProvider,
    )


def test_factory_rejects_unknown_provider(monkeypatch):

    monkeypatch.setenv(
        "AI_PROVIDER",
        "unknown",
    )

    try:
        get_ai_provider()
        assert False, "Expected ValueError"

    except ValueError as exc:

        assert "Unsupported AI provider" in str(exc)