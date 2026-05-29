"""Probe Naver search extraction for blog rank debugging."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright

from src.blog_lookup import _create_browser_context
from src.blog_models import SEARCH_MODE_BLOG_TAB, SEARCH_MODE_UNIFIED
from src.blog_search import find_post_rank, search_blog_results

BLOG_ID = "58qjijwjwf"
KEYWORDS = ["엘지 알뜰폰", "엘지 알뜰폰 로밍", "엘지알뜰폰 로밍"]
# First post from screenshots - user should verify logNo
POST_URL = f"https://blog.naver.com/{BLOG_ID}/224297630157"


async def main() -> None:
    async with async_playwright() as pw:
        browser, _, page = await _create_browser_context(pw)
        try:
            for mode in (SEARCH_MODE_UNIFIED, SEARCH_MODE_BLOG_TAB):
                print(f"\n=== {mode} ===")
                for kw in KEYWORDS:
                    results = await search_blog_results(page, kw, mode=mode, max_rank=50)
                    rank, found = find_post_rank(POST_URL, results, max_rank=50)
                    hits = [
                        r
                        for r in results
                        if r.blog_id == BLOG_ID
                    ][:5]
                    print(
                        json.dumps(
                            {
                                "keyword": kw,
                                "result_count": len(results),
                                "found": found,
                                "rank": rank,
                                "blog_hits": [
                                    {"rank": h.rank, "title": h.title[:40], "post_id": h.post_id}
                                    for h in hits
                                ],
                            },
                            ensure_ascii=False,
                        )
                    )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
