"""네이버 지도 키워드 검색 (공유 로직)."""

from __future__ import annotations

import logging
from urllib.parse import quote

from playwright.async_api import Frame, Page, Response

from src.matcher import SearchResultItem
from src.parser import (
    APOLLO_EXTRACT_SCRIPT,
    IFRAME_SEARCH,
    MAP_SEARCH_URL,
    PLACE_LINK_SELECTORS,
    infer_list_category,
    list_url_for_category,
    list_url_for_keyword,
    merge_place_tuples,
    parse_places_from_apollo_payload,
    parse_places_from_dom_links,
    parse_places_from_response_body,
    to_search_results,
)

logger = logging.getLogger(__name__)

RESPONSE_HINTS = ("search", "place", "hospital", "allSearch", "list", "graphql")
NAVIGATION_TIMEOUT_MS = 45_000
IFRAME_ATTACH_TIMEOUT_MS = 10_000
MAP_FALLBACK_WAIT_MS = 2_000
APOLLO_POLL_MS = 250
APOLLO_MAX_ATTEMPTS = 7


async def search_keyword_results(
    page: Page,
    keyword: str,
    max_rank: int,
    *,
    place_url: str | None = None,
) -> list[SearchResultItem]:
    captured_places: list[tuple[str, str]] = []

    async def on_response(response: Response) -> None:
        url = response.url.lower()
        if not any(hint in url for hint in RESPONSE_HINTS):
            return
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type and "text" not in content_type:
            return
        try:
            body = await response.text()
        except Exception:
            return
        places = parse_places_from_response_body(body)
        if places:
            captured_places.extend(places)

    page.on("response", on_response)

    display = max(max_rank, 20)
    primary_category = infer_list_category(keyword, place_url)
    categories = [primary_category]
    for category in ("hospital", "restaurant", "place"):
        if category not in categories:
            categories.append(category)

    all_places: list[tuple[str, str]] = []
    for category in categories:
        list_url = list_url_for_category(keyword, display, category)
        await page.goto(list_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        apollo_places = await _collect_places_from_apollo(page, min_count=min(5, max_rank))
        dom_places = await _collect_places_from_dom(page, max_rank)
        all_places = merge_place_tuples(all_places, apollo_places)
        all_places = merge_place_tuples(all_places, captured_places)
        all_places = merge_place_tuples(all_places, dom_places)
        if all_places:
            break

    if not all_places:
        map_url = MAP_SEARCH_URL.format(keyword=quote(keyword))
        await page.goto(map_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await page.wait_for_timeout(MAP_FALLBACK_WAIT_MS)
        iframe_places = await _collect_places_from_search_iframe(page)
        all_places = merge_place_tuples(all_places, iframe_places)

    page.remove_listener("response", on_response)

    results = to_search_results(all_places[:max_rank])
    if not results:
        raise RuntimeError("검색 결과를 파싱하지 못했습니다.")

    return results


async def _collect_places_from_apollo(page: Page, *, min_count: int = 1) -> list[tuple[str, str]]:
    best_places: list[tuple[str, str]] = []

    for attempt in range(APOLLO_MAX_ATTEMPTS):
        for frame in page.frames:
            try:
                payload = await frame.evaluate(APOLLO_EXTRACT_SCRIPT)
            except Exception:
                continue

            if not isinstance(payload, dict):
                continue

            places, _ = parse_places_from_apollo_payload(payload)
            if len(places) > len(best_places):
                best_places = places

        if len(best_places) >= min_count:
            break

        await page.wait_for_timeout(APOLLO_POLL_MS)

    if best_places:
        logger.debug("Parsed %s places from Apollo state", len(best_places))
    return best_places


async def _collect_places_from_search_iframe(page: Page) -> list[tuple[str, str]]:
    iframe_element = page.locator(IFRAME_SEARCH)
    try:
        await iframe_element.wait_for(state="attached", timeout=IFRAME_ATTACH_TIMEOUT_MS)
    except Exception:
        return []

    best_places: list[tuple[str, str]] = []
    for frame in page.frames:
        if "pcmap.place.naver.com" not in (frame.url or ""):
            continue
        try:
            payload = await frame.evaluate(APOLLO_EXTRACT_SCRIPT)
        except Exception:
            continue
        places, _ = parse_places_from_apollo_payload(payload)
        if len(places) > len(best_places):
            best_places = places

    return best_places


async def _collect_places_from_dom(page: Page, max_rank: int) -> list[tuple[str, str]]:
    places: list[tuple[str, str]] = []

    target_frame: Frame | None = None
    for frame in page.frames:
        if "pcmap.place.naver.com" in (frame.url or ""):
            target_frame = frame
            break

    if target_frame is None:
        target_frame = page.main_frame

    for selector in PLACE_LINK_SELECTORS:
        try:
            elements = target_frame.locator(selector)
            count = await elements.count()
            if count == 0:
                continue

            links: list[dict[str, str]] = []
            for i in range(min(count, max_rank)):
                item = elements.nth(i)
                href = await item.get_attribute("href") or ""
                text = (await item.inner_text()).strip()
                links.append({"href": href, "text": text})

            parsed = parse_places_from_dom_links(links)
            places = merge_place_tuples(places, parsed)
            if places:
                break
        except Exception as exc:
            logger.debug("Selector failed %s: %s", selector, exc)

    return places
