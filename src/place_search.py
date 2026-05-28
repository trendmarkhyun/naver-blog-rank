"""업체명으로 네이버 플레이스 후보 검색."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from playwright.async_api import Page, async_playwright

from src.parser import (
    IFRAME_SEARCH,
    MAP_SEARCH_URL,
    PLACE_LINK_SELECTORS,
    PLACE_LIST_URL,
    extract_place_id_from_text,
)
from src.place_url import build_place_url
from src.settings import load_settings

PLACE_NAME_SEARCH_SCRIPT = """
() => {
  const state = window.__APOLLO_STATE__ || {};
  const root = state.ROOT_QUERY || {};
  const queryKeys = Object.keys(root).filter((key) => /list|search|query/i.test(key));
  const candidates = [];
  const seen = new Set();

  const pickField = (item, keys) => {
    for (const key of keys) {
      const value = item[key];
      if (typeof value === 'string' && value.trim()) {
        return value.trim();
      }
    }
    return '';
  };

  const addItem = (item, href = '') => {
    if (!item || typeof item !== 'object') return;
    const id = item.id != null ? String(item.id) : '';
    const name = item.name != null ? String(item.name).trim() : '';
    if (!id || !name || seen.has(id)) return;
    seen.add(id);
    candidates.push({
      place_id: id,
      name,
      address: pickField(item, [
        'roadAddress', 'address', 'commonAddress', 'shortAddress',
        'newAddress', 'abbrAddress', 'formattedAddress',
      ]),
      category: pickField(item, [
        'categoryName', 'category', 'businessCategory', 'bizCategory',
        'industryCategory', 'categoryCodeName',
      ]),
      href: typeof href === 'string' ? href : '',
    });
  };

  for (const queryKey of queryKeys) {
    const result = root[queryKey];
    const groups = [
      result?.businesses?.items,
      result?.items,
      result?.places?.items,
    ];
    for (const items of groups) {
      if (!Array.isArray(items)) continue;
      for (const ref of items) {
        const item = ref?.__ref ? state[ref.__ref] : ref;
        addItem(item);
      }
    }
  }

  if (!candidates.length) {
    for (const key of Object.keys(state)) {
      const node = state[key];
      if (!node || typeof node !== 'object') continue;
      if (node.id && node.name) {
        addItem(node);
      }
    }
  }

  return { candidates };
}
"""

WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class PlaceCandidate:
    place_id: str
    name: str
    address: str
    category: str
    place_url: str

    @property
    def summary(self) -> str:
        parts = [part for part in (self.address, self.category) if part]
        return " · ".join(parts) if parts else "주소 정보 없음"


def normalize_place_name(text: str) -> str:
    return WHITESPACE_RE.sub(" ", (text or "").strip().lower())


def candidate_from_raw(raw: dict) -> PlaceCandidate | None:
    place_id = str(raw.get("place_id", "")).strip()
    name = str(raw.get("name", "")).strip()
    if not place_id.isdigit() or not name:
        return None

    href = str(raw.get("href", "")).strip()
    category = str(raw.get("category", "")).strip()
    address = str(raw.get("address", "")).strip()
    return PlaceCandidate(
        place_id=place_id,
        name=name,
        address=address,
        category=category,
        place_url=build_place_url(place_id, category=category, href=href),
    )


def parse_place_candidates(payload: dict) -> list[PlaceCandidate]:
    candidates: list[PlaceCandidate] = []
    seen: set[str] = set()
    for raw in payload.get("candidates", []):
        if not isinstance(raw, dict):
            continue
        candidate = candidate_from_raw(raw)
        if candidate is None or candidate.place_id in seen:
            continue
        seen.add(candidate.place_id)
        candidates.append(candidate)
    return candidates


def is_exact_name_match(query: str, candidate: PlaceCandidate) -> bool:
    return normalize_place_name(query) == normalize_place_name(candidate.name)


def score_candidate(query: str, candidate: PlaceCandidate) -> int:
    return 100 if is_exact_name_match(query, candidate) else 0


def filter_candidates(
    query: str,
    candidates: list[PlaceCandidate],
    *,
    limit: int = 20,
) -> list[PlaceCandidate]:
    if not candidates:
        return []

    exact_matches = [candidate for candidate in candidates if is_exact_name_match(query, candidate)]
    return exact_matches[:limit]


def pick_auto_candidate(
    query: str,
    candidates: list[PlaceCandidate],
) -> PlaceCandidate | None:
    filtered = filter_candidates(query, candidates)
    if len(filtered) == 1:
        return filtered[0]
    return None


async def _collect_candidates_from_apollo(page: Page) -> list[PlaceCandidate]:
    best: list[PlaceCandidate] = []
    for _ in range(10):
        for frame in page.frames:
            try:
                payload = await frame.evaluate(PLACE_NAME_SEARCH_SCRIPT)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            places = parse_place_candidates(payload)
            if len(places) > len(best):
                best = places
        if best:
            break
        await page.wait_for_timeout(500)
    return best


async def _collect_candidates_from_dom(page: Page, *, limit: int) -> list[PlaceCandidate]:
    candidates: list[PlaceCandidate] = []
    seen: set[str] = set()

    for frame in page.frames:
        for selector in PLACE_LINK_SELECTORS:
            try:
                elements = frame.locator(selector)
                count = await elements.count()
                if count == 0:
                    continue

                for index in range(min(count, limit)):
                    item = elements.nth(index)
                    href = await item.get_attribute("href") or ""
                    place_id = extract_place_id_from_text(href)
                    if not place_id or place_id in seen:
                        continue
                    name = (await item.inner_text()).strip()
                    if not name:
                        name = f"place_{place_id}"
                    seen.add(place_id)
                    candidates.append(
                        PlaceCandidate(
                            place_id=place_id,
                            name=name,
                            address="",
                            category="",
                            place_url=build_place_url(place_id, href=href),
                        )
                    )
            except Exception:
                continue
    return candidates


async def _collect_candidates_from_search_iframe(page: Page) -> list[PlaceCandidate]:
    iframe_element = page.locator(IFRAME_SEARCH)
    try:
        await iframe_element.wait_for(state="attached", timeout=15000)
    except Exception:
        return []

    best: list[PlaceCandidate] = []
    for frame in page.frames:
        if "pcmap.place.naver.com" not in (frame.url or ""):
            continue
        try:
            payload = await frame.evaluate(PLACE_NAME_SEARCH_SCRIPT)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        places = parse_place_candidates(payload)
        if len(places) > len(best):
            best = places
    return best


def _merge_candidates(*groups: list[PlaceCandidate]) -> list[PlaceCandidate]:
    merged: list[PlaceCandidate] = []
    index: dict[str, PlaceCandidate] = {}

    for group in groups:
        for candidate in group:
            existing = index.get(candidate.place_id)
            if existing is None:
                index[candidate.place_id] = candidate
                continue
            index[candidate.place_id] = PlaceCandidate(
                place_id=candidate.place_id,
                name=candidate.name or existing.name,
                address=candidate.address or existing.address,
                category=candidate.category or existing.category,
                place_url=candidate.place_url or existing.place_url,
            )

    for candidate in index.values():
        merged.append(candidate)
    return merged


async def search_places_by_name(query: str, *, limit: int = 30) -> list[PlaceCandidate]:
    query = (query or "").strip()
    if not query:
        return []

    settings = load_settings()
    display = max(limit, 20)
    list_url = PLACE_LIST_URL.format(keyword=quote(query), display=display)

    async with async_playwright() as playwright:
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
        try:
            await page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
            apollo_candidates = await _collect_candidates_from_apollo(page)
            dom_candidates = await _collect_candidates_from_dom(page, limit=display)
            candidates = _merge_candidates(apollo_candidates, dom_candidates)

            if not candidates:
                map_url = MAP_SEARCH_URL.format(keyword=quote(query))
                await page.goto(map_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3500)
                iframe_candidates = await _collect_candidates_from_search_iframe(page)
                dom_candidates = await _collect_candidates_from_dom(page, limit=display)
                candidates = _merge_candidates(candidates, iframe_candidates, dom_candidates)
        finally:
            await browser.close()

    return filter_candidates(query, candidates, limit=limit)
