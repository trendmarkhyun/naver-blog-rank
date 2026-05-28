"""블로그 순위 조회 결과 단기 캐시."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.blog_lookup import BlogRankResult

TTL_SECONDS = 300


@dataclass
class _CacheEntry:
    result: BlogRankResult
    expires_at: float


_cache: dict[tuple[str, str, str, int], _CacheEntry] = {}


def _cache_key(keyword: str, post_url: str, mode: str, max_rank: int) -> tuple[str, str, str, int]:
    return (keyword.strip(), post_url.strip(), mode, max_rank)


def get_cached_blog_lookup(
    keyword: str, post_url: str, mode: str, max_rank: int
) -> BlogRankResult | None:
    key = _cache_key(keyword, post_url, mode, max_rank)
    entry = _cache.get(key)
    if entry is None:
        return None
    if entry.expires_at <= time.time():
        _cache.pop(key, None)
        return None
    return entry.result


def set_cached_blog_lookup(
    keyword: str, post_url: str, mode: str, max_rank: int, result: BlogRankResult
) -> None:
    if result.error:
        return
    key = _cache_key(keyword, post_url, mode, max_rank)
    _cache[key] = _CacheEntry(result=result, expires_at=time.time() + TTL_SECONDS)


def clear_blog_lookup_cache() -> None:
    _cache.clear()
