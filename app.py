"""네이버 플레이스 순위 모니터 — Supabase 팀원별 UI."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from src.auth import AuthError, MemberSession, login
from src.place_url import PlaceUrlError, parse_place_url
from src.supabase_store import SupabaseStore, SupabaseStoreError
from src.ui_helpers import format_change, format_rank
from src.watchlist import WatchlistError, WatchlistItem

st.set_page_config(
    page_title="네이버 플레이스 순위 모니터",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main-title { font-size: 1.75rem; font-weight: 700; margin-bottom: 0.2rem; }
    .sub-title { color: #666; margin-bottom: 1rem; }
    .watch-row {
        border: 1px solid #e8ece9; border-radius: 10px;
        padding: 0.65rem 0.75rem; margin-bottom: 0.5rem; background: #fff;
    }
    .watch-row.changed { background: #fffbe6; border-color: #f0d96b; }
    .watch-name { font-weight: 600; color: #222; }
    .watch-meta { color: #666; font-size: 0.9rem; }
    .watch-rank { font-weight: 700; color: #03C75A; font-size: 1.05rem; }
    .watch-changed { color: #b8860b; font-weight: 600; font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _store() -> SupabaseStore:
    return SupabaseStore()


def require_member() -> MemberSession:
    if st.session_state.get("member"):
        return st.session_state.member

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

    st.stop()


def logout_button() -> None:
    if st.button("로그아웃", key="logout"):
        st.session_state.pop("member", None)
        st.session_state.pop("items", None)
        st.rerun()


def load_items(member_id: str) -> list[WatchlistItem]:
    return _store().list_items(member_id)


def render_item(item: WatchlistItem, member: MemberSession) -> None:
    row_class = "watch-row changed" if item.changed else "watch-row"
    change_text = format_change(item)
    rank_text = format_rank(item.rank, item.found, member.max_rank)

    c_del, c_body = st.columns([0.08, 0.92])
    with c_del:
        if st.button("✕", key=f"del_{item.id}", help="등록 해제"):
            _store().delete_item(member.id, item.id)
            st.session_state.items = load_items(member.id)
            st.rerun()
    with c_body:
        st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="watch-name">{item.place_name}</div>'
            f'<div class="watch-meta">키워드: {item.keyword}</div>'
            f'<div class="watch-rank">{rank_text}</div>'
            + (f'<div class="watch-changed">✓ {change_text}</div>' if change_text else ""),
            unsafe_allow_html=True,
        )
        if item.updated_at:
            st.caption(f"갱신: {item.updated_at}")
        elif item.rank is None:
            st.caption("순위 대기 중 (30분 이내 자동 갱신)")
        st.markdown("</div>", unsafe_allow_html=True)


@st.fragment(run_every=timedelta(minutes=5))
def auto_reload_items() -> None:
    member: MemberSession = st.session_state.member
    st.session_state.items = load_items(member.id)


def on_max_rank_change() -> None:
    member: MemberSession = st.session_state.member
    max_rank = st.session_state.max_rank_slider
    _store().update_member_max_rank(member.id, max_rank)
    member.max_rank = max_rank
    st.session_state.member = member


def render_dashboard(member: MemberSession) -> None:
    if "items" not in st.session_state:
        st.session_state.items = load_items(member.id)

    items: list[WatchlistItem] = st.session_state.items
    left, right = st.columns([2, 3])

    with left:
        st.subheader("등록")
        max_rank = st.slider(
            "탐색할 최대 순위",
            min_value=10,
            max_value=100,
            value=member.max_rank,
            step=10,
            key="max_rank_slider",
            on_change=on_max_rank_change,
        )

        with st.form("register_form"):
            keyword = st.text_input("검색 키워드", placeholder="예: 공주시 맛집")
            place_url = st.text_input(
                "플레이스 URL",
                placeholder="https://map.naver.com/p/entry/place/1234567890",
            )
            place_name = st.text_input("업체명 (선택)", placeholder="예: 까우")
            register_clicked = st.form_submit_button("등록", type="primary", use_container_width=True)

        if register_clicked:
            if not keyword.strip() or not place_url.strip():
                st.error("키워드와 플레이스 URL을 입력해 주세요.")
            else:
                try:
                    parse_place_url(place_url.strip())
                    _store().add_item(
                        member.id,
                        place_url=place_url.strip(),
                        keyword=keyword.strip(),
                        place_name=place_name.strip(),
                    )
                    st.session_state.items = load_items(member.id)
                    st.success("등록 완료. 순위는 30분 이내 자동 갱신됩니다.")
                    st.rerun()
                except (WatchlistError, PlaceUrlError) as exc:
                    st.error(str(exc))
                except SupabaseStoreError as exc:
                    st.error(f"저장 오류: {exc}")

        st.info(
            "순위는 GitHub Actions가 **30분마다** 자동 갱신합니다.\n\n"
            "등록 직후에는 '순위 대기 중'으로 표시될 수 있습니다."
        )

    with right:
        st.subheader(f"내 등록 업체 ({len(items)}/20)")

        if st.button("목록 새로고침", key="reload"):
            st.session_state.items = load_items(member.id)
            st.rerun()

        auto_reload_items()

        if not items:
            st.info("좌측에서 키워드와 URL을 입력한 뒤 [등록]을 눌러 주세요.")
        else:
            latest = max((i.updated_at for i in items if i.updated_at), default=None)
            if latest:
                st.caption(f"마지막 순위 갱신: {latest}")
            for item in items:
                render_item(item, member)


member = require_member()

header_left, header_right = st.columns([4, 1])
with header_left:
    st.markdown('<p class="main-title">네이버 플레이스 순위 모니터</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="sub-title">{member.display_name}님 · 팀원별 개인 모니터링</p>',
        unsafe_allow_html=True,
    )
with header_right:
    logout_button()

render_dashboard(member)

st.divider()
st.caption("순위 기준: Apollo placeList 일반 목록 (유료 광고 제외). 30분마다 GitHub Actions가 갱신합니다.")
