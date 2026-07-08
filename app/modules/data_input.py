from __future__ import annotations

import logging

import streamlit as st

from app import session_state as ss
from app import ui
from app.services.i18n import t
from app.services.llm import get_active_api_config
from app.services.storage import (
    ManagedFileMissingError,
    delete_data_file,
    get_active_data_file,
    get_data_file_result_counts,
    get_project_files,
    load_project_dataframe,
    read_dataframe_bytes,
    save_data_bytes,
    set_active_data_file,
    validate_dataframe,
)


logger = logging.getLogger(__name__)


def _render_active_summary(project_id: int, user_id: int) -> None:
    api_ready = get_active_api_config(user_id) is not None
    active_file = get_active_data_file(project_id, user_id)
    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.markdown(ui.status_pill(t("api_ready") if api_ready else t("api_missing"), active=api_ready), unsafe_allow_html=True)
        col2.markdown(f"**{t('current_data_source')}**: {active_file['filename'] if active_file else t('no_data')}")


def _render_upload(project_id: int, user_id: int) -> None:
    ui.section_title(t("upload_dataset"))
    ui.upload_hint(t("upload_drag_hint"), f"{t('upload_dataset_hint')} {t('upload_csv_hint')}")
    upload = st.file_uploader(t("select_dataset_file"), type=["csv", "xlsx", "xls"], accept_multiple_files=False, label_visibility="collapsed")
    if upload is None:
        return

    try:
        preview_df = read_dataframe_bytes(upload.name, upload.getvalue())
        missing = validate_dataframe(preview_df)
        if missing:
            st.error(f"{t('required_columns_missing')}: {', '.join(missing)}")
            return
        ss.set_value(ss.PENDING_DATASET_UPLOAD, {"name": upload.name, "bytes": upload.getvalue()})
        ui.section_title(t("upload_preview"), upload.name)
        st.dataframe(preview_df.head(10), use_container_width=True)
        if st.button(t("save_to_project"), key="save_pending_dataset", use_container_width=True):
            pending = ss.get(ss.PENDING_DATASET_UPLOAD)
            if pending:
                saved = save_data_bytes(user_id, project_id, pending["name"], pending["bytes"])
                st.success(f"{t('success_saved')} ({saved['row_count']} rows)")
                ss.pop(ss.PENDING_DATASET_UPLOAD, None)
                st.rerun()
    except ValueError:
        logger.exception("Dataset validation failed for project_id=%s filename=%s", project_id, upload.name)
        st.error(t("upload_failed_generic"))
    except Exception:
        logger.exception("Dataset upload failed for project_id=%s filename=%s", project_id, upload.name)
        st.error(t("upload_failed_generic"))


def _render_files(project_id: int, user_id: int) -> None:
    files = get_project_files(project_id, user_id)
    result_counts = get_data_file_result_counts(project_id, user_id)

    pending_delete_id = ss.get(ss.PENDING_DELETE_DATA_FILE_ID)
    if pending_delete_id:
        ui.confirm_dialog(
            t("confirm_delete_title"),
            t("delete_data_file_confirm"),
            t("confirm_delete"),
            t("cancel"),
            lambda: delete_data_file(project_id, user_id, int(pending_delete_id)),
            ss.PENDING_DELETE_DATA_FILE_ID,
        )

    ui.section_title(t("uploaded_files"), t("file_list_scroll_hint"))
    if not files:
        ui.empty_state(t("no_data"), t("upload_dataset_hint"))
        return

    with ui.fixed_list_container(height=320):
        header = st.columns([3, 1.2, 1.1, 1.4, 1.4])
        for col, label in zip(header, [t("select_dataset_file"), t("created_at"), t("run_status"), t("bound_results"), t("actions")]):
            col.caption(label)
        ui.row_separator()

        for file in files:
            file_id = int(file["id"])
            counts = result_counts.get(file_id, {"screening": 0, "topic": 0})
            cols = st.columns([3, 1.2, 1.1, 1.4, 1.4], vertical_alignment="center")
            cols[0].markdown(f"**{file['filename']}**")
            cols[0].caption(f"{t('record_count')}: {file['row_count']} | {t('abstract_count')}: {file['abstract_count']}")
            cols[1].caption(file["created_at"])
            if file["is_active"]:
                cols[2].markdown(ui.status_pill(t("active"), active=True), unsafe_allow_html=True)
            elif cols[2].button(t("set_active_file"), key=f"set_active_{file_id}", use_container_width=True):
                set_active_data_file(project_id, user_id, file_id)
                st.rerun()
            cols[3].caption(f"{t('screening_results')}: {counts['screening']} | {t('topic_overview')}: {counts['topic']}")
            if cols[4].button(t("delete"), key=f"delete_file_{file_id}", use_container_width=True):
                ss.set_value(ss.PENDING_DELETE_DATA_FILE_ID, file_id)
                st.rerun()
            ui.row_separator()


def _render_active_preview(project_id: int, user_id: int) -> None:
    try:
        active_file, active_df = load_project_dataframe(project_id, user_id)
    except ManagedFileMissingError:
        logger.exception("Active data file is missing for project_id=%s user_id=%s", project_id, user_id)
        st.warning(t("managed_file_missing"))
        return
    except Exception:
        logger.exception("Active data preview failed for project_id=%s user_id=%s", project_id, user_id)
        st.error(t("data_preview_failed"))
        return

    if not active_file or active_df is None:
        return

    ui.section_title(t("active_data_source_preview"), active_file["filename"])
    metrics = st.columns(2)
    metrics[0].metric(t("record_count"), active_file["row_count"])
    metrics[1].metric(t("abstract_count"), active_file["abstract_count"])
    st.dataframe(active_df.head(10), use_container_width=True)


def render(project: dict, user: dict) -> None:
    project_id = int(project["id"])
    user_id = int(user["id"])

    _render_active_summary(project_id, user_id)
    _render_upload(project_id, user_id)
    _render_files(project_id, user_id)
    _render_active_preview(project_id, user_id)
