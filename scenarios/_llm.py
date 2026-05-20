"""Shared OpenAI client for scenario narrative generation."""

from __future__ import annotations

import os
import streamlit as st
from openai import OpenAI


def _get_api_key() -> str | None:
    try:
        key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        key = None
    return key or os.getenv("OPENAI_API_KEY")


_api_key = _get_api_key()
client: OpenAI | None = OpenAI(api_key=_api_key) if _api_key else None

MODEL = "gpt-4o"


def llm_available() -> bool:
    return client is not None


def complete(system: str, user: str, temperature: float = 0.2) -> str:
    """Single chat completion. Returns the assistant text."""
    if client is None:
        return "[LLM unavailable — set OPENAI_API_KEY environment variable]"
    response = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content
