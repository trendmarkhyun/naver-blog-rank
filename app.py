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
from src.place_search import PlaceCandidate, pick_auto_candidate, search_places_by_name
from src.place_url import PlaceUrlError, parse_place_url
from src.playwright_bootstrap import ensure_playwright_browser
from src.supabase_store import SupabaseStore, SupabaseStoreError
from src.ui_helpers import format_change, format_rank
from src.watchlist import WatchlistError, WatchlistItem

st.set_page_config(
    page_title="시월기획 플레이스 순위 모니터링",
    page_icon=str(PROJECT_ROOT / "assets" / "siwol_logo.png"),
    layout="wide",
)

LOGO_PATH = PROJECT_ROOT / "assets" / "siwol_logo.png"
BRAND_TITLE = "시월기획 플레이스 순위 모니터링"

st.markdown(
    """
    <style>
    .main-title { font-size: 1.55rem; font-weight: 700; margin: 0.35rem 0 0.15rem 0; line-height: 1.35; }
    .sub-title { color: #666; margin: 0 0 1rem 0; font-size: 1rem; }
    .brand-logo img { max-width: 140px; width: 140px; height: auto; margin-bottom: 0.25rem; }
    .login-offset { height: 3rem; }
    .login-panel { max-width: 420px; margin-top: 1.5rem; }
    .header-logout { display: flex; justify-content: flex-end; align-items: flex-start; padding-top: 0.25rem; }
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
    .candidate-row {
        border: 1px solid #e8ece9; border-radius: 10px;
        padding: 0.75rem 0.85rem; margin-bottom: 0.5rem; background: #fafbfa;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


WATCHLIST_KEY = "watchlist_items"
CANDIDATES_KEY = "place_candidates"
PENDING_ACTION_KEY = "pending_action"
PENDING_KEYWORD_KEY = "pending_keyword"
PENDING_MAX_RANK_KEY = "pending_max_rank"
SEARCH_QUERY_KEY = "place_search_query"
MANUAL_URL_KEY = "manual_url_expanded"


def _get_watchlist() -> list[WatchlistItem] | None:
    return st.session_state.get(WATCHLIST_KEY)


def _set_watchlist(items: list[WatchlistItem]) -> None:
    st.session_state[WATCHLIST_KEY] = items


def _store() -> SupabaseStore:
    return SupabaseStore()


def _clear_place_search_state() -> None:
    for key in (
        CANDIDATES_KEY,
        PENDING_ACTION_KEY,
        PENDING_KEYWORD_KEY,
        PENDING_MAX_RANK_KEY,
        SEARCH_QUERY_KEY,
    ):
        st.session_state.pop(key, None)


def render_logo(*, width: int = 140) -> None:
    if LOGO_PATH.exists():
        st.markdown('<div class="brand-logo">', unsafe_allow_html=True)
        st.image(str(LOGO_PATH), width=width)
        st.markdown("</div>", unsafe_allow_html=True)


def render_brand_header(member: MemberSession) -> None:
    brand_col, logout_col = st.columns([5, 1])
    with brand_col:
        render_logo()
        st.markdown(f'<p class="main-title">{BRAND_TITLE}</p>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="sub-title">{member.display_name}님 개인 모니터링</p>',
            unsafe_allow_html=True,
        )
    with logout_col:
        st.markdown('<div class="header-logout">', unsafe_allow_html=True)
        logout_button()
        st.markdown("</div>", unsafe_allow_html=True)


def require_member() -> MemberSession:
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


def logout_button() -> None:
    if st.button("로그아웃", key="logout"):
        st.session_state.pop("member", None)
        st.session_state.pop(WATCHLIST_KEY, None)
        _clear_place_search_state()
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


def run_place_search(business_name: str) -> list[PlaceCandidate]:
    ensure_playwright_browser()
    return asyncio.run(search_places_by_name(business_name))


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


def register_candidate(
    store: SupabaseStore,
    member: MemberSession,
    candidate: PlaceCandidate,
    keyword: str,
    max_rank: int,
) -> None:
    with st.spinner("순위 조회 및 등록 중..."):
        result = run_lookup(keyword, candidate.place_url, max_rank)

    if result.error and not result.place_id:
        st.error(result.error)
        return

    item = store.add_item(
        member.id,
        place_url=candidate.place_url,
        keyword=keyword.strip(),
        place_name=result.place_name or candidate.name,
    )
    store.apply_rank_refresh(
        item,
        rank=result.rank,
        found=result.found,
        place_name=result.place_name or candidate.name,
        updated_at=result.collected_at,
    )
    updated_items = load_items(member.id)
    _set_watchlist(updated_items)
    _clear_place_search_state()
    st.success(f"등록 완료: {candidate.name} ({len(updated_items)}/20)")
    st.rerun()


def lookup_candidate(candidate: PlaceCandidate, keyword: str, max_rank: int) -> None:
    with st.spinner("네이버 지도 검색 중..."):
        result = run_lookup(keyword, candidate.place_url, max_rank)
    st.markdown("**조회 결과**")
    render_lookup_result(result)


def resolve_with_url(
    store: SupabaseStore,
    member: MemberSession,
    *,
    keyword: str,
    place_url: str,
    max_rank: int,
    register: bool,
    lookup: bool,
) -> None:
    parse_place_url(place_url.strip())
    with st.spinner("네이버 지도 검색 중..."):
        result = run_lookup(keyword, place_url, max_rank)

    if lookup:
        st.markdown("**조회 결과**")
        render_lookup_result(result)

    if register:
        if result.error and not result.place_id:
            st.error(result.error)
            return
        item = store.add_item(
            member.id,
            place_url=place_url.strip(),
            keyword=keyword.strip(),
            place_name=result.place_name or "",
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
        _clear_place_search_state()
        st.success(f"등록 완료 ({len(updated_items)}/20)")
        st.rerun()


def resolve_with_business_name(
    store: SupabaseStore,
    member: MemberSession,
    *,
    keyword: str,
    business_name: str,
    max_rank: int,
    register: bool,
    lookup: bool,
) -> None:
    with st.spinner("업체 검색 중..."):
        candidates = run_place_search(business_name)

    auto_candidate = pick_auto_candidate(business_name, candidates)
    if auto_candidate is not None:
        if register:
            register_candidate(store, member, auto_candidate, keyword, max_rank)
        else:
            lookup_candidate(auto_candidate, keyword, max_rank)
        return

    if not candidates:
        st.error(
            f"'{business_name}'와(과) 정확히 일치하는 업체를 찾지 못했습니다. "
            "네이버 플레이스에 표시된 업체명 풀네임을 입력하거나 URL 직접 입력을 이용해 주세요."
        )
        st.session_state[MANUAL_URL_KEY] = True
        return

    st.session_state[CANDIDATES_KEY] = candidates
    st.session_state[SEARCH_QUERY_KEY] = business_name
    st.session_state[PENDING_KEYWORD_KEY] = keyword.strip()
    st.session_state[PENDING_MAX_RANK_KEY] = max_rank
    st.session_state[PENDING_ACTION_KEY] = "register" if register else "lookup"
    st.rerun()


def render_candidate_picker(store: SupabaseStore, member: MemberSession) -> None:
    candidates: list[PlaceCandidate] = st.session_state.get(CANDIDATES_KEY) or []
    if not candidates:
        return

    keyword = st.session_state.get(PENDING_KEYWORD_KEY, "")
    max_rank = int(st.session_state.get(PENDING_MAX_RANK_KEY) or member.max_rank)
    action = st.session_state.get(PENDING_ACTION_KEY, "register")
    search_query = st.session_state.get(SEARCH_QUERY_KEY, "")

    st.markdown("**업체 선택**")
    st.caption(f"'{search_query}' 검색 결과 {len(candidates)}건 — 등록할 업체를 선택해 주세요.")

    for candidate in candidates:
        col_info, col_btn = st.columns([4.5, 1.5])
        with col_info:
            st.markdown(
                f'<div class="candidate-row">'
                f'<div class="watch-name">{candidate.name}</div>'
                f'<div class="watch-meta">{candidate.summary}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("선택", key=f"pick_{candidate.place_id}", use_container_width=True):
                if action == "register":
                    register_candidate(store, member, candidate, keyword, max_rank)
                else:
                    lookup_candidate(candidate, keyword, max_rank)
                    _clear_place_search_state()

    col_cancel, col_manual = st.columns(2)
    with col_cancel:
        if st.button("다시 검색", key="cancel_candidate_pick", use_container_width=True):
            _clear_place_search_state()
            st.rerun()
    with col_manual:
        if st.button("URL 직접 입력", key="open_manual_url", use_container_width=True):
            _clear_place_search_state()
            st.session_state[MANUAL_URL_KEY] = True
            st.rerun()


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

        manual_expanded = bool(st.session_state.get(MANUAL_URL_KEY))
        with st.expander("URL로 직접 입력", expanded=manual_expanded):
            st.caption("업체명으로 찾지 못할 때만 사용하세요.")
            manual_place_url = st.text_input(
                "플레이스 URL",
                placeholder="https://map.naver.com/p/entry/place/1234567890",
                key="manual_place_url",
            )

        with st.form("input_form"):
            keyword = st.text_input("검색 키워드", placeholder="예: 신부동 맛집")
            business_name = st.text_input(
                "업체명",
                placeholder="예: 아르스킨의원 홍대점 (네이버 표기와 동일하게)",
            )
            col_reg, col_lookup = st.columns(2)
            register_clicked = col_reg.form_submit_button("등록", use_container_width=True)
            lookup_clicked = col_lookup.form_submit_button(
                "순위 조회", type="primary", use_container_width=True
            )

        if register_clicked or lookup_clicked:
            if not keyword.strip():
                st.error("검색 키워드를 입력해 주세요.")
            elif manual_place_url.strip():
                try:
                    resolve_with_url(
                        store,
                        member,
                        keyword=keyword,
                        place_url=manual_place_url,
                        max_rank=max_rank,
                        register=register_clicked,
                        lookup=lookup_clicked,
                    )
                except (WatchlistError, PlaceUrlError) as exc:
                    st.error(str(exc))
                except SupabaseStoreError as exc:
                    st.error(f"저장 오류: {exc}")
                except RuntimeError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"등록/조회 실패: {exc}")
            elif not business_name.strip():
                st.error("업체명을 입력하거나 URL 직접 입력을 이용해 주세요.")
            else:
                try:
                    resolve_with_business_name(
                        store,
                        member,
                        keyword=keyword,
                        business_name=business_name.strip(),
                        max_rank=max_rank,
                        register=register_clicked,
                        lookup=lookup_clicked,
                    )
                except (WatchlistError, PlaceUrlError) as exc:
                    st.error(str(exc))
                except SupabaseStoreError as exc:
                    st.error(f"저장 오류: {exc}")
                except RuntimeError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"등록/조회 실패: {exc}")

        render_candidate_picker(store, member)

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
            st.info("좌측에서 키워드와 업체명을 입력한 뒤 [등록] 또는 [순위 조회]를 눌러 주세요.")
        else:
            latest = max((i.updated_at for i in items if i.updated_at), default=None)
            if latest:
                st.caption(f"마지막 순위 갱신: {latest}")
            for item in items:
                render_item(item, member)


member = require_member()

render_brand_header(member)

render_dashboard(member)

st.divider()
st.caption("순위 기준: Apollo placeList 일반 목록 (유료 광고 제외).")
