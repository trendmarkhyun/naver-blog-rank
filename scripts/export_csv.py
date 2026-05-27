#!/usr/bin/env python3
"""순위 CSV 내보내기 CLI."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.export import export_rankings_to_csv
from src.settings import load_settings
from src.storage import Storage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="순위 히스토리 CSV 내보내기")
    parser.add_argument("--from", dest="date_from", help="시작일 YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="종료일 YYYY-MM-DD")
    parser.add_argument(
        "--output",
        help="출력 CSV 경로 (기본: exports/rankings_YYYYMMDD.csv)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    storage = Storage(settings.db_path)

    output = args.output
    if not output:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = str(PROJECT_ROOT / "exports" / f"rankings_{stamp}.csv")

    count = export_rankings_to_csv(
        storage=storage,
        output_path=output,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    print(f"Exported {count} rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
