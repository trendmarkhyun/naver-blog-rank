"""블로그 순위 엑셀 내보내기."""

from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook

from src.blog_models import (
    SEARCH_MODE_BLOG_TAB,
    SEARCH_MODE_UNIFIED,
    BlogProfile,
    effective_search_mode,
    format_rank_label,
)


def _mode_label(mode: str) -> str:
    if mode == SEARCH_MODE_BLOG_TAB:
        return "블로그탭"
    return "통합검색"


def export_blogs_to_xlsx(
    profiles: list[BlogProfile],
    *,
    global_mode: str,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "블로그순위"

    headers = [
        "광고주명",
        "블로그 URL",
        "블로그 제목",
        "게시글 제목",
        "작성일",
        "조회수",
        "댓글수",
        "키워드1",
        "순위1",
        "키워드2",
        "순위2",
        "키워드3",
        "순위3",
        "키워드4",
        "순위4",
        "검색기준",
        "갱신시각",
    ]
    ws.append(headers)

    for profile in profiles:
        mode = effective_search_mode(profile, global_mode)
        mode_text = _mode_label(mode)
        if not profile.posts:
            ws.append(
                [
                    profile.advertiser_name,
                    profile.blog_url,
                    profile.blog_title,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    mode_text,
                    "",
                ]
            )
            continue

        for post in profile.posts:
            keywords = sorted(post.keywords, key=lambda k: k.slot)
            while len(keywords) < 4:
                from src.blog_models import BlogKeyword

                keywords.append(
                    BlogKeyword(id="", blog_post_id=post.id, slot=len(keywords) + 1)
                )

            row = [
                profile.advertiser_name,
                profile.blog_url,
                profile.blog_title,
                post.title,
                post.published_at or "",
                post.views if post.views is not None else "",
                post.comments if post.comments is not None else "",
            ]
            latest_updated = ""
            for kw in keywords[:4]:
                row.append(kw.keyword)
                row.append(format_rank_label(kw.rank, kw.found, kw.keyword))
                if kw.updated_at and (not latest_updated or kw.updated_at > latest_updated):
                    latest_updated = kw.updated_at
            row.extend([mode_text, latest_updated])
            ws.append(row)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def default_export_filename() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"blog_rank_{stamp}.xlsx"
