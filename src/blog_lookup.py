"""블로그 키워드 순위 조회."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.blog_lookup_cache import get_cached_blog_lookup, set_cached_blog_lookup
from src.blog_models import (
    BLOG_MAX_RANK,
    SEARCH_MODE_UNIFIED,
    BlogKeyword,
    BlogPost,
    BlogProfile,
    effective_search_mode,
)
from src.blog_search import find_post_rank, search_blog_results, _delay_between_requests
from src.settings import load_settings
from src.storage import Storage


@dataclass
class BlogRankResult:
    keyword: str
    post_url: str
    post_id: str
    rank: int | None
    found: bool
    result_count: int
    max_rank: int
    search_mode: str
    collected_at: str
    error: str | None = None


@dataclass
class KeywordRankTarget:
    keyword_id: str
    keyword: str
    post_url: str
    post_id: str
    search_mode: str


async def _create_browser_context(playwright) -> tuple[Browser, BrowserContext, Page]:
    settings = load_settings()
    browser = await playwright.chromium.launch(headless=settings.headless)
    context = await browser.new_context(
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        viewport={"width": 1400, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    return browser, context, page


async def lookup_post_rank(
    keyword: str,
    post_url: str,
    *,
    mode: str = SEARCH_MODE_UNIFIED,
    max_rank: int = BLOG_MAX_RANK,
) -> BlogRankResult:
    keyword = (keyword or "").strip()
    collected_at = Storage.now_kst_iso()

    if not keyword:
        return BlogRankResult(
            keyword="",
            post_url=post_url,
            post_id="",
            rank=None,
            found=False,
            result_count=0,
            max_rank=max_rank,
            search_mode=mode,
            collected_at=collected_at,
            error="키워드를 입력해 주세요.",
        )

    cached = get_cached_blog_lookup(keyword, post_url, mode, max_rank)
    if cached is not None:
        return cached

    try:
        async with async_playwright() as playwright:
            browser, _, page = await _create_browser_context(playwright)
            try:
                results = await search_blog_results(
                    page, keyword, mode=mode, max_rank=max_rank
                )
                rank, found = find_post_rank(post_url, results, max_rank=max_rank)
            finally:
                await browser.close()

        post_id = post_url.rstrip("/").split("/")[-1]
        result = BlogRankResult(
            keyword=keyword,
            post_url=post_url,
            post_id=post_id,
            rank=rank,
            found=found,
            result_count=len(results),
            max_rank=max_rank,
            search_mode=mode,
            collected_at=collected_at,
        )
        set_cached_blog_lookup(keyword, post_url, mode, max_rank, result)
        return result
    except Exception as exc:
        return BlogRankResult(
            keyword=keyword,
            post_url=post_url,
            post_id="",
            rank=None,
            found=False,
            result_count=0,
            max_rank=max_rank,
            search_mode=mode,
            collected_at=collected_at,
            error=str(exc),
        )


def collect_keyword_targets(
    profiles: list[BlogProfile],
    global_mode: str,
) -> list[KeywordRankTarget]:
    targets: list[KeywordRankTarget] = []
    for profile in profiles:
        mode = effective_search_mode(profile, global_mode)
        for post in profile.posts:
            for kw in post.keywords:
                text = kw.keyword.strip()
                if not text or not kw.id:
                    continue
                targets.append(
                    KeywordRankTarget(
                        keyword_id=kw.id,
                        keyword=text,
                        post_url=post.post_url,
                        post_id=post.post_id,
                        search_mode=mode,
                    )
                )
    return targets


def group_keyword_targets(
    targets: list[KeywordRankTarget],
) -> list[tuple[tuple[str, str], list[KeywordRankTarget]]]:
    groups: dict[tuple[str, str], list[KeywordRankTarget]] = defaultdict(list)
    for target in targets:
        groups[(target.keyword, target.search_mode)].append(target)
    return list(groups.items())


async def refresh_single_keyword_group(
    keyword: str,
    mode: str,
    group_targets: list[KeywordRankTarget],
    *,
    max_rank: int = BLOG_MAX_RANK,
) -> dict[str, BlogRankResult]:
    """키워드 1개(SERP 1회)에 대한 순위 결과."""
    if not group_targets:
        return {}

    collected_at = Storage.now_kst_iso()
    results_by_keyword_id: dict[str, BlogRankResult] = {}

    async with async_playwright() as playwright:
        browser, _, page = await _create_browser_context(playwright)
        try:
            serp = await search_blog_results(page, keyword, mode=mode, max_rank=max_rank)
            for target in group_targets:
                rank, found = find_post_rank(target.post_url, serp, max_rank=max_rank)
                results_by_keyword_id[target.keyword_id] = BlogRankResult(
                    keyword=keyword,
                    post_url=target.post_url,
                    post_id=target.post_id,
                    rank=rank,
                    found=found,
                    result_count=len(serp),
                    max_rank=max_rank,
                    search_mode=mode,
                    collected_at=collected_at,
                )
        finally:
            await browser.close()

    return results_by_keyword_id


async def refresh_keyword_targets(
    targets: list[KeywordRankTarget],
    *,
    max_rank: int = BLOG_MAX_RANK,
    on_group_complete: Callable[[int, int, str, str], None] | None = None,
) -> dict[str, BlogRankResult]:
    if not targets:
        return {}

    groups = group_keyword_targets(targets)
    results_by_keyword_id: dict[str, BlogRankResult] = {}

    for index, ((keyword, mode), group_targets) in enumerate(groups):
        if index > 0:
            await _delay_between_requests()
        partial = await refresh_single_keyword_group(
            keyword, mode, group_targets, max_rank=max_rank
        )
        results_by_keyword_id.update(partial)
        if on_group_complete is not None:
            on_group_complete(index + 1, len(groups), keyword, mode)

    return results_by_keyword_id


async def refresh_profile_ranks(
    profile: BlogProfile,
    *,
    global_mode: str,
    max_rank: int = BLOG_MAX_RANK,
) -> dict[str, BlogRankResult]:
    mode = effective_search_mode(profile, global_mode)
    targets: list[KeywordRankTarget] = []
    for post in profile.posts:
        for kw in post.keywords:
            text = kw.keyword.strip()
            if not text or not kw.id:
                continue
            targets.append(
                KeywordRankTarget(
                    keyword_id=kw.id,
                    keyword=text,
                    post_url=post.post_url,
                    post_id=post.post_id,
                    search_mode=mode,
                )
            )
    return await refresh_keyword_targets(targets, max_rank=max_rank)


async def refresh_all_blogs(
    profiles: list[BlogProfile],
    *,
    global_mode: str,
    max_rank: int = BLOG_MAX_RANK,
) -> dict[str, BlogRankResult]:
    targets = collect_keyword_targets(profiles, global_mode)
    return await refresh_keyword_targets(targets, max_rank=max_rank)


def apply_rank_results_to_keywords(
    posts: list[BlogPost],
    results: dict[str, BlogRankResult],
) -> None:
    for post in posts:
        for kw in post.keywords:
            result = results.get(kw.id)
            if result is None:
                continue
            kw.rank = result.rank
            kw.found = result.found
            kw.updated_at = result.collected_at
