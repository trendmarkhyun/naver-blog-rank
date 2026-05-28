"""네이버 블로그 키워드 순위 체커 — Streamlit UI."""

from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from src.app_common import inject_base_css, render_brand_header, require_member
from src.auth import MemberSession
from src.blog_export import default_export_filename, export_blogs_to_xlsx
from src.blog_lookup import (
    apply_rank_results_to_keywords,
    collect_keyword_targets,
    group_keyword_targets,
    refresh_profile_ranks,
    refresh_single_keyword_group,
)
from src.blog_models import (
    MAX_BLOGS,
    MAX_POSTS,
    SEARCH_MODE_BLOG_TAB,
    SEARCH_MODE_UNIFIED,
    SEARCH_MODES,
    BlogPost,
    BlogProfile,
    BlogStoreError,
    effective_search_mode,
    format_rank_label,
    rank_badge_class,
    summarize_profile_ranks,
)
from src.blog_posts import fetch_blog_posts
from src.blog_store import BlogStore
from src.blog_ui_styles import (
    inject_blog_ui_css,
    rank_badge_html,
    render_pills_html,
)
from src.playwright_bootstrap import ensure_playwright_browser
from src.settings import load_settings
from src.supabase_store import SupabaseStoreError

st.set_page_config(
    page_title="시월기획 블로그 순위 체커",
    page_icon=str(PROJECT_ROOT / "assets" / "siwol_logo.png"),
    layout="wide",
)

BRAND_TITLE = "블로그 순위 체커"
PROFILES_KEY = "blog_profiles"
EXPANDED_KEY = "expanded_blog_ids"
MORE_POSTS_KEY = "blog_more_posts"

INITIAL_VISIBLE_POSTS = 10
POST_TABLE_COLS = [5, 38, 14.25, 14.25, 14.25, 14.25]

inject_base_css()
inject_blog_ui_css()


def _store() -> BlogStore:
    return BlogStore()


def _get_profiles() -> list[BlogProfile] | None:
    return st.session_state.get(PROFILES_KEY)


def _set_profiles(profiles: list[BlogProfile]) -> None:
    st.session_state[PROFILES_KEY] = profiles


def _get_expanded() -> set[str]:
    value = st.session_state.get(EXPANDED_KEY)
    if value is None:
        value = set()
        st.session_state[EXPANDED_KEY] = value
    return value


def _toggle_expanded(profile_id: str) -> None:
    expanded = _get_expanded()
    if profile_id in expanded:
        expanded.discard(profile_id)
    else:
        expanded.add(profile_id)


def _is_more_posts_open(profile_id: str) -> bool:
    mapping = st.session_state.setdefault(MORE_POSTS_KEY, {})
    return bool(mapping.get(profile_id))


def _toggle_more_posts(profile_id: str) -> None:
    mapping = st.session_state.setdefault(MORE_POSTS_KEY, {})
    mapping[profile_id] = not mapping.get(profile_id, False)


def load_profiles(member_id: str) -> list[BlogProfile]:
    return _store().list_profiles(member_id)


def ensure_profiles(member_id: str) -> list[BlogProfile]:
    cached = _get_profiles()
    if cached is None:
        cached = load_profiles(member_id)
        _set_profiles(cached)
    return cached


def reload_profiles(member_id: str) -> list[BlogProfile]:
    profiles = load_profiles(member_id)
    _set_profiles(profiles)
    return profiles


def _save_keyword_slot(state_key: str, post_id: str, slot: int) -> None:
    """on_change: 해당 슬롯만 DB upsert (전체 리렌더 없음)."""
    value = st.session_state.get(state_key, "")
    _store().upsert_keyword(post_id, slot, value)


def run_fetch_posts(blog_id: str):
    ensure_playwright_browser()
    return asyncio.run(fetch_blog_posts(blog_id))


