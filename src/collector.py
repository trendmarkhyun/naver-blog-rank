"""Playwright 기반 네이버 지도 순위 수집."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Page, async_playwright

from src.config_loader import AppConfig, CollectionTarget
from src.matcher import MatchResult, find_business_rank
from src.search import search_keyword_results
from src.settings import Settings
from src.storage import Storage

logger = logging.getLogger(__name__)


@dataclass
class CollectionOutcome:
    target: CollectionTarget
    match: MatchResult
    result_count: int
    error: str | None = None


class NaverPlaceCollector:
    def __init__(self, settings: Settings, config: AppConfig, storage: Storage) -> None:
        self.settings = settings
        self.config = config
        self.storage = storage
        self.settings.log_dir.mkdir(parents=True, exist_ok=True)

    async def collect_all(self) -> list[CollectionOutcome]:
        outcomes: list[CollectionOutcome] = []
        collected_at = Storage.now_kst_iso()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.settings.headless)
            try:
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

                for index, target in enumerate(self.config.targets):
                    if index > 0:
                        delay = random.uniform(
                            self.settings.delay_min,
                            self.settings.delay_max,
                        )
                        logger.info("Waiting %.1fs before next keyword", delay)
                        await asyncio.sleep(delay)

                    outcome = await self._collect_target_with_retry(
                        page=page,
                        target=target,
                        collected_at=collected_at,
                    )
                    outcomes.append(outcome)
            finally:
                await browser.close()

        return outcomes

    async def _collect_target_with_retry(
        self,
        page: Page,
        target: CollectionTarget,
        collected_at: str,
    ) -> CollectionOutcome:
        last_error: str | None = None

        for attempt in range(1, self.settings.max_retries + 2):
            try:
                outcome = await self._collect_single_target(page, target)
                self._persist_outcome(outcome, collected_at)
                return outcome
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Attempt %s failed for %s / %s: %s",
                    attempt,
                    target.business.id,
                    target.keyword,
                    exc,
                )
                await self._save_failure_screenshot(page, target, attempt)
                if attempt <= self.settings.max_retries:
                    await asyncio.sleep(2 * attempt)

        outcome = CollectionOutcome(
            target=target,
            match=MatchResult(found=False, rank=None),
            result_count=0,
            error=last_error,
        )
        self._persist_outcome(outcome, collected_at)
        return outcome

    async def _collect_single_target(
        self,
        page: Page,
        target: CollectionTarget,
    ) -> CollectionOutcome:
        keyword = target.keyword
        if self.config.region:
            keyword = f"{self.config.region} {keyword}"

        logger.info("Collecting rank: business=%s keyword=%s", target.business.id, keyword)

        max_rank = min(self.config.max_rank, self.settings.max_rank)
        results = await search_keyword_results(page, keyword, max_rank)
        match = find_business_rank(target.business, results)
        logger.info(
            "Result: business=%s keyword=%s found=%s rank=%s count=%s",
            target.business.id,
            target.keyword,
            match.found,
            match.rank,
            len(results),
        )

        return CollectionOutcome(
            target=target,
            match=match,
            result_count=len(results),
        )

    async def _save_failure_screenshot(
        self,
        page: Page,
        target: CollectionTarget,
        attempt: int,
    ) -> None:
        safe_keyword = re.sub(r"[^\w가-힣]+", "_", target.keyword)[:30]
        filename = (
            f"error_{target.business.id}_{safe_keyword}_{attempt}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        path = self.settings.log_dir / filename
        try:
            await page.screenshot(path=str(path), full_page=True)
            logger.info("Saved failure screenshot: %s", path)
        except Exception as exc:
            logger.debug("Could not save screenshot: %s", exc)

    def _persist_outcome(self, outcome: CollectionOutcome, collected_at: str) -> None:
        self.storage.save_ranking(
            collected_at=collected_at,
            business_id=outcome.target.business.id,
            keyword=outcome.target.keyword,
            rank=outcome.match.rank,
            found=outcome.match.found,
            result_count=outcome.result_count,
            error=outcome.error,
        )


async def run_collection(
    settings: Settings,
    config: AppConfig,
    storage: Storage,
) -> list[CollectionOutcome]:
    collector = NaverPlaceCollector(settings, config, storage)
    return await collector.collect_all()
