"""Smoke tests for the meta-synthesis layer package."""


def test_meta_package_imports() -> None:
    from src.meta import formatter, llm_client, payload_builder  # noqa: F401


def test_storage_package_imports() -> None:
    from src.storage import db, models  # noqa: F401


def test_pipeline_parser_builds() -> None:
    from src.pipeline import build_parser

    parser = build_parser()
    assert parser.prog == "sfe"
