#!/usr/bin/env python3
"""Supabase 전체 블로그 키워드 순위 갱신 (GitHub Actions용)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.blog_lookup import _create_browser_context, collect_keyword_targets
from src.blog_models import BLOG_MAX_RANK, SEARCH_MODE_UNIFIED
from src.blog_search import _delay_between_requests, find_post_rank, search_blog_results
from src.blog_store import BlogStore
from src.storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def refresh_all(refreshed_by: str) -> int:
    store = BlogStore()
    updated_at = Storage.now_kst_iso()

    members_resp = (
        store.client.table("members")
        .select("id, blog_search_mode, blog_max_rank")
        .execute()
    )
    keyword_groups: dict[tuple[str, str], list[tuple]] = defaultdict(list)

    for row in members_resp.data or []:
        member_id = str(row["id"])
        global_mode = str(row.get("blog_search_mode") or SEARCH_MODE_UNIFIED)
        member_max_rank = int(row.get("blog_max_rank") or BLOG_MAX_RANK)
        profiles = store.load_all_with_posts(member_id)
        if not profiles:
            continue

        for target in collect_keyword_targets(profiles, global_mode):
            keyword_groups[(target.keyword, target.search_mode)].append(
                (target, member_max_rank)
            )

    if not keyword_groups:
        logger.info("갱신할 블로그 키워드가 없습니다.")
        return 0

    from playwright.async_api import async_playwright

    updated_count = 0

    async with async_playwright() as playwright:
        browser, _, page = await _create_browser_context(playwright)
        try:
            for index, ((keyword, mode), entries) in enumerate(keyword_groups.items()):
                if index > 0:
                    await _delay_between_requests()

                max_rank = max(entry[1] for entry in entries)
                targets = [entry[0] for entry in entries]
                logger.info(
                    "키워드 '%s' (%s, %d개 항목, max_rank=%d)",
                    keyword,
                    mode,
                    len(targets),
                    max_rank,
                )

                serp = await search_blog_results(
                    page,
                    keyword,
                    mode=mode,
                    max_rank=max_rank,
                )

                for target in targets:
                    rank, found = find_post_rank(
                        target.post_url,
                        serp,
                        max_rank=max_rank,
                    )
                    store.apply_keyword_rank(
                        target.keyword_id,
                        rank=rank,
                        found=found,
                        updated_at=updated_at,
                    )
                    updated_count += 1
                    logger.info(
                        "  %s / %s → %s",
                        target.post_id,
                        keyword,
                        f"{rank}위" if found else "순위 없음",
                    )
        finally:
            await browser.close()

    logger.info("갱신 완료: %d개 (by %s)", updated_count, refreshed_by)
    return updated_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Supabase 블로그 키워드 순위 갱신")
    parser.add_argument(
        "--by",
        default="manual",
        help="갱신 주체 (github-actions, manual 등)",
    )
    args = parser.parse_args()

    try:
        count = asyncio.run(refresh_all(args.by))
        return 0 if count >= 0 else 1
    except Exception as exc:
        logger.exception("갱신 실패: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
