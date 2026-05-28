"""Streamlit 개발자 단축키(C=캐시 삭제) 오동작 방지."""

from __future__ import annotations

import streamlit.components.v1 as components

HANDLER_KEY = "__blogRankClearCacheBlocker"


def ensure_streamlit_keyboard_guard() -> None:
    """매 rerun마다 부모 document에 키 차단기를 재부착."""
    components.html(
        f"""
<script>
(function () {{
  const root = window.parent;
  const doc = root.document;
  const handlerKey = "{HANDLER_KEY}";

  function isTypingContext(event) {{
    const path = event.composedPath ? event.composedPath() : [event.target];
    for (let i = 0; i < path.length; i++) {{
      const node = path[i];
      if (!node || !node.tagName) continue;
      const tag = node.tagName.toUpperCase();
      if (tag === "INPUT" || tag === "TEXTAREA") return true;
      if (node.isContentEditable) return true;
    }}
    return false;
  }}

  function blocker(event) {{
    if (event.key !== "c" && event.key !== "C") return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (isTypingContext(event)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    event.stopPropagation();
  }}

  const previous = root[handlerKey];
  if (previous) {{
    doc.removeEventListener("keydown", previous, true);
    root.removeEventListener("keydown", previous, true);
  }}
  root[handlerKey] = blocker;
  doc.addEventListener("keydown", blocker, true);
  root.addEventListener("keydown", blocker, true);
}})();
</script>
        """,
        height=0,
        width=0,
    )