def run_refresh_profile(profile: BlogProfile, global_mode: str, max_rank: int):
    ensure_playwright_browser()
    return asyncio.run(
        refresh_profile_ranks(profile, global_mode=global_mode, max_rank=max_rank)
    )


def run_refresh_all_with_progress(
    member_id: str,
    profiles: list[BlogProfile],
    global_mode: str,
    max_rank: int,
) -> dict:
    ensure_playwright_browser()
    store = _store()
    loaded: list[BlogProfile] = []
    for profile in profiles:
        full = store.load_profile_with_posts(member_id, profile.id)
        if full:
            loaded.append(full)

    targets = collect_keyword_targets(loaded, global_mode)
    groups = group_keyword_targets(targets)
    if not groups:
        return {}

    settings = load_settings()
    all_results: dict = {}
    progress = st.progress(0.0, text="순위 체크 준비 중...")

    for index, ((keyword, mode), group_targets) in enumerate(groups):
        mode_label = "통합검색" if mode == SEARCH_MODE_UNIFIED else "블로그탭"
        progress.progress(
            index / len(groups),
            text=f"키워드 처리 중 ({index + 1}/{len(groups)}): {keyword} · {mode_label}",
        )
        partial = asyncio.run(
            refresh_single_keyword_group(
                keyword, mode, group_targets, max_rank=max_rank
            )
        )
        all_results.update(partial)
        if index < len(groups) - 1:
            time.sleep(random.uniform(settings.delay_min, settings.delay_max))

    progress.progress(1.0, text=f"완료 — {len(groups)}개 키워드 처리")
    return all_results


def _save_posts_from_fetch(member_id: str, profile: BlogProfile) -> BlogProfile | None:
    store = _store()
    result = run_fetch_posts(profile.blog_id)
    if result.error and not result.posts:
        st.warning(result.error)
        return store.load_profile_with_posts(member_id, profile.id)

    posts = [
        BlogPost(
            id="",
            blog_profile_id=profile.id,
            post_id=item.post_id,
            post_url=item.post_url,
            title=item.title,
            published_at=item.published_at,
            views=item.views,
            comments=item.comments,
            fetched_at=store.now_iso(),
        )
        for item in result.posts
    ]
    store.upsert_posts(profile.id, posts)
    return store.load_profile_with_posts(member_id, profile.id)


def _persist_rank_results(member_id: str, results: dict) -> None:
    store = _store()
    profiles = load_profiles(member_id)
    for profile in profiles:
        full = store.load_profile_with_posts(member_id, profile.id)
        if not full:
            continue
        apply_rank_results_to_keywords(full.posts, results)
        for post in full.posts:
            for kw in post.keywords:
                if kw.id and kw.id in results:
                    result = results[kw.id]
                    store.apply_keyword_rank(
                        kw.id,
                        rank=result.rank,
                        found=result.found,
                        updated_at=result.collected_at,
                    )
    reload_profiles(member_id)


def _apply_and_persist_ranks(
    member_id: str,
    profile_id: str,
    results: dict,
) -> None:
    store = _store()
    profile = store.load_profile_with_posts(member_id, profile_id)
    if profile is None:
        return
    apply_rank_results_to_keywords(profile.posts, results)
    for post in profile.posts:
        for kw in post.keywords:
            if kw.id and kw.id in results:
                result = results[kw.id]
                store.apply_keyword_rank(
                    kw.id,
                    rank=result.rank,
                    found=result.found,
                    updated_at=result.collected_at,
                )
    reload_profiles(member_id)


def _capped_post_count(posts: list[BlogPost]) -> int:
    return min(len(posts), MAX_POSTS)


def _visible_post_count(profile_id: str, posts: list[BlogPost]) -> int:
    total = _capped_post_count(posts)
    if _is_more_posts_open(profile_id):
        return total
    return min(INITIAL_VISIBLE_POSTS, total)


