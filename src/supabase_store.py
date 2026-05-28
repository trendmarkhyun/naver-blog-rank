"""Supabase 연결 및 팀원(members) CRUD — 블로그 앱용."""

from __future__ import annotations

import os
from dataclasses import dataclass

from supabase import Client, create_client

from src.storage import Storage


class SupabaseStoreError(Exception):
    pass


@dataclass
class Member:
    id: str
    display_name: str
    team_code: str
    max_rank: int


def _get_secret(key: str) -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass

    value = os.getenv(key, "").strip()
    if not value:
        raise SupabaseStoreError(f"{key}가 설정되지 않았습니다.")
    return value


def get_client() -> Client:
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


class SupabaseStore:
    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_client()

    def upsert_member(self, display_name: str, team_code: str) -> Member:
        existing = (
            self.client.table("members")
            .select("*")
            .eq("display_name", display_name)
            .eq("team_code", team_code)
            .limit(1)
            .execute()
        )
        rows = existing.data or []
        if rows:
            row = rows[0]
            return Member(
                id=str(row["id"]),
                display_name=str(row["display_name"]),
                team_code=str(row["team_code"]),
                max_rank=int(row.get("max_rank") or 50),
            )

        inserted = (
            self.client.table("members")
            .insert(
                {
                    "display_name": display_name,
                    "team_code": team_code,
                    "max_rank": 50,
                    "blog_search_mode": "unified",
                    "blog_max_rank": 50,
                }
            )
            .execute()
        )
        if not inserted.data:
            raise SupabaseStoreError("팀원 등록에 실패했습니다.")
        row = inserted.data[0]
        return Member(
            id=str(row["id"]),
            display_name=str(row["display_name"]),
            team_code=str(row["team_code"]),
            max_rank=int(row.get("max_rank") or 50),
        )

    @staticmethod
    def now_iso() -> str:
        return Storage.now_kst_iso()
