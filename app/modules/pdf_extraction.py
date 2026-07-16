from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from app import ui
from app.services.i18n import t
from app.services.llm import get_active_api_config
from app.services.pdf_service import get_pdf_results, list_pdf_runs, run_pdf_extraction
from app.services.storage import (
    ManagedFileMissingError,
    delete_pdf_file,
    delete_pdf_template,
    get_active_template,
    get_project_pdf_files,
    list_pdf_templates,
    read_dataframe_bytes,
    require_existing_path,
    save_pdf_files,
    save_template_bytes,
    set_active_template,
)
from app.services.utils import json_loads


logger = logging.getLogger(__name__)

TEMPLATE_SUFFIXES = {".csv", ".xlsx", ".xls"}


def _ensure_state(project_id: int) -> None:
    prefix = f"pdf_{project_id}"
    st.session_state.setdefault(f"{prefix}_pending_template_upload", None)
    st.session_state.setdefault(f"{prefix}_selected_template_id", None)
    st.session_state.setdefault(f"{prefix}_selected_pdf_ids", [])
    st.session_state.setdefault(f"{prefix}_handled_template_token", "")
    st.session_state.setdefault(f"{prefix}_template_upload_nonce", 0)
    st.session_state.setdefault(f"{prefix}_handled_pdf_upload_token", "")
    st.session_state.setdefault(f"{prefix}_pending_delete_pdf_ids", [])
    st.session_state.setdefault(f"{prefix}_extraction_running", False)


def _valid_suffix(filename: str, allowed: set[str]) -> bool:
    return Path(filename).suffix.lower() in allowed


def _set_pdf_selection(prefix: str, available_ids: list[int], selected_ids: list[int]) -> None:
    selected_set = set(selected_ids)
    st.session_state[f"{prefix}_selected_pdf_ids"] = [file_id for file_id in available_ids if file_id in selected_set]
    for file_id in available_ids:
        st.session_state[f"{prefix}_select_pdf_{file_id}"] = file_id in selected_set


def _render_pdf_results(project_id: int, user_id: int) -> None:
    runs = list_pdf_runs(project_id, user_id)
    if not runs:
        return
    ui.section_title(t("pdf_results"))
    selected_run = st.selectbox(t("pdf_run"), runs, format_func=lambda item: f"#{item['id']} | {item['created_at']} | {item['status']}")
    results_df = get_pdf_results(int(selected_run["id"]))
    st.dataframe(results_df, use_container_width=True)
    if selected_run.get("output_path"):
        try:
            output_path = require_existing_path(selected_run["output_path"])
            with output_path.open("rb") as fh:
                st.download_button(t("export_results"), data=fh.read(), file_name=output_path.name, mime="text/csv")
        except ManagedFileMissingError:
            logger.exception("PDF extraction output file is missing for run_id=%s", selected_run["id"])
            st.warning(t("result_file_missing"))


def _render_pdf_selection(prefix: str, pdf_files: list[dict]) -> list[int]:
    file_map = {int(item["id"]): item for item in pdf_files}
    available_ids = list(file_map.keys())
    selected_pdf_ids = [file_id for file_id in st.session_state.get(f"{prefix}_selected_pdf_ids", []) if file_id in file_map]
    st.session_state[f"{prefix}_selected_pdf_ids"] = selected_pdf_ids

    ui.section_title(t("pdf_selection_for_run"), t("selected_pdf_files_hint"))
    select_col, clear_col = st.columns(2)
    if select_col.button(t("select_all"), key=f"{prefix}_select_all_pdf", use_container_width=True):
        _set_pdf_selection(prefix, available_ids, available_ids)
        st.rerun()
    if clear_col.button(t("clear_selection"), key=f"{prefix}_clear_pdf_selection", use_container_width=True):
        _set_pdf_selection(prefix, available_ids, [])
        st.rerun()

    current_selection: list[int] = []
    with ui.fixed_list_container(height=220):
        for file_id in available_ids:
            checked = st.checkbox(
                file_map[file_id]["filename"],
                value=file_id in selected_pdf_ids,
                key=f"{prefix}_select_pdf_{file_id}",
            )
            if checked:
                current_selection.append(file_id)
    st.session_state[f"{prefix}_selected_pdf_ids"] = current_selection
    return current_selection


