from __future__ import annotations

from typing import Any

import streamlit as st


LANGUAGE = "language"
CURRENT_MODULE = "current_module"
CURRENT_PROJECT_ID = "current_project_id"
CURRENT_USER = "current_user"
AUTH_VIEW = "auth_view"
SHOW_CREATE_PROJECT = "show_create_project"
EDITING_PROJECT_ID = "editing_project_id"
PENDING_DELETE_PROJECT_ID = "pending_delete_project_id"
PENDING_DATASET_UPLOAD = "pending_dataset_upload"
PENDING_DELETE_DATA_FILE_ID = "pending_delete_data_file_id"
PENDING_DELETE_TOPIC_RUN_ID = "pending_delete_topic_run_id"
DELETE_API_CONFIG_ID = "delete_api_config_id"


def project_key(project_id: int | str, name: str) -> str:
    return f"project_{project_id}_{name}"


def get(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


def set_value(key: str, value: Any) -> None:
    st.session_state[key] = value


def set_default(key: str, value: Any) -> Any:
    return st.session_state.setdefault(key, value)


def pop(key: str, default: Any = None) -> Any:
    return st.session_state.pop(key, default)
