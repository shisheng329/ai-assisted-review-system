from __future__ import annotations

import logging
import re
import sqlite3
import sys
from html import escape
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import session_state as ss
from app import ui
from app.modules import bertopic_analysis, dashboard, data_input, llm_screening, pdf_extraction, profile, project_list
from app.services import db
from app.services.auth import authenticate_user, bootstrap_auth, login_user, logout_user, register_user
from app.services.i18n import language_options, set_language, t
from app.services.projects import get_project


logger = logging.getLogger(__name__)


MODULES = {
    "dashboard": dashboard.render,
    "data_input": data_input.render,
    "screening_settings": llm_screening.render_settings,
    "screening": llm_screening.render,
    "bertopic": bertopic_analysis.render,
    "pdf_extraction": pdf_extraction.render,
}

NAV_MARKS = {
    "projects": "P",
    "profile": "U",
    "dashboard": "D",
    "data_input": "I",
    "screening_settings": "F",
    "screening": "S",
    "bertopic": "C",
    "pdf_extraction": "X",
}


def init_session() -> None:
    ss.set_default(ss.LANGUAGE, "zh-CN")
    ss.set_default(ss.CURRENT_MODULE, "projects")
    ss.set_default(ss.CURRENT_PROJECT_ID, None)


def _user_initial(user: dict) -> str:
    display = (user.get("display_name") or user.get("username") or "U").strip()
    return display[:1].upper()


def _set_auth_view(view: str) -> None:
    ss.set_value(ss.AUTH_VIEW, view)


def _is_valid_email(email: str) -> bool:
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()) is not None


def _current_language_label(language_map: dict[str, str], current_lang: str) -> str:
    return next((label for label, value in language_map.items() if value == current_lang), next(iter(language_map.keys())))


