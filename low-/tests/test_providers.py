import pytest

from api import providers
from api.generator import GeneratorError
from api.providers import default_model, generate, provider_statuses, resolve_provider
from api.settings import Settings


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_resolve_provider_defaults_to_ollama():
    assert resolve_provider(make_settings()) == "ollama"


def test_resolve_provider_override_wins():
    settings = make_settings(llm_provider="ollama")
    assert resolve_provider(settings, "anthropic") == "anthropic"


def test_resolve_provider_rejects_unknown():
    with pytest.raises(GeneratorError):
        resolve_provider(make_settings(), "banana")


def test_default_models_per_provider():
    settings = make_settings(ollama_model="qwen3:4b", anthropic_model="claude-opus-4-8", openai_model="gpt-x")
    assert default_model(settings, "ollama") == "qwen3:4b"
    assert default_model(settings, "openai") == "gpt-x"
    assert default_model(settings, "anthropic") == "claude-opus-4-8"


def test_openai_requires_api_key():
    settings = make_settings(llm_provider="openai", openai_model="gpt-x", openai_api_key="")
    with pytest.raises(GeneratorError, match="OPENAI_API_KEY"):
        generate("system", "user", settings)


def test_anthropic_requires_api_key():
    settings = make_settings(llm_provider="anthropic", anthropic_api_key="")
    with pytest.raises(GeneratorError, match="ANTHROPIC_API_KEY"):
        generate("system", "user", settings)


def test_generate_uses_override_and_cleans_output(monkeypatch):
    settings = make_settings(llm_provider="ollama")
    captured = {}

    def fake_openai(system_prompt, user_prompt, settings, model):
        captured["model"] = model
        return "<think>secret</think>الإجابة النهائية"

    monkeypatch.setitem(providers._GENERATORS, "openai", fake_openai)
    result = generate("system", "user", settings, provider="openai", model="custom-model")

    assert captured["model"] == "custom-model"
    assert result.provider == "openai"
    assert result.model == "custom-model"
    assert result.text == "الإجابة النهائية"
    assert result.latency_ms >= 0


def test_provider_statuses_reports_configuration(monkeypatch):
    monkeypatch.setattr("api.providers.check_ollama_reachable", lambda settings: False)
    settings = make_settings(anthropic_api_key="sk-test", openai_api_key="", openai_model="")

    statuses = {item["id"]: item for item in provider_statuses(settings)}

    assert statuses["ollama"]["active"] is True
    assert statuses["ollama"]["available"] is False
    assert statuses["anthropic"]["configured"] is True
    assert statuses["openai"]["configured"] is False
