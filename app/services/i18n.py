from __future__ import annotations

import streamlit as st

from app.i18n.messages import MESSAGES


def current_language() -> str:
    return st.session_state.get("language", "zh-CN")


def set_language(language: str) -> None:
    st.session_state["language"] = language if language in MESSAGES else "zh-CN"


def t(key: str) -> str:
    language = current_language()
    return MESSAGES.get(language, MESSAGES["zh-CN"]).get(key, key)


def language_options() -> dict[str, str]:
    return {"中文": "zh-CN", "English": "en"}
