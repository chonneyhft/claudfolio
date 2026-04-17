"""Email delivery via smtplib for the daily briefing."""

from __future__ import annotations


def send_email(briefing: str, recipient: str) -> None:
    """Send `briefing` to `recipient` over SMTP."""
    raise NotImplementedError
