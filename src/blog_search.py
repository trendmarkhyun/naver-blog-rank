"""네이버 블로그 검색 결과 크롤링."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from urllib.parse import quote_plus

from playwright.async_api import Page

from src.blog_models import SEARCH_MODE_BLOG_TAB, SEARCH_MODE_UNIFIED
from src.blog_url import parse_blog_url, post_urls_match
from src.settings import load_settings

logger = logging.getLogger(__name__)

AD_MARKERS = (
    "ad",
    "powerblog",
    "파워블로그",
    "광고",
    "sponsored",
    "sp_nreview",
    "ad_section",
)


@dataclass
class BlogSearchResultItem:
    rank: int
    url: str
    title: str
    blog_id: str
    post_id: str | None
    is_ad: bool = False


EXTRACT_BLOG_RESULTS_SCRIPT = """
(mode) => {
  const adMarkers = ['ad', 'powerblog', '파워블로그', '광고', 'sponsored', 'sp_nreview'];
  const rows = [];
  const seen = new Set();

  const isAdNode = (node) => {
    if (!node) return false;
    const text = (node.textContent || '').toLowerCase();
    const cls = (node.className || '').toLowerCase();
    const html = (node.innerHTML || '').toLowerCase();
    return adMarkers.some((m) => text.includes(m) || cls.includes(m) || html.includes(m));
  };

  const extractIds = (href) => {
    let blogId = '';
    let postId = '';
    const logMatch = href.match(/logNo=(\\d+)/i);
    if (logMatch) postId = logMatch[1];
    const blogMatch = href.match(/blogId=([^&]+)/i);
    if (blogMatch) blogId = decodeURIComponent(blogMatch[1]);
    const pathMatch = href.match(/blog\\.naver\\.com\\/([^/?#]+)\\/(\\d+)/);
    if (pathMatch) {
      blogId = blogId || pathMatch[1];
      postId = postId || pathMatch[2];
    }
    const homeMatch = href.match(/blog\\.naver\\.com\\/([^/?#]+)/);
    if (homeMatch && !blogId) blogId = homeMatch[1];
    return { blogId, postId };
  };

  const selectors = mode === 'blog_tab'
    ? ['.view_wrap', '.detail_box', '.total_wrap .bx', '.lst_total li', '.api_subject_bx']
    : ['.api_subject_bx', '.sp_blog .api_subject_bx', '.view_wrap', '.total_wrap .bx'];

  for (const selector of selectors) {
    document.querySelectorAll(selector).forEach((node) => {
      const link = node.querySelector('a[href*="blog.naver.com"], a[href*="blogId="]');
      if (!link) return;
      const href = link.href || link.getAttribute('href') || '';
      if (!href.includes('blog.naver.com') && !href.includes('blogId=')) return;
      const ids = extractIds(href);
      if (!ids.blogId) return;
      const key = `${ids.blogId}:${ids.postId || href}`;
      if (seen.has(key)) return;
      seen.add(key);
      rows.push({
        url: href,
        title: (link.textContent || '').trim(),
        blogId: ids.blogId,
        postId: ids.postId || '',
        isAd: isAdNode(node),
      });
    });
    if (rows.length) break;
  }

  if (!rows.length) {
    document.querySelectorAll('a[href*="blog.naver.com"]').forEach((link) => {
      const href = link.href || link.getAttribute('href') || '';
      const ids = extractIds(href);
      if (!ids.blogId || !ids.postId) return;
      const key = `${ids.blogId}:${ids.postId}`;
      if (seen.has(key)) return;
      seen.add(key);
      const parent = link.closest('li, div, section');
      rows.push({
        url: href,
        title: (link.textContent || '').trim(),
        blogId: ids.blogId,
        postId: ids.postId,
        isAd: isAdNode(parent),
      });
    });
  }

  return rows;
}
"""


def _build_search_url(keyword: str, mode: str) -> str:
    encoded = quote_plus(keyword)
    if mode == SEARCH_MODE_BLOG_TAB:
        return f"https://search.naver.com/search.naver?where=blog&query={encoded}"
    return f"https://search.naver.com/search.naver?query={encoded}"


def _is_ad_item(item: BlogSearchResultItem) -> bool:
    combined = f"{item.title} {item.url}".lower()
    return item.is_ad or any(marker in combined for marker in AD_MARKERS)


async def _delay_between_requests() -> None:
    settings = load_settings()
    delay = random.uniform(settings.delay_min, settings.delay_max)
    await asyncio.sleep(delay)


async def search_blog_results(
    page: Page,
    keyword: str,
    *,
    mode: str = SEARCH_MODE_UNIFIED,
    max_rank: int = 50,
) -> list[BlogSearchResultItem]:
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    url = _build_search_url(keyword, mode)
    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(1.2)

    raw_rows = await page.evaluate(EXTRACT_BLOG_RESULTS_SCRIPT, mode)
    results: list[BlogSearchResultItem] = []
    rank = 0

    for row in raw_rows or []:
        item = BlogSearchResultItem(
            rank=0,
            url=str(row.get("url") or ""),
            title=str(row.get("title") or ""),
            blog_id=str(row.get("blogId") or ""),
            post_id=str(row.get("postId") or "") or None,
            is_ad=bool(row.get("isAd")),
        )
        if _is_ad_item(item):
            continue
        rank += 1
        item.rank = rank
        results.append(item)
        if rank >= max_rank:
            break

    return results


def find_post_rank(
    post_url: str,
    results: list[BlogSearchResultItem],
    *,
    max_rank: int = 50,
) -> tuple[int | None, bool]:
    try:
        target = parse_blog_url(post_url)
    except Exception:
        return None, False

    for item in results:
        if item.rank > max_rank:
            break
        if post_urls_match(post_url, item.url):
            return item.rank, True
        if target.post_id and item.post_id and target.post_id == item.post_id:
            if target.blog_id == item.blog_id:
                return item.rank, True

    return None, False
