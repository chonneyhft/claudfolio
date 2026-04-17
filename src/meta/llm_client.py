"""Anthropic Claude client wrapper for the meta-synthesis call.

Install the `llm` dependency group (`uv sync --group llm`) before wiring this up.
"""

from __future__ import annotations


def generate_briefing(payload: dict, system_prompt: str) -> str:
    """Send the structured payload through Claude and return the briefing text."""
    raise NotImplementedError
