"""Base sub-agent: encapsulates an Anthropic tool-use loop for domain-specific investigation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from loguru import logger


@dataclass
class SubAgentResult:
    answer: str
    trace: list[dict[str, Any]]
    token_usage: dict[str, int]


class BaseSubAgent:
    """Generic sub-agent that runs a tool-use loop with domain-specific tools.

    Subclasses define tool_schemas and tool_handlers for their domain.
    """

    def __init__(
        self,
        system_prompt_path: str | Path,
        tool_schemas: list[dict[str, Any]],
        tool_handlers: dict[str, Callable[..., Any]],
        *,
        max_turns: int = 8,
        model: str = "claude-sonnet-4-6",
    ):
        self._system_prompt = Path(system_prompt_path).read_text()
        self._tool_schemas = tool_schemas
        self._tool_handlers = tool_handlers
        self._max_turns = max_turns
        self._model = model

    def run(self, user_message: str) -> SubAgentResult:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("anthropic SDK not installed") from exc

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_message},
        ]
        trace: list[dict[str, Any]] = []
        token_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

        for turn in range(self._max_turns):
            try:
                response = client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=[
                        {
                            "type": "text",
                            "text": self._system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=self._tool_schemas,
                    messages=messages,
                )
            except Exception as exc:
                logger.error(f"sub-agent API call failed on turn {turn}: {exc}")
                return SubAgentResult(
                    answer=f"Sub-agent error: {exc}",
                    trace=trace,
                    token_usage=token_usage,
                )

            token_usage["input_tokens"] += response.usage.input_tokens
            token_usage["output_tokens"] += response.usage.output_tokens

            if response.stop_reason == "end_turn":
                text_parts = [
                    block.text
                    for block in response.content
                    if getattr(block, "type", None) == "text"
                ]
                answer = "\n".join(text_parts) if text_parts else ""
                trace.append({"turn": turn, "type": "final_message", "content": answer})
                return SubAgentResult(answer=answer, trace=trace, token_usage=token_usage)

            tool_calls = [
                block for block in response.content
                if getattr(block, "type", None) == "tool_use"
            ]

            if not tool_calls:
                text_parts = [
                    block.text
                    for block in response.content
                    if getattr(block, "type", None) == "text"
                ]
                answer = "\n".join(text_parts) if text_parts else ""
                trace.append({"turn": turn, "type": "message", "content": answer})
                return SubAgentResult(answer=answer, trace=trace, token_usage=token_usage)

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tc in tool_calls:
                handler = self._tool_handlers.get(tc.name)
                if handler is None:
                    result_str = json.dumps({"error": f"Unknown tool: {tc.name}"})
                else:
                    try:
                        result = handler(tc.input)
                        result_str = json.dumps(result, default=str)
                    except Exception as exc:
                        logger.warning(f"sub-agent tool {tc.name} failed: {exc}")
                        result_str = json.dumps({"error": str(exc)})

                trace.append({
                    "turn": turn,
                    "type": "tool_call",
                    "tool": tc.name,
                    "input": tc.input,
                    "result": json.loads(result_str),
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})

        logger.warning(f"sub-agent hit max turns ({self._max_turns})")
        return SubAgentResult(
            answer="Investigation reached maximum turns without completing.",
            trace=trace,
            token_usage=token_usage,
        )
