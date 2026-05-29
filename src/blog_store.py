"""Supabase 블로그 순위 저장소."""

from __future__ import annotations

import uuid

from src.blog_models import (
    BLOG_MAX_RANK,
    MAX_BLOGS,
    MAX_KEYWORDS,
    MAX_POSTS,
    SEARCH_MODE_UNIFIED,
    BlogKeyword,
    BlogMemberSettings,
    BlogPost,
    BlogProfile,
    BlogStoreError,
)
from src.blog_dates import sort_posts_newest_first
from src.blog_url import BlogUrlError, build_blog_home_url, parse_blog_url
from src.storage import Storage
from src.supabase_store import SupabaseStoreError, get_client


class BlogStore:
    def __init__(self, client=None) -> None:
        self.client = client or get_client()

    @staticmethod
    def now_iso() -> str:
        return Storage.now_kst_iso()

    def get_member_settings(self, member_id: str) -> BlogMemberSettings:
        response = (
            self.client.table("members")
            .select("blog_search_mode, blog_max_rank")
            .eq("id", member_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return BlogMemberSettings()
        row = rows[0]
        return BlogMemberSettings(
            blog_search_mode=str(row.get("blog_search_mode") or SEARCH_MODE_UNIFIED),
            blog_max_rank=int(row.get("blog_max_rank") or BLOG_MAX_RANK),
        )

    def update_member_blog_search_mode(self, member_id: str, mode: str) -> None:
        self.client.table("members").update({"blog_search_mode": mode}).eq("id", member_id).execute()

    def list_profiles(self, member_id: str) -> list[BlogProfile]:
        response = (
            self.client.table("blog_profiles")
            .select("*")
            .eq("member_id", member_id)
            .order("sort_order")
            .order("created_at")
            .execute()
        )
        return [_row_to_profile(row) for row in (response.data or [])]

    def get_profile(self, member_id: str, profile_id: str) -> BlogProfile | None:
        response = (
            self.client.table("blog_profiles")
            .select("*")
            .eq("member_id", member_id)
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        return _row_to_profile(rows[0])

    def add_profile(
        self,
        member_id: str,
        *,
        blog_url: str,
        blog_title: str,
        advertiser_name: str,
    ) -> BlogProfile:
        blog_url = blog_url.strip()
        blog_title = blog_title.strip()
        advertiser_name = advertiser_name.strip()

        if not blog_url:
            raise BlogStoreError("블로그 홈 URL을 입력해 주세요.")

        try:
            parsed = parse_blog_url(blog_url)
        except BlogUrlError as exc:
            raise BlogStoreError(str(exc)) from exc

        current = self.list_profiles(member_id)
        if len(current) >= MAX_BLOGS:
            raise BlogStoreError(f"최대 {MAX_BLOGS}개까지 등록할 수 있습니다.")

        for profile in current:
            if profile.blog_id == parsed.blog_id:
                raise BlogStoreError("이미 등록된 블로그입니다.")

        sort_order = len(current) + 1
        home_url = build_blog_home_url(parsed.blog_id)
        payload = {
            "id": str(uuid.uuid4()),
            "member_id": member_id,
            "blog_id": parsed.blog_id,
            "blog_url": home_url,
            "blog_title": blog_title,
            "advertiser_name": advertiser_name,
            "search_mode": None,
            "sort_order": sort_order,
        }
        inserted = self.client.table("blog_profiles").insert(payload).execute()
        if not inserted.data:
            raise SupabaseStoreError("블로그 등록에 실패했습니다.")
        return _row_to_profile(inserted.data[0])

    def delete_profile(self, member_id: str, profile_id: str) -> None:
        self.client.table("blog_profiles").delete().eq("member_id", member_id).eq(
            "id", profile_id
        ).execute()
        self._reorder_profiles(member_id)

    def update_profile_search_mode(
        self, member_id: str, profile_id: str, search_mode: str | None
    ) -> None:
        self.client.table("blog_profiles").update({"search_mode": search_mode}).eq(
            "member_id", member_id
        ).eq("id", profile_id).execute()

    def _reorder_profiles(self, member_id: str) -> None:
        profiles = self.list_profiles(member_id)
        for index, profile in enumerate(profiles, start=1):
            if profile.sort_order != index:
                self.client.table("blog_profiles").update({"sort_order": index}).eq(
                    "id", profile.id
                ).execute()

    def list_posts(self, profile_id: str) -> list[BlogPost]:
        response = (
            self.client.table("blog_posts")
            .select("*")
            .eq("blog_profile_id", profile_id)
            .execute()
        )
        posts = sort_posts_newest_first([_row_to_post(row) for row in (response.data or [])])
        if not posts:
            return posts

        post_ids = [post.id for post in posts]
        keywords_resp = (
            self.client.table("blog_post_keywords")
            .select("*")
            .in_("blog_post_id", post_ids)
            .execute()
        )
        keywords_by_post: dict[str, list[BlogKeyword]] = {pid: [] for pid in post_ids}
        for row in keywords_resp.data or []:
            kw = _row_to_keyword(row)
            keywords_by_post.setdefault(kw.blog_post_id, []).append(kw)

        for post in posts:
            existing = sorted(keywords_by_post.get(post.id, []), key=lambda k: k.slot)
            slots = {kw.slot: kw for kw in existing}
            post.keywords = [
                slots.get(
                    slot,
                    BlogKeyword(
                        id="",
                        blog_post_id=post.id,
                        slot=slot,
                    ),
                )
                for slot in range(1, MAX_KEYWORDS + 1)
            ]
        return posts

    def upsert_posts(self, profile_id: str, posts: list[BlogPost]) -> list[BlogPost]:
        if not posts:
            return []

        payloads = []
        for post in posts[:MAX_POSTS]:
            post_id = post.id or str(uuid.uuid4())
            payloads.append(
                {
                    "id": post_id,
                    "blog_profile_id": profile_id,
                    "post_id": post.post_id,
                    "post_url": post.post_url,
                    "title": post.title,
                    "published_at": post.published_at,
                    "views": post.views,
                    "comments": post.comments,
                    "fetched_at": post.fetched_at or self.now_iso(),
                }
            )

        upserted = self.client.table("blog_posts").upsert(
            payloads, on_conflict="blog_profile_id,post_id"
        ).execute()
        saved = [_row_to_post(row) for row in (upserted.data or [])]

        if saved:
            post_ids = [post.id for post in saved]
            existing_kw_resp = (
                self.client.table("blog_post_keywords")
                .select("blog_post_id, slot")
                .in_("blog_post_id", post_ids)
                .execute()
            )
            existing_slots: set[tuple[str, int]] = set()
            for row in existing_kw_resp.data or []:
                existing_slots.add((str(row["blog_post_id"]), int(row["slot"])))

            for saved_post in saved:
                for slot in range(1, MAX_KEYWORDS + 1):
                    if (saved_post.id, slot) in existing_slots:
                        continue
                    self.client.table("blog_post_keywords").insert(
                        {
                            "id": str(uuid.uuid4()),
                            "blog_post_id": saved_post.id,
                            "slot": slot,
                            "keyword": "",
                            "rank": None,
                            "found": False,
                            "updated_at": None,
                        }
                    ).execute()

        return self.list_posts(profile_id)

    def upsert_keyword(
        self,
        post_id: str,
        slot: int,
        keyword: str,
    ) -> BlogKeyword:
        if slot < 1 or slot > MAX_KEYWORDS:
            raise BlogStoreError(f"키워드 슬롯은 1~{MAX_KEYWORDS}만 가능합니다.")

        keyword = keyword.strip()
        payload = {
            "id": str(uuid.uuid4()),
            "blog_post_id": post_id,
            "slot": slot,
            "keyword": keyword,
        }
        existing = (
            self.client.table("blog_post_keywords")
            .select("*")
            .eq("blog_post_id", post_id)
            .eq("slot", slot)
            .limit(1)
            .execute()
        )
        rows = existing.data or []
        if rows:
            row_id = str(rows[0]["id"])
            update_payload = {"keyword": keyword}
            if not keyword:
                update_payload.update({"rank": None, "found": False, "updated_at": None})
            self.client.table("blog_post_keywords").update(update_payload).eq("id", row_id).execute()
            response = (
                self.client.table("blog_post_keywords")
                .select("*")
                .eq("id", row_id)
                .limit(1)
                .execute()
            )
            return _row_to_keyword((response.data or [{}])[0])

        inserted = self.client.table("blog_post_keywords").insert(payload).execute()
        return _row_to_keyword((inserted.data or [{}])[0])

    def get_post(self, post_id: str) -> BlogPost | None:
        response = (
            self.client.table("blog_posts")
            .select("*")
            .eq("id", post_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        post = _row_to_post(rows[0])
        keywords_resp = (
            self.client.table("blog_post_keywords")
            .select("*")
            .eq("blog_post_id", post_id)
            .execute()
        )
        slots = {int(row["slot"]): _row_to_keyword(row) for row in (keywords_resp.data or [])}
        post.keywords = [
            slots.get(
                slot,
                BlogKeyword(id="", blog_post_id=post_id, slot=slot),
            )
            for slot in range(1, MAX_KEYWORDS + 1)
        ]
        return post

    def apply_keyword_rank(
        self,
        keyword_id: str,
        *,
        rank: int | None,
        found: bool,
        updated_at: str,
    ) -> None:
        self.client.table("blog_post_keywords").update(
            {
                "rank": rank,
                "found": found,
                "updated_at": updated_at,
            }
        ).eq("id", keyword_id).execute()

    def load_profile_with_posts(self, member_id: str, profile_id: str) -> BlogProfile | None:
        profile = self.get_profile(member_id, profile_id)
        if profile is None:
            return None
        profile.posts = self.list_posts(profile_id)
        return profile

    def load_all_with_posts(self, member_id: str) -> list[BlogProfile]:
        profiles = self.list_profiles(member_id)
        for profile in profiles:
            profile.posts = self.list_posts(profile.id)
        return profiles


def _row_to_profile(row: dict) -> BlogProfile:
    return BlogProfile(
        id=str(row["id"]),
        member_id=str(row["member_id"]),
        blog_id=str(row["blog_id"]),
        blog_url=str(row["blog_url"]),
        blog_title=str(row.get("blog_title") or ""),
        advertiser_name=str(row.get("advertiser_name") or ""),
        search_mode=row.get("search_mode"),
        sort_order=int(row.get("sort_order") or 0),
        created_at=row.get("created_at"),
    )


def _row_to_post(row: dict) -> BlogPost:
    return BlogPost(
        id=str(row["id"]),
        blog_profile_id=str(row["blog_profile_id"]),
        post_id=str(row["post_id"]),
        post_url=str(row["post_url"]),
        title=str(row.get("title") or ""),
        published_at=row.get("published_at"),
        views=row.get("views"),
        comments=row.get("comments"),
        fetched_at=row.get("fetched_at"),
    )


def _row_to_keyword(row: dict) -> BlogKeyword:
    return BlogKeyword(
        id=str(row.get("id") or ""),
        blog_post_id=str(row.get("blog_post_id") or ""),
        slot=int(row.get("slot") or 0),
        keyword=str(row.get("keyword") or ""),
        rank=row.get("rank"),
        found=bool(row.get("found", False)),
        updated_at=row.get("updated_at"),
    )
