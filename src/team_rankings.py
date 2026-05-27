"""팀 공유 순위 스냅샷 (GitHub Actions → JSON)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from src.settings import PROJECT_ROOT
from src.watchlist import WatchlistData, WatchlistItem, _item_from_dict

TEAM_RANKINGS_PATH = PROJECT_ROOT / "data" / "team_rankings.json"
DEFAULT_TEAM_RANKINGS_URL = (
    "https://raw.githubusercontent.com/trendmarkhyun/place-rank/main/data/team_rankings.json"
)


@dataclass
class TeamRankingsSnapshot:
    refreshed_at: str | None
    refreshed_by: str
    max_rank: int
    items: list[WatchlistItem]
    source_url: str | None = None


def _parse_snapshot(raw: dict) -> TeamRankingsSnapshot:
    items = [_item_from_dict(item) for item in raw.get("items", [])]
    return TeamRankingsSnapshot(
        refreshed_at=raw.get("refreshed_at"),
        refreshed_by=str(raw.get("refreshed_by", "unknown")),
        max_rank=int(raw.get("max_rank", 50)),
        items=items,
        source_url=raw.get("source_url"),
    )


def load_team_rankings(path: Path | None = None) -> TeamRankingsSnapshot | None:
    file_path = path or TEAM_RANKINGS_PATH
    if not file_path.exists():
        return None

    with file_path.open(encoding="utf-8") as f:
        raw = json.load(f)

    return _parse_snapshot(raw)


def save_team_rankings(
    snapshot: TeamRankingsSnapshot,
    path: Path | None = None,
) -> None:
    file_path = path or TEAM_RANKINGS_PATH
    file_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "refreshed_at": snapshot.refreshed_at,
        "refreshed_by": snapshot.refreshed_by,
        "max_rank": snapshot.max_rank,
        "items": [
            {
                "id": item.id,
                "place_id": item.place_id,
                "place_url": item.place_url,
                "place_name": item.place_name,
                "keyword": item.keyword,
                "rank": item.rank,
                "prev_rank": item.prev_rank,
                "found": item.found,
                "changed": item.changed,
                "updated_at": item.updated_at,
            }
            for item in snapshot.items
        ],
    }
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def fetch_team_rankings_from_url(url: str) -> TeamRankingsSnapshot:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "naver-place-rank/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = json.loads(response.read().decode("utf-8"))

    snapshot = _parse_snapshot(raw)
    snapshot.source_url = url
    return snapshot


def get_team_rankings_remote_url() -> str | None:
    url = os.getenv("TEAM_RANKINGS_URL", "").strip()
    if url:
        return url

    try:
        import streamlit as st

        if hasattr(st, "secrets") and "TEAM_RANKINGS_URL" in st.secrets:
            return str(st.secrets["TEAM_RANKINGS_URL"]).strip()
    except Exception:
        pass

    return DEFAULT_TEAM_RANKINGS_URL


def load_team_rankings_for_ui() -> TeamRankingsSnapshot | None:
    remote_url = get_team_rankings_remote_url()
    if remote_url:
        try:
            return fetch_team_rankings_from_url(remote_url)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError):
            pass

    return load_team_rankings()


def snapshot_from_watchlist(
    data: WatchlistData,
    *,
    refreshed_at: str,
    refreshed_by: str,
) -> TeamRankingsSnapshot:
    return TeamRankingsSnapshot(
        refreshed_at=refreshed_at,
        refreshed_by=refreshed_by,
        max_rank=data.max_rank,
        items=list(data.items),
    )
