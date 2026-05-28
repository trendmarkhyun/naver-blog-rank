"""네이버 플레이스 URL 파싱."""

from __future__ import annotations

import re

from src.parser import extract_place_id_from_text

# pcmap.place.naver.com/restaurant/1234567890/home
PCMAP_PATH_PATTERN = re.compile(r"/(?:restaurant|place|hospital|hairshop|nailshop)/(\d+)")
FOOD_CATEGORY_HINTS = ("음식", "카페", "식당", "레스토랑", "술집", "베이커리", "디저트")
MEDICAL_CATEGORY_HINTS = ("한의원", "병원", "의원", "치과", "약국", "한방")


class PlaceUrlError(ValueError):
    pass


def infer_place_path(category: str = "", href: str = "") -> str:
    combined = f"{category} {href}".lower()
    if "/restaurant/" in combined or any(hint in category for hint in FOOD_CATEGORY_HINTS):
        return "restaurant"
    if "/hospital/" in combined or any(hint in category for hint in MEDICAL_CATEGORY_HINTS):
        return "hospital"
    if "/hairshop/" in combined:
        return "hairshop"
    if "/nailshop/" in combined:
        return "nailshop"
    return "place"


def build_place_url(place_id: str, *, category: str = "", href: str = "") -> str:
    path = infer_place_path(category, href)
    if href:
        match = PCMAP_PATH_PATTERN.search(href)
        if match and match.group(1) == str(place_id):
            if href.startswith("http"):
                return href.split("?")[0]
            return f"https://pcmap.place.naver.com{href.split('?')[0]}"
    return f"https://pcmap.place.naver.com/{path}/{place_id}/home"


def parse_place_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        raise PlaceUrlError("플레이스 URL을 입력해 주세요.")

    place_id = extract_place_id_from_text(text)
    if not place_id:
        match = PCMAP_PATH_PATTERN.search(text)
        if match:
            place_id = match.group(1)

    if not place_id or not place_id.isdigit():
        raise PlaceUrlError(
            "플레이스 ID를 URL에서 찾을 수 없습니다. "
            "예: https://map.naver.com/p/entry/place/1234567890"
        )

    return place_id
