"""UI 공통 렌더링."""

from __future__ import annotations

from src.watchlist import WatchlistItem


def format_rank(
    rank: int | None,
    found: bool,
    max_rank: int,
    *,
    pending: bool = False,
) -> str:
    if pending:
        return "조회 전"
    if found and rank is not None:
        return f"{rank}위"
    return f"{max_rank}위 밖"


def format_change(item: WatchlistItem) -> str:
    if not item.changed:
        return ""
    prev = "미노출" if item.prev_rank is None else f"{item.prev_rank}위"
    curr = "미노출" if not item.found or item.rank is None else f"{item.rank}위"
    return f"변동 ({prev} → {curr})"


def render_rank_item_readonly(item: WatchlistItem, max_rank: int) -> None:
    import streamlit as st

    row_class = "watch-row changed" if item.changed else "watch-row"
    change_text = format_change(item)
    rank_text = format_rank(item.rank, item.found, max_rank)

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
