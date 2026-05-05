from __future__ import annotations

import streamlit as st

from app import ui
from app.services.i18n import t
from app.services.llm import get_active_api_config
from app.services.storage import (
    delete_data_file,
    get_active_data_file,
    get_project_files,
    load_project_dataframe,
    read_dataframe_bytes,
    save_data_bytes,
    set_active_data_file,
    validate_dataframe,
)


def render(project: dict, user: dict) -> None:
    api_ready = get_active_api_config(int(user["id"])) is not None
    active_file = get_active_data_file(int(project["id"]), int(user["id"]))
    st.caption((t("api_ready") if api_ready else t("api_missing")) + f" | {t('current_data_source')}: {active_file['filename'] if active_file else t('no_data')}")
    ui.section_title(t("upload_dataset"))
    upload = st.file_uploader(t("upload_dataset"), type=["csv", "xlsx", "xls"], accept_multiple_files=False)
    if upload is not None:
        try:
            preview_df = read_dataframe_bytes(upload.name, upload.getvalue())
            missing = validate_dataframe(preview_df)
            if missing:
                st.error(f"{t('required_columns_missing')}: {', '.join(missing)}")
            else:
                st.session_state["pending_dataset_upload"] = {"name": upload.name, "bytes": upload.getvalue()}
                ui.section_title(t("preview"), upload.name)
                st.dataframe(preview_df.head(10), use_container_width=True)
                if st.button(t("save_to_project"), key="save_pending_dataset", use_container_width=True):
                    pending = st.session_state.get("pending_dataset_upload")
                    if pending:
                        saved = save_data_bytes(int(user["id"]), int(project["id"]), pending["name"], pending["bytes"])
                        st.success(f"{t('success_saved')} ({saved['row_count']} rows)")
                        st.session_state.pop("pending_dataset_upload", None)
                        st.rerun()
        except Exception as exc:
            st.error(f"{t('required_columns_missing')}: {exc}")

    active_file, active_df = load_project_dataframe(int(project["id"]), int(user["id"]))
    if active_file and active_df is not None:
        ui.section_title(t("preview"), active_file["filename"])
        st.caption(f"{t('current_data_source')}: {active_file['filename']}")
        st.dataframe(active_df.head(10), use_container_width=True)
        col1, col2 = st.columns(2)
        col1.metric(t("record_count"), active_file["row_count"])
        col2.metric(t("abstract_count"), active_file["abstract_count"])

    ui.section_title(t("uploaded_files"))
    files = get_project_files(int(project["id"]), int(user["id"]))
    if not files:
        st.info(t("no_data"))
        return
    for file in files:
        cols = st.columns([3, 1.2, 1.2, 1])
        cols[0].markdown(f"**{file['filename']}**")
        cols[0].caption(f"{t('record_count')}: {file['row_count']} | {t('abstract_count')}: {file['abstract_count']}")
        cols[1].caption(file["created_at"])
        if file["is_active"]:
            cols[2].success(t("active"))
        elif cols[2].button(t("set_active_file"), key=f"set_active_{file['id']}"):
            set_active_data_file(int(project["id"]), int(user["id"]), int(file["id"]))
            st.rerun()
        if cols[3].button(t("delete"), key=f"delete_file_{file['id']}"):
            delete_data_file(int(project["id"]), int(user["id"]), int(file["id"]))
            st.rerun()
