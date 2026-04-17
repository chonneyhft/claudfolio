"""Slack webhook delivery for the daily briefing."""

from __future__ import annotations


def post_to_slack(briefing: str, webhook_url: str) -> None:
    """POST `briefing` to a Slack incoming webhook."""
    raise NotImplementedError
