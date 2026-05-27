#!/usr/bin/env python3
"""팀 watchlist 순위 갱신 (GitHub Actions / 로컬 실행)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.lookup import refresh_watchlist
from src.storage import Storage
from src.team_config import entries_to_watchlist_items, load_team_watchlist
from src.team_rankings import load_team_rankings, save_team_rankings, snapshot_from_watchlist
from src.watchlist import WatchlistData


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="팀 공유 순위 JSON 갱신")
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "team_watchlist.yaml"),
        help="팀 watchlist YAML 경로",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data" / "team_rankings.json"),
        help="출력 JSON 경로",
    )
    parser.add_argument(
        "--by",
        default="github-actions",
        help="갱신 주체 표시 (github-actions, manual 등)",
    )
    return parser.parse_args()


async def run(config_path: Path, output_path: Path, refreshed_by: str) -> int:
    config = load_team_watchlist(config_path)
    if not config.items:
        print("팀 watchlist가 비어 있습니다. config/team_watchlist.yaml을 확인하세요.")
        return 1

    existing_snapshot = load_team_rankings(output_path)
    existing_map = {}
    if existing_snapshot:
        existing_map = {item.id: item for item in existing_snapshot.items}

    items = entries_to_watchlist_items(config.items, existing_map)
    data = WatchlistData(items=items, max_rank=config.max_rank)

    print(f"갱신 대상: {len(data.items)}개 (max_rank={data.max_rank})")
    await refresh_watchlist(data.items, data.max_rank)

    refreshed_at = Storage.now_kst_iso()
    snapshot = snapshot_from_watchlist(
        data,
        refreshed_at=refreshed_at,
        refreshed_by=refreshed_by,
    )
    save_team_rankings(snapshot, output_path)
    print(f"저장 완료: {output_path} ({refreshed_at})")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(
        run(
            Path(args.config),
            Path(args.output),
            args.by,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
