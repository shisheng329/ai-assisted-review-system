from __future__ import annotations

from pathlib import Path

import streamlit as st

from app import ui
from app.services.i18n import t
from app.services.llm import get_active_api_config
from app.services.pdf_service import get_pdf_results, list_pdf_runs, run_pdf_extraction
from app.services.storage import (
    delete_pdf_file,
    delete_pdf_template,
    get_active_template,
    get_project_pdf_files,
    list_pdf_templates,
    read_dataframe_bytes,
    save_pdf_files,
    save_template_bytes,
    set_active_template,
)
from app.services.utils import json_loads


TEMPLATE_SUFFIXES = {".csv", ".xlsx", ".xls"}


def _ensure_state(project_id: int) -> None:
    prefix = f"pdf_{project_id}"
    st.session_state.setdefault(f"{prefix}_pending_template_upload", None)
    st.session_state.setdefault(f"{prefix}_selected_template_id", None)
    st.session_state.setdefault(f"{prefix}_selected_pdf_ids", [])
    st.session_state.setdefault(f"{prefix}_pending_selected_pdf_ids", None)
    st.session_state.setdefault(f"{prefix}_handled_template_token", "")
    st.session_state.setdefault(f"{prefix}_handled_pdf_upload_token", "")


def _valid_suffix(filename: str, allowed: set[str]) -> bool:
    return Path(filename).suffix.lower() in allowed


def _apply_pending_pdf_selection(prefix: str) -> None:
    pending = st.session_state.get(f"{prefix}_pending_selected_pdf_ids")
    if pending is not None:
        st.session_state[f"{prefix}_selected_pdf_ids"] = pending
        st.session_state[f"{prefix}_pending_selected_pdf_ids"] = None


def _render_pdf_results(project_id: int, user_id: int) -> None:
    runs = list_pdf_runs(project_id, user_id)
    if not runs:
        return
    ui.section_title(t("pdf_results"))
    selected_run = st.selectbox(t("pdf_run"), runs, format_func=lambda item: f"#{item['id']} | {item['created_at']} | {item['status']}")
    results_df = get_pdf_results(int(selected_run["id"]))
    st.dataframe(results_df, use_container_width=True)
    if selected_run.get("output_path"):
        with open(selected_run["output_path"], "rb") as fh:
            st.download_button(t("export_results"), data=fh.read(), file_name="pdf_results.csv", mime="text/csv")