def _render_pdf_delete_list(project_id: int, user_id: int, prefix: str, pdf_files: list[dict]) -> None:
    pending_delete_ids = st.session_state.get(f"{prefix}_pending_delete_pdf_ids", [])
    if pending_delete_ids:
        def _delete_files() -> None:
            for file_id in pending_delete_ids:
                delete_pdf_file(project_id, user_id, int(file_id))
                st.session_state.pop(f"{prefix}_select_pdf_{file_id}", None)
                st.session_state.pop(f"{prefix}_delete_pdf_candidate_{file_id}", None)
            st.session_state[f"{prefix}_selected_pdf_ids"] = [
                file_id for file_id in st.session_state.get(f"{prefix}_selected_pdf_ids", []) if file_id not in pending_delete_ids
            ]

        ui.confirm_dialog(
            t("confirm_delete_title"),
            t("delete_pdf_files_confirm"),
            t("confirm_delete"),
            t("cancel"),
            _delete_files,
            f"{prefix}_pending_delete_pdf_ids",
        )

    ui.section_title(t("pdf_delete_list"))
    delete_ids: list[int] = []
    with ui.fixed_list_container(height=220):
        for file in pdf_files:
            file_id = int(file["id"])
            if st.checkbox(file["filename"], key=f"{prefix}_delete_pdf_candidate_{file_id}"):
                delete_ids.append(file_id)
    if st.button(t("delete_selected_files"), key=f"{prefix}_delete_selected_pdf_button", use_container_width=True, disabled=not delete_ids):
        st.session_state[f"{prefix}_pending_delete_pdf_ids"] = delete_ids
        st.rerun()


