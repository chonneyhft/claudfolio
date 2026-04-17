"""Smoke tests for the quantitative engine package."""


def test_quant_package_imports() -> None:
    from src.engines.quantitative import (  # noqa: F401
        features,
        model,
        price_fetcher,
        technicals,
    )
