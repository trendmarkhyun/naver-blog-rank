"""업체 매칭 로직."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.config_loader import Business


@dataclass
class SearchResultItem:
    rank: int
    place_id: str
    name: str


@dataclass
class MatchResult:
    found: bool
    rank: int | None
    matched_by: str | None = None


def normalize_name(name: str) -> str:
    text = name.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def find_business_rank(
    business: Business,
    results: list[SearchResultItem],
) -> MatchResult:
    for item in results:
        if item.place_id == business.place_id:
            return MatchResult(found=True, rank=item.rank, matched_by="place_id")

    target_name = normalize_name(business.name)
    if not target_name:
        return MatchResult(found=False, rank=None, matched_by=None)

    for item in results:
        if normalize_name(item.name) == target_name:
            return MatchResult(found=True, rank=item.rank, matched_by="name")

    for item in results:
        item_name = normalize_name(item.name)
        if target_name in item_name or item_name in target_name:
            return MatchResult(found=True, rank=item.rank, matched_by="name_partial")

    return MatchResult(found=False, rank=None, matched_by=None)
