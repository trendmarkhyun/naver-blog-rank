"""단건·배치 순위 조회 API."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.config_loader import Business
from src.matcher import find_business_rank
from src.place_url import PlaceUrlError, parse_place_url
from src.search import search_keyword_results
from src.settings import load_settings
from src.storage import Storage
from src.watchlist import WatchlistItem, apply_rank_refresh


@dataclass
class RankLookupResult:
    keyword: str
    place_id: str
    place_name: str | None
    rank: int | None
    found: bool
    result_count: int
    max_rank: int
    collected_at: str
    error: str | None = None


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


def _place_name_from_results(results, rank: int | None) -> str | None:
    if rank is None:
        return None
    for item in results:
        if item.rank == rank:
            return item.name
    return None


async def lookup_rank(
    keyword: str,
    place_url: str,
    *,
    max_rank: int | None = None,
) -> RankLookupResult:
    keyword = (keyword or "").strip()
    if not keyword:
        return RankLookupResult(
            keyword="",
            place_id="",
            place_name=None,
            rank=None,
            found=False,
            result_count=0,
            max_rank=max_rank or 50,
            collected_at=Storage.now_kst_iso(),
            error="키워드를 입력해 주세요.",
        )

    settings = load_settings()
    effective_max_rank = max_rank if max_rank is not None else settings.max_rank
    collected_at = Storage.now_kst_iso()

    try:
        place_id = parse_place_url(place_url)
    except PlaceUrlError as exc:
        return RankLookupResult(
            keyword=keyword,
            place_id="",
            place_name=None,
            rank=None,
            found=False,
            result_count=0,
            max_rank=effective_max_rank,
            collected_at=collected_at,
            error=str(exc),
        )

    business = Business(id="lookup", name="", place_id=place_id)

    try:
        async with async_playwright() as playwright:
            browser, _, page = await _create_browser_context(playwright)
            try:
                results = await search_keyword_results(page, keyword, effective_max_rank)
            finally:
                await browser.close()

        match = find_business_rank(business, results)
        place_name = _place_name_from_results(results, match.rank)

        return RankLookupResult(
            keyword=keyword,
            place_id=place_id,
            place_name=place_name,
            rank=match.rank,
            found=match.found,
            result_count=len(results),
            max_rank=effective_max_rank,
            collected_at=collected_at,
        )
    except Exception as exc:
        return RankLookupResult(
            keyword=keyword,
            place_id=place_id,
            place_name=None,
            rank=None,
            found=False,
            result_count=0,
            max_rank=effective_max_rank,
            collected_at=collected_at,
            error=str(exc),
        )


async def refresh_watchlist(
    items: list[WatchlistItem],
    max_rank: int,
) -> list[WatchlistItem]:
    if not items:
        return items

    updated_at = Storage.now_kst_iso()
    keyword_groups: dict[str, list[WatchlistItem]] = defaultdict(list)
    for item in items:
        keyword_groups[item.keyword].append(item)

    async with async_playwright() as playwright:
        browser, _, page = await _create_browser_context(playwright)
        try:
            for keyword, group_items in keyword_groups.items():
                results = await search_keyword_results(page, keyword, max_rank)
                for item in group_items:
                    business = Business(id=item.id, name=item.place_name, place_id=item.place_id)
                    match = find_business_rank(business, results)
                    place_name = _place_name_from_results(results, match.rank) or item.place_name
                    apply_rank_refresh(
                        item,
                        rank=match.rank,
                        found=match.found,
                        place_name=place_name,
                        updated_at=updated_at,
                    )
        finally:
            await browser.close()

    return items
