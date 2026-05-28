"""Streamlit 공통 UI (로그인·브랜드 헤더)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.auth import AuthError, MemberSession, login
from src.supabase_store import SupabaseStoreError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / "assets" / "siwol_logo.png"

BASE_CSS = """
<style>
.main-title { font-size: 1.55rem; font-weight: 700; margin: 0.35rem 0 0.15rem 0; line-height: 1.35; }
.sub-title { color: #666; margin: 0 0 1rem 0; font-size: 1rem; }
.brand-logo img { max-width: 140px; width: 140px; height: auto; margin-bottom: 0.25rem; }
.login-offset { height: 3rem; }
.login-panel { max-width: 420px; margin-top: 1.5rem; }
.header-logout { display: flex; justify-content: flex-end; align-items: flex-start; padding-top: 0.25rem; }
</style>
"""


def inject_base_css() -> None:
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def render_logo(*, width: int = 140) -> None:
    if LOGO_PATH.exists():
        st.markdown('<div class="brand-logo">', unsafe_allow_html=True)
        st.image(str(LOGO_PATH), width=width)
        st.markdown("</div>", unsafe_allow_html=True)


def logout_button(*, extra_session_keys: tuple[str, ...] = ()) -> None:
    if st.button("로그아웃", key="logout"):
        st.session_state.pop("member", None)
        for key in extra_session_keys:
            st.session_state.pop(key, None)
        st.rerun()


def render_brand_header(
    member: MemberSession,
    *,
    title: str,
    subtitle: str | None = None,
    extra_session_keys: tuple[str, ...] = (),
) -> None:
    brand_col, logout_col = st.columns([5, 1])
    with brand_col:
        render_logo()
        st.markdown(f'<p class="main-title">{title}</p>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="sub-title">{subtitle or f"{member.display_name}님 개인 모니터링"}</p>',
            unsafe_allow_html=True,
        )
    with logout_col:
        st.markdown('<div class="header-logout">', unsafe_allow_html=True)
        logout_button(extra_session_keys=extra_session_keys)
        st.markdown("</div>", unsafe_allow_html=True)


def require_member(*, extra_session_keys: tuple[str, ...] = ()) -> MemberSession:
    if st.session_state.get("member"):
        return st.session_state.member

    render_logo()
    st.markdown('<div class="login-offset"></div>', unsafe_allow_html=True)

    left_pad, login_col, _ = st.columns([1, 1.4, 1.6])
    with login_col:
        st.markdown('<div class="login-panel">', unsafe_allow_html=True)
        st.markdown("### 로그인")
        st.caption("이름과 팀원코드를 입력하세요. 팀원코드는 관리자에게 문의하세요.")

        with st.form("login_form"):
            name = st.text_input("이름", placeholder="예: 김민수")
            code = st.text_input("팀원코드", type="password", placeholder="팀 공용 코드")
            submitted = st.form_submit_button("들어가기", type="primary", use_container_width=True)

        if submitted:
            try:
                st.session_state.member = login(name, code)
                st.rerun()
            except AuthError as exc:
                st.error(str(exc))
            except SupabaseStoreError as exc:
                st.error(f"연결 오류: {exc}")

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()
