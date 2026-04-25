from __future__ import annotations

import sqlite3
import sys
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


def init_session() -> None:
    st.session_state.setdefault("language", "zh-CN")
    st.session_state.setdefault("current_module", "projects")
    st.session_state.setdefault("current_project_id", None)


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(circle at top left, #f2f7ff 0%, #f6f8fc 40%, #eef3fb 100%); }
        header[data-testid="stHeader"] {
            background: rgba(246, 248, 252, 0.98);
        }
        .block-container {
            padding-top: 0.75rem !important;
        }
        .topbar {
            position: sticky;
            top: 2.85rem;
            z-index: 999;
            padding: 0.55rem 0.85rem 0.65rem;
            margin-top: 0.15rem;
            margin-bottom: 0.75rem;
            border-radius: 14px;
            background: #f6f8fc;
            border: 1px solid rgba(39,93,245,0.12);
            box-shadow: 0 10px 24px rgba(20,33,61,0.08);
            overflow: visible;
        }
        .topbar p {
            margin-bottom: 0;
        }
        .topbar .stMarkdown {
            min-width: 0;
        }
        .topbar [data-testid="stHorizontalBlock"] {
            align-items: center;
            row-gap: 0.35rem;
        }
        .topbar [data-testid="stButton"] button,
        .topbar [data-testid="stBaseButton-secondary"] {
            min-height: 2.35rem;
        }
        .topbar [data-testid="stMarkdownContainer"] {
            overflow: visible;
        }
        .hero-card {
            padding: 1rem 1.25rem;
            border-radius: 24px;
            background: linear-gradient(135deg, rgba(39,93,245,0.08), rgba(12,178,125,0.08));
            border: 1px solid rgba(39,93,245,0.12);
            margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_auth() -> None:
    st.markdown(f"<div class='hero-card'><h2>{t('app_title')}</h2><p>{t('theme_hint')}</p></div>", unsafe_allow_html=True)
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


def render_base_topbar(user: dict, project: dict | None) -> None:
    st.markdown("<div class='topbar'>", unsafe_allow_html=True)
    title_col, project_col, action_col = st.columns([3.2, 4.2, 1.4], vertical_alignment="center")
    title_col.markdown(f"**{t('app_title')}**")
    title_col.caption(f"{user['display_name']} / {user['username']}")
    project_col.caption(f"{t('active_project')}: {project['name']}" if project else t("projects"))
    if action_col.button(t("logout"), use_container_width=True):
        logout_user()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_main_nav() -> str:
    return st.segmented_control(
        t("main_navigation"),
        options=["projects", "profile"],
        default=st.session_state.get("current_module", "projects"),
        format_func=lambda key: t(key),
    )


def render_project_topbar(user: dict, project: dict) -> str:
    nav_options = ["dashboard", "data_input", "screening", "bertopic", "pdf_extraction", "profile"]
    current = st.session_state.get("current_module", "dashboard")
    current = current if current in nav_options else "dashboard"

    st.markdown("<div class='topbar'>", unsafe_allow_html=True)
    title_col, project_col, back_col, nav_col, action_col = st.columns([2.55, 1.35, 1.55, 5.55, 1.4], vertical_alignment="center")
    title_col.markdown(f"**{t('app_title')}**")
    title_col.caption(f"{user['display_name']} / {user['username']}")
    project_col.caption(f"{t('active_project')}: {project['name']}")
    if back_col.button(t("back_to_projects"), use_container_width=True):
        st.session_state["current_project_id"] = None
        st.session_state["current_module"] = "projects"
        st.rerun()
    with nav_col:
        nav = st.segmented_control(
            t("project_navigation"),
            options=nav_options,
            default=current,
            format_func=lambda key: t(key),
            label_visibility="collapsed",
        )
    if action_col.button(t("logout"), use_container_width=True):
        logout_user()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return nav


def render_authenticated() -> None:
    user = st.session_state["current_user"]
    current_project_id = st.session_state.get("current_project_id")
    project = get_project(int(current_project_id), int(user["id"])) if current_project_id else None
    if current_project_id and not project:
        st.session_state["current_project_id"] = None
        st.session_state["current_module"] = "projects"
        project = None

    if project is None:
        render_base_topbar(user, None)
        nav = render_main_nav()
        st.session_state["current_module"] = nav
        if nav == "projects":
            project_list.render(user)
        else:
            profile.render(user)
        return

    nav = render_project_topbar(user, project)
    st.session_state["current_module"] = nav
    if nav == "profile":
        profile.render(user)
    else:
        MODULES[nav](project, user)


def main() -> None:
    st.set_page_config(page_title="20260423 System Demo", page_icon="📚", layout="wide")
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
