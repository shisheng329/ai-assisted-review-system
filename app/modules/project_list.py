from __future__ import annotations

import streamlit as st

from app import ui
from app.services.i18n import t
from app.services.projects import create_project, delete_project, list_projects, update_project


def _project_form(user_id: int, key_prefix: str, project: dict | None = None) -> None:
    with st.form(f"{key_prefix}_project_form", clear_on_submit=project is None):
        name = st.text_input(t("project_name"), value=(project or {}).get("name", ""), key=f"{key_prefix}_name")
        description = st.text_area(t("project_description"), value=(project or {}).get("description", ""), key=f"{key_prefix}_description")
        submitted = st.form_submit_button(t("save") if project else t("create_project"), use_container_width=True)
    if not submitted:
        return
    if not name.strip():
        st.error(t("project_name_required"))
        return
    if project:
        update_project(user_id, int(project["id"]), name, description)
        st.session_state.pop("editing_project_id", None)
        st.success(t("project_saved"))
        st.rerun()
    project_id = create_project(user_id, name, description)
    st.session_state["current_project_id"] = project_id
    st.session_state["current_module"] = "dashboard"
    st.session_state["show_create_project"] = False
    st.success(t("success_created"))
    st.rerun()


def _open_project(project_id: int) -> None:
    st.session_state["current_project_id"] = project_id
    st.session_state["current_module"] = "dashboard"
    st.rerun()


def render(user: dict) -> None:
    user_id = int(user["id"])
    projects = list_projects(user_id)
    ui.section_title(t("project_management"), f"{len(projects)}")

    if not projects:
        ui.empty_state(t("no_projects_hint"), t("project_management_hint"))
        _project_form(user_id, "create_first")
        return

    action_col, spacer_col = st.columns([1.2, 5], vertical_alignment="center")
    if action_col.button(t("new_project"), key="new_project_button", use_container_width=True):
        st.session_state["show_create_project"] = not st.session_state.get("show_create_project", False)
    with spacer_col:
        st.caption(t("project_management_hint"))

    if st.session_state.get("show_create_project", False):
        with st.expander(t("new_project"), expanded=True):
            _project_form(user_id, "create_project")

    header = st.columns([1.6, 2.5, 1.4, 1.4, 2.1])
    for col, label in zip(header, [t("project_name"), t("project_description"), t("created_at"), t("updated_at"), t("actions")]):
        col.caption(label)
    ui.row_separator()

    for project in projects:
        project_id = int(project["id"])
        if st.session_state.get("editing_project_id") == project_id:
            with st.expander(f"{t('edit_project')}: {project['name']}", expanded=True):
                _project_form(user_id, f"edit_{project_id}", project)
                if st.button(t("cancel"), key=f"cancel_edit_{project_id}"):
                    st.session_state.pop("editing_project_id", None)
                    st.rerun()
            ui.row_separator()
            continue

        row = st.columns([1.6, 2.5, 1.4, 1.4, 2.1], vertical_alignment="center")
        row[0].markdown(f"**{project['name']}**")
        row[1].caption(project["description"] or t("empty_description"))
        row[2].caption(project["created_at"])
        row[3].caption(project["updated_at"])
        actions = row[4].columns(3)
        if actions[0].button(t("open"), key=f"open_project_{project_id}", use_container_width=True):
            _open_project(project_id)
        if actions[1].button(t("edit"), key=f"edit_project_{project_id}", use_container_width=True):
            st.session_state["editing_project_id"] = project_id
            st.rerun()
        if actions[2].button(t("delete"), key=f"delete_project_{project_id}", use_container_width=True):
            st.session_state["pending_delete_project_id"] = project_id
            st.rerun()

        if st.session_state.get("pending_delete_project_id") == project_id:
            st.warning(t("delete_project_confirm"))
            confirm_col, cancel_col, _ = st.columns([1.2, 1.2, 4])
            if confirm_col.button(t("confirm_delete"), key=f"confirm_delete_project_{project_id}", use_container_width=True):
                delete_project(user_id, project_id)
                if st.session_state.get("current_project_id") == project_id:
                    st.session_state["current_project_id"] = None
                    st.session_state["current_module"] = "projects"
                st.session_state.pop("pending_delete_project_id", None)
                st.success(t("project_deleted"))
                st.rerun()
            if cancel_col.button(t("cancel"), key=f"cancel_delete_project_{project_id}", use_container_width=True):
                st.session_state.pop("pending_delete_project_id", None)
                st.rerun()
        ui.row_separator()
