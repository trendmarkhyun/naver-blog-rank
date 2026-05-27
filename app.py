"""네이버 플레이스 순위 조회·모니터링 UI."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.lookup import lookup_rank, refresh_watchlist
from src.team_rankings import fetch_team_rankings_from_url, load_team_rankings_for_ui
from src.ui_helpers import format_change, format_rank, render_rank_item_readonly
from src.watchlist import (
    WatchlistData,
    WatchlistError,
    add_item,
    load_watchlist,
    remove_item,
    save_watchlist,
)

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
    .watch-row.changed {
        background: #fffbe6; border-color: #f0d96b;
    }
    .watch-name { font-weight: 600; color: #222; }
    .watch-meta { color: #666; font-size: 0.9rem; }
    .watch-rank { font-weight: 700; color: #03C75A; font-size: 1.05rem; }
    .watch-changed { color: #b8860b; font-weight: 600; font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_session_state() -> None:
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = load_watchlist()
    if "last_refresh_at" not in st.session_state:
        st.session_state.last_refresh_at = None
    if "team_snapshot" not in st.session_state:
        st.session_state.team_snapshot = load_team_rankings_for_ui()


def persist_watchlist(data: WatchlistData) -> None:
    save_watchlist(data)
    st.session_state.watchlist = data


def render_lookup_result(result) -> None:
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
        st.caption(f"플레이스 ID: `{result.place_id}` · {result.collected_at}")


def render_watchlist_item_editable(item, max_rank: int) -> None:
    row_class = "watch-row changed" if item.changed else "watch-row"
    change_text = format_change(item)
    rank_text = format_rank(item.rank, item.found, max_rank)

    c_del, c_body = st.columns([0.08, 0.92])
    with c_del:
        if st.button("✕", key=f"del_{item.id}", help="등록 해제"):
            data = st.session_state.watchlist
            remove_item(data, item.id)
            persist_watchlist(data)
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
def auto_refresh_local_panel() -> None:
    data: WatchlistData = st.session_state.watchlist
    if not data.items:
        return

    with st.spinner("순위 자동 갱신 중..."):
        asyncio.run(refresh_watchlist(data.items, data.max_rank))
        persist_watchlist(data)
        st.session_state.last_refresh_at = data.items[0].updated_at if data.items else None


@st.fragment(run_every=timedelta(minutes=5))
def auto_refresh_team_panel() -> None:
    st.session_state.team_snapshot = load_team_rankings_for_ui()


def on_max_rank_change() -> None:
    data = st.session_state.watchlist
    data.max_rank = st.session_state.max_rank_slider
    persist_watchlist(data)


def render_team_dashboard() -> None:
    st.subheader("팀 공유 순위")
    st.caption(
        "GitHub Actions가 30분마다 순위를 갱신합니다. "
        "업체 추가·삭제는 GitHub에서 `config/team_watchlist.yaml`을 수정하세요."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("GitHub 데이터 새로고침", use_container_width=True):
            st.session_state.team_snapshot = load_team_rankings_for_ui()
            st.rerun()
    with col_b:
        remote_url = st.text_input(
            "Raw JSON URL (선택)",
            value="https://raw.githubusercontent.com/trendmarkhyun/place-rank/main/data/team_rankings.json",
            key="team_raw_url",
        )
        if st.button("URL에서 불러오기", use_container_width=True) and remote_url.strip():
            try:
                st.session_state.team_snapshot = fetch_team_rankings_from_url(remote_url.strip())
                st.success("불러오기 완료")
            except Exception as exc:
                st.error(f"불러오기 실패: {exc}")

    auto_refresh_team_panel()

    snapshot = st.session_state.team_snapshot
    if snapshot is None or not snapshot.items:
        st.info(
            "아직 팀 순위 데이터가 없습니다.\n\n"
            "1. GitHub에 저장소를 push\n"
            "2. `config/team_watchlist.yaml`에 업체 등록\n"
            "3. Actions → **Team Rank Monitor** 실행\n"
            "4. `data/team_rankings.json` 생성 후 이 화면에서 확인"
        )
        return

    meta = f"마지막 갱신: {snapshot.refreshed_at or '—'} · by {snapshot.refreshed_by}"
    if snapshot.source_url:
        meta += f" · {snapshot.source_url}"
    st.caption(meta)
    st.markdown(f"**등록 업체 ({len(snapshot.items)}/20)**")

    for item in snapshot.items:
        render_rank_item_readonly(item, snapshot.max_rank)


def render_local_dashboard() -> None:
    data: WatchlistData = st.session_state.watchlist
    left, right = st.columns([2, 3])

    with left:
        st.subheader("등록 / 조회")
        data.max_rank = st.slider(
            "탐색할 최대 순위",
            min_value=10,
            max_value=100,
            value=data.max_rank,
            step=10,
            key="max_rank_slider",
            on_change=on_max_rank_change,
        )

        with st.form("input_form"):
            keyword = st.text_input("검색 키워드", placeholder="예: 강남역 맛집")
            place_url = st.text_input(
                "플레이스 메인 URL",
                placeholder="예: https://map.naver.com/p/entry/place/2051450000",
            )
            col_reg, col_lookup = st.columns(2)
            register_clicked = col_reg.form_submit_button("등록", use_container_width=True)
            lookup_clicked = col_lookup.form_submit_button(
                "순위 조회", type="primary", use_container_width=True
            )

        if register_clicked or lookup_clicked:
            if not keyword.strip() or not place_url.strip():
                st.error("키워드와 플레이스 URL을 모두 입력해 주세요.")
            else:
                with st.spinner("네이버 지도 검색 중..."):
                    result = asyncio.run(
                        lookup_rank(
                            keyword.strip(),
                            place_url.strip(),
                            max_rank=data.max_rank,
                        )
                    )

                if lookup_clicked:
                    st.markdown("**조회 결과**")
                    render_lookup_result(result)

                if register_clicked:
                    if result.error:
                        st.error(result.error)
                    else:
                        try:
                            add_item(
                                data,
                                place_url=place_url.strip(),
                                keyword=keyword.strip(),
                                place_name=result.place_name or "",
                                place_id=result.place_id,
                                rank=result.rank,
                                found=result.found,
                                updated_at=result.collected_at,
                            )
                            persist_watchlist(data)
                            st.success(f"등록 완료 ({len(data.items)}/20)")
                            st.rerun()
                        except WatchlistError as exc:
                            st.error(str(exc))

    with right:
        st.subheader(f"내 PC 등록 업체 ({len(data.items)}/20)")
        st.caption("5분마다 자동 갱신 · 이 PC에만 저장")

        if st.button("지금 전체 갱신", key="local_refresh"):
            if data.items:
                with st.spinner("순위 갱신 중..."):
                    asyncio.run(refresh_watchlist(data.items, data.max_rank))
                    persist_watchlist(data)
                    st.session_state.last_refresh_at = (
                        data.items[0].updated_at if data.items else None
                    )
                st.rerun()
            else:
                st.info("등록된 업체가 없습니다.")

        auto_refresh_local_panel()

        if not data.items:
            st.info("좌측에서 키워드와 URL을 입력한 뒤 [등록]을 눌러 주세요.")
        else:
            if st.session_state.last_refresh_at:
                st.caption(f"마지막 갱신: {st.session_state.last_refresh_at}")
            for item in data.items:
                render_watchlist_item_editable(item, data.max_rank)


init_session_state()

st.markdown('<p class="main-title">네이버 플레이스 순위 모니터</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-title">팀 공유 대시보드(GitHub)와 개인 PC 모니터를 함께 사용할 수 있습니다.</p>',
    unsafe_allow_html=True,
)

tab_team, tab_local = st.tabs(["팀 공유 (GitHub)", "내 PC 모니터"])

with tab_team:
    render_team_dashboard()

with tab_local:
    render_local_dashboard()

st.divider()
st.caption(
    "순위 기준: Apollo placeList 일반 목록 (유료 광고 제외). "
    "팀 공유는 GitHub Actions 실행 중 갱신됩니다."
)
