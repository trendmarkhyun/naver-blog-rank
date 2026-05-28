"""브라우저 쿠키 기반 로그인 정보 저장."""

from __future__ import annotations

from datetime import datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st

COOKIE_NAME_KEY = "siwol_login_name"
COOKIE_CODE_KEY = "siwol_login_code"
COOKIE_MANAGER_KEY = "siwol_cookie_manager"
COOKIE_MANAGER_STATE_KEY = "siwol_cookie_manager_instance"
COOKIE_READY_KEY = "siwol_cookies_ready"
LOGIN_MANUAL_MODE_KEY = "login_manual_mode"
COOKIE_MAX_AGE_DAYS = 365


def get_cookie_manager() -> stx.CookieManager:
    if COOKIE_MANAGER_STATE_KEY not in st.session_state:
        st.session_state[COOKIE_MANAGER_STATE_KEY] = stx.CookieManager(
            key=COOKIE_MANAGER_KEY
        )
    return st.session_state[COOKIE_MANAGER_STATE_KEY]


def ensure_cookies_ready() -> None:
    if st.session_state.get(COOKIE_READY_KEY):
        return

    cookies = get_cookie_manager().get_all()
    if cookies is None:
        st.stop()

    st.session_state[COOKIE_READY_KEY] = True


def get_saved_login() -> tuple[str, str] | None:
    ensure_cookies_ready()
    manager = get_cookie_manager()
    name = (manager.get(COOKIE_NAME_KEY) or "").strip()
    code = (manager.get(COOKIE_CODE_KEY) or "").strip()
    if name and code:
        return name, code
    return None


def save_login(display_name: str, team_code: str) -> None:
    ensure_cookies_ready()
    manager = get_cookie_manager()
    expires = datetime.now() + timedelta(days=COOKIE_MAX_AGE_DAYS)
    manager.set(COOKIE_NAME_KEY, display_name.strip(), expires_at=expires)
    manager.set(COOKIE_CODE_KEY, team_code.strip(), expires_at=expires)
    st.session_state[LOGIN_MANUAL_MODE_KEY] = False


def mask_team_code(team_code: str) -> str:
    length = max(min(len(team_code), 12), 6)
    return "●" * length


def is_manual_login_mode() -> bool:
    return bool(st.session_state.get(LOGIN_MANUAL_MODE_KEY))


def enable_manual_login_mode() -> None:
    st.session_state[LOGIN_MANUAL_MODE_KEY] = True


def clear_saved_login() -> None:
    ensure_cookies_ready()
    manager = get_cookie_manager()
    manager.delete(COOKIE_NAME_KEY)
    manager.delete(COOKIE_CODE_KEY)
    st.session_state.pop(LOGIN_MANUAL_MODE_KEY, None)
