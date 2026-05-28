"""블로그 순위 체커 UI — SaaS 대시보드 스타일."""

from __future__ import annotations

BLOG_UI_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root{
  --bg-page:#FFFFFF;
  --bg-card:#FFFFFF;
  --bg-soft:#FAFAFA;
  --text-main:#111111;
  --text-sub:#6B7280;
  --text-muted:#9CA3AF;
  --border:#E5E7EB;
  --border-light:#F1F5F9;
  --brand:#00C853;
  --brand-hover:#00A844;
  --rank-in-bg:#E8F5E9;
  --rank-in-text:#2E7D32;
  --rank-out-bg:#F3F4F6;
  --rank-out-text:#6B7280;
  --radius:10px;
  --font:'Pretendard',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}

html,body,[class*="css"]{font-family:var(--font)!important;line-height:1.4!important}
.stApp{background:var(--bg-page)!important}
.block-container{max-width:1200px!important;padding-top:16px!important;padding-bottom:32px!important}

/* ── 브랜드 헤더 ── */
.main-title{font-size:20px!important;font-weight:700!important;color:var(--text-main)!important;margin:0!important}
.sub-title{font-size:13px!important;color:var(--text-sub)!important;margin:4px 0 0!important}
.header-logout .stButton>button{
  height:36px!important;min-height:36px!important;padding:0 14px!important;
  background:#fff!important;border:1px solid var(--border)!important;color:var(--text-main)!important;
  font-size:13px!important;font-weight:500!important;border-radius:var(--radius)!important;box-shadow:none!important;
}

/* ── 메인 액션 헤더 ── */
.blog-action-header{margin:20px 0 16px}
.blog-action-title{font-size:28px;font-weight:700;color:var(--text-main);margin:0;line-height:1.3}
div[data-testid="stHorizontalBlock"]:has(.blog-action-header-marker){
  align-items:center!important;margin-bottom:16px!important;
}
div[data-testid="stHorizontalBlock"]:has(.blog-action-header-marker) .stButton>button,
div[data-testid="stHorizontalBlock"]:has(.blog-action-header-marker) .stDownloadButton>button{
  height:40px!important;min-height:40px!important;background:#fff!important;
  border:1px solid var(--border)!important;color:var(--text-main)!important;
  font-size:14px!important;font-weight:500!important;border-radius:var(--radius)!important;box-shadow:none!important;
}

/* ── 패널 ── */
.blog-panel{
  border:1px solid var(--border);border-radius:12px;overflow:hidden;
  background:var(--bg-card);margin-bottom:20px;
}
.blog-panel-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 16px;border-bottom:1px solid var(--border-light);
}
.blog-panel-title{font-size:15px;font-weight:600;color:var(--text-main)}
.blog-panel-count{font-size:13px;color:var(--text-sub)}
.blog-add-row{padding:12px 16px;border-bottom:1px solid var(--border-light);background:var(--bg-soft)}
.blog-add-plus{
  width:44px;height:44px;border-radius:var(--radius);border:1px solid var(--border);
  background:#fff;display:flex;align-items:center;justify-content:center;
  color:var(--text-sub);font-size:22px;line-height:1;
}

