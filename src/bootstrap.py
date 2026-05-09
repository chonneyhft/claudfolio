"""Shared process bootstrap. Every entrypoint (CLI, MCP, API, TUI) calls
``load_env()`` before touching engines or storage so API keys and DB URLs
resolve consistently regardless of how the process was launched.
"""

from __future__ import annotations

from dotenv import load_dotenv

_loaded = False


def load_env() -> None:
    """Load .env into os.environ. Idempotent — safe to call from any entrypoint."""
    global _loaded
    if _loaded:
        return
    load_dotenv()
    _loaded = True