def _render_auth_topbar() -> None:
    language_map = language_options()
    current_lang = ss.get(ss.LANGUAGE, "zh-CN")
    current_label = _current_language_label(language_map, current_lang)
    brand_col, spacer_col, lang_col, login_col, register_col = st.columns([3.2, 2.2, 1.5, 1.0, 1.25], vertical_alignment="center")
    with brand_col:
        st.markdown(
            f"""
            <div class='brand-block brand-compact'>
              <span class='brand-mark'>L</span>
              <span class='brand-title'>{escape(t('app_title'))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with spacer_col:
        st.empty()
    with lang_col:
        selected_label = st.radio(
            t("language"),
            list(language_map.keys()),
            index=list(language_map.keys()).index(current_label),
            horizontal=True,
            label_visibility="collapsed",
            key="auth_language_choice",
        )
        selected_language = language_map[selected_label]
        if selected_language != current_lang:
            set_language(selected_language)
            st.rerun()
    with login_col:
        if st.button(t("login"), key="auth_nav_login", use_container_width=True):
            _set_auth_view("login")
            st.rerun()
    with register_col:
        if st.button(t("register"), key="auth_nav_register", use_container_width=True):
            _set_auth_view("register")
            st.rerun()


def _render_auth_home() -> None:
    st.markdown(
        f"""
        <section class='app-hero'>
          <p class='kicker'>{escape(t('homepage_kicker'))}</p>
          <h2>{escape(t('homepage_headline'))}</h2>
          <p>{escape(t('homepage_intro'))}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    flow_col, use_col = st.columns([1.05, 0.95], gap="medium")
    with flow_col:
        ui.surface(
            t("homepage_flow_title"),
            "\n".join([t("homepage_flow_1"), t("homepage_flow_2"), t("homepage_flow_3")]),
        )
    with use_col:
        ui.surface(
            t("homepage_use_cases_title"),
            "\n".join([t("homepage_use_cases_1"), t("homepage_use_cases_2"), t("homepage_use_cases_3")]),
        )


def _render_login_form() -> None:
    ui.page_header(t("login"), t("homepage_intro"))
    with st.form("login_form"):
        email = st.text_input(t("email"), key="login_email")
        password = st.text_input(t("password"), type="password", key="login_password")
        submitted = st.form_submit_button(t("sign_in"), use_container_width=True)
    if submitted:
        if not email.strip() or not password:
            st.error(t("required_fields_missing"))
            return
        user = authenticate_user(email, password)
        if user:
            login_user(user)
            st.rerun()
        st.error(t("invalid_credentials"))
    if st.button(t("back_home"), key="login_back_home"):
        _set_auth_view("home")
        st.rerun()


def _render_register_form() -> None:
    ui.page_header(t("register"), t("homepage_intro"))
    with st.form("register_form"):
        username = st.text_input(t("username"), key="register_username")
        email = st.text_input(t("email"), key="register_email")
        password = st.text_input(t("password"), type="password", key="register_password")
        confirm_password = st.text_input(t("confirm_password"), type="password", key="register_confirm_password")
        submitted = st.form_submit_button(t("sign_up"), use_container_width=True)
    if submitted:
        if not username.strip() or not email.strip() or not password or not confirm_password:
            st.error(t("required_fields_missing"))
            return
        if not _is_valid_email(email):
            st.error(t("invalid_email"))
            return
        if password != confirm_password:
            st.error(t("passwords_do_not_match"))
            return
        try:
            register_user(username, email, password, display_name=username, preferred_language=ss.get(ss.LANGUAGE, "zh-CN"))
            user = authenticate_user(email, password)
            if user:
                login_user(user)
                st.rerun()
            st.error(t("operation_failed"))
        except sqlite3.IntegrityError:
            st.error(t("username_or_email_exists"))
        except Exception:
            logger.exception("User registration failed")
            st.error(t("operation_failed"))
    if st.button(t("back_home"), key="register_back_home"):
        _set_auth_view("home")
        st.rerun()


def render_auth() -> None:
    ss.set_default(ss.AUTH_VIEW, "home")
    _render_auth_topbar()
    st.markdown("<div class='row-separator'></div>", unsafe_allow_html=True)
    auth_view = ss.get(ss.AUTH_VIEW, "home")
    if auth_view == "login":
        _render_login_form()
    elif auth_view == "register":
        _render_register_form()
    else:
        _render_auth_home()


def render_shell_header(user: dict, title: str, project: dict | None = None) -> None:
    subtitle = f"{t('active_project')}: {project['name']}" if project else ""
    title_col, account_col = st.columns([5, 1.45], vertical_alignment="center")
    with title_col:
        st.markdown(
            f"""
            <section class="shell-title">
              <h1>{escape(title)}</h1>
              <p>{escape(subtitle)}</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
    display_name = user.get("display_name") or user.get("username") or t("current_user")
    with account_col:
        with st.popover(f"{_user_initial(user)}  {display_name}", use_container_width=True):
            st.caption(user.get("email", ""))
            if st.button(t("profile"), key=f"top_profile_{project['id'] if project else 'root'}", use_container_width=True):
                ss.set_value(ss.CURRENT_MODULE, "profile")
                st.rerun()
            if st.button(t("logout"), key=f"top_logout_{project['id'] if project else 'root'}", use_container_width=True):
                logout_user()
                st.rerun()


def _render_nav_item(option: str, current: str, prefix: str) -> None:
    label = t(option)
    mark = NAV_MARKS.get(option, label[:1].upper())
    if option == current:
        st.sidebar.markdown(
            f"<div class='nav-active'><span class='nav-mark'>{escape(mark)}</span><span>{escape(label)}</span></div>",
            unsafe_allow_html=True,
        )
    elif st.sidebar.button(f"{mark}  {label}", key=f"{prefix}_{option}", use_container_width=True):
        ss.set_value(ss.CURRENT_MODULE, option)
        st.rerun()


def render_sidebar(user: dict, options: list[str], current: str, project: dict | None = None) -> None:
    st.sidebar.markdown(
        f"""
        <div class="brand-block">
          <span class="brand-mark">L</span>
          <span class="brand-title">Literature Lab</span>
        </div>
        <div class="sidebar-caption">{escape(t('app_title'))}</div>
        """,
        unsafe_allow_html=True,
    )
    for option in options:
        _render_nav_item(option, current, "nav_project" if project else "nav_main")

    st.sidebar.markdown("---")
    if project and st.sidebar.button(t("back_to_projects"), use_container_width=True):
        ss.set_value(ss.CURRENT_PROJECT_ID, None)
        ss.set_value(ss.CURRENT_MODULE, "projects")
        st.rerun()


def render_authenticated() -> None:
    user = ss.get(ss.CURRENT_USER)
    current_project_id = ss.get(ss.CURRENT_PROJECT_ID)
    project = get_project(int(current_project_id), int(user["id"])) if current_project_id else None
    if current_project_id and not project:
        ss.set_value(ss.CURRENT_PROJECT_ID, None)
        ss.set_value(ss.CURRENT_MODULE, "projects")
        project = None

    if project is None:
        options = ["projects", "profile"]
        current = ss.get(ss.CURRENT_MODULE, "projects")
        current = current if current in options else "projects"
        ss.set_value(ss.CURRENT_MODULE, current)
        render_sidebar(user, options, current)
        ui.apply_page_width("compact" if current == "profile" else "standard")
        render_shell_header(user, t(current), None)
        if current == "projects":
            project_list.render(user)
        else:
            profile.render(user)
        return

    options = ["dashboard", "data_input", "screening_settings", "screening", "bertopic", "pdf_extraction", "profile"]
    current = ss.get(ss.CURRENT_MODULE, "dashboard")
    current = current if current in options else "dashboard"
    ss.set_value(ss.CURRENT_MODULE, current)
    render_sidebar(user, options, current, project)
    width_mode = {
        "dashboard": "wide",
        "data_input": "wide",
        "screening_settings": "compact",
        "screening": "standard",
        "bertopic": "wide",
        "pdf_extraction": "compact",
        "profile": "compact",
    }.get(current, "standard")
    ui.apply_page_width(width_mode)
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
    if ss.get(ss.CURRENT_USER):
        render_authenticated()
    else:
        render_auth()


if __name__ == "__main__":
    main()