def render_post_table_header() -> None:
    labels = [
        "#",
        "포스팅 제목",
        "키워드1",
        "키워드2",
        "키워드3",
        "키워드4",
    ]
    cols = st.columns(POST_TABLE_COLS, gap="small")
    for index, (col, label) in enumerate(zip(cols, labels)):
        with col:
            marker = " blog-tbl-head-marker" if index == 0 else ""
            kw_head = " blog-tbl-kw-head" if index >= 2 else ""
            st.markdown(
                f'<div class="blog-tbl-head-cell{marker}{kw_head}">{label}</div>',
                unsafe_allow_html=True,
            )


def render_post_row(
    profile: BlogProfile,
    post: BlogPost,
    row_index: int,
) -> None:
    cols = st.columns(
        POST_TABLE_COLS,
        vertical_alignment="center",
        gap="small",
    )
    with cols[0]:
        st.markdown(f'<div class="nc">{row_index}</div>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            f'<div class="ptitle">{post.title}</div>'
            f'<div class="pdate">{post.published_at or ""}</div>',
            unsafe_allow_html=True,
        )

    for slot_index, col in enumerate(cols[2:], start=1):
        kw = next((k for k in post.keywords if k.slot == slot_index), None)
        keyword_value = kw.keyword if kw else ""
        kw_key = f"kw_{profile.id}_{post.id}_{slot_index}"

        with col:
            if kw_key not in st.session_state:
                st.session_state[kw_key] = keyword_value

            st.text_input(
                "키워드",
                key=kw_key,
                placeholder="입력",
                label_visibility="collapsed",
                on_change=_save_keyword_slot,
                args=(kw_key, post.id, slot_index),
            )

            current_text = st.session_state.get(kw_key, keyword_value)
            css = rank_badge_class(
                kw.rank if kw else None,
                kw.found if kw else False,
                current_text,
            )
            label = format_rank_label(
                kw.rank if kw else None,
                kw.found if kw else False,
                current_text,
            )
            st.markdown(
                rank_badge_html(label, css),
                unsafe_allow_html=True,
            )


