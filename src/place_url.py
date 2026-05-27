"""네이버 플레이스 URL 파싱."""

from __future__ import annotations

import re

from src.parser import extract_place_id_from_text

# pcmap.place.naver.com/restaurant/1234567890/home
PCMAP_PATH_PATTERN = re.compile(r"/(?:restaurant|place|hospital|hairshop|nailshop)/(\d+)")


class PlaceUrlError(ValueError):
    pass


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
