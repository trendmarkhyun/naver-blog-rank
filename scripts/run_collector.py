#!/usr/bin/env python3
"""순위 수집 CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector import run_collection
from src.config_loader import ConfigError, load_config
from src.settings import load_settings
from src.storage import Storage


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"collector_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="네이버 플레이스 순위 수집")
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "targets.yaml"),
        help="targets.yaml 경로",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    setup_logging(settings.log_dir)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logging.error("Config error: %s", exc)
        return 1

    storage = Storage(settings.db_path)
    storage.sync_businesses(config.businesses)

    logging.info("Starting collection for %s targets", len(config.targets))
    outcomes = asyncio.run(run_collection(settings, config, storage))

    success = sum(1 for o in outcomes if o.error is None)
    found = sum(1 for o in outcomes if o.match.found)
    logging.info(
        "Finished: total=%s success=%s found=%s",
        len(outcomes),
        success,
        found,
    )

    for outcome in outcomes:
        target = outcome.target
        if outcome.error:
            logging.error(
                "[%s] %s / %s -> ERROR: %s",
                target.business.id,
                target.business.name,
                target.keyword,
                outcome.error,
            )
        else:
            rank_text = str(outcome.match.rank) if outcome.match.found else "N/A"
            logging.info(
                "[%s] %s / %s -> rank=%s (results=%s)",
                target.business.id,
                target.business.name,
                target.keyword,
                rank_text,
                outcome.result_count,
            )

    return 0 if success == len(outcomes) else 2


if __name__ == "__main__":
    raise SystemExit(main())
