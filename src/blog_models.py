"""블로그 순위 체커 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_BLOGS = 100
MAX_POSTS = 50
MAX_KEYWORDS = 4
BLOG_MAX_RANK = 50

SEARCH_MODE_UNIFIED = "unified"
SEARCH_MODE_BLOG_TAB = "blog_tab"
SEARCH_MODES = (SEARCH_MODE_UNIFIED, SEARCH_MODE_BLOG_TAB)


class BlogStoreError(Exception):
    pass


@dataclass
class BlogKeyword:
    id: str
    blog_post_id: str
    slot: int
    keyword: str = ""
    rank: int | None = None
    found: bool = False
    updated_at: str | None = None


@dataclass
class BlogPost:
    id: str
    blog_profile_id: str
    post_id: str
    post_url: str
    title: str
    published_at: str | None = None
    views: int | None = None
    comments: int | None = None
    fetched_at: str | None = None
    keywords: list[BlogKeyword] = field(default_factory=list)


@dataclass
class BlogProfile:
    id: str
    member_id: str
    blog_id: str
    blog_url: str
    blog_title: str
    advertiser_name: str
    search_mode: str | None = None
    sort_order: int = 0
    created_at: str | None = None
    posts: list[BlogPost] = field(default_factory=list)


@dataclass
class BlogMemberSettings:
    blog_search_mode: str = SEARCH_MODE_UNIFIED
    blog_max_rank: int = BLOG_MAX_RANK


def effective_search_mode(profile: BlogProfile, global_mode: str) -> str:
    if profile.search_mode in SEARCH_MODES:
        return profile.search_mode
    if global_mode in SEARCH_MODES:
        return global_mode
    return SEARCH_MODE_UNIFIED


def rank_badge_class(rank: int | None, found: bool, keyword: str) -> str:
    if not keyword.strip():
        return "rn"
    if not found or rank is None:
        return "rn"
    if rank == 1:
        return "r1"
    if rank <= 10:
        return "rt"
    if rank <= BLOG_MAX_RANK:
        return "rm"
    return "rn"


def format_rank_label(rank: int | None, found: bool, keyword: str) -> str:
    if not keyword.strip():
        return "-"
    if found and rank is not None:
        return f"{rank}위"
    return "50위 밖"


@dataclass
class RankSummaryPills:
    first_place: int = 0
    top_ten: int = 0
    empty: int = 0

    def to_labels(self) -> list[tuple[str, str]]:
        labels: list[tuple[str, str]] = []
        if self.first_place:
            labels.append(("py", f"1위 ×{self.first_place}"))
        if self.top_ten:
            labels.append(("pg", f"10위내 ×{self.top_ten}"))
        if self.empty:
            labels.append(("pn", f"미입력 ×{self.empty}"))
        if not labels:
            labels.append(("pn", "키워드 미입력"))
        return labels


def summarize_keyword_ranks(keywords: list[BlogKeyword]) -> RankSummaryPills:
    summary = RankSummaryPills()
    for kw in keywords:
        text = kw.keyword.strip()
        if not text:
            summary.empty += 1
            continue
        if kw.found and kw.rank == 1:
            summary.first_place += 1
        elif kw.found and kw.rank is not None and 2 <= kw.rank <= 10:
            summary.top_ten += 1
    return summary


def summarize_profile_ranks(posts: list[BlogPost]) -> RankSummaryPills:
    summary = RankSummaryPills()
    for post in posts:
        for kw in post.keywords:
            text = kw.keyword.strip()
            if not text:
                summary.empty += 1
                continue
            if kw.found and kw.rank == 1:
                summary.first_place += 1
            elif kw.found and kw.rank is not None and 2 <= kw.rank <= 10:
                summary.top_ten += 1
    return summary
