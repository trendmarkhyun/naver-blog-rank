"""Streamlit Cloud 등에서 Playwright Chromium 준비."""

from __future__ import annotations

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)
_ready = False


def ensure_playwright_browser() -> None:
    global _ready
    if _ready or os.getenv("PLAYWRIGHT_SKIP_BOOTSTRAP", "").lower() in {"1", "true", "yes"}:
        return

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        _ready = True
        return
    except Exception as exc:
        logger.info("Playwright browser missing, installing chromium: %s", exc)

    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Playwright Chromium 설치에 실패했습니다. "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    _ready = True
