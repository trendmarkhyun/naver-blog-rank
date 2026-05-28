"""이름 + 팀원코드 로그인."""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.supabase_store import SupabaseStore, SupabaseStoreError


@dataclass
class MemberSession:
    id: str
    display_name: str
    team_code: str
    max_rank: int


class AuthError(Exception):
    pass


def _team_access_code() -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and "TEAM_ACCESS_CODE" in st.secrets:
            return str(st.secrets["TEAM_ACCESS_CODE"]).strip()
    except Exception:
        pass

    code = os.getenv("TEAM_ACCESS_CODE", "").strip()
    if not code:
        raise AuthError("TEAM_ACCESS_CODE가 설정되지 않았습니다.")
    return code


def login(display_name: str, team_code: str) -> MemberSession:
    display_name = (display_name or "").strip()
    team_code = (team_code or "").strip()

    if not display_name:
        raise AuthError("이름을 입력해 주세요.")
    if not team_code:
        raise AuthError("팀원코드를 입력해 주세요.")

    if team_code != _team_access_code():
        raise AuthError("팀원코드가 올바르지 않습니다.")

    try:
        member = SupabaseStore().upsert_member(display_name, team_code)
    except SupabaseStoreError as exc:
        raise AuthError(str(exc)) from exc

    return MemberSession(
        id=member.id,
        display_name=member.display_name,
        team_code=member.team_code,
        max_rank=member.max_rank,
    )
