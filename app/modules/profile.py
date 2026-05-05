from __future__ import annotations

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


def render(user: dict) -> None:
    ui.section_title(t("profile"))
    st.caption(f"{user['display_name']} / {user['username']} / {user['email']}")

    language_map = language_options()
    current_lang = st.session_state.get("language", user.get("preferred_language", "zh-CN"))
    selected_label = next((label for label, value in language_map.items() if value == current_lang), "中文")
    language_label = st.selectbox(t("language_pref"), list(language_map.keys()), index=list(language_map.keys()).index(selected_label))
    chosen_lang = language_map[language_label]
    if chosen_lang != current_lang:
        set_language(chosen_lang)
        st.rerun()

    ui.section_title(t("api_configs"))
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
        selected_provider_label = st.selectbox(t("provider"), catalog_labels, key="catalog_provider")
        selected_spec = get_provider_spec(selected_provider_label)
        model_options = list(selected_spec.default_models) if selected_spec else []
        selected_model = st.selectbox(t("model"), model_options, key="catalog_model") if model_options else ""
        provider_name_value = selected_spec.provider_name if selected_spec else ""
        base_url_value = selected_spec.base_url if selected_spec else ""
        st.text_input(t("base_url"), value=base_url_value, disabled=True, key="catalog_base_url")

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
    if submitted and all([provider_name.strip(), base_url.strip(), model_name.strip(), api_key.strip()]):
        save_api_config(int(user["id"]), provider_name, base_url, api_key, model_name, chosen_lang, activate=True)
        st.success(t("success_saved"))
        st.rerun()

    configs = list_api_configs(int(user["id"]))
    active_config = get_active_api_config(int(user["id"]))
    if not configs:
        st.info(t("no_data"))
        return

    if st.button(t("test_api_config"), key="test_active_api_config", use_container_width=True, disabled=active_config is None):
        try:
            st.success(f"{t('api_test_success')}: {test_active_api_config(int(user['id']))}")
        except Exception as exc:
            st.error(f"{t('api_test_failed')}: {exc}")

    for config in configs:
        cols = st.columns([1.7, 2.45, 1.65, 1.9, 1.25])
        cols[0].markdown(f"**{config['provider_name']}**")
        cols[1].caption(config["base_url"])
        cols[2].caption(config["model_name"])
        if active_config and active_config["id"] == config["id"]:
            cols[3].success(t("active"))
        elif cols[3].button(t("save_and_activate"), key=f"activate_api_{config['id']}", use_container_width=True):
            activate_api_config(int(user["id"]), int(config["id"]))
            st.rerun()
        if cols[4].button(t("delete_config"), key=f"delete_api_{config['id']}", use_container_width=True):
            delete_api_config(int(user["id"]), int(config["id"]))
            st.success(t("success_saved"))
            st.rerun()
