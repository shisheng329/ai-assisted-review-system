from __future__ import annotations

import logging

import streamlit as st

from app import ui
from app.services.i18n import language_options, set_language, t
from app.services.llm import (
    activate_api_config,
    delete_api_config,
    get_active_api_config,
    list_api_configs,
    save_api_config,
    test_active_api_config,
)
from app.services.provider_catalog import get_provider_spec, list_provider_specs


logger = logging.getLogger(__name__)


def _render_account_info(user: dict) -> str:
    ui.section_title(t("account_info"))
    with st.container(border=True):
        info_col, lang_col = st.columns([2.2, 1.4], vertical_alignment="center")
        with info_col:
            ui.info_row(t("username"), user["username"])
            ui.info_row(t("email"), user["email"])

        language_map = language_options()
        current_lang = st.session_state.get("language", user.get("preferred_language", "zh-CN"))
        selected_label = next((label for label, value in language_map.items() if value == current_lang), next(iter(language_map.keys())))
        with lang_col:
            language_label = st.radio(
                t("language_pref"),
                list(language_map.keys()),
                index=list(language_map.keys()).index(selected_label),
                horizontal=True,
                key="profile_language_pref",
            )
        chosen_lang = language_map[language_label]
        if chosen_lang != current_lang:
            set_language(chosen_lang)
            st.rerun()
        return chosen_lang


def _render_api_form(user: dict, chosen_lang: str) -> None:
    ui.section_title(t("api_config_form"), t("api_config_hint"))
    catalog_specs = list_provider_specs()
    catalog_labels = [spec.provider_name for spec in catalog_specs]
    mode = st.radio(
        t("api_config_mode"),
        ["catalog", "custom"],
        horizontal=True,
        key="api_config_mode",
        format_func=lambda item: t("catalog_mode") if item == "catalog" else t("custom_mode"),
    )

    selected_model = ""
    provider_name_value = ""
    base_url_value = ""
    if mode == "catalog":
        provider_col, model_col = st.columns(2)
        selected_provider_label = provider_col.selectbox(t("provider"), catalog_labels, key="catalog_provider")
        selected_spec = get_provider_spec(selected_provider_label)
        model_options = list(selected_spec.default_models) if selected_spec else []
        selected_model = model_col.selectbox(t("model"), model_options, key="catalog_model") if model_options else ""
        provider_name_value = selected_spec.provider_name if selected_spec else ""
        base_url_value = selected_spec.base_url if selected_spec else ""

    with st.form("api_config_form", clear_on_submit=True):
        if mode == "catalog":
            provider_name = st.text_input(t("provider_name"), value=provider_name_value, disabled=True)
            base_url = st.text_input(t("base_url"), value=base_url_value, disabled=True)
            model_name = st.text_input(t("model_name"), value=selected_model, disabled=True)
        else:
            provider_name = st.text_input(t("provider_name"), value="OpenAI-Compatible")
            base_url = st.text_input(t("base_url"), placeholder="https://api.example.com/v1")
            model_name = st.text_input(t("model_name"), placeholder="gpt-4o-mini")
        api_key = st.text_input(t("api_key"), type="password")
        submitted = st.form_submit_button(t("save_and_activate"), use_container_width=True)

    if not submitted:
        return
    if not all([provider_name.strip(), base_url.strip(), model_name.strip(), api_key.strip()]):
        st.error(t("required_fields_missing"))
        return
    save_api_config(int(user["id"]), provider_name, base_url, api_key, model_name, chosen_lang, activate=True)
    st.success(t("api_config_saved"))
    st.rerun()


def _render_api_configs(user: dict) -> None:
    user_id = int(user["id"])
    configs = list_api_configs(user_id)
    active_config = get_active_api_config(user_id)
    active_id = int(active_config["id"]) if active_config else None

    pending_delete_id = st.session_state.get("delete_api_config_id")
    if pending_delete_id:
        ui.confirm_dialog(
            t("confirm_delete_title"),
            t("delete_api_config_confirm"),
            t("confirm_delete"),
            t("cancel"),
            lambda: delete_api_config(user_id, int(pending_delete_id)),
            "delete_api_config_id",
        )

    ui.section_title(t("saved_api_config_list"), f"{len(configs)}")
    test_result = st.empty()
    test_disabled = active_config is None
    if st.button(t("test_api_config"), key="test_active_api_config", use_container_width=True, disabled=test_disabled):
        try:
            test_result.success(f"{t('api_test_success')}: {test_active_api_config(user_id)}")
        except Exception:
            logger.exception("API config test failed for user_id=%s", user_id)
            test_result.error(f"{t('api_test_failed')}: {t('api_connection_failed')}")

    if not configs:
        ui.empty_state(t("no_api_configs"), t("api_config_hint"))
        return

    with ui.fixed_list_container(height=300):
        header = st.columns([1.5, 2.3, 1.4, 1.2, 1.8])
        for col, label in zip(header, [t("provider"), t("base_url"), t("model"), t("run_status"), t("actions")]):
            col.caption(label)
        ui.row_separator()

        for config in configs:
            config_id = int(config["id"])
            is_active_config = active_id == config_id
            row = st.columns([1.5, 2.3, 1.4, 1.2, 1.8], vertical_alignment="center")
            row[0].markdown(f"**{config['provider_name']}**")
            row[1].caption(config["base_url"])
            row[2].caption(config["model_name"])
            row[3].markdown(ui.status_pill(t("current_api_in_use") if is_active_config else t("inactive"), active=is_active_config), unsafe_allow_html=True)
            action_cols = row[4].columns(2)
            if action_cols[0].button(t("set_current_api"), key=f"activate_api_{config_id}", use_container_width=True, disabled=is_active_config):
                activate_api_config(user_id, config_id)
                st.rerun()
            if action_cols[1].button(t("delete"), key=f"delete_api_{config_id}", use_container_width=True):
                st.session_state["delete_api_config_id"] = config_id
                st.rerun()
            ui.row_separator()


def render(user: dict) -> None:
    chosen_lang = _render_account_info(user)
    _render_api_configs(user)
    _render_api_form(user, chosen_lang)
