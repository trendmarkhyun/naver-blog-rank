"""순위 조회 결과 단기 캐시."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.lookup import RankLookupResult

TTL_SECONDS = 300


@dataclass
class _CacheEntry:
    result: RankLookupResult
    expires_at: float


_cache: dict[tuple[str, str, int], _CacheEntry] = {}


def _cache_key(keyword: str, place_url: str, max_rank: int) -> tuple[str, str, int]:
    return (keyword.strip(), place_url.strip(), max_rank)


def get_cached_lookup(keyword: str, place_url: str, max_rank: int) -> RankLookupResult | None:
    key = _cache_key(keyword, place_url, max_rank)
    entry = _cache.get(key)
    if entry is None:
        return None
    if entry.expires_at <= time.time():
        _cache.pop(key, None)
        return None
    return entry.result


def clear_lookup_cache() -> None:
    _cache.clear()


def set_cached_lookup(keyword: str, place_url: str, max_rank: int, result: RankLookupResult) -> None:
    if result.error:
        return
    key = _cache_key(keyword, place_url, max_rank)
    _cache[key] = _CacheEntry(result=result, expires_at=time.time() + TTL_SECONDS)