/* ── 블로그 목록 행 ── */
.blog-row-marker{display:none}
div[data-testid="stHorizontalBlock"]:has(.blog-row-marker){
  min-height:52px!important;align-items:center!important;
  padding:8px 16px!important;margin:0!important;
  border-bottom:1px solid var(--border-light)!important;background:#fff!important;
}
div[data-testid="stHorizontalBlock"]:has(.blog-row-marker):hover{background:var(--bg-soft)!important}
.bnum-circle{
  width:28px;height:28px;border-radius:50%;background:var(--brand);color:#fff;
  font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:center;
}
.burl{font-size:14px;font-weight:500;color:var(--text-main);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bname{font-size:13px;color:var(--text-sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bowner{font-size:13px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bpills{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.pill{padding:3px 8px;border-radius:6px;font-size:12px;font-weight:500;white-space:nowrap}
.pg{background:var(--rank-in-bg);color:var(--rank-in-text)}
.py{background:#FFF8E1;color:#F57F17}
.pn{background:var(--rank-out-bg);color:var(--rank-out-text)}

/* ── 행 액션 버튼 ── */
div[data-testid="stHorizontalBlock"]:has(.blog-row-marker)
  > div[data-testid="column"]:last-child [data-testid="stHorizontalBlock"]{
  display:inline-flex!important;gap:6px!important;justify-content:flex-end!important;
  border:none!important;background:transparent!important;padding:0!important;
}
div[data-testid="stHorizontalBlock"]:has(.blog-row-marker)
  > div[data-testid="column"]:last-child .stButton>button{
  width:32px!important;height:32px!important;min-height:32px!important;padding:0!important;
  border:1px solid var(--border)!important;border-radius:8px!important;
  background:#fff!important;color:var(--text-sub)!important;font-size:13px!important;box-shadow:none!important;
}

/* ── 아코디언 펼침 영역 ── */
.blog-expanded-marker{display:none}

/* ── 펼침 툴바 ── */
.blog-control-bar-marker{display:none}
div[data-testid="stHorizontalBlock"]:has(.blog-control-bar-marker){
  min-height:48px!important;align-items:center!important;
  padding:8px 16px!important;margin:0!important;background:var(--bg-soft)!important;
  border-bottom:1px solid var(--border-light)!important;
}
.blog-control-info{font-size:13px;color:var(--text-sub);line-height:1.4}
div[data-testid="stHorizontalBlock"]:has(.blog-control-bar-marker) .stButton>button[kind="secondary"]{
  height:36px!important;min-height:36px!important;background:#fff!important;
  border:1px solid var(--border)!important;color:var(--text-main)!important;
  font-size:13px!important;font-weight:500!important;border-radius:var(--radius)!important;
}

/* ── 테이블 카드 ── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-tbl-head-marker){
  margin:0 16px 16px!important;padding:0!important;
  border:1px solid var(--border-light)!important;border-radius:12px!important;
  background:#fff!important;box-shadow:none!important;overflow-x:auto!important;
}
.blog-tbl-head-cell{
  font-size:12px;font-weight:600;color:var(--text-sub);
  min-height:40px;display:flex;align-items:center;white-space:nowrap;
}
div[data-testid="stHorizontalBlock"]:has(.blog-tbl-head-marker){
  align-items:center!important;gap:6px!important;padding:0 12px!important;
  border-bottom:1px solid var(--border-light)!important;background:var(--bg-soft)!important;
  min-height:40px!important;margin:0!important;
}
div[data-testid="stHorizontalBlock"]:has(.blog-tbl-head-marker):hover{background:var(--bg-soft)!important}

/* ── 테이블 데이터 행 ── */
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker)){
  align-items:center!important;gap:6px!important;padding:6px 12px!important;
  border-bottom:1px solid var(--border-light)!important;min-height:56px!important;background:#fff;
}
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker)):hover{
  background:var(--bg-soft)!important;
}
.nc{font-size:13px;color:var(--text-muted);text-align:center}
.ptitle{font-size:14px;font-weight:500;color:var(--text-main);line-height:1.35;
  display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.pdate{font-size:12px;color:var(--text-muted);margin-top:2px}
.sc{display:flex;flex-direction:column;gap:2px}
.si{font-size:12px;color:var(--text-sub);white-space:nowrap}

/* ── 키워드 + 순위 가로 배치 ── */
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker))
  > div[data-testid="column"]:nth-child(n+4) div[data-testid="stVerticalBlock"]{
  flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;
  gap:6px!important;width:100%!important;
}
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker))
  > div[data-testid="column"]:nth-child(n+4) .stTextInput{
  flex:1 1 auto!important;min-width:0!important;margin:0!important;width:auto!important;
}
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker))
  > div[data-testid="column"]:nth-child(n+4) div[data-testid="stWidgetLabel"],
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker))
  > div[data-testid="column"]:nth-child(n+4) .stTextInput label{display:none!important}
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker))
  > div[data-testid="column"]:nth-child(n+4) .stTextInput input{
  height:32px!important;min-height:32px!important;max-height:32px!important;
  font-size:13px!important;padding:0 8px!important;border-radius:8px!important;
  border:1px solid var(--border)!important;background:#fff!important;
}
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7):last-child):not(:has(.blog-tbl-head-marker))
  > div[data-testid="column"]:nth-child(n+4) .blog-kw-badge{
  flex:0 0 auto!important;width:auto!important;margin:0!important;
}
.rb{
  display:inline-flex;align-items:center;height:22px;padding:0 7px;
  border-radius:5px;font-size:11px;font-weight:600;white-space:nowrap;line-height:1;
}
.rank-in{background:var(--rank-in-bg);color:var(--rank-in-text)}
.rank-out{background:var(--rank-out-bg);color:var(--rank-out-text)}

