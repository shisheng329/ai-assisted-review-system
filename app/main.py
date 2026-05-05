from __future__ import annotations

import sqlite3
import sys
from html import escape
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-green: #10b981;
            --app-green-dark: #059669;
            --app-green-soft: #d1fae5;
            --app-bg: #f4f6f8;
            --app-card: #ffffff;
            --app-text: #111827;
            --app-muted: #6b7280;
            --app-border: #e5e7eb;
        }
        .stApp { background: var(--app-bg); color: var(--app-text); }
        header[data-testid="stHeader"] {
            background: transparent;
            height: 0;
        }
        .block-container {
            padding-top: 1.1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 1360px;
        }
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--app-border);
            box-shadow: 10px 0 30px rgba(15, 23, 42, 0.04);
            min-width: 220px !important;
            width: 220px !important;
            max-width: 220px !important;
        }
        section[data-testid="stSidebar"] > div {
            padding: 1.1rem 0.7rem 1rem;
            width: 220px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button {
            width: 100%;
            justify-content: flex-start;
            border: 0;
            border-radius: 8px;
            color: #334155;
            background: transparent;
            min-height: 2rem;
            padding: 0.35rem 0.6rem;
            font-weight: 500;
            box-shadow: none;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
            color: var(--app-green-dark);
            background: #ecfdf5;
        }
        .brand-block {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.05rem 0.1rem 0.9rem;
            margin-bottom: 0.2rem;
        }
        .brand-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.85rem;
            height: 1.85rem;
            border-radius: 8px;
            background: var(--app-green);
            color: #ffffff;
            font-weight: 800;
        }
        .brand-title {
            color: #111827;
            font-size: 1.05rem;
            font-weight: 800;
            letter-spacing: 0;
            white-space: nowrap;
        }
        .sidebar-caption {
            color: var(--app-muted);
            font-size: 0.7rem;
            line-height: 1.35;
            margin: 0 0 0.55rem;
        }
        .nav-active {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            min-height: 2rem;
            padding: 0 0.55rem;
            margin: 0.12rem 0;
            border-radius: 8px;
            background: var(--app-green-soft);
            color: var(--app-green-dark);
            border-left: 3px solid var(--app-green);
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .nav-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.1rem;
            height: 1.1rem;
            border-radius: 6px;
            background: rgba(16, 185, 129, 0.13);
            font-size: 0.7rem;
            font-weight: 800;
            flex: 0 0 auto;
        }
        .shell-header {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: center;
            margin-bottom: 1rem;
        }
        .shell-title h1 {
            margin: 0;
            font-size: 1.45rem;
            line-height: 1.2;
            font-weight: 800;
            letter-spacing: 0;
        }
        .shell-title p {
            margin: 0.22rem 0 0;
            color: var(--app-muted);
            font-size: 0.88rem;
        }
        .shell-user {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: var(--app-muted);
            font-size: 0.86rem;
            white-space: nowrap;
        }
        .avatar-dot {
            width: 2.25rem;
            height: 2.25rem;
            border-radius: 50%;
            background: #111827;
            color: #ffffff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
        }
        .page-head {
            margin: 0 0 1rem;
        }
        .page-head h1 {
            margin: 0;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: 0;
        }
        .page-head p {
            color: var(--app-muted);
            margin: 0.25rem 0 0;
        }
        .section-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            margin: 1.05rem 0 0.45rem;
        }
        .section-head h2 {
            margin: 0;
            font-size: 1rem;
            font-weight: 750;
            letter-spacing: 0;
        }
        .section-head span {
            color: var(--app-muted);
            font-size: 0.82rem;
        }
        div[data-testid="stForm"],
        div[data-testid="stExpander"],
        div[data-testid="stDataFrame"],
        div[data-testid="stPlotlyChart"],
        div[data-testid="stMetric"],
        div[data-testid="stFileUploader"],
        div[data-testid="stAlert"] {
            border-radius: 8px !important;
        }
        div[data-testid="stForm"],
        div[data-testid="stExpander"] {
            border: 1px solid var(--app-border);
            background: #ffffff;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--app-border);
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        .stat-card {
            background: #ffffff;
            border: 1px solid var(--app-border);
            border-radius: 8px;
            padding: 1rem;
            min-height: 7rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        .stat-label {
            color: var(--app-muted);
            font-size: 0.82rem;
            font-weight: 650;
        }
        .stat-value {
            margin-top: 0.35rem;
            color: var(--app-text);
            font-size: 1.75rem;
            line-height: 1.1;
            font-weight: 800;
        }
        .stat-note {
            margin-top: 0.45rem;
            color: var(--app-muted);
            font-size: 0.78rem;
        }
        .hero-card {
            padding: 1.15rem 1.25rem;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid var(--app-border);
            margin-bottom: 1rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        .hero-card h2 {
            margin-top: 0;
            letter-spacing: 0;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            min-height: 1.45rem;
            padding: 0 0.55rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .pill-on {
            color: #047857;
            background: #d1fae5;
        }
        .pill-off {
            color: #64748b;
            background: #f1f5f9;
        }
        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button,
        [data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            border: 1px solid var(--app-border);
            font-weight: 650;
            min-height: 2.45rem;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        [data-testid="stButton"] button *,
        [data-testid="stDownloadButton"] button *,
        [data-testid="stFormSubmitButton"] button * {
            white-space: nowrap !important;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.15;
        }
        [data-testid="stButton"] button p,
        [data-testid="stDownloadButton"] button p,
        [data-testid="stFormSubmitButton"] button p {
            margin: 0;
        }
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {
            background: var(--app-green);
            border-color: var(--app-green);
        }
        @media (max-width: 760px) {
            .shell-header {
                display: block;
            }
            .shell-user {
                margin-top: 0.5rem;
                white-space: normal;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    apply_styles()
    if st.session_state.get("current_user"):
        render_authenticated()
    else:
        render_auth()


if __name__ == "__main__":
    main()
