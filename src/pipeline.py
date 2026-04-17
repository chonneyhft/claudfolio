"""SFE CLI entry point. Dispatches to engines, meta-layer, and delivery."""

from __future__ import annotations

import argparse
import sys

from loguru import logger


def run_sentiment(args: argparse.Namespace) -> int:
    logger.info("sentiment engine: not yet implemented")
    return 0


def run_quant(args: argparse.Namespace) -> int:
    logger.info("quantitative engine: not yet implemented")
    return 0


def run_enrichment(args: argparse.Namespace) -> int:
    logger.info("enrichment signals: not yet implemented")
    return 0


def run_meta(args: argparse.Namespace) -> int:
    logger.info("meta-synthesis layer: not yet implemented")
    return 0


def run_all(args: argparse.Namespace) -> int:
    logger.info("full pipeline: not yet implemented")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sfe", description="Signal Fusion Engine CLI")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("run-sentiment", help="Run the sentiment engine").set_defaults(func=run_sentiment)
    subs.add_parser("run-quant", help="Run the quantitative engine").set_defaults(func=run_quant)
    subs.add_parser("run-enrichment", help="Run enrichment signals").set_defaults(func=run_enrichment)
    subs.add_parser("run-meta", help="Run the meta-synthesis layer").set_defaults(func=run_meta)
    subs.add_parser("run-all", help="Run the full pipeline end to end").set_defaults(func=run_all)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
