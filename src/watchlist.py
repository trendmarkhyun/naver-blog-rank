"""등록 업체 watchlist (JSON 영속)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.place_url import PlaceUrlError, parse_place_url
from src.settings import PROJECT_ROOT

WATCHLIST_PATH = PROJECT_ROOT / "data" / "watchlist.json"
MAX_ITEMS = 20


class WatchlistError(Exception):
    pass


@dataclass
class WatchlistItem:
    id: str
    place_id: str
    place_url: str
    place_name: str
    keyword: str
    rank: int | None = None
    prev_rank: int | None = None
    found: bool = False
    changed: bool = False
    updated_at: str | None = None


@dataclass
class WatchlistData:
    items: list[WatchlistItem] = field(default_factory=list)
    max_rank: int = 50


def _item_from_dict(data: dict) -> WatchlistItem:
    return WatchlistItem(
        id=str(data["id"]),
        place_id=str(data["place_id"]),
        place_url=str(data["place_url"]),
        place_name=str(data.get("place_name", "")),
        keyword=str(data["keyword"]),
        rank=data.get("rank"),
        prev_rank=data.get("prev_rank"),
        found=bool(data.get("found", False)),
        changed=bool(data.get("changed", False)),
        updated_at=data.get("updated_at"),
    )


def load_watchlist(path: Path | None = None) -> WatchlistData:
    file_path = path or WATCHLIST_PATH
    if not file_path.exists():
        return WatchlistData()

    with file_path.open(encoding="utf-8") as f:
        raw = json.load(f)

    items = [_item_from_dict(item) for item in raw.get("items", [])]
    return WatchlistData(items=items, max_rank=int(raw.get("max_rank", 50)))


def save_watchlist(data: WatchlistData, path: Path | None = None) -> None:
    file_path = path or WATCHLIST_PATH
    file_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "items": [asdict(item) for item in data.items],
        "max_rank": data.max_rank,
    }
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _find_duplicate(data: WatchlistData, place_id: str, keyword: str) -> WatchlistItem | None:
    for item in data.items:
        if item.place_id == place_id and item.keyword == keyword:
            return item
    return None


def add_item(
    data: WatchlistData,
    *,
    place_url: str,
    keyword: str,
    place_name: str,
    place_id: str,
    rank: int | None,
    found: bool,
    updated_at: str,
) -> WatchlistData:
    keyword = keyword.strip()
    place_url = place_url.strip()

    if not keyword:
        raise WatchlistError("키워드를 입력해 주세요.")

    try:
        parsed_id = parse_place_url(place_url)
    except PlaceUrlError as exc:
        raise WatchlistError(str(exc)) from exc

    if parsed_id != place_id:
        place_id = parsed_id

    if _find_duplicate(data, place_id, keyword):
        raise WatchlistError("이미 등록된 업체·키워드 조합입니다.")

    if len(data.items) >= MAX_ITEMS:
        raise WatchlistError(f"최대 {MAX_ITEMS}개까지 등록할 수 있습니다.")

    item = WatchlistItem(
        id=str(uuid.uuid4()),
        place_id=place_id,
        place_url=place_url,
        place_name=place_name or f"place_{place_id}",
        keyword=keyword,
        rank=rank,
        prev_rank=None,
        found=found,
        changed=False,
        updated_at=updated_at,
    )
    data.items.append(item)
    return data


def remove_item(data: WatchlistData, item_id: str) -> WatchlistData:
    data.items = [item for item in data.items if item.id != item_id]
    return data


def rank_changed(prev_rank: int | None, new_rank: int | None, prev_found: bool, new_found: bool) -> bool:
    return prev_rank != new_rank or prev_found != new_found


def apply_rank_refresh(
    item: WatchlistItem,
    *,
    rank: int | None,
    found: bool,
    place_name: str | None,
    updated_at: str,
) -> None:
    item.prev_rank = item.rank
    prev_found = item.found
    item.rank = rank
    item.found = found
    item.changed = rank_changed(item.prev_rank, rank, prev_found, found)
    if place_name:
        item.place_name = place_name
    item.updated_at = updated_at
