"""네이버 블로그 게시글 목록 수집."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from playwright.async_api import Page, async_playwright

from src.blog_models import MAX_POSTS
from src.blog_url import build_blog_post_url
from src.settings import load_settings

logger = logging.getLogger(__name__)

POST_LIST_URL = "https://blog.naver.com/PostList.naver?blogId={blog_id}&from=postList"
VIEW_COUNT_PATTERN = re.compile(r"([\d,]+)")
COMMENT_COUNT_PATTERN = re.compile(r"(\d+)")
UNAVAILABLE_MARKERS = ("비공개", "비로그인", "로그인", "비공개", "-", "조회불가")


@dataclass
class FetchedBlogPost:
    post_id: str
    post_url: str
    title: str
    published_at: str | None = None
    views: int | None = None
    comments: int | None = None


@dataclass
class FetchPostsResult:
    posts: list[FetchedBlogPost]
    error: str | None = None


EXTRACT_POSTS_SCRIPT = f"""
() => {{
  const rows = [];
  const seen = new Set();

  const addPost = (postId, title, dateText, viewsText, commentsText) => {{
    if (!postId || seen.has(postId)) return;
    seen.add(postId);
    rows.push({{
      postId: String(postId),
      title: (title || '').trim(),
      dateText: (dateText || '').trim(),
      viewsText: (viewsText || '').trim(),
      commentsText: (commentsText || '').trim(),
    }});
  }};

  const parseRow = (row) => {{
    const link = row.querySelector('a[href*="logNo="], a[href*="blog.naver.com/"]');
    if (!link) return;
    const href = link.getAttribute('href') || '';
    let postId = '';
    const logMatch = href.match(/logNo=(\\d+)/);
    if (logMatch) postId = logMatch[1];
    const pathMatch = href.match(/blog\\.naver\\.com\\/[^/?#]+\\/(\\d+)/);
    if (!postId && pathMatch) postId = pathMatch[1];
    if (!postId) return;

    const title = link.textContent || row.querySelector('.title, .tit')?.textContent || '';
    const dateText = row.querySelector('.date, .se_publishDate, time')?.textContent || '';
    const viewsText = row.querySelector('.hit, .view, .count')?.textContent || '';
    const commentsText = row.querySelector('.comment, .reply, .num')?.textContent || '';
    addPost(postId, title, dateText, viewsText, commentsText);
  }};

  document.querySelectorAll('table.blog2_list tbody tr, .post-list li, .list_post li').forEach(parseRow);
  document.querySelectorAll('a[href*="logNo="]').forEach((link) => {{
    const href = link.getAttribute('href') || '';
    const logMatch = href.match(/logNo=(\\d+)/);
    if (!logMatch) return;
    const row = link.closest('tr, li, div');
    const dateText = row?.querySelector('.date, time')?.textContent || '';
    const viewsText = row?.querySelector('.hit, .view')?.textContent || '';
    const commentsText = row?.querySelector('.comment, .reply')?.textContent || '';
    addPost(logMatch[1], link.textContent, dateText, viewsText, commentsText);
  }});

  return rows.slice(0, {MAX_POSTS});
}}
"""


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    lowered = text.strip().lower()
    if any(marker in lowered for marker in UNAVAILABLE_MARKERS):
        return None
    match = VIEW_COUNT_PATTERN.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_comments(text: str | None) -> int | None:
    if not text:
        return None
    lowered = text.strip().lower()
    if any(marker in lowered for marker in UNAVAILABLE_MARKERS):
        return None
    match = COMMENT_COUNT_PATTERN.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def format_stat(value: int | None) -> str:
    """UI 표시용 — 수집 실패 시 '-'."""
    if value is None:
        return "-"
    return f"{value:,}"


async def _extract_posts_from_page(page: Page) -> list[FetchedBlogPost]:
    posts: list[FetchedBlogPost] = []

    for frame in page.frames:
        try:
            raw_rows = await frame.evaluate(EXTRACT_POSTS_SCRIPT)
        except Exception:
            continue
        for row in raw_rows or []:
            post_id = str(row.get("postId") or "")
            if not post_id:
                continue
            posts.append(
                FetchedBlogPost(
                    post_id=post_id,
                    post_url=build_blog_post_url(
                        _blog_id_from_frame_url(frame.url) or _blog_id_from_page(page.url),
                        post_id,
                    ),
                    title=str(row.get("title") or f"post_{post_id}"),
                    published_at=str(row.get("dateText") or "") or None,
                    views=_parse_int(str(row.get("viewsText") or "")),
                    comments=_parse_comments(str(row.get("commentsText") or "")),
                )
            )
        if posts:
            break

    if not posts:
        raw_rows = await page.evaluate(EXTRACT_POSTS_SCRIPT)
        blog_id = _blog_id_from_page(page.url)
        for row in raw_rows or []:
            post_id = str(row.get("postId") or "")
            if not post_id:
                continue
            posts.append(
                FetchedBlogPost(
                    post_id=post_id,
                    post_url=build_blog_post_url(blog_id, post_id),
                    title=str(row.get("title") or f"post_{post_id}"),
                    published_at=str(row.get("dateText") or "") or None,
                    views=_parse_int(str(row.get("viewsText") or "")),
                    comments=_parse_comments(str(row.get("commentsText") or "")),
                )
            )

    deduped: dict[str, FetchedBlogPost] = {}
    for post in posts:
        deduped[post.post_id] = post
    return list(deduped.values())[:MAX_POSTS]


def _blog_id_from_page(url: str) -> str:
    match = re.search(r"blogId=([^&]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"blog\.naver\.com/([^/?#]+)", url)
    if match:
        return match.group(1)
    return "unknown"


def _blog_id_from_frame_url(url: str) -> str | None:
    blog_id = _blog_id_from_page(url)
    return None if blog_id == "unknown" else blog_id


async def fetch_blog_posts(blog_id: str) -> FetchPostsResult:
    settings = load_settings()
    url = POST_LIST_URL.format(blog_id=blog_id)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=settings.headless)
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
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(1.5)

            posts = await _extract_posts_from_page(page)
            if not posts:
                await page.goto(
                    f"https://blog.naver.com/{blog_id}",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                await asyncio.sleep(1.5)
                posts = await _extract_posts_from_page(page)

            if not posts:
                return FetchPostsResult(posts=[], error="게시글을 불러오지 못했습니다.")

            for post in posts:
                if "unknown" in post.post_url:
                    post.post_url = build_blog_post_url(blog_id, post.post_id)

            return FetchPostsResult(posts=posts)
        except Exception as exc:
            logger.exception("fetch_blog_posts failed for %s", blog_id)
            return FetchPostsResult(posts=[], error=str(exc))
        finally:
            await browser.close()
