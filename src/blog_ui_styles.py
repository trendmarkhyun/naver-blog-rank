"""블로그 순위 체커 UI 스타일 (목업 기반)."""

BLOG_UI_CSS = """
<style>
/* ── 레이아웃 ── */
.blog-wrap{padding:0.5rem 0 1.5rem 0}
.blog-topbar{display:flex;align-items:center;gap:8px;margin-bottom:1.25rem;flex-wrap:wrap}
.blog-page-title{font-size:16px;font-weight:500;color:#222;flex:1}

/* ── 패널 ── */
.blog-panel{border:0.5px solid #e0e0e0;border-radius:12px;overflow:hidden;background:#fff;margin-bottom:1.25rem}
.blog-panel-header{display:flex;align-items:center;justify-content:space-between;padding:9px 14px;background:#f7f7f7;border-bottom:0.5px solid #e0e0e0}
.blog-panel-title{font-size:13px;font-weight:500;color:#222}
.blog-panel-count{font-size:11px;color:#888}

/* ── + 추가 행 ── */
.blog-add-row{background:#f7f7f7;border-bottom:0.5px solid #e8e8e8;padding:0.25rem 0}
.blog-add-plus{width:28px;height:28px;border-radius:50%;border:0.5px solid #ddd;background:#fff;display:flex;align-items:center;justify-content:center;color:#666;font-size:18px;font-weight:400;line-height:1;margin-top:4px}

/* ── 블로그 행 ── */
.blog-row-wrap{border-bottom:0.5px solid #ececec;background:#fff}
.blog-row-wrap:last-child{border-bottom:none}
.blog-row-wrap:hover{background:#f7f7f7}
.bnum{display:flex;align-items:center;justify-content:center;padding:4px 0}
.bnum-circle{width:18px;height:18px;border-radius:50%;background:#03C75A;color:#fff;font-size:10px;font-weight:500;display:flex;align-items:center;justify-content:center}
.burl{font-size:12px;font-weight:500;color:#222;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:8px 0}
.bname{font-size:12px;color:#666;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:8px 0}
.bowner{font-size:11px;color:#888;white-space:nowrap;padding:8px 0}
.bpills{display:flex;gap:3px;flex-wrap:wrap;padding:6px 0}
.pill{height:17px;padding:0 6px;border-radius:8px;font-size:9px;font-weight:500;display:inline-flex;align-items:center;white-space:nowrap}
.pg{background:#D4EDDA;color:#155724}
.py{background:#FFF3CD;color:#856404}
.pn{background:#f0f0f0;color:#888}

/* ── 펼침 상세 ── */
.blog-detail{border-top:0.5px solid #ececec;background:#fff;padding:0 0 0.5rem 0}
.blog-detail-bar{background:#f7f7f7;border-bottom:0.5px solid #ececec;padding:7px 12px;margin-bottom:0}
.blog-detail-info{font-size:11px;color:#666}

/* ── 게시글 테이블 ── */
.blog-tbl-head{display:grid;grid-template-columns:4% 27% 10% 14.75% 14.75% 14.75% 14.75%;padding:6px 8px;background:#fff;border-bottom:0.5px solid #ececec;font-size:11px;font-weight:500;color:#666;gap:4px}
.blog-tbl-row{border-bottom:0.5px solid #ececec;padding:4px 0}
.blog-tbl-row:hover{background:#f7f7f7}
.ptitle{font-size:12px;font-weight:500;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pdate{font-size:10px;color:#888;margin-top:2px}
.sc{display:flex;flex-direction:column;gap:2px}
.si{font-size:11px;color:#666}
.kc{display:flex;flex-direction:column;gap:3px}
.rb{height:18px;display:flex;align-items:center;justify-content:center;border-radius:4px;font-size:10px;font-weight:500;width:100%}
.r1{background:#FFF3CD;color:#856404}
.rt{background:#D4EDDA;color:#155724}
.rm{background:#E1F5EE;color:#0F6E56}
.rn{background:#f0f0f0;color:#888}
.nc{text-align:center;color:#888;font-size:11px;padding-top:4px}

/* ── 하단 global-bar ── */
.blog-global-bar{padding:0 2px;margin:8px 0}
.blog-note{font-size:11px;color:#888;text-align:right;margin-top:8px}

/* ── Streamlit 위젯 → 목업 톤 맞춤 ── */
div[data-testid="stForm"] .stTextInput input{
  height:30px;font-size:12px;border-radius:8px;
}
div[data-testid="column"] .stButton > button[kind="secondary"]{
  height:34px;font-size:12px;border-radius:8px;
}
div[data-testid="column"] .stButton > button[kind="primary"]{
  height:30px;font-size:12px;border-radius:8px;background:#03C75A;border-color:#03C75A;
}
div[data-testid="column"] .stDownloadButton > button{
  height:34px;font-size:12px;border-radius:8px;
}
/* ── 행 액션 버튼 (X, ▼) ── */
.blog-row-wrap div[data-testid="column"]:last-child{
  min-width:76px;padding-left:4px;
}
.blog-row-wrap div[data-testid="column"]:last-child [data-testid="stHorizontalBlock"]{
  gap:12px !important;justify-content:flex-end;align-items:center;flex-wrap:nowrap;
}
.blog-row-wrap div[data-testid="column"]:last-child [data-testid="column"]{
  flex:0 0 32px !important;min-width:32px !important;max-width:36px !important;width:32px !important;
}
.blog-row-wrap div[data-testid="column"]:last-child .stButton{
  width:32px;min-width:32px;
}
.blog-row-wrap div[data-testid="column"]:last-child .stButton > button{
  min-height:28px;height:28px;min-width:28px;max-width:32px;width:32px !important;
  padding:0;font-size:13px;border:0.5px solid #e0e0e0;border-radius:6px;
  background:#fff;color:#666;box-shadow:none;margin:0;
}
.blog-row-wrap div[data-testid="column"]:last-child .stButton > button:hover{
  background:#f0f0f0;color:#444;border-color:#ccc;
}
.blog-row-wrap div[data-testid="column"]:last-child .stButton:first-child > button:hover{
  color:#dc3545;border-color:#f5c6cb;background:#fff5f5;
}
/* 세그먼트 라디오 (통합검색/블로그탭) */
div.blog-seg-radio div[role="radiogroup"]{
  gap:0;border:0.5px solid #ddd;border-radius:6px;overflow:hidden;flex-wrap:nowrap;
}
div.blog-seg-radio div[role="radiogroup"] label{
  background:#fff;margin:0;padding:4px 10px;font-size:11px;border-right:0.5px solid #ddd;
}
div.blog-seg-radio div[role="radiogroup"] label:last-child{border-right:none}
div.blog-seg-radio div[role="radiogroup"] label[data-checked="true"],
div.blog-seg-radio div[role="radiogroup"] label:has(input:checked){
  background:#03C75A;color:#fff;font-weight:500;
}
div.blog-global-seg div[role="radiogroup"] label{
  padding:6px 14px;font-size:12px;
}
/* 키워드 입력 */
div.blog-kw-input input{
  height:22px;font-size:11px;border-radius:4px;padding:0 5px;
}
</style>
"""


def inject_blog_ui_css() -> None:
    import streamlit as st

    st.markdown(BLOG_UI_CSS, unsafe_allow_html=True)


def render_pills_html(labels: list[tuple[str, str]]) -> str:
    parts = []
    for css_class, text in labels:
        parts.append(f'<span class="pill {css_class}">{text}</span>')
    return "".join(parts)


def rank_badge_html(rank_label: str, css_class: str) -> str:
    return f'<div class="rb {css_class}">{rank_label}</div>'
