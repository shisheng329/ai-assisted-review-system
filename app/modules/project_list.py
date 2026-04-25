from __future__ import annotations

import streamlit as st

from app.services.i18n import t
from app.services.projects import create_project, list_projects


def render(user: dict) -> None:
    st.subheader(t("projects"))
    with st.expander(t("create_project"), expanded=True):
        with st.form("create_project_form", clear_on_submit=True):
            name = st.text_input(t("project_name"))
            description = st.text_area(t("project_description"))
            submitted = st.form_submit_button(t("create_project"), use_container_width=True)
        if submitted and name.strip():
            project_id = create_project(int(user["id"]), name, description)
            st.session_state["current_project_id"] = project_id
            st.session_state["current_module"] = "dashboard"
            st.success(t("success_created"))
            st.rerun()

    projects = list_projects(int(user["id"]))
    if not projects:
        st.info(t("no_data"))
        return

    for project in projects:
        col1, col2, col3 = st.columns([3, 4, 1.2])
        with col1:
            st.markdown(f"**{project['name']}**")
            if project["description"]:
                st.caption(project["description"])
        with col2:
            st.caption(f"{t('created_at')}: {project['created_at']}")
            st.caption(f"{t('updated_at')}: {project['updated_at']}")
        with col3:
            if st.button(t("open_project"), key=f"open_project_{project['id']}", use_container_width=True):
                st.session_state["current_project_id"] = int(project["id"])
                st.session_state["current_module"] = "dashboard"
                st.rerun()
