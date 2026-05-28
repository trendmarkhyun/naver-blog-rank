"""Streamlit 개발자 단축키(C=캐시 삭제) 오동작 방지 + 디버그 로그."""

from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

SESSION_FLAG = "_streamlit_keyboard_guard_installed"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEBUG_LOG_PATHS = (
    PROJECT_ROOT / "debug-dc5c4d.log",
    PROJECT_ROOT.parent / "naver-place-rank" / "debug-dc5c4d.log",
)
DEBUG_INGEST_URL = "http://127.0.0.1:7415/ingest/a804cf9b-475a-4381-ad3c-f6cfbed9ecf4"
DEBUG_SESSION_ID = "dc5c4d"


def agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    *,
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
    }
    try:
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        for log_path in DEBUG_LOG_PATHS:
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
            except OSError:
                continue
    except OSError:
        pass
    # #endregion


def ensure_streamlit_keyboard_guard() -> None:
    """입력창 밖에서 C 키가 Streamlit 'Clear caches'를 열지 않도록 차단."""
    if st.session_state.get(SESSION_FLAG):
        return

    st.session_state[SESSION_FLAG] = True
    agent_debug_log(
        "A",
        "streamlit_guard.py:ensure_streamlit_keyboard_guard",
        "keyboard guard installed",
        {"toolbar_note": "blocks solo C outside inputs"},
        run_id="post-fix",
    )

    components.html(
        f"""
<script>
(function () {{
  const root = window.parent;
  const doc = root.document;
  if (doc.__blogRankKeyboardGuard) return;
  doc.__blogRankKeyboardGuard = true;

  const ingest = "{DEBUG_INGEST_URL}";
  const sessionId = "{DEBUG_SESSION_ID}";

  function isEditableTarget(target) {{
    if (!target) return false;
    const tag = target.tagName || "";
    if (tag === "INPUT" || tag === "TEXTAREA") return true;
    if (target.isContentEditable) return true;
    return !!target.closest("input, textarea, [contenteditable='true']");
  }}

  function logKey(event, blocked) {{
    const target = event.target;
    const tag = target && target.tagName ? target.tagName : "";
    fetch(ingest, {{
      method: "POST",
      headers: {{
        "Content-Type": "application/json",
        "X-Debug-Session-Id": sessionId,
      }},
      body: JSON.stringify({{
        sessionId,
        hypothesisId: blocked ? "A" : "B",
        location: "streamlit_guard.js:keydown",
        message: blocked ? "blocked clear-cache shortcut" : "allowed key in editable field",
        data: {{
          key: event.key,
          tag,
          isEditable: isEditableTarget(target),
          blocked,
        }},
        timestamp: Date.now(),
        runId: "post-fix",
      }}),
    }}).catch(function () {{}});
  }}

  function onKeyDown(event) {{
    if (event.key !== "c" && event.key !== "C") return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;

    if (isEditableTarget(event.target)) {{
      logKey(event, false);
      return;
    }}

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    logKey(event, true);
  }}

  doc.addEventListener("keydown", onKeyDown, true);
  root.addEventListener("keydown", onKeyDown, true);
}})();
</script>
        """,
        height=0,
        width=0,
    )