def render(project: dict, user: dict) -> None:
    project_id = int(project["id"])
    user_id = int(user["id"])
    prefix = f"pdf_{project_id}"
    _ensure_state(project_id)
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

    ui.section_title(t("pdf_step_template"))
    ui.upload_hint(t("upload_drag_hint"), f"{t('pdf_template_hint')} {t('upload_template_hint_short')}")
    template_upload = st.file_uploader(
        t("template_upload"),
        accept_multiple_files=False,
        key=f"{prefix}_template_upload_{st.session_state[f'{prefix}_template_upload_nonce']}",
        label_visibility="collapsed",
    )
    if template_upload is not None:
        if not _valid_suffix(template_upload.name, TEMPLATE_SUFFIXES):
            st.error(t("template_upload_failed"))
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
            except Exception:
                logger.exception("Template upload failed for project_id=%s filename=%s", project_id, template_upload.name)
                st.error(t("template_upload_failed"))

    pending_template = st.session_state.get(f"{prefix}_pending_template_upload")
    if pending_template:
        st.dataframe(pending_template["preview"], use_container_width=True)
        if st.button(t("save_template"), key=f"{prefix}_save_template_button", use_container_width=True):
            try:
                saved = save_template_bytes(user_id, project_id, pending_template["name"], pending_template["bytes"])
                st.session_state[f"{prefix}_handled_template_token"] = pending_template["token"]
                st.session_state[f"{prefix}_pending_template_upload"] = None
                st.session_state[f"{prefix}_template_upload_nonce"] += 1
                st.session_state[f"{prefix}_selected_template_id"] = int(saved["template_id"])
                st.success(t("success_saved"))
                st.rerun()
            except Exception:
                logger.exception("Saving PDF template failed for project_id=%s", project_id)
                st.error(t("template_upload_failed"))

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
        ui.empty_state(t("no_templates"), t("template_upload"))

    preview_payload = pending_template["preview"] if pending_template else None
    preview_name = pending_template["name"] if pending_template else ""
    if preview_payload is None and selected_template:
        preview_payload = json_loads(selected_template["preview_json"], [])
        preview_name = selected_template["filename"]
    if preview_payload is not None:
        ui.section_title(t("template_preview"))
        st.caption(preview_name)
        st.dataframe(preview_payload, use_container_width=True)
    else:
        ui.empty_state(t("upload_template_first"), t("template_upload"))

    ui.section_title(t("pdf_step_files"))
    ui.upload_hint(t("upload_drag_hint"), t("upload_pdf_hint"))
    pdf_uploads = st.file_uploader(t("pdf_upload"), accept_multiple_files=True, key=f"{prefix}_pdf_upload", label_visibility="collapsed")
    if pdf_uploads:
        invalid_files = [item.name for item in pdf_uploads if not _valid_suffix(item.name, {".pdf"})]
        if invalid_files:
            st.error(t("pdf_upload_failed"))
        else:
            upload_token = "|".join(f"{item.name}:{len(item.getvalue())}" for item in pdf_uploads)
            if upload_token and upload_token != st.session_state[f"{prefix}_handled_pdf_upload_token"]:
                try:
                    saved_ids = save_pdf_files(user_id, project_id, pdf_uploads)
                    existing_ids = st.session_state.get(f"{prefix}_selected_pdf_ids", [])
                    st.session_state[f"{prefix}_selected_pdf_ids"] = sorted(set(existing_ids + saved_ids))
                    st.session_state[f"{prefix}_handled_pdf_upload_token"] = upload_token
                    st.success(t("success_saved"))
                    st.rerun()
                except Exception:
                    logger.exception("PDF upload failed for project_id=%s", project_id)
                    st.error(t("pdf_upload_failed"))

    pdf_files = get_project_pdf_files(project_id, user_id)
    if pdf_files:
        selected_pdf_ids = _render_pdf_selection(prefix, pdf_files)
    else:
        selected_pdf_ids = []
        ui.empty_state(t("no_pdf_files"), t("pdf_upload"))

    ui.section_title(t("start_extraction"))
    template_ready = selected_template is not None
    pdf_ready = bool(selected_pdf_ids)
    extraction_running = bool(st.session_state.get(f"{prefix}_extraction_running"))
    disabled_reasons = []
    if api_config is None:
        disabled_reasons.append(t("api_required"))
    if not template_ready:
        disabled_reasons.append(t("upload_template_first"))
    if not pdf_ready:
        disabled_reasons.append(t("select_pdf_first"))
    if extraction_running:
        disabled_reasons.append(t("pdf_task_running"))
    if disabled_reasons:
        st.info(t("pdf_start_disabled_reasons").format(reasons="?".join(disabled_reasons)))

    start_disabled = bool(disabled_reasons)
    if st.button(t("start_extraction"), use_container_width=True, disabled=start_disabled):
        st.session_state[f"{prefix}_extraction_running"] = True
        progress_bar = st.progress(0)
        progress_text = st.empty()
        current_file_text = st.empty()
        failure_box = st.empty()

        def update_progress(done: int, total: int, filename: str, stage: str, error: str) -> None:
            ratio = 0 if total <= 0 else min(1.0, done / total)
            progress_bar.progress(ratio)
            progress_text.caption(t("pdf_progress_count").format(done=done, total=total))
            if filename:
                current_file_text.caption(t("pdf_progress_file").format(filename=filename))
            if stage == "failed" and error:
                failure_box.warning(t("pdf_file_failed").format(filename=filename, reason=" ".join(error.split())[:180]))

        try:
            with st.status(t("extraction_in_progress"), expanded=True) as status:
                result = run_pdf_extraction(
                    project_id,
                    user_id,
                    int(selected_template["id"]),
                    json_loads(selected_template["columns_json"], []),
                    selected_pdf_ids,
                    progress_callback=update_progress,
                )
                status.update(label=t("pdf_extraction_complete"), state="complete", expanded=False)
            st.success(
                t("pdf_summary").format(
                    success=result["success_count"],
                    failed=result["failed_count"],
                )
            )
            for failure in result["failures"]:
                st.warning(
                    t("pdf_file_failed").format(
                        filename=failure["file_name"],
                        reason=" ".join(str(failure["error_message"]).split())[:180],
                    )
                )
        except Exception:
            logger.exception("PDF extraction failed for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("pdf_extraction_failed"))
        finally:
            st.session_state[f"{prefix}_extraction_running"] = False

    _render_pdf_results(project_id, user_id)

    if pdf_files:
        st.divider()
        _render_pdf_delete_list(project_id, user_id, prefix, pdf_files)
