"""네이버 블로그 검색 결과 크롤링 (data-meta-area 동적 수집)."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from urllib.parse import quote_plus

from playwright.async_api import Page

from src.blog_models import SEARCH_MODE_BLOG_TAB, SEARCH_MODE_UNIFIED
from src.blog_url import parse_blog_url, post_urls_match
from src.settings import load_settings

logger = logging.getLogger(__name__)

# --- data-meta-area / 클래스 패턴 (동적 분류 + 폴백) ---

META_AD_PATTERN = re.compile(r"(adR|ipR)", re.I)
META_POPULAR_PATTERN = re.compile(r"(bsR|qpR)", re.I)
META_SMART_PATTERN = re.compile(r"b[1-5]R", re.I)
META_WEBSITE_PATTERN = re.compile(r"(hdR|bdR|coR|gen)", re.I)

FALLBACK_AD_AREAS = ("ugB_ipR", "ugB_adR")
FALLBACK_POPULAR_AREAS = ("ugB_bsR", "ugB_qpR")
FALLBACK_SMART_AREAS = tuple(f"ugB_b{i}R" for i in range(1, 6))
FALLBACK_WEBSITE_AREAS = ("rrB_hdR", "rrB_bdR", "urB_coR", "web_gen")

BLOG_POST_PATH_PATTERN = re.compile(
    r"blog\.naver\.com/([a-zA-Z0-9_-]+)/(\d+)",
    re.I,
)

AREA_TYPE_AD = "ad"
AREA_TYPE_POPULAR = "popular"
AREA_TYPE_SMARTBLOCK = "smartblock"
AREA_TYPE_WEBSITE = "website"
AREA_TYPE_BLOG_TAB = "blog_tab"
AREA_TYPE_UNKNOWN = "unknown"

PAGE_LOAD_WAIT_SEC = 1.5
MAIN_PACK_SELECTOR = "#main_pack"


@dataclass
class BlogSearchResultItem:
    rank: int
    url: str
    title: str
    blog_id: str
    post_id: str | None
    is_ad: bool = False
    area_type: str = AREA_TYPE_UNKNOWN
    meta_area: str = ""


def classify_meta_area(token: str) -> str:
    """data-meta-area 값 또는 클래스 토큰으로 영역 유형 분류."""
    normalized = (token or "").strip()
    if not normalized:
        return AREA_TYPE_UNKNOWN
    if META_AD_PATTERN.search(normalized):
        return AREA_TYPE_AD
    if META_SMART_PATTERN.search(normalized):
        return AREA_TYPE_SMARTBLOCK
    if META_POPULAR_PATTERN.search(normalized):
        return AREA_TYPE_POPULAR
    if META_WEBSITE_PATTERN.search(normalized):
        return AREA_TYPE_WEBSITE
    return AREA_TYPE_UNKNOWN


def normalize_blog_post_url(raw: str | None) -> str | None:
    """blog.naver.com/{ID}/숫자 형태만 유효."""
    if not raw:
        return None
    match = BLOG_POST_PATH_PATTERN.search(raw)
    if not match:
        return None
    blog_id, post_id = match.group(1), match.group(2)
    return f"https://blog.naver.com/{blog_id}/{post_id}"


def parse_blog_ids(url: str) -> tuple[str, str]:
    match = BLOG_POST_PATH_PATTERN.search(url)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


EXTRACT_BLOG_RESULTS_SCRIPT = """
(mode) => {
  const AD_RE = /adR|ipR/i;
  const POPULAR_RE = /bsR|qpR/i;
  const SMART_RE = /b[1-5]R/i;
  const WEB_RE = /hdR|bdR|coR|gen/i;
  const BLOG_PATH = /blog\\.naver\\.com\\/([a-zA-Z0-9_-]+)\\/(\\d+)/i;
  const MAX_RANK = 50;

  const FALLBACK_AD = ['ugB_ipR', 'ugB_adR'];
  const FALLBACK_POPULAR = ['ugB_bsR', 'ugB_qpR'];
  const FALLBACK_SMART = ['ugB_b1R', 'ugB_b2R', 'ugB_b3R', 'ugB_b4R', 'ugB_b5R'];
  const FALLBACK_WEBSITE = ['rrB_hdR', 'rrB_bdR', 'urB_coR', 'web_gen'];

  const normalizeBlogUrl = (raw) => {
    if (!raw) return null;
    const match = raw.match(BLOG_PATH);
    if (!match) return null;
    return `https://blog.naver.com/${match[1]}/${match[2]}`;
  };

  const getMetaToken = (el) => {
    const meta = (el.getAttribute('data-meta-area') || '').trim();
    if (meta) return meta;
    const cls = (el.className || '').toString();
    const hit = cls.match(/(?:ugB|rrB|urB|web)_[A-Za-z0-9_]+/);
    return hit ? hit[0] : cls;
  };

  const classifyToken = (token) => {
    if (!token) return 'unknown';
    if (AD_RE.test(token)) return 'ad';
    if (SMART_RE.test(token)) return 'smartblock';
    if (POPULAR_RE.test(token)) return 'popular';
    if (WEB_RE.test(token)) return 'website';
    return 'unknown';
  };

  const extractItemFromRoot = (root) => {
    const btn = root.querySelector('button[data-url*="blog.naver.com"]');
    if (btn) {
      const url = normalizeBlogUrl(btn.getAttribute('data-url'));
      if (url) {
        const pathMatch = url.match(BLOG_PATH);
        return {
          url,
          title: (btn.textContent || '').replace(/\\s+/g, ' ').trim(),
          blogId: pathMatch ? pathMatch[1] : '',
          postId: pathMatch ? pathMatch[2] : '',
        };
      }
    }

    const hrefLink = root.querySelector('a[href*="blog.naver.com"]');
    if (hrefLink) {
      const url = normalizeBlogUrl(hrefLink.href || hrefLink.getAttribute('href'));
      if (url) {
        const pathMatch = url.match(BLOG_PATH);
        return {
          url,
          title: (hrefLink.textContent || '').replace(/\\s+/g, ' ').trim(),
          blogId: pathMatch ? pathMatch[1] : '',
          postId: pathMatch ? pathMatch[2] : '',
        };
      }
    }

    const cruLink = root.querySelector('a[cru*="blog.naver.com"]');
    if (cruLink) {
      const url = normalizeBlogUrl(cruLink.getAttribute('cru'));
      if (url) {
        const pathMatch = url.match(BLOG_PATH);
        return {
          url,
          title: (cruLink.textContent || '').replace(/\\s+/g, ' ').trim(),
          blogId: pathMatch ? pathMatch[1] : '',
          postId: pathMatch ? pathMatch[2] : '',
        };
      }
    }

    return null;
  };

  const extractItemsInside = (container) => {
    let itemNodes = Array.from(container.querySelectorAll('[data-template-id="ugcItem"]'));
    if (!itemNodes.length) {
      itemNodes = Array.from(container.querySelectorAll('[data-template-id="ugcItemDesk"]'));
    }

    const rows = [];
    const seen = new Set();
    for (const node of itemNodes) {
      const row = extractItemFromRoot(node);
      if (!row || seen.has(row.url)) continue;
      seen.add(row.url);
      rows.push(row);
    }
    return rows;
  };

  const isNestedInsideContainer = (el, mainPack) => {
    let parent = el.parentElement;
    while (parent && parent !== mainPack) {
      if (parent.hasAttribute('data-meta-area')) {
        const parentType = classifyToken(getMetaToken(parent));
        if (parentType === 'popular' || parentType === 'smartblock') {
          return true;
        }
        break;
      }
      parent = parent.parentElement;
    }
    return false;
  };

  const appendRow = (row, rank, areaType, token) => {
    blogRows.push({
      ...row,
      rank,
      areaType,
      metaArea: token,
      isAd: false,
    });
  };

  const processAreaElement = (areaEl) => {
    const token = getMetaToken(areaEl);
    const areaType = classifyToken(token);
    if (areaType === 'ad') return;

    if (areaType === 'smartblock') {
      let blockRank = 0;
      for (const row of extractItemsInside(areaEl)) {
        blockRank += 1;
        if (blockRank > MAX_RANK) break;
        appendRow(row, blockRank, areaType, token);
      }
      return;
    }

    if (areaType === 'popular') {
      for (const row of extractItemsInside(areaEl)) {
        globalRank += 1;
        if (globalRank > MAX_RANK) return;
        appendRow(row, globalRank, areaType, token);
      }
      return;
    }

    if (areaType === 'website') {
      const row = extractItemFromRoot(areaEl);
      if (!row) return;
      globalRank += 1;
      if (globalRank > MAX_RANK) return;
      appendRow(row, globalRank, areaType, token);
    }
  };

  const mainPack = document.querySelector('#main_pack');
  if (!mainPack) return { blogRows: [] };

  const blogRows = [];
  let globalRank = 0;

  if (mode === 'blog_tab') {
    let tabRank = 0;
    const seen = new Set();
    const tabNodes = mainPack.querySelectorAll('[data-template-id="ugcItem"], [data-template-id="ugcItemDesk"]');
    const roots = tabNodes.length ? tabNodes : [mainPack];
    for (const root of roots) {
      const row = extractItemFromRoot(root);
      if (!row || seen.has(row.url)) continue;
      seen.add(row.url);
      tabRank += 1;
      if (tabRank > MAX_RANK) break;
      appendRow(row, tabRank, 'blog_tab', 'blog_tab');
    }
    return { blogRows };
  }

  const metaAreas = Array.from(mainPack.querySelectorAll('[data-meta-area]'));
  for (const areaEl of metaAreas) {
    const token = getMetaToken(areaEl);
    const areaType = classifyToken(token);
    if (areaType === 'ad') continue;
    if ((areaType === 'popular' || areaType === 'smartblock') && isNestedInsideContainer(areaEl, mainPack)) {
      continue;
    }
    processAreaElement(areaEl);
    if (globalRank >= MAX_RANK) break;
  }

  if (!blogRows.length) {
    const fallbackSelectors = [
      ...FALLBACK_AD.map((id) => `[data-meta-area*="${id}"], .${id}, [class*="${id}"]`),
      ...FALLBACK_POPULAR.map((id) => `[data-meta-area*="${id}"], .${id}, [class*="${id}"]`),
      ...FALLBACK_SMART.map((id) => `[data-meta-area*="${id}"], .${id}, [class*="${id}"]`),
      ...FALLBACK_WEBSITE.map((id) => `[data-meta-area*="${id}"], .${id}, [class*="${id}"]`),
    ];

    for (const selector of fallbackSelectors) {
      mainPack.querySelectorAll(selector).forEach((areaEl) => {
        const token = getMetaToken(areaEl);
        const areaType = classifyToken(token);
        if (areaType === 'ad') return;
        if ((areaType === 'popular' || areaType === 'smartblock') && isNestedInsideContainer(areaEl, mainPack)) {
          return;
        }
        processAreaElement(areaEl);
      });
      if (globalRank >= MAX_RANK && blogRows.length) break;
    }
  }

  if (!blogRows.length) {
    extractItemsInside(mainPack).forEach((row) => {
      globalRank += 1;
      if (globalRank > MAX_RANK) return;
      appendRow(row, globalRank, 'unknown', '');
    });
  }

  return { blogRows };
}
"""


def _build_search_url(keyword: str, mode: str) -> str:
    encoded = quote_plus(keyword)
    if mode == SEARCH_MODE_BLOG_TAB:
        return f"https://search.naver.com/search.naver?where=blog&query={encoded}"
    return f"https://search.naver.com/search.naver?query={encoded}"


async def _delay_between_requests() -> None:
    settings = load_settings()
    delay = random.uniform(settings.delay_min, settings.delay_max)
    await asyncio.sleep(delay)


async def _prepare_search_page(page: Page) -> None:
    try:
        await page.wait_for_selector(MAIN_PACK_SELECTOR, timeout=10_000)
    except Exception:
        logger.warning("main_pack not found before crawl")

    await asyncio.sleep(PAGE_LOAD_WAIT_SEC)

    for _ in range(3):
        await page.evaluate("window.scrollBy(0, Math.max(window.innerHeight, 900))")
        await asyncio.sleep(0.35)

    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(0.25)


def _rows_to_results(raw_rows: list[dict], *, max_rank: int) -> list[BlogSearchResultItem]:
    """JS에서 계산한 rank(스마트블록=블록 내, 인기글/웹사이트=연속)를 유지."""
    results: list[BlogSearchResultItem] = []
    seen: set[str] = set()

    for row in raw_rows or []:
        url = normalize_blog_post_url(str(row.get("url") or ""))
        if not url or url in seen:
            continue

        area_type = str(row.get("areaType") or AREA_TYPE_UNKNOWN)
        if area_type == AREA_TYPE_AD:
            continue

        item_rank = int(row.get("rank") or 0)
        if item_rank <= 0 or item_rank > max_rank:
            continue

        seen.add(url)
        blog_id, post_id = parse_blog_ids(url)
        results.append(
            BlogSearchResultItem(
                rank=item_rank,
                url=url,
                title=str(row.get("title") or ""),
                blog_id=blog_id,
                post_id=post_id or None,
                is_ad=False,
                area_type=area_type,
                meta_area=str(row.get("metaArea") or ""),
            )
        )

    return results


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
    await _prepare_search_page(page)

    payload = await page.evaluate(EXTRACT_BLOG_RESULTS_SCRIPT, mode)
    raw_rows = (payload or {}).get("blogRows") or []
    return _rows_to_results(raw_rows, max_rank=max_rank)


def find_post_rank_with_url(
    post_url: str,
    results: list[BlogSearchResultItem],
    *,
    max_rank: int = 50,
) -> tuple[int | None, str | None]:
    """대상 게시글의 (순위, URL) 또는 (None, None)."""
    try:
        target = parse_blog_url(post_url)
    except Exception:
        return None, None

    for item in results:
        if item.rank > max_rank:
            break
        if post_urls_match(post_url, item.url):
            return item.rank, item.url
        if target.post_id and item.post_id and target.post_id == item.post_id:
            if target.blog_id == item.blog_id:
                return item.rank, item.url

    return None, None


def find_post_rank(
    post_url: str,
    results: list[BlogSearchResultItem],
    *,
    max_rank: int = 50,
) -> tuple[int | None, bool]:
    rank, matched_url = find_post_rank_with_url(post_url, results, max_rank=max_rank)
    return rank, matched_url is not None


async def lookup_post_rank_in_serp(
    page: Page,
    keyword: str,
    post_url: str,
    *,
    mode: str = SEARCH_MODE_UNIFIED,
    max_rank: int = 50,
) -> tuple[int | None, str | None]:
    """SERP에서 게시글 순위 조회 — (순위, URL) 또는 (None, None)."""
    results = await search_blog_results(page, keyword, mode=mode, max_rank=max_rank)
    return find_post_rank_with_url(post_url, results, max_rank=max_rank)