def render(project: dict, user: dict) -> None:
    project_id = int(project["id"])
    user_id = int(user["id"])
    prefix = f"pdf_{project_id}"
    _ensure_state(project_id)
    _apply_pending_pdf_selection(prefix)
    api_config = get_active_api_config(user_id)

    templates = list_pdf_templates(project_id, user_id)
    active_template = get_active_template(project_id, user_id)
    if active_template and st.session_state[f"{prefix}_selected_template_id"] is None:
        st.session_state[f"{prefix}_selected_template_id"] = int(active_template["id"])
    template_map = {int(item["id"]): item for item in templates}
    selected_template_id = st.session_state.get(f"{prefix}_selected_template_id")
    selected_template = template_map.get(selected_template_id) or active_template
    if selected_template:
        st.session_state[f"{prefix}_selected_template_id"] = int(selected_template["id"])

    pdf_files = get_project_pdf_files(project_id, user_id)
    available_pdf_ids = [int(item["id"]) for item in pdf_files]
    selected_pdf_ids = [file_id for file_id in st.session_state.get(f"{prefix}_selected_pdf_ids", []) if file_id in available_pdf_ids]
    if not selected_pdf_ids and available_pdf_ids:
        selected_pdf_ids = available_pdf_ids
        st.session_state[f"{prefix}_selected_pdf_ids"] = selected_pdf_ids

    ui.section_title(t("start_extraction"))
    template_ready = selected_template is not None
    pdf_ready = bool(selected_pdf_ids)
    if st.button(t("start_extraction"), use_container_width=True, disabled=(api_config is None or not template_ready or not pdf_ready)):
        try:
            with st.spinner(t("extraction_in_progress")):
                result = run_pdf_extraction(
                    project_id,
                    user_id,
                    int(selected_template["id"]),
                    json_loads(selected_template["columns_json"], []),
                    selected_pdf_ids,
                )
            st.success(f"{t('run_complete')} #{result['run_id']}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    template_upload = st.file_uploader(t("template_upload"), accept_multiple_files=False, key=f"{prefix}_template_upload")
    if template_upload is not None:
        if not _valid_suffix(template_upload.name, TEMPLATE_SUFFIXES):
            st.error(f"{t('operation_failed')}: unsupported template file type")
        else:
            try:
                template_bytes = template_upload.getvalue()
                template_token = f"{template_upload.name}:{len(template_bytes)}"
                if template_token != st.session_state[f"{prefix}_handled_template_token"]:
                    preview_df = read_dataframe_bytes(template_upload.name, template_bytes)
                    st.session_state[f"{prefix}_pending_template_upload"] = {
                        "name": template_upload.name,
                        "bytes": template_bytes,
                        "preview": preview_df.head(5).fillna("").to_dict(orient="records"),
                        "token": template_token,
                    }
            except Exception as exc:
                st.error(f"{t('operation_failed')}: {exc}")

    ui.section_title(t("manage_templates"))
    if templates:
        chosen_template_id = st.selectbox(
            t("select_template"),
            options=[int(item["id"]) for item in templates],
            index=[int(item["id"]) for item in templates].index(int(st.session_state[f"{prefix}_selected_template_id"])) if st.session_state[f"{prefix}_selected_template_id"] in template_map else 0,
            format_func=lambda template_id: template_map[template_id]["filename"],
            key=f"{prefix}_template_selectbox",
        )
        st.session_state[f"{prefix}_selected_template_id"] = chosen_template_id
        selected_template = template_map[chosen_template_id]
        template_action_col1, template_action_col2 = st.columns(2)
        if template_action_col1.button(t("save_and_activate"), key=f"{prefix}_activate_template", use_container_width=True):
            set_active_template(project_id, user_id, chosen_template_id)
            st.success(t("success_saved"))
            st.rerun()
        if template_action_col2.button(t("delete_template"), key=f"{prefix}_delete_template", use_container_width=True):
            delete_pdf_template(project_id, user_id, chosen_template_id)
            st.session_state[f"{prefix}_selected_template_id"] = None
            st.success(t("success_saved"))
            st.rerun()
    else:
        st.info(t("no_templates"))

    pending_template = st.session_state.get(f"{prefix}_pending_template_upload")
    if pending_template:
        if st.button(t("save_template"), key=f"{prefix}_save_template_button", use_container_width=True):
            saved = save_template_bytes(user_id, project_id, pending_template["name"], pending_template["bytes"])
            st.session_state[f"{prefix}_handled_template_token"] = pending_template["token"]
            st.session_state[f"{prefix}_pending_template_upload"] = None
            st.session_state[f"{prefix}_selected_template_id"] = int(saved["template_id"])
            st.success(t("success_saved"))
            st.rerun()

    preview_payload = None
    preview_name = ""
    if pending_template:
        preview_payload = pending_template["preview"]
        preview_name = pending_template["name"]
    elif selected_template:
        preview_payload = json_loads(selected_template["preview_json"], [])
        preview_name = selected_template["filename"]

    if preview_payload is not None:
        ui.section_title(t("template_preview"))
        st.caption(preview_name)
        st.dataframe(preview_payload, use_container_width=True)
    else:
        st.info(t("upload_template_first"))

    ui.section_title(t("manage_pdf_files"))
    pdf_uploads = st.file_uploader(t("pdf_upload"), accept_multiple_files=True, key=f"{prefix}_pdf_upload")
    if pdf_uploads:
        invalid_files = [item.name for item in pdf_uploads if not _valid_suffix(item.name, {".pdf"})]
        if invalid_files:
            st.error(f"{t('operation_failed')}: unsupported PDF file type - {', '.join(invalid_files)}")
        else:
            upload_token = "|".join(f"{item.name}:{len(item.getvalue())}" for item in pdf_uploads)
            if upload_token and upload_token != st.session_state[f"{prefix}_handled_pdf_upload_token"]:
                save_pdf_files(user_id, project_id, pdf_uploads)
                st.session_state[f"{prefix}_handled_pdf_upload_token"] = upload_token
                st.success(t("success_saved"))
                st.rerun()

    pdf_files = get_project_pdf_files(project_id, user_id)
    file_map = {int(item["id"]): item for item in pdf_files}
    if pdf_files:
        st.multiselect(
            t("selected_pdf_files"),
            options=list(file_map.keys()),
            default=[file_id for file_id in st.session_state[f"{prefix}_selected_pdf_ids"] if file_id in file_map],
            format_func=lambda file_id: file_map[file_id]["filename"],
            key=f"{prefix}_selected_pdf_ids",
        )
        delete_target = st.selectbox(
            t("delete_file"),
            options=[0, *list(file_map.keys())],
            format_func=lambda file_id: t("delete_file") if file_id == 0 else file_map[file_id]["filename"],
            key=f"{prefix}_delete_pdf_target",
        )
        if delete_target and st.button(t("delete_file"), key=f"{prefix}_delete_pdf_button", use_container_width=True):
            delete_pdf_file(project_id, user_id, int(delete_target))
            st.session_state[f"{prefix}_pending_selected_pdf_ids"] = [file_id for file_id in st.session_state[f"{prefix}_selected_pdf_ids"] if file_id != delete_target]
            st.success(t("success_saved"))
            st.rerun()
    else:
        st.info(t("no_pdf_files"))

    _render_pdf_results(project_id, user_id)
