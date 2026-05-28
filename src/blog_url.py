"""네이버 블로그 URL 파싱."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

BLOG_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
POST_ID_PATTERN = re.compile(r"^(\d+)$")

# blog.naver.com/myblog/123456789
PATH_POST_PATTERN = re.compile(r"blog\.naver\.com/([^/?#]+)/(\d+)")
# blog.naver.com/myblog
PATH_HOME_PATTERN = re.compile(r"blog\.naver\.com/([^/?#]+)")
# m.blog.naver.com/PostView.naver?blogId=x&logNo=123
QUERY_PATTERN = re.compile(r"[?&]blogId=([^&]+).*?[?&]logNo=(\d+)", re.I)


class BlogUrlError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBlogUrl:
    blog_id: str
    post_id: str | None = None


def build_blog_home_url(blog_id: str) -> str:
    return f"https://blog.naver.com/{blog_id}"


def build_blog_post_url(blog_id: str, post_id: str) -> str:
    return f"https://blog.naver.com/{blog_id}/{post_id}"


def _validate_blog_id(blog_id: str) -> str:
    blog_id = (blog_id or "").strip()
    if not blog_id or not BLOG_ID_PATTERN.match(blog_id):
        raise BlogUrlError("블로그 ID 형식이 올바르지 않습니다.")
    return blog_id


def parse_blog_url(url: str) -> ParsedBlogUrl:
    text = (url or "").strip()
    if not text:
        raise BlogUrlError("블로그 URL을 입력해 주세요.")

    if not text.startswith("http"):
        text = f"https://{text}"

    parsed = urlparse(text)
    host = (parsed.netloc or "").lower()
    full = text

    if "blog.naver.com" not in host and "blog.naver.com" not in full:
        raise BlogUrlError(
            "네이버 블로그 URL을 입력해 주세요. "
            "예: https://blog.naver.com/myblog"
        )

    query_match = QUERY_PATTERN.search(full)
    if query_match:
        return ParsedBlogUrl(
            blog_id=_validate_blog_id(query_match.group(1)),
            post_id=query_match.group(2),
        )

    post_match = PATH_POST_PATTERN.search(full)
    if post_match:
        blog_id = post_match.group(1)
        if blog_id.lower() in ("postlist.naver", "postview.naver", "prologue"):
            raise BlogUrlError("블로그 홈 URL을 입력해 주세요.")
        return ParsedBlogUrl(
            blog_id=_validate_blog_id(blog_id),
            post_id=post_match.group(2),
        )

    home_match = PATH_HOME_PATTERN.search(full)
    if home_match:
        blog_id = home_match.group(1)
        if blog_id.lower() in ("postlist.naver", "postview.naver", "prologue"):
            raise BlogUrlError("블로그 홈 URL을 입력해 주세요.")
        return ParsedBlogUrl(blog_id=_validate_blog_id(blog_id))

    raise BlogUrlError(
        "블로그 ID를 URL에서 찾을 수 없습니다. "
        "예: https://blog.naver.com/myblog"
    )


def parse_post_url(url: str) -> ParsedBlogUrl:
    parsed = parse_blog_url(url)
    if not parsed.post_id:
        raise BlogUrlError("게시글 URL이 아닙니다.")
    return parsed


def post_urls_match(target_url: str, result_url: str) -> bool:
    try:
        target = parse_blog_url(target_url)
        result = parse_blog_url(result_url)
    except BlogUrlError:
        return False

    if target.blog_id != result.blog_id:
        return False

    if target.post_id and result.post_id:
        return target.post_id == result.post_id

    return target_url.split("?")[0].rstrip("/") == result_url.split("?")[0].rstrip("/")
