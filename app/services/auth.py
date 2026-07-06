from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from . import db
from .utils import utc_now_iso


COOKIE_NAME = "demo_auth_token"


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    salt, digest = stored_hash.split("$", 1)
    expected = _hash_password(password, salt)
    return hmac.compare_digest(expected, f"{salt}${digest}")


def register_user(
    username: str,
    email: str,
    password: str,
    display_name: str | None = None,
    preferred_language: str = "zh-CN",
) -> int:
    clean_username = username.strip()
    clean_email = email.strip().lower()
    clean_display_name = (display_name or clean_username).strip()
    salt = secrets.token_hex(8)
    password_hash = _hash_password(password, salt)
    return db.execute(
        """
        INSERT INTO users (username, email, password_hash, display_name, preferred_language, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (clean_username, clean_email, password_hash, clean_display_name, preferred_language, utc_now_iso()),
    )


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM users WHERE lower(email) = lower(?)", (email.strip(),))
    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return dict(row)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    db.execute(
        "INSERT INTO sessions (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user_id, token, expires_at, utc_now_iso()),
    )
    return token


def get_user_by_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    row = db.fetch_one(
        """
        SELECT users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ? AND sessions.expires_at > ?
        """,
        (token, now),
    )
    if not row:
        return None
    return dict(row)


def set_cookie(token: str | None) -> None:
    max_age = 14 * 24 * 60 * 60 if token else 0
    value = token or ""
    components.html(
        f"""
        <script>
        document.cookie = "{COOKIE_NAME}={value}; path=/; max-age={max_age}; SameSite=Lax";
        </script>
        """,
        height=0,
        width=0,
    )


def get_cookie_token() -> str | None:
    try:
        return st.context.cookies.get(COOKIE_NAME)
    except Exception:
        return st.session_state.get(COOKIE_NAME)


def bootstrap_auth() -> None:
    if st.session_state.get("current_user"):
        return
    token = get_cookie_token()
    if token:
        st.session_state[COOKIE_NAME] = token
        user = get_user_by_session(token)
        if user:
            st.session_state["current_user"] = user
            st.session_state["language"] = user.get("preferred_language", "zh-CN")


def login_user(user: dict[str, Any]) -> None:
    token = create_session(int(user["id"]))
    st.session_state["current_user"] = user
    st.session_state[COOKIE_NAME] = token
    st.session_state["language"] = user.get("preferred_language", "zh-CN")
    set_cookie(token)


def logout_user() -> None:
    token = st.session_state.get(COOKIE_NAME) or get_cookie_token()
    if token:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    st.session_state.pop("current_user", None)
    st.session_state.pop(COOKIE_NAME, None)
    st.session_state.pop("current_project_id", None)
    set_cookie(None)
