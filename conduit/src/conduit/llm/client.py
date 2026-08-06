"""Resolve and invoke chat LLMs without hardcoding a single vendor."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol


class LlmClient(Protocol):
    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        """Return a JSON object parsed from the model response."""


@dataclass
class _ChatCompletionsClient:
    """OpenAI SDK client (works with OpenAI, Ollama, vLLM, LM Studio, etc.)."""

    model: str
    api_key: str
    base_url: str | None = None
    use_json_mode: bool = False

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        from openai import OpenAI

        from conduit.llm.json_util import extract_json_object

        kwargs: dict[str, Any] = {"api_key": self.api_key or "local"}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        client = OpenAI(**kwargs)
        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if self.use_json_mode:
            create_kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**create_kwargs)
        content = resp.choices[0].message.content or "{}"
        return extract_json_object(content) or {}


@dataclass
class _AnthropicClient:
    model: str
    api_key: str

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        from anthropic import Anthropic

        from conduit.llm.json_util import extract_json_object

        client = Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system + "\nReply with a single JSON object only.",
            messages=[{"role": "user", "content": user}],
            temperature=0,
        )
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return extract_json_object("\n".join(parts)) or {}


def _normalize_provider(name: str) -> str:
    # Accept legacy alias
    if name in {"openai_compatible", "compatible"}:
        return "custom"
    return name


def resolve_provider() -> str | None:
    """Return provider name or None if no LLM is configured."""
    explicit = _normalize_provider(
        os.environ.get("CONDUIT_LLM_PROVIDER", "").strip().lower()
    )
    if explicit in {"openai", "anthropic", "ollama", "custom"}:
        return explicit
    if explicit in {"none", "off", "disabled"}:
        return None
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "openai"
    if os.environ.get("CONDUIT_LLM_BASE_URL", "").strip():
        return "custom"
    return None


def _api_key_for(provider: str) -> str:
    generic = os.environ.get("CONDUIT_LLM_API_KEY", "").strip()
    if generic:
        return generic
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if provider == "openai":
        return os.environ.get("OPENAI_API_KEY", "").strip()
    # ollama / custom: key optional
    return os.environ.get("OPENAI_API_KEY", "").strip()


def _default_model(provider: str) -> str:
    override = os.environ.get("CONDUIT_LLM_MODEL", "").strip()
    if override:
        return override
    if provider == "anthropic":
        return "claude-3-5-haiku-latest"
    if provider in {"ollama", "custom"}:
        return "llama3.2"
    return "gpt-4o-mini"


def get_llm_client() -> LlmClient | None:
    """Build a client from env, or None when LLM use should be skipped."""
    provider = resolve_provider()
    if not provider:
        return None

    model = _default_model(provider)
    api_key = _api_key_for(provider)
    base_url = os.environ.get("CONDUIT_LLM_BASE_URL", "").strip() or None

    if provider == "anthropic":
        if not api_key:
            return None
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return None
        return _AnthropicClient(model=model, api_key=api_key)

    try:
        import openai  # noqa: F401
    except ImportError:
        return None

    if provider == "ollama":
        return _ChatCompletionsClient(
            model=model,
            api_key=api_key or "ollama",
            base_url=base_url or "http://127.0.0.1:11434/v1",
            use_json_mode=False,
        )

    if provider == "custom":
        if not base_url:
            return None
        return _ChatCompletionsClient(
            model=model,
            api_key=api_key or "local",
            base_url=base_url,
            use_json_mode=False,
        )

    # openai cloud
    if not api_key:
        return None
    return _ChatCompletionsClient(
        model=model,
        api_key=api_key,
        base_url=base_url,
        use_json_mode=True,
    )
