"""Assemble per-ticker engine outputs into the meta-layer JSON payload."""

from __future__ import annotations

from datetime import date


def build_payload(on_date: date) -> dict:
    """Return the structured payload described in the planning doc."""
    raise NotImplementedError
