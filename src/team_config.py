"""팀 공유 watchlist YAML 로드."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.place_url import parse_place_url
from src.settings import PROJECT_ROOT
from src.watchlist import MAX_ITEMS, WatchlistError, WatchlistItem

TEAM_WATCHLIST_PATH = PROJECT_ROOT / "config" / "team_watchlist.yaml"


@dataclass
class TeamWatchlistEntry:
    place_url: str
    keyword: str
    place_name: str = ""


@dataclass
class TeamWatchlistConfig:
    max_rank: int = 50
    items: list[TeamWatchlistEntry] = field(default_factory=list)


def stable_item_id(place_id: str, keyword: str) -> str:
    raw = f"{place_id}:{keyword}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def load_team_watchlist(path: Path | None = None) -> TeamWatchlistConfig:
    file_path = path or TEAM_WATCHLIST_PATH
    if not file_path.exists():
        return TeamWatchlistConfig()

    with file_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    max_rank = int(raw.get("max_rank", 50))
    entries: list[TeamWatchlistEntry] = []

    for i, item in enumerate(raw.get("items", [])):
        if not isinstance(item, dict):
            raise WatchlistError(f"team_watchlist items[{i}] must be a mapping")

        place_url = str(item.get("place_url", "")).strip()
        keyword = str(item.get("keyword", "")).strip()
        place_name = str(item.get("place_name", "")).strip()

        if not place_url:
            raise WatchlistError(f"team_watchlist items[{i}].place_url is required")
        if not keyword:
            raise WatchlistError(f"team_watchlist items[{i}].keyword is required")

        parse_place_url(place_url)
        entries.append(
            TeamWatchlistEntry(
                place_url=place_url,
                keyword=keyword,
                place_name=place_name,
            )
        )

    if len(entries) > MAX_ITEMS:
        raise WatchlistError(f"팀 watchlist는 최대 {MAX_ITEMS}개까지 가능합니다.")

    return TeamWatchlistConfig(max_rank=max_rank, items=entries)


def entries_to_watchlist_items(
    entries: list[TeamWatchlistEntry],
    existing: dict[str, WatchlistItem] | None = None,
) -> list[WatchlistItem]:
    existing = existing or {}
    items: list[WatchlistItem] = []

    for entry in entries:
        place_id = parse_place_url(entry.place_url)
        item_id = stable_item_id(place_id, entry.keyword)
        prev = existing.get(item_id)

        if prev:
            items.append(prev)
            continue

        items.append(
            WatchlistItem(
                id=item_id,
                place_id=place_id,
                place_url=entry.place_url,
                place_name=entry.place_name or f"place_{place_id}",
                keyword=entry.keyword,
                rank=None,
                prev_rank=None,
                found=False,
                changed=False,
                updated_at=None,
            )
        )

    return items
