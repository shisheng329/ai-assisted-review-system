from __future__ import annotations

import sqlite3
import sys
from html import escape
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import ui
from app.modules import bertopic_analysis, dashboard, data_input, llm_screening, pdf_extraction, profile, project_list
from app.services import db
from app.services.auth import authenticate_user, bootstrap_auth, login_user, logout_user, register_user
from app.services.i18n import language_options, set_language, t
from app.services.projects import get_project


MODULES = {
    "dashboard": dashboard.render,
    "data_input": data_input.render,
    "screening": llm_screening.render,
    "bertopic": bertopic_analysis.render,
    "pdf_extraction": pdf_extraction.render,
}

NAV_MARKS = {
    "projects": "P",
    "profile": "U",
    "dashboard": "D",
    "data_input": "I",
    "screening": "S",
    "bertopic": "C",
    "pdf_extraction": "X",
}


def init_session() -> None:
    st.session_state.setdefault("language", "zh-CN")
    st.session_state.setdefault("current_module", "projects")
    st.session_state.setdefault("current_project_id", None)


def _user_initial(user: dict) -> str:
    display = (user.get("display_name") or user.get("username") or "U").strip()
    return display[:1].upper()


def render_auth() -> None:
    st.markdown(
        f"""
        <div class='hero-card'>
          <div class='brand-block' style='padding-bottom:0.5rem;margin-bottom:0;'>
            <span class='brand-mark'>L</span>
            <span class='brand-title'>{escape(t('app_title'))}</span>
          </div>
          <p>{escape(t('theme_hint'))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    language_map = language_options()
    current_lang = st.session_state.get("language", "zh-CN")
    current_label = next((label for label, value in language_map.items() if value == current_lang), "中文")
    label = st.selectbox(t("language"), list(language_map.keys()), index=list(language_map.keys()).index(current_label))
    set_language(language_map[label])

    login_col, register_col = st.columns(2)
    with login_col:
        st.markdown(f"### {t('login')}")
        with st.form("login_form"):
            username = st.text_input(t("username"))
            password = st.text_input(t("password"), type="password")
            submitted = st.form_submit_button(t("sign_in"), use_container_width=True)
        if submitted:
            user = authenticate_user(username, password)
            if user:
                login_user(user)
                st.rerun()
            st.error(t("operation_failed"))
    with register_col:
        st.markdown(f"### {t('register')}")
        with st.form("register_form"):
            username = st.text_input(t("username"), key="register_username")
            email = st.text_input(t("email"))
            display_name = st.text_input(t("display_name"))
            password = st.text_input(t("password"), type="password", key="register_password")
            submitted = st.form_submit_button(t("sign_up"), use_container_width=True)
        if submitted:
            try:
                register_user(username, email, password, display_name, st.session_state["language"])
                user = authenticate_user(username, password)
                if user:
                    login_user(user)
                    st.rerun()
            except sqlite3.IntegrityError:
                st.error(t("username_or_email_exists"))
            except Exception:
                st.error(t("operation_failed"))


def render_shell_header(user: dict, title: str, project: dict | None = None) -> None:
    subtitle = f"{t('active_project')}: {project['name']}" if project else t("projects")
    st.markdown(
        f"""
        <div class="shell-header">
          <div class="shell-title">
            <h1>{escape(title)}</h1>
            <p>{escape(subtitle)}</p>
          </div>
          <div class="shell-user">
            <span>{escape(user['display_name'])} / {escape(user['username'])}</span>
            <span class="avatar-dot">{escape(_user_initial(user))}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_nav_item(option: str, current: str, prefix: str) -> None:
    label = t(option)
    mark = NAV_MARKS.get(option, label[:1].upper())
    if option == current:
        st.sidebar.markdown(
            f"<div class='nav-active'><span class='nav-mark'>{escape(mark)}</span><span>{escape(label)}</span></div>",
            unsafe_allow_html=True,
        )
    elif st.sidebar.button(f"{mark}  {label}", key=f"{prefix}_{option}", use_container_width=True):
        st.session_state["current_module"] = option
        st.rerun()


def render_sidebar(user: dict, options: list[str], current: str, project: dict | None = None) -> None:
    st.sidebar.markdown(
        f"""
        <div class="brand-block">
          <span class="brand-mark">L</span>
          <span class="brand-title">Dashboard</span>
        </div>
        <div class="sidebar-caption">{escape(t('app_title'))}</div>
        """,
        unsafe_allow_html=True,
    )
    for option in options:
        _render_nav_item(option, current, "nav_project" if project else "nav_main")

    st.sidebar.markdown("---")
    if project and st.sidebar.button(t("back_to_projects"), use_container_width=True):
        st.session_state["current_project_id"] = None
        st.session_state["current_module"] = "projects"
        st.rerun()
    if st.sidebar.button(t("logout"), use_container_width=True):
        logout_user()
        st.rerun()


def render_authenticated() -> None:
    user = st.session_state["current_user"]
    current_project_id = st.session_state.get("current_project_id")
    project = get_project(int(current_project_id), int(user["id"])) if current_project_id else None
    if current_project_id and not project:
        st.session_state["current_project_id"] = None
        st.session_state["current_module"] = "projects"
        project = None

    if project is None:
        options = ["projects", "profile"]
        current = st.session_state.get("current_module", "projects")
        current = current if current in options else "projects"
        st.session_state["current_module"] = current
        render_sidebar(user, options, current)
        render_shell_header(user, t(current), None)
        if current == "projects":
            project_list.render(user)
        else:
            profile.render(user)
        return

    options = ["dashboard", "data_input", "screening", "bertopic", "pdf_extraction", "profile"]
    current = st.session_state.get("current_module", "dashboard")
    current = current if current in options else "dashboard"
    st.session_state["current_module"] = current
    render_sidebar(user, options, current, project)
    render_shell_header(user, t(current), project)
    if current == "profile":
        profile.render(user)
    else:
        MODULES[current](project, user)


def main() -> None:
    st.set_page_config(page_title="20260423 System Demo", page_icon="L", layout="wide")
    db.init_db()
    init_session()
    bootstrap_auth()
    ui.apply_global_styles()
    if st.session_state.get("current_user"):
        render_authenticated()
    else:
        render_auth()


if __name__ == "__main__":
    main()