/* ── 라디오 (통합검색/블로그탭) ── */
div[data-testid="stHorizontalBlock"]:has(.blog-control-bar-marker) div[role="radiogroup"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker) div[role="radiogroup"]{
  gap:12px!important;flex-wrap:nowrap!important;
}
div[data-testid="stHorizontalBlock"]:has(.blog-control-bar-marker) div[role="radiogroup"] label,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker) div[role="radiogroup"] label{
  font-size:13px!important;font-weight:500!important;color:var(--text-main)!important;
  background:transparent!important;padding:0!important;margin:0!important;
}
div[data-testid="stHorizontalBlock"]:has(.blog-control-bar-marker) div[role="radiogroup"] label[data-checked="true"],
div[data-testid="stHorizontalBlock"]:has(.blog-control-bar-marker) div[role="radiogroup"] label:has(input:checked),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker) div[role="radiogroup"] label:has(input:checked){
  color:var(--brand)!important;font-weight:600!important;
}

/* ── Primary / Form ── */
.stButton>button[kind="primary"],
.stDownloadButton>button,
.stFormSubmitButton>button[kind="primary"]{
  height:44px!important;min-height:44px!important;padding:0 20px!important;
  background:var(--brand)!important;border:1px solid var(--brand)!important;
  color:#fff!important;font-size:14px!important;font-weight:600!important;
  border-radius:var(--radius)!important;box-shadow:none!important;
}
.stButton>button[kind="primary"]:hover{background:var(--brand-hover)!important;border-color:var(--brand-hover)!important}
div[data-testid="stForm"] .stTextInput input{
  height:44px!important;font-size:14px!important;border-radius:var(--radius)!important;
  border:1px solid var(--border)!important;padding:0 12px!important;
}

/* ── 하단 글로벌 ── */
.blog-global-footer-marker{display:none}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker){
  border:1px solid var(--border)!important;border-radius:12px!important;
  padding:16px!important;background:#fff!important;margin-top:8px!important;box-shadow:none!important;
}
.blog-global-title{font-size:15px;font-weight:600;color:var(--text-main);margin-bottom:8px}
.blog-note{font-size:12px;color:var(--text-muted);text-align:center;margin-top:12px}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker) div[role="radiogroup"]{
  gap:12px!important;flex-wrap:nowrap!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker) div[role="radiogroup"] label{
  font-size:13px!important;font-weight:500!important;color:var(--text-main)!important;
  background:transparent!important;padding:0!important;margin:0!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker) div[role="radiogroup"] label:has(input:checked){
  color:var(--brand)!important;font-weight:600!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-global-footer-marker) .stButton>button[kind="primary"]{
  width:100%!important;margin-top:12px!important;height:48px!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.blog-tbl-head-marker) .stButton>button{
  width:100%!important;margin:8px 12px 12px!important;height:36px!important;
  background:var(--bg-soft)!important;border:1px solid var(--border-light)!important;
  color:var(--text-sub)!important;font-size:13px!important;border-radius:8px!important;
}
</style>
"""

ICON_EYE = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" style="vertical-align:-2px;margin-right:3px">'
    '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>'
)
ICON_MESSAGE = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" style="vertical-align:-2px;margin-right:3px">'
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
)


def inject_blog_ui_css() -> None:
    import streamlit as st

    st.markdown(BLOG_UI_CSS, unsafe_allow_html=True)


def render_pills_html(labels: list[tuple[str, str]]) -> str:
    if not labels:
        return '<span class="pill pn">키워드 미입력</span>'
    return "".join(f'<span class="pill {css}">{text}</span>' for css, text in labels)


def rank_badge_html(rank_label: str, css_class: str) -> str:
    badge_cls = "rank-in" if css_class in {"r1", "rt", "rm"} else "rank-out"
    if rank_label == "-":
        badge_cls = "rank-out"
    return f'<div class="blog-kw-badge"><span class="rb {badge_cls}">{rank_label}</span></div>'
