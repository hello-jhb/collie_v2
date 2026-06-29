"""Moose LLM abstraction.

GPT calls enter Moose through this interface, not through scattered OpenAI imports.
The API-key lookup mirrors the existing Collie pattern: Streamlit secrets first, then
the `OPENAI_API_KEY` environment variable.
"""

from __future__ import annotations

import json
import os
from jsonschema import ValidationError, validate
from typing import Any

from openai import OpenAI


MODEL_DEFAULT = "gpt-4o"
TIMEOUT_DEFAULT_SECONDS = 45.0


class LLMUnavailable(RuntimeError):
    """Raised when Moose cannot call the configured LLM."""


_client: OpenAI | None = None
_client_api_key: str | None = None


def _get_api_key() -> str | None:
    try:
        import streamlit as st

        key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        key = None
    return key or os.getenv("OPENAI_API_KEY")


def _get_client() -> OpenAI | None:
    global _client, _client_api_key

    api_key = _get_api_key()
    if not api_key:
        _client = None
        _client_api_key = None
        return None
    if _client is None or api_key != _client_api_key:
        _client = OpenAI(api_key=api_key)
        _client_api_key = api_key
    return _client


class LLMClient:
    """JSON completion interface for GPT-backed Moose agents."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.0,
        timeout_seconds: float | None = None,
    ) -> None:
        self.model = model or os.getenv("MOOSE_OPENAI_MODEL") or MODEL_DEFAULT
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("MOOSE_OPENAI_TIMEOUT_SECONDS", TIMEOUT_DEFAULT_SECONDS)
        )

    def complete_json(
        self,
        system_prompt: str | None = None,
        user_payload: dict[str, Any] | None = None,
        schema: dict[str, Any] | None = None,
        *,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Return JSON matching schema from an LLM completion."""
        client = _get_client()
        if client is None:
            raise LLMUnavailable("OPENAI_API_KEY is not set in environment or Streamlit secrets.")
        if schema is None:
            raise LLMUnavailable("LLMClient.complete_json requires a JSON schema.")

        system = system_prompt or (
            "You are a Moose real estate investment analysis agent. Return only valid JSON. "
            "Do not include markdown, prose, or commentary outside the JSON object."
        )
        payload = prompt if prompt is not None else json.dumps(user_payload or {}, indent=2, default=str)
        try:
            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                timeout=self.timeout_seconds,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": (
                            f"{payload}\n\nReturn JSON that follows this schema:\n"
                            f"{json.dumps(schema, indent=2)}"
                        ),
                    },
                ],
            )
        except Exception as exc:
            raise LLMUnavailable(f"OpenAI call failed: {type(exc).__name__}: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMUnavailable("OpenAI returned an empty response.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"OpenAI returned invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMUnavailable("OpenAI JSON response was not an object.")
        try:
            validate(instance=parsed, schema=schema)
        except ValidationError as exc:
            raise LLMUnavailable(f"OpenAI JSON response failed schema validation: {exc.message}") from exc
        return parsed
