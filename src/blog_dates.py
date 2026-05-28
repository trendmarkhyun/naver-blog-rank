"""네이버 블로그 게시글 날짜 파싱·정렬."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_MINUTE_AGO = re.compile(r"^(\d+)\s*분\s*전$")
_HOUR_AGO = re.compile(r"^(\d+)\s*시간\s*전$")
_DAY_AGO = re.compile(r"^(\d+)\s*일\s*전$")
_ABSOLUTE_DATE = re.compile(r"^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?$")


def parse_published_at(raw: str | None, *, now: datetime | None = None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None

    current = now or datetime.now(KST)

    if text in {"방금 전", "방금"}:
        return current
    if text == "어제":
        return (current - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)

    minute_match = _MINUTE_AGO.match(text)
    if minute_match:
        return current - timedelta(minutes=int(minute_match.group(1)))

    hour_match = _HOUR_AGO.match(text)
    if hour_match:
        return current - timedelta(hours=int(hour_match.group(1)))

    day_match = _DAY_AGO.match(text)
    if day_match:
        return current - timedelta(days=int(day_match.group(1)))

    absolute_match = _ABSOLUTE_DATE.match(text)
    if absolute_match:
        year = int(absolute_match.group(1))
        month = int(absolute_match.group(2))
        day = int(absolute_match.group(3))
        return datetime(year, month, day, 12, 0, 0, tzinfo=KST)

    return None


def post_sort_key(published_at: str | None, post_id: str | None) -> tuple[float, int]:
    parsed = parse_published_at(published_at)
    if parsed is not None:
        return (parsed.timestamp(), _post_id_int(post_id))

    pid = _post_id_int(post_id)
    if pid:
        return (float(pid), pid)

    return (0.0, 0)


def _post_id_int(post_id: str | None) -> int:
    if post_id and post_id.isdigit():
        return int(post_id)
    return 0


def sort_posts_newest_first(posts: list) -> list:
    return sorted(
        posts,
        key=lambda post: post_sort_key(
            getattr(post, "published_at", None),
            getattr(post, "post_id", None),
        ),
        reverse=True,
    )
