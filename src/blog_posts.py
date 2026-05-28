"""네이버 블로그 게시글 목록 수집."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from urllib.parse import unquote_plus

from playwright.async_api import Page, async_playwright

from src.blog_models import MAX_POSTS
from src.blog_url import build_blog_post_url
from src.settings import load_settings

logger = logging.getLogger(__name__)

POST_LIST_URL = "https://blog.naver.com/PostList.naver?blogId={blog_id}&from=postList"
POST_TITLE_LIST_API = (
    "https://blog.naver.com/PostTitleListAsync.naver"
    "?blogId={blog_id}&viewdate=&currentPage={page}&categoryNo=0"
    "&parentCategoryNo=0&countPerPage={count_per_page}"
)
API_PAGE_SIZE = 30
VIEW_COUNT_PATTERN = re.compile(r"([\d,]+)")
COMMENT_COUNT_PATTERN = re.compile(r"(\d+)")
UNAVAILABLE_MARKERS = ("비공개", "비로그인", "로그인", "비공개", "-", "조회불가")
GENERIC_TITLE_MARKERS = ("동영상", "사진", "이미지", "포스트")


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
  const skipTitle = new Set(['동영상', '사진', '이미지']);

  const addPost = (postId, title, dateText) => {{
    const cleanTitle = (title || '').replace(/\\s+/g, ' ').trim();
    if (!postId || seen.has(postId)) return;
    if (!cleanTitle || skipTitle.has(cleanTitle)) return;
    seen.add(postId);
    rows.push({{
      postId: String(postId),
      title: cleanTitle,
      dateText: (dateText || '').trim(),
    }});
  }};

  const parseRow = (row) => {{
    const titleLink = row.querySelector(
      '.title a, td.title a, a.link_title, span.ell2 a, .list_title a, a[href*="logNo="]'
    );
    if (!titleLink) return;
    const href = titleLink.getAttribute('href') || '';
    const logMatch = href.match(/logNo=(\\d+)/);
    const pathMatch = href.match(/blog\\.naver\\.com\\/[^/?#]+\\/(\\d+)/);
    const postId = logMatch ? logMatch[1] : (pathMatch ? pathMatch[1] : '');
    if (!postId) return;
    const title = titleLink.textContent || row.querySelector('.title, .tit, span.ell2')?.textContent || '';
    const dateText = row.querySelector('.date, .se_publishDate, time, td.date')?.textContent || '';
    addPost(postId, title, dateText);
  }};

  document.querySelectorAll('table.blog2_list tbody tr, .post-list li, .list_post li').forEach(parseRow);
  return rows.slice(0, {MAX_POSTS});
}}
"""

FETCH_POSTS_API_SCRIPT = """
async ({ blogId, pageNum, countPerPage }) => {
  const url =
    `https://blog.naver.com/PostTitleListAsync.naver?blogId=${encodeURIComponent(blogId)}` +
    `&viewdate=&currentPage=${pageNum}&categoryNo=0&parentCategoryNo=0&countPerPage=${countPerPage}`;
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) {
    return { resultCode: 'F', postList: [] };
  }
  return await res.json();
}
"""


def decode_post_title(raw_title: str) -> str:
    title = unquote_plus((raw_title or "").strip())
    return re.sub(r"\s+", " ", title).strip()


def is_generic_title(title: str) -> bool:
    normalized = (title or "").strip()
    if not normalized:
        return True
    if normalized in GENERIC_TITLE_MARKERS:
        return True
    return normalized.startswith("동영상")


def posts_from_api_payload(blog_id: str, payload: dict) -> list[FetchedBlogPost]:
    if payload.get("resultCode") not in (None, "S"):
        return []

    posts: list[FetchedBlogPost] = []
    for item in payload.get("postList") or []:
        post_id = str(item.get("logNo") or "").strip()
        if not post_id:
            continue
        title = decode_post_title(str(item.get("title") or ""))
        if is_generic_title(title):
            continue
        posts.append(
            FetchedBlogPost(
                post_id=post_id,
                post_url=build_blog_post_url(blog_id, post_id),
                title=title or f"post_{post_id}",
                published_at=str(item.get("addDate") or "").strip() or None,
            )
        )
    return posts


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


async def _fetch_posts_via_api(page: Page, blog_id: str) -> list[FetchedBlogPost]:
    posts: list[FetchedBlogPost] = []
    seen: set[str] = set()
    page_num = 1

    while len(posts) < MAX_POSTS:
        payload = await page.evaluate(
            FETCH_POSTS_API_SCRIPT,
            {"blogId": blog_id, "pageNum": page_num, "countPerPage": API_PAGE_SIZE},
        )
        batch = posts_from_api_payload(blog_id, payload or {})
        if not batch:
            break

        added = 0
        for post in batch:
            if post.post_id in seen:
                continue
            seen.add(post.post_id)
            posts.append(post)
            added += 1
            if len(posts) >= MAX_POSTS:
                break

        if added == 0 or len(batch) < API_PAGE_SIZE:
            break
        page_num += 1

    return posts[:MAX_POSTS]


async def _extract_posts_from_dom(page: Page, blog_id: str) -> list[FetchedBlogPost]:
    posts: list[FetchedBlogPost] = []

    for frame in page.frames:
        try:
            raw_rows = await frame.evaluate(EXTRACT_POSTS_SCRIPT)
        except Exception:
            continue
        for row in raw_rows or []:
            post_id = str(row.get("postId") or "")
            title = str(row.get("title") or "").strip()
            if not post_id or is_generic_title(title):
                continue
            posts.append(
                FetchedBlogPost(
                    post_id=post_id,
                    post_url=build_blog_post_url(
                        _blog_id_from_frame_url(frame.url) or blog_id,
                        post_id,
                    ),
                    title=title or f"post_{post_id}",
                    published_at=str(row.get("dateText") or "") or None,
                )
            )
        if posts:
            break

    if not posts:
        raw_rows = await page.evaluate(EXTRACT_POSTS_SCRIPT)
        for row in raw_rows or []:
            post_id = str(row.get("postId") or "")
            title = str(row.get("title") or "").strip()
            if not post_id or is_generic_title(title):
                continue
            posts.append(
                FetchedBlogPost(
                    post_id=post_id,
                    post_url=build_blog_post_url(blog_id, post_id),
                    title=title or f"post_{post_id}",
                    published_at=str(row.get("dateText") or "") or None,
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
    home_url = f"https://blog.naver.com/{blog_id}"

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
            await page.goto(home_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(1.0)

            posts = await _fetch_posts_via_api(page, blog_id)
            if not posts:
                await page.goto(
                    POST_LIST_URL.format(blog_id=blog_id),
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                await asyncio.sleep(1.0)
                posts = await _fetch_posts_via_api(page, blog_id)

            if not posts:
                posts = await _extract_posts_from_dom(page, blog_id)

            if not posts:
                return FetchPostsResult(posts=[], error="게시글을 불러오지 못했습니다.")

            return FetchPostsResult(posts=posts[:MAX_POSTS])
        except Exception as exc:
            logger.exception("fetch_blog_posts failed for %s", blog_id)
            return FetchPostsResult(posts=[], error=str(exc))
        finally:
            await browser.close()
