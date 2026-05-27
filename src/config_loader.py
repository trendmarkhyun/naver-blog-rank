"""YAML 설정 로드 및 검증."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Business:
    id: str
    name: str
    place_id: str


@dataclass
class CollectionTarget:
    business: Business
    keyword: str


@dataclass
class AppConfig:
    max_rank: int = 50
    region: str = ""
    businesses: list[Business] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    targets: list[CollectionTarget] = field(default_factory=list)


class ConfigError(Exception):
    pass


def _require_dict(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{path} must be a mapping")
    return value


def _require_list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise ConfigError(f"{path} must be a list")
    return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    root = _require_dict(raw, "root")
    defaults = _require_dict(root.get("defaults", {}), "defaults")

    max_rank = int(defaults.get("max_rank", 50))
    region = str(defaults.get("region", "") or "")

    if max_rank < 1:
        raise ConfigError("defaults.max_rank must be >= 1")

    businesses_raw = _require_list(root.get("businesses", []), "businesses")
    businesses: list[Business] = []
    business_map: dict[str, Business] = {}

    for i, item in enumerate(businesses_raw):
        biz = _require_dict(item, f"businesses[{i}]")
        biz_id = str(biz.get("id", "")).strip()
        name = str(biz.get("name", "")).strip()
        place_id = str(biz.get("place_id", "")).strip()

        if not biz_id:
            raise ConfigError(f"businesses[{i}].id is required")
        if not name:
            raise ConfigError(f"businesses[{i}].name is required")
        if not place_id:
            raise ConfigError(f"businesses[{i}].place_id is required")
        if biz_id in business_map:
            raise ConfigError(f"Duplicate business id: {biz_id}")

        business = Business(id=biz_id, name=name, place_id=place_id)
        businesses.append(business)
        business_map[biz_id] = business

    if not businesses:
        raise ConfigError("At least one business is required")

    keywords_raw = _require_list(root.get("keywords", []), "keywords")
    keywords: list[str] = []
    keyword_set: set[str] = set()

    for i, kw in enumerate(keywords_raw):
        text = str(kw).strip()
        if not text:
            raise ConfigError(f"keywords[{i}] must not be empty")
        if text not in keyword_set:
            keywords.append(text)
            keyword_set.add(text)

    if not keywords:
        raise ConfigError("At least one keyword is required")

    targets_raw = root.get("targets")
    targets: list[CollectionTarget] = []

    if targets_raw is None:
        for business in businesses:
            for keyword in keywords:
                targets.append(CollectionTarget(business=business, keyword=keyword))
    else:
        targets_list = _require_list(targets_raw, "targets")
        seen_pairs: set[tuple[str, str]] = set()

        for i, item in enumerate(targets_list):
            target = _require_dict(item, f"targets[{i}]")
            business_id = str(target.get("business_id", "")).strip()
            target_keywords = _require_list(target.get("keywords", []), f"targets[{i}].keywords")

            if not business_id:
                raise ConfigError(f"targets[{i}].business_id is required")
            if business_id not in business_map:
                raise ConfigError(f"Unknown business_id in targets[{i}]: {business_id}")

            business = business_map[business_id]
            for j, kw in enumerate(target_keywords):
                keyword = str(kw).strip()
                if not keyword:
                    raise ConfigError(f"targets[{i}].keywords[{j}] must not be empty")
                if keyword not in keyword_set:
                    raise ConfigError(
                        f"Keyword '{keyword}' in targets[{i}] is not listed in keywords"
                    )

                pair = (business_id, keyword)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                targets.append(CollectionTarget(business=business, keyword=keyword))

    if not targets:
        raise ConfigError("At least one target (business × keyword) is required")

    return AppConfig(
        max_rank=max_rank,
        region=region,
        businesses=businesses,
        keywords=keywords,
        targets=targets,
    )
