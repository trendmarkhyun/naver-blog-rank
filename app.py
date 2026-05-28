"""네이버 플레이스 순위 모니터 — Supabase 팀원별 UI."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from src.auth import AuthError, MemberSession, login
from src.lookup import RankLookupResult, lookup_rank, refresh_watchlist
from src.place_url import PlaceUrlError, parse_place_url
from src.playwright_bootstrap import ensure_playwright_browser
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
    .result-card {
        background: linear-gradient(135deg, #f8fff9 0%, #ffffff 100%);
        border: 1px solid #d4edda; border-radius: 12px;
        padding: 1rem 1.25rem; margin: 0.75rem 0;
    }
    .rank-number { font-size: 2.2rem; font-weight: 800; color: #03C75A; }
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


WATCHLIST_KEY = "watchlist_items"


def _get_watchlist() -> list[WatchlistItem] | None:
    return st.session_state.get(WATCHLIST_KEY)


def _set_watchlist(items: list[WatchlistItem]) -> None:
    st.session_state[WATCHLIST_KEY] = items


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
        st.session_state.pop(WATCHLIST_KEY, None)
        st.rerun()


def load_items(member_id: str) -> list[WatchlistItem]:
    return _store().list_items(member_id)


def ensure_items(member_id: str) -> list[WatchlistItem]:
    cached = _get_watchlist()
    if cached is None:
        cached = load_items(member_id)
        _set_watchlist(cached)
    return cached


def run_lookup(keyword: str, place_url: str, max_rank: int) -> RankLookupResult:
    ensure_playwright_browser()
    return asyncio.run(
        lookup_rank(keyword.strip(), place_url.strip(), max_rank=max_rank)
    )


def run_refresh_all(items: list[WatchlistItem], max_rank: int) -> None:
    ensure_playwright_browser()
    asyncio.run(refresh_watchlist(items, max_rank))


def render_lookup_result(result: RankLookupResult) -> None:
    if result.error and not result.place_id:
        st.error(result.error)
    elif result.error:
        st.error(f"조회 실패: {result.error}")
    elif result.found and result.rank is not None:
        st.markdown(
            f'<div class="result-card"><div class="rank-number">{result.rank}위</div></div>',
            unsafe_allow_html=True,
        )
        if result.place_name:
            st.markdown(f"**업체명:** {result.place_name}")
        st.caption(f"플레이스 ID: `{result.place_id}` · {result.collected_at}")
    else:
        st.warning(f"{result.max_rank}위 이내에 노출되지 않습니다.")
        if result.place_name:
            st.markdown(f"**업체명:** {result.place_name}")
        st.caption(f"플레이스 ID: `{result.place_id}` · {result.collected_at}")


def render_item(item: WatchlistItem, member: MemberSession) -> None:
    pending = item.rank is None and not item.updated_at
    row_class = "watch-row changed" if item.changed else "watch-row"
    change_text = format_change(item)
    rank_text = format_rank(item.rank, item.found, member.max_rank, pending=pending)

    c_del, c_body = st.columns([0.08, 0.92])
    with c_del:
        if st.button("✕", key=f"del_{item.id}", help="등록 해제"):
            _store().delete_item(member.id, item.id)
            _set_watchlist(load_items(member.id))
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
        st.markdown("</div>", unsafe_allow_html=True)


@st.fragment(run_every=timedelta(minutes=5))
def auto_reload_items() -> None:
    member: MemberSession = st.session_state.member
    try:
        _set_watchlist(load_items(member.id))
    except SupabaseStoreError:
        if _get_watchlist() is None:
            _set_watchlist([])


def on_max_rank_change() -> None:
    member: MemberSession = st.session_state.member
    max_rank = st.session_state.max_rank_slider
    _store().update_member_max_rank(member.id, max_rank)
    member.max_rank = max_rank
    st.session_state.member = member


def render_dashboard(member: MemberSession) -> None:
    items: list[WatchlistItem] = ensure_items(member.id)
    store = _store()
    left, right = st.columns([2, 3])

    with left:
        st.subheader("등록 / 조회")
        max_rank = st.slider(
            "탐색할 최대 순위",
            min_value=10,
            max_value=100,
            value=member.max_rank,
            step=10,
            key="max_rank_slider",
            on_change=on_max_rank_change,
        )

        with st.form("input_form"):
            keyword = st.text_input("검색 키워드", placeholder="예: 신부동 맛집")
            place_url = st.text_input(
                "플레이스 URL",
                placeholder="https://map.naver.com/p/entry/place/1234567890",
            )
            place_name = st.text_input("업체명 (선택)", placeholder="자동 조회 시 채워짐")
            col_reg, col_lookup = st.columns(2)
            register_clicked = col_reg.form_submit_button("등록", use_container_width=True)
            lookup_clicked = col_lookup.form_submit_button(
                "순위 조회", type="primary", use_container_width=True
            )

        if register_clicked or lookup_clicked:
            if not keyword.strip() or not place_url.strip():
                st.error("키워드와 플레이스 URL을 모두 입력해 주세요.")
            else:
                try:
                    parse_place_url(place_url.strip())
                    with st.spinner("네이버 지도 검색 중..."):
                        result = run_lookup(keyword, place_url, max_rank)

                    if lookup_clicked:
                        st.markdown("**조회 결과**")
                        render_lookup_result(result)

                    if register_clicked:
                        if result.error and not result.place_id:
                            st.error(result.error)
                        else:
                            item = store.add_item(
                                member.id,
                                place_url=place_url.strip(),
                                keyword=keyword.strip(),
                                place_name=result.place_name or place_name.strip(),
                            )
                            store.apply_rank_refresh(
                                item,
                                rank=result.rank,
                                found=result.found,
                                place_name=result.place_name,
                                updated_at=result.collected_at,
                            )
                            updated_items = load_items(member.id)
                            _set_watchlist(updated_items)
                            st.success(f"등록 완료 ({len(updated_items)}/20)")
                            st.rerun()
                except (WatchlistError, PlaceUrlError) as exc:
                    st.error(str(exc))
                except SupabaseStoreError as exc:
                    st.error(f"저장 오류: {exc}")
                except RuntimeError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"등록/조회 실패: {exc}")

        st.caption("30분마다 GitHub Actions로도 자동 갱신됩니다.")

    with right:
        st.subheader(f"내 등록 업체 ({len(items)}/20)")

        col_reload, col_refresh = st.columns(2)
        with col_reload:
            if st.button("목록 새로고침", key="reload", use_container_width=True):
                _set_watchlist(load_items(member.id))
                st.rerun()
        with col_refresh:
            if st.button("지금 전체 갱신", key="refresh_all", use_container_width=True):
                if items:
                    try:
                        with st.spinner("순위 갱신 중..."):
                            run_refresh_all(items, max_rank)
                            store.refresh_member_items(items)
                        _set_watchlist(load_items(member.id))
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"갱신 실패: {exc}")
                else:
                    st.info("등록된 업체가 없습니다.")

        auto_reload_items()

        if not items:
            st.info("좌측에서 키워드와 URL을 입력한 뒤 [등록] 또는 [순위 조회]를 눌러 주세요.")
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
st.caption("순위 기준: Apollo placeList 일반 목록 (유료 광고 제외).")
