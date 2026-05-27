#!/usr/bin/env python3
"""네이버 지도 검색 결과 프로브 (파서 검증용)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright

from src.parser import (
    APOLLO_EXTRACT_SCRIPT,
    PLACE_LIST_URL,
    parse_places_from_apollo_payload,
    to_search_results,
)

KEYWORDS = ["강남역 맛집", "홍대 카페"]


async def probe_keyword(page, keyword: str) -> dict:
    url = PLACE_LIST_URL.format(keyword=quote(keyword), display=20)
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3500)

    payload = None
    for frame in page.frames:
        try:
            payload = await frame.evaluate(APOLLO_EXTRACT_SCRIPT)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("places"):
            break

    places, total = parse_places_from_apollo_payload(payload or {})
    results = to_search_results(places[:10])

    return {
        "keyword": keyword,
        "url": url,
        "total": total,
        "result_count": len(results),
        "top5": [
            {"rank": r.rank, "place_id": r.place_id, "name": r.name}
            for r in results[:5]
        ],
        "error": (payload or {}).get("error"),
    }


async def main() -> None:
    output: dict = {"keywords": []}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(locale="ko-KR", timezone_id="Asia/Seoul")
        for keyword in KEYWORDS:
            output["keywords"].append(await probe_keyword(page, keyword))
            await page.wait_for_timeout(2000)
        await browser.close()

    out_path = PROJECT_ROOT / "PROBE_RESULT.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
