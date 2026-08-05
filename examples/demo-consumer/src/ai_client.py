"""Demo consumer still using a deprecated OpenAI model id."""

from __future__ import annotations

from typing import Any

DEFAULT_MODEL = "gpt-4-0613"


def build_client() -> Any:
    from openai import OpenAI

    return OpenAI()


def complete(prompt: str, model: str = DEFAULT_MODEL) -> str:
    client = build_client()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=64,
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print(f"Using model {DEFAULT_MODEL}")
