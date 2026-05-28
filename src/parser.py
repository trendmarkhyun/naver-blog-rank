"""네이버 지도 검색 결과 파싱."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from src.matcher import SearchResultItem

APOLLO_EXTRACT_SCRIPT = """
() => {
  const state = window.__APOLLO_STATE__ || {};
  const root = state.ROOT_QUERY || {};
  const queryKeys = Object.keys(root).filter((key) => /list/i.test(key));
  if (!queryKeys.length) {
    return { error: 'placeList not found', places: [], total: 0 };
  }

  let bestPlaces = [];
  let bestTotal = 0;

  for (const queryKey of queryKeys) {
    const result = root[queryKey];
    const items = result?.businesses?.items || [];
    const places = [];

    for (const ref of items) {
      const item = state[ref.__ref];
      if (item?.id && item?.name) {
        places.push({ place_id: String(item.id), name: String(item.name) });
      }
    }

    if (places.length > bestPlaces.length) {
      bestPlaces = places;
      bestTotal = result?.businesses?.total ?? places.length;
    }
  }

  return {
    error: null,
    total: bestTotal,
    places: bestPlaces,
  };
}
"""
MAP_SEARCH_URL = "https://map.naver.com/p/search/{keyword}"
PLACE_LIST_URL = (
    "https://pcmap.place.naver.com/place/list"
    "?query={keyword}&display={display}&locale=ko"
)
RESTAURANT_LIST_URL = (
    "https://pcmap.place.naver.com/restaurant/list"
    "?query={keyword}&display={display}&locale=ko"
)
HOSPITAL_LIST_URL = (
    "https://pcmap.place.naver.com/hospital/list"
    "?query={keyword}&display={display}&locale=ko"
)
FOOD_KEYWORD_HINTS = ("맛집", "음식", "식당", "카페", "레스토랑", "술집", "밥집", "먹")
MEDICAL_KEYWORD_HINTS = ("한의원", "병원", "의원", "치과", "약국", "한방", "정형외과", "피부과")
CATEGORY_PATH_PATTERN = re.compile(
    r"/(?:restaurant|place|hospital|hairshop|nailshop)/(\d+)"
)
# DOM 셀렉터 (네이버 UI 변경 시 이 파일만 수정)
IFRAME_SEARCH = "iframe#searchIframe"
PLACE_LINK_SELECTORS = [
    "a[href*='/place/']",
    "a[href*='/hospital/']",
    "a[href*='/restaurant/']",
    "a[href*='/hairshop/']",
    "a[href*='/nailshop/']",
    "a[href*='entry/place']",
    "a.place_bluelink",
    "span.place_bluelink",
]
MORE_BUTTON_SELECTORS = [
    "button:has-text('더보기')",
    "a:has-text('더보기')",
    "span:has-text('더보기')",
]

PLACE_ID_PATTERNS = [
    CATEGORY_PATH_PATTERN,
    re.compile(r"/place/(?:entry/)?(\d+)"),
    re.compile(r"/search/[^/]+/place/(\d+)"),
    re.compile(r"placeId[=:](\d+)"),
    re.compile(r'"id"\s*:\s*"(\d+)"'),
]


def extract_place_id_from_text(text: str) -> str | None:
    for pattern in PLACE_ID_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _extract_name_from_node(node: dict[str, Any]) -> str | None:
    for key in ("name", "title", "placeName", "place_name", "bizName"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_place_id_from_node(node: dict[str, Any]) -> str | None:
    for key in ("id", "placeId", "place_id", "nid"):
        value = node.get(key)
        if value is not None:
            text = str(value).strip()
            if text.isdigit():
                return text
    return None


def _walk_json_for_places(node: Any, found: list[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        place_id = _extract_place_id_from_node(node)
        name = _extract_name_from_node(node)
        if place_id and name:
            found.append((place_id, name))

        for value in node.values():
            _walk_json_for_places(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_json_for_places(item, found)


def parse_places_from_json(payload: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    _walk_json_for_places(payload, found)

    unique: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for place_id, name in found:
        if place_id in seen_ids:
            continue
        seen_ids.add(place_id)
        unique.append((place_id, name))
    return unique


def parse_places_from_response_body(body: str) -> list[tuple[str, str]]:
    body = body.strip()
    if not body:
        return []

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return parse_places_from_json(body)

    return parse_places_from_json(payload)


def parse_places_from_apollo_payload(payload: dict[str, Any]) -> tuple[list[tuple[str, str]], int]:
    if payload.get("error"):
        return [], 0

    places: list[tuple[str, str]] = []
    for item in payload.get("places", []):
        place_id = str(item.get("place_id", "")).strip()
        name = str(item.get("name", "")).strip()
        if place_id and name:
            places.append((place_id, name))

    total = int(payload.get("total") or len(places))
    return places, total


def infer_list_category(keyword: str, place_url: str | None = None) -> str:
    url = (place_url or "").lower()
    if "/restaurant/" in url:
        return "restaurant"
    if "/hospital/" in url:
        return "hospital"
    if any(hint in keyword for hint in FOOD_KEYWORD_HINTS):
        return "restaurant"
    if any(hint in keyword for hint in MEDICAL_KEYWORD_HINTS):
        return "hospital"
    return "place"


def list_url_for_category(keyword: str, display: int, category: str) -> str:
    encoded = quote(keyword)
    if category == "restaurant":
        return RESTAURANT_LIST_URL.format(keyword=encoded, display=display)
    if category == "hospital":
        return HOSPITAL_LIST_URL.format(keyword=encoded, display=display)
    return PLACE_LIST_URL.format(keyword=encoded, display=display)


def list_url_for_keyword(
    keyword: str,
    display: int,
    *,
    place_url: str | None = None,
) -> str:
    category = infer_list_category(keyword, place_url)
    return list_url_for_category(keyword, display, category)


def merge_place_tuples(
    existing: list[tuple[str, str]],
    new_places: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    seen = {place_id for place_id, _ in existing}
    merged = list(existing)

    for place_id, name in new_places:
        if place_id in seen:
            continue
        seen.add(place_id)
        merged.append((place_id, name))

    return merged


def parse_places_from_dom_links(links: list[dict[str, str]]) -> list[tuple[str, str]]:
    places: list[tuple[str, str]] = []
    seen: set[str] = set()

    for link in links:
        href = link.get("href", "")
        text = link.get("text", "").strip()
        place_id = extract_place_id_from_text(href)
        if not place_id or place_id in seen:
            continue
        if not text:
            text = f"place_{place_id}"
        seen.add(place_id)
        places.append((place_id, text))

    return places


def to_search_results(places: list[tuple[str, str]]) -> list[SearchResultItem]:
    return [
        SearchResultItem(rank=i + 1, place_id=place_id, name=name)
        for i, (place_id, name) in enumerate(places)
    ]