def _render_search_mode_radio(
    *,
    key: str,
    current_mode: str,
    css_class: str = "blog-seg-radio",
) -> str:
    st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
    selected = st.radio(
        "검색 기준",
        options=list(SEARCH_MODES),
        index=0 if current_mode == SEARCH_MODE_UNIFIED else 1,
        format_func=lambda x: "통합검색" if x == SEARCH_MODE_UNIFIED else "블로그탭",
        horizontal=True,
        key=key,
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return selected


def render_profile_control_bar(
    member: MemberSession,
    profile: BlogProfile,
    settings,
    post_count: int,
) -> None:
    store = _store()
    global_mode = settings.blog_search_mode

    left, center, right = st.columns([2.2, 2, 1.2], vertical_alignment="center")
    with left:
        st.markdown(
            '<div class="blog-control-bar-marker"></div>'
            f'<div class="blog-control-info">게시글 {post_count}개 · 광고 제외 자연 노출 기준</div>',
            unsafe_allow_html=True,
        )
    with center:
        current_effective = effective_search_mode(profile, global_mode)
        selected_mode = _render_search_mode_radio(
            key=f"mode_{profile.id}",
            current_mode=current_effective,
        )
        if selected_mode != current_effective:
            override = None if selected_mode == global_mode else selected_mode
            store.update_profile_search_mode(member.id, profile.id, override)
            reload_profiles(member.id)
            st.rerun()
    with right:
        if st.button(
            "순위 체크",
            key=f"rank_check_{profile.id}",
            type="secondary",
            use_container_width=True,
        ):
            with st.spinner("순위 체크 중..."):
                results = run_refresh_profile(profile, global_mode, settings.blog_max_rank)
                _apply_and_persist_ranks(member.id, profile.id, results)
            st.rerun()


def render_profile_detail(member: MemberSession, profile: BlogProfile, settings) -> None:
    store = _store()
    global_mode = settings.blog_search_mode

    full_profile = store.load_profile_with_posts(member.id, profile.id)
    if full_profile is None:
        return
    profile = full_profile

    if not profile.posts:
        with st.spinner("게시글 불러오는 중..."):
            refreshed = _save_posts_from_fetch(member.id, profile)
            if refreshed:
                profile = refreshed

    st.markdown('<div class="blog-expanded-marker"></div>', unsafe_allow_html=True)
    render_profile_control_bar(member, profile, settings, _capped_post_count(profile.posts))

    with st.container(border=True):
        render_post_table_header()

        visible_count = _visible_post_count(profile.id, profile.posts)
        for index, post in enumerate(profile.posts[:visible_count], start=1):
            render_post_row(profile, post, index)

        remaining = _capped_post_count(profile.posts) - INITIAL_VISIBLE_POSTS
        if remaining > 0:
            label = (
                "게시글 접기"
                if _is_more_posts_open(profile.id)
                else f"게시글 더보기 ({remaining}개 더)"
            )
            if st.button(label, key=f"more_{profile.id}"):
                _toggle_more_posts(profile.id)
                st.rerun()


def render_profile_row(member: MemberSession, profile: BlogProfile, index: int) -> None:
    store = _store()
    settings = store.get_member_settings(member.id)
    full = store.load_profile_with_posts(member.id, profile.id) or profile
    pills = summarize_profile_ranks(full.posts).to_labels()
    pills_html = render_pills_html(pills)
    display_url = profile.blog_url.replace("https://", "").replace("http://", "")
    expanded = profile.id in _get_expanded()

    cols = st.columns(
        [0.35, 2.2, 1.4, 1.0, 1.0, 0.55],
        vertical_alignment="center",
    )
    with cols[0]:
        st.markdown(
            f'<div class="blog-row-marker"><div class="bnum-circle">{index}</div></div>',
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(f'<div class="burl">{display_url}</div>', unsafe_allow_html=True)
    with cols[2]:
        st.markdown(
            f'<div class="bname">{profile.blog_title or "-"}</div>',
            unsafe_allow_html=True,
        )
    with cols[3]:
        st.markdown(
            f'<div class="bowner">{profile.advertiser_name or "-"}</div>',
            unsafe_allow_html=True,
        )
    with cols[4]:
        st.markdown(f'<div class="bpills">{pills_html}</div>', unsafe_allow_html=True)
    with cols[5]:
        btn_del, btn_exp = st.columns(2, gap="small", vertical_alignment="center")
        with btn_del:
            if st.button(
                "✕",
                key=f"del_blog_{profile.id}",
                help="삭제",
                type="secondary",
            ):
                store.delete_profile(member.id, profile.id)
                _get_expanded().discard(profile.id)
                reload_profiles(member.id)
                st.rerun()
        with btn_exp:
            chev = "▲" if expanded else "▼"
            if st.button(
                chev,
                key=f"expand_{profile.id}",
                help="펼치기",
                type="secondary",
            ):
                _toggle_expanded(profile.id)
                st.rerun()

    if expanded:
        render_profile_detail(member, profile, settings)


def render_add_row(member: MemberSession, profile_count: int) -> None:
    st.markdown(
        '<div class="blog-panel-header">'
        '<span class="blog-panel-title">블로그 URL 관리</span>'
        f'<span class="blog-panel-count">{profile_count} / {MAX_BLOGS}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="blog-add-row">', unsafe_allow_html=True)
    with st.form("add_blog_form", clear_on_submit=True):
        cols = st.columns([0.25, 3, 2, 1, 0.8])
        with cols[0]:
            st.markdown('<div class="blog-add-plus">+</div>', unsafe_allow_html=True)
        with cols[1]:
            blog_url = st.text_input(
                "블로그 홈 URL",
                placeholder="https://blog.naver.com/myblog",
                label_visibility="collapsed",
            )
        with cols[2]:
            blog_title = st.text_input(
                "블로그 제목",
                placeholder="블로그 제목",
                label_visibility="collapsed",
            )
        with cols[3]:
            advertiser = st.text_input(
                "광고주명",
                placeholder="광고주명 (선택)",
                label_visibility="collapsed",
            )
        with cols[4]:
            submitted = st.form_submit_button("등록", type="primary", use_container_width=True)

        if submitted:
            try:
                _store().add_profile(
                    member.id,
                    blog_url=blog_url,
                    blog_title=blog_title,
                    advertiser_name=advertiser,
                )
                reload_profiles(member.id)
                st.success("블로그가 등록되었습니다.")
                st.rerun()
            except (BlogStoreError, SupabaseStoreError) as exc:
                st.error(str(exc))
    st.markdown("</div>", unsafe_allow_html=True)


def render_global_bar(member: MemberSession, profiles: list[BlogProfile]) -> None:
    settings = _store().get_member_settings(member.id)
    with st.container(border=True):
        st.markdown('<div class="blog-global-footer-marker"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="blog-global-title">전체 검색 기준</div>',
            unsafe_allow_html=True,
        )
        selected = _render_search_mode_radio(
            key="global_search_mode",
            current_mode=settings.blog_search_mode,
        )
        if selected != settings.blog_search_mode:
            _store().update_member_blog_search_mode(member.id, selected)
            settings.blog_search_mode = selected

        if st.button("전체 순위 체크", type="primary", use_container_width=True):
            if not profiles:
                st.info("등록된 블로그가 없습니다.")
            else:
                results = run_refresh_all_with_progress(
                    member.id,
                    profiles,
                    settings.blog_search_mode,
                    settings.blog_max_rank,
                )
                if not results:
                    st.info("입력된 키워드가 없습니다.")
                else:
                    _persist_rank_results(member.id, results)
                st.rerun()


def render_dashboard(member: MemberSession) -> None:
    profiles = ensure_profiles(member.id)
    settings = _store().get_member_settings(member.id)

    act_left, act_right = st.columns([3, 1.2], vertical_alignment="center")
    with act_left:
        st.markdown(
            '<div class="blog-action-header-marker"></div>'
            f'<h2 class="blog-action-title">{BRAND_TITLE}</h2>',
            unsafe_allow_html=True,
        )
    with act_right:
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button("전체 새로고침", key="reload_all", use_container_width=True):
                for profile in profiles:
                    if profile.id in _get_expanded():
                        _save_posts_from_fetch(member.id, profile)
                reload_profiles(member.id)
                st.rerun()
        with btn2:
            if profiles:
                loaded = _store().load_all_with_posts(member.id)
                xlsx_bytes = export_blogs_to_xlsx(
                    loaded,
                    global_mode=settings.blog_search_mode,
                )
                st.download_button(
                    "엑셀 저장",
                    data=xlsx_bytes,
                    file_name=default_export_filename(),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.button("엑셀 저장", disabled=True, use_container_width=True)

    st.markdown('<div class="blog-panel">', unsafe_allow_html=True)
    render_add_row(member, len(profiles))

    if not profiles:
        st.info("상단 + 추가 행에서 블로그 홈 URL을 등록해 주세요.")
    else:
        for index, profile in enumerate(profiles, start=1):
            render_profile_row(member, profile, index)
    st.markdown("</div>", unsafe_allow_html=True)

    render_global_bar(member, profiles)
    st.markdown(
        '<div class="blog-note">광고 제외 · 자연 노출 기준 · 최대 50위까지 탐색</div>',
        unsafe_allow_html=True,
    )


member = require_member(extra_session_keys=(PROFILES_KEY, EXPANDED_KEY, MORE_POSTS_KEY))
render_brand_header(
    member,
    title="시월기획 블로그 순위 체크",
    subtitle=f"{member.display_name}님 · 최대 {MAX_BLOGS}개 블로그 · 게시글 {MAX_POSTS}개",
    extra_session_keys=(PROFILES_KEY, EXPANDED_KEY, MORE_POSTS_KEY),
)
render_dashboard(member)
