"""LLM provider layer.

Three interchangeable answer generators sit behind one interface:

- ``ollama``    — the default local model (no data leaves the machine).
- ``openai``    — any OpenAI-compatible chat-completions API (OpenAI, Groq,
                  OpenRouter, DeepSeek, Together, a local vLLM server, ...).
- ``anthropic`` — the Claude API through the official ``anthropic`` SDK.

The active provider comes from settings (``LLM_PROVIDER``) and can be
overridden per request. API keys are only ever read from the environment.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from api.generator import GeneratorError, clean_llm_output
from api.settings import Settings

SUPPORTED_PROVIDERS = ("ollama", "openai", "anthropic")


@dataclass
class GenerationResult:
    text: str
    provider: str
    model: str
    latency_ms: float


def resolve_provider(settings: Settings, override: str | None = None) -> str:
    provider = (override or settings.llm_provider or "ollama").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise GeneratorError(f"Unsupported LLM provider: {provider}")
    return provider


def default_model(settings: Settings, provider: str) -> str:
    if provider == "ollama":
        return settings.ollama_model
    if provider == "openai":
        return settings.openai_model
    return settings.anthropic_model


def _generate_ollama(system_prompt: str, user_prompt: str, settings: Settings, model: str) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
        },
    }
    try:
        response = httpx.post(url, json=payload, timeout=settings.ollama_timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GeneratorError(str(exc)) from exc
    message = data.get("message") or {}
    return str(message.get("content") or "")


def _generate_openai(system_prompt: str, user_prompt: str, settings: Settings, model: str) -> str:
    if not settings.openai_api_key:
        raise GeneratorError("OPENAI_API_KEY is not configured")
    if not model:
        raise GeneratorError("OPENAI_MODEL is not configured")
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": settings.llm_max_tokens,
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=settings.llm_timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GeneratorError(str(exc)) from exc
    try:
        return str(data["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as exc:
        raise GeneratorError(f"Unexpected response from OpenAI-compatible API: {exc}") from exc


def _generate_anthropic(system_prompt: str, user_prompt: str, settings: Settings, model: str) -> str:
    if not settings.anthropic_api_key:
        raise GeneratorError("ANTHROPIC_API_KEY is not configured")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise GeneratorError("The 'anthropic' package is not installed") from exc

    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
    )
    try:
        response = client.messages.create(
            model=model,
            max_tokens=settings.llm_max_tokens,
            thinking={"type": "adaptive"},
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as exc:
        raise GeneratorError(str(exc)) from exc

    if response.stop_reason == "refusal":
        raise GeneratorError("The Claude API declined this request (stop_reason=refusal)")
    return "".join(block.text for block in response.content if block.type == "text")


_GENERATORS = {
    "ollama": _generate_ollama,
    "openai": _generate_openai,
    "anthropic": _generate_anthropic,
}


def generate(
    system_prompt: str,
    user_prompt: str,
    settings: Settings,
    provider: str | None = None,
    model: str | None = None,
) -> GenerationResult:
    resolved_provider = resolve_provider(settings, provider)
    resolved_model = (model or "").strip() or default_model(settings, resolved_provider)
    started = time.perf_counter()
    raw = _GENERATORS[resolved_provider](system_prompt, user_prompt, settings, resolved_model)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    return GenerationResult(
        text=clean_llm_output(raw),
        provider=resolved_provider,
        model=resolved_model,
        latency_ms=latency_ms,
    )


def check_ollama_reachable(settings: Settings) -> bool:
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def provider_statuses(settings: Settings) -> list[dict[str, object]]:
    active = resolve_provider(settings)
    return [
        {
            "id": "ollama",
            "label": "Ollama (محلي)",
            "kind": "local",
            "model": settings.ollama_model,
            "configured": True,
            "available": check_ollama_reachable(settings),
            "active": active == "ollama",
        },
        {
            "id": "openai",
            "label": "OpenAI-compatible API",
            "kind": "api",
            "model": settings.openai_model or None,
            "configured": bool(settings.openai_api_key and settings.openai_model),
            "available": bool(settings.openai_api_key and settings.openai_model),
            "active": active == "openai",
        },
        {
            "id": "anthropic",
            "label": "Anthropic Claude API",
            "kind": "api",
            "model": settings.anthropic_model,
            "configured": bool(settings.anthropic_api_key),
            "available": bool(settings.anthropic_api_key),
            "active": active == "anthropic",
        },
    ]
