from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from app import ui
from app.services.i18n import t
from app.services.llm import get_active_api_config
from app.services.screening import (
    assemble_prompt,
    assemble_prompt_components,
    create_bilingual_review,
    delete_criteria_snapshot,
    delete_prompt_version,
    delete_screening_run,
    expand_criteria_with_ai,
    get_criteria_snapshot,
    get_existing_screening_runs_for_file,
    get_prompt_version,
    get_screening_results,
    list_criteria_snapshots,
    list_prompt_versions,
    list_screening_runs,
    parse_dimension_rules,
    run_screening,
    save_criteria_snapshot,
    save_prompt_version,
)
from app.services.storage import ManagedFileMissingError, get_active_data_file, load_project_dataframe, require_existing_path


logger = logging.getLogger(__name__)


def _default_dimensions() -> list[dict[str, str]]:
    return [{"id": "D1", "name": "", "description": ""}]


def _prefix(project_id: int) -> str:
    return f"screening_{project_id}"


def _ensure_state(prefix: str) -> None:
    defaults: dict[str, Any] = {
        f"{prefix}_review_topic": "",
        f"{prefix}_key_points": "",
        f"{prefix}_inclusion": "",
        f"{prefix}_exclusion": "",
        f"{prefix}_dimensions": _default_dimensions(),
        f"{prefix}_ai_expanded": None,
        f"{prefix}_expanded_topic": "",
        f"{prefix}_expanded_include": "",
        f"{prefix}_expanded_exclude": "",
        f"{prefix}_expanded_dims": "",
        f"{prefix}_prompt": "",
        f"{prefix}_prompt_editor": "",
        f"{prefix}_assembled_prompt_text": "",
        f"{prefix}_prompt_components": None,
        f"{prefix}_bilingual": None,
        f"{prefix}_workflow_mode": "use_ai",
        f"{prefix}_batch_size": 10,
        f"{prefix}_rate_limit": 60,
        f"{prefix}_temperature": 0.2,
        f"{prefix}_last_saved_criteria_signature": "",
        f"{prefix}_last_saved_criteria_id": None,
        f"{prefix}_pending_dimension_action": None,
        f"{prefix}_pending_load_criteria_id": None,
        f"{prefix}_pending_load_prompt_id": None,
        f"{prefix}_pending_delete_criteria_id": None,
        f"{prefix}_pending_delete_prompt_id": None,
        f"{prefix}_pending_delete_screening_run_id": None,
        f"{prefix}_criteria_library_open_ids": set(),
        f"{prefix}_prompt_library_open_ids": set(),
        f"{prefix}_show_save_criteria_dialog": False,
        f"{prefix}_confirm_start_screening": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _normalize_dimensions(dimensions: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for idx, dim in enumerate(dimensions or _default_dimensions()):
        normalized.append({
            "id": f"D{idx + 1}",
            "name": str(dim.get("name", "") or ""),
            "description": str(dim.get("description", "") or ""),
        })
    return normalized or _default_dimensions()


def _sync_dimension_widget_state(prefix: str, dimensions: list[dict[str, str]]) -> None:
    for idx, dim in enumerate(_normalize_dimensions(dimensions)):
        st.session_state[f"{prefix}_dim_name_{idx}"] = dim.get("name", "")
        st.session_state[f"{prefix}_dim_desc_{idx}"] = dim.get("description", "")


def _collect_dimensions_from_widgets(prefix: str) -> list[dict[str, str]]:
    dimensions = _normalize_dimensions(st.session_state.get(f"{prefix}_dimensions", _default_dimensions()))
    collected: list[dict[str, str]] = []
    for idx, dim in enumerate(dimensions):
        collected.append({
            "id": f"D{idx + 1}",
            "name": str(st.session_state.get(f"{prefix}_dim_name_{idx}", dim.get("name", "")) or ""),
            "description": str(st.session_state.get(f"{prefix}_dim_desc_{idx}", dim.get("description", "")) or ""),
        })
    return collected or _default_dimensions()


def _apply_pending_dimension_action(prefix: str) -> None:
    action = st.session_state.pop(f"{prefix}_pending_dimension_action", None)
    dimensions = _collect_dimensions_from_widgets(prefix)
    if action:
        kind, index = action
        index = int(index)
        if kind == "add":
            dimensions.insert(index + 1, {"id": "", "name": "", "description": ""})
        elif kind == "remove" and len(dimensions) > 1:
            dimensions.pop(index)
    dimensions = _normalize_dimensions(dimensions)
    st.session_state[f"{prefix}_dimensions"] = dimensions
    _sync_dimension_widget_state(prefix, dimensions)


def _set_ai_expanded_state(prefix: str, ai_expanded: dict[str, str] | None) -> None:
    st.session_state[f"{prefix}_ai_expanded"] = ai_expanded
    st.session_state[f"{prefix}_expanded_topic"] = (ai_expanded or {}).get("REVIEW_TOPIC", "")
    st.session_state[f"{prefix}_expanded_include"] = (ai_expanded or {}).get("INCLUSION_CRITERIA", "")
    st.session_state[f"{prefix}_expanded_exclude"] = (ai_expanded or {}).get("EXCLUSION_CRITERIA", "")
    st.session_state[f"{prefix}_expanded_dims"] = (ai_expanded or {}).get("DIMENSION_RULES", "")


def _current_ai_expanded(prefix: str) -> dict[str, str] | None:
    keys = (
        f"{prefix}_expanded_topic",
        f"{prefix}_expanded_include",
        f"{prefix}_expanded_exclude",
        f"{prefix}_expanded_dims",
    )
    if not st.session_state.get(f"{prefix}_ai_expanded") and not any(st.session_state.get(key) for key in keys):
        return None
    return {
        "REVIEW_TOPIC": st.session_state.get(f"{prefix}_expanded_topic", "").strip(),
        "INCLUSION_CRITERIA": st.session_state.get(f"{prefix}_expanded_include", "").strip(),
        "EXCLUSION_CRITERIA": st.session_state.get(f"{prefix}_expanded_exclude", "").strip(),
        "DIMENSION_RULES": st.session_state.get(f"{prefix}_expanded_dims", "").strip(),
    }


def _set_prompt_text(prefix: str, prompt: str, components: dict[str, object] | None = None) -> str:
    st.session_state[f"{prefix}_prompt"] = prompt
    st.session_state[f"{prefix}_prompt_editor"] = prompt
    st.session_state[f"{prefix}_assembled_prompt_text"] = prompt
    st.session_state[f"{prefix}_prompt_components"] = components
    st.session_state[f"{prefix}_bilingual"] = None
    return prompt


def _criteria_signature(prefix: str, dimensions: list[dict[str, str]]) -> str:
    payload = {
        "review_topic": st.session_state.get(f"{prefix}_review_topic", ""),
        "key_points": st.session_state.get(f"{prefix}_key_points", ""),
        "inclusion": st.session_state.get(f"{prefix}_inclusion", ""),
        "exclusion": st.session_state.get(f"{prefix}_exclusion", ""),
        "dimensions": _normalize_dimensions(dimensions),
        "workflow_mode": st.session_state.get(f"{prefix}_workflow_mode", "use_ai"),
        "ai_expanded": _current_ai_expanded(prefix),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _criteria_saved(prefix: str, dimensions: list[dict[str, str]]) -> bool:
    return bool(st.session_state.get(f"{prefix}_last_saved_criteria_id")) and st.session_state.get(f"{prefix}_last_saved_criteria_signature") == _criteria_signature(prefix, dimensions)


def _criteria_has_content(prefix: str, dimensions: list[dict[str, str]]) -> bool:
    text_values = [
        st.session_state.get(f"{prefix}_review_topic", ""),
        st.session_state.get(f"{prefix}_inclusion", ""),
        st.session_state.get(f"{prefix}_exclusion", ""),
    ]
    dim_values = [f"{dim.get('name', '')} {dim.get('description', '')}" for dim in dimensions]
    return any(str(value).strip() for value in [*text_values, *dim_values])


def _mark_criteria_saved(prefix: str, snapshot_id: int, dimensions: list[dict[str, str]]) -> None:
    st.session_state[f"{prefix}_last_saved_criteria_id"] = snapshot_id
    st.session_state[f"{prefix}_last_saved_criteria_signature"] = _criteria_signature(prefix, dimensions)


def _save_snapshot(prefix: str, project_id: int, user_id: int, dimensions: list[dict[str, str]], name: str, include_ai_expanded: bool = True) -> int:
    ai_expanded = _current_ai_expanded(prefix) if include_ai_expanded else None
    st.session_state[f"{prefix}_ai_expanded"] = ai_expanded
    snapshot_id = save_criteria_snapshot(
        project_id,
        user_id,
        st.session_state[f"{prefix}_review_topic"],
        st.session_state[f"{prefix}_key_points"],
        st.session_state[f"{prefix}_inclusion"],
        st.session_state[f"{prefix}_exclusion"],
        _normalize_dimensions(dimensions),
        ai_expanded,
        name=name,
    )
    _mark_criteria_saved(prefix, snapshot_id, dimensions)
    return snapshot_id


def _assemble_from_state(prefix: str, dimensions: list[dict[str, str]]) -> str:
    workflow_mode = st.session_state.get(f"{prefix}_workflow_mode", "use_ai")
    if workflow_mode == "use_ai":
        expanded = _current_ai_expanded(prefix)
        if expanded:
            expanded_dimensions = parse_dimension_rules(expanded.get("DIMENSION_RULES", ""), dimensions)
            prompt = assemble_prompt(
                expanded.get("REVIEW_TOPIC", ""),
                expanded.get("INCLUSION_CRITERIA", ""),
                expanded.get("EXCLUSION_CRITERIA", ""),
                expanded_dimensions,
            )
            components = assemble_prompt_components(
                expanded.get("REVIEW_TOPIC", ""),
                expanded.get("INCLUSION_CRITERIA", ""),
                expanded.get("EXCLUSION_CRITERIA", ""),
                expanded_dimensions,
            )
            return _set_prompt_text(prefix, prompt, components)

    prompt = assemble_prompt(
        st.session_state[f"{prefix}_review_topic"],
        st.session_state[f"{prefix}_inclusion"],
        st.session_state[f"{prefix}_exclusion"],
        dimensions,
    )
    components = assemble_prompt_components(
        st.session_state[f"{prefix}_review_topic"],
        st.session_state[f"{prefix}_inclusion"],
        st.session_state[f"{prefix}_exclusion"],
        dimensions,
    )
    return _set_prompt_text(prefix, prompt, components)


def _load_snapshot_into_state(prefix: str, snapshot: dict[str, Any]) -> None:
    dimensions = _normalize_dimensions(snapshot.get("dimensions") or _default_dimensions())
    st.session_state[f"{prefix}_review_topic"] = snapshot.get("review_topic", "")
    st.session_state[f"{prefix}_key_points"] = snapshot.get("key_points", "")
    st.session_state[f"{prefix}_inclusion"] = snapshot.get("inclusion_draft", "")
    st.session_state[f"{prefix}_exclusion"] = snapshot.get("exclusion_draft", "")
    st.session_state[f"{prefix}_dimensions"] = dimensions
    _sync_dimension_widget_state(prefix, dimensions)
    _set_ai_expanded_state(prefix, snapshot.get("ai_expanded"))
    st.session_state[f"{prefix}_workflow_mode"] = "use_ai" if snapshot.get("ai_expanded") else "skip_ai"
    _mark_criteria_saved(prefix, int(snapshot["id"]), dimensions)


def _load_prompt_into_state(prefix: str, version: dict[str, Any]) -> None:
    prompt_text = version.get("prompt_text", "")
    st.session_state[f"{prefix}_prompt"] = prompt_text
    st.session_state[f"{prefix}_prompt_editor"] = prompt_text
    st.session_state[f"{prefix}_assembled_prompt_text"] = prompt_text
    bilingual = version.get("bilingual")
    st.session_state[f"{prefix}_bilingual"] = bilingual
    st.session_state[f"{prefix}_prompt_components"] = (bilingual or {}).get("components") if isinstance(bilingual, dict) else None


def _apply_pending_loads(prefix: str, project_id: int, user_id: int) -> None:
    pending_criteria_id = st.session_state.pop(f"{prefix}_pending_load_criteria_id", None)
    if pending_criteria_id:
        snapshot = get_criteria_snapshot(project_id, user_id, int(pending_criteria_id))
        if snapshot:
            _load_snapshot_into_state(prefix, snapshot)
            st.toast(t("criteria_loaded"))

    pending_prompt_id = st.session_state.pop(f"{prefix}_pending_load_prompt_id", None)
    if pending_prompt_id:
        version = get_prompt_version(project_id, user_id, int(pending_prompt_id))
        if version:
            _load_prompt_into_state(prefix, version)
            st.toast(t("prompt_loaded"))


def _toggle_open(prefix: str, group: str, item_id: int) -> None:
    key = f"{prefix}_{group}_open_ids"
    open_ids = set(st.session_state.get(key, set()))
    if item_id in open_ids:
        open_ids.remove(item_id)
    else:
        open_ids.add(item_id)
    st.session_state[key] = open_ids


def _render_bilingual_review(prefix: str, bilingual: dict[str, Any]) -> None:
    left, right = st.columns(2)
    with left:
        ui.readonly_panel(t("english_version"), str(bilingual.get("english", "") or ""), height=340)
    with right:
        ui.readonly_panel(t("chinese_version"), str(bilingual.get("chinese", "") or ""), height=340)


def _render_dimensions(prefix: str) -> list[dict[str, str]]:
    ui.section_title(t("dimensions"))
    dimensions = _normalize_dimensions(st.session_state[f"{prefix}_dimensions"])
    header = st.columns([0.7, 2.4, 3.8, 1.15, 1.15])
    header[1].caption(t("dimension_name"))
    header[2].caption(t("dimension_description"))
    for idx, dim in enumerate(dimensions):
        cols = st.columns([0.7, 2.4, 3.8, 1.15, 1.15], vertical_alignment="center")
        cols[0].markdown(f"**D{idx + 1}**")
        cols[1].text_input(
            t("dimension_name"),
            key=f"{prefix}_dim_name_{idx}",
            label_visibility="collapsed",
            placeholder=t("dimension_name"),
        )
        cols[2].text_input(
            t("dimension_description"),
            key=f"{prefix}_dim_desc_{idx}",
            label_visibility="collapsed",
            placeholder=t("dimension_description"),
        )
        if cols[3].button(t("add"), key=f"{prefix}_add_dim_{idx}", help=t("add_dimension"), use_container_width=True):
            st.session_state[f"{prefix}_pending_dimension_action"] = ("add", idx)
            st.rerun()
        if cols[4].button(
            t("remove"),
            key=f"{prefix}_remove_dim_{idx}",
            help=t("remove_dimension"),
            use_container_width=True,
            disabled=len(dimensions) == 1,
        ):
            st.session_state[f"{prefix}_pending_dimension_action"] = ("remove", idx)
            st.rerun()

    dimensions = _collect_dimensions_from_widgets(prefix)
    st.session_state[f"{prefix}_dimensions"] = dimensions
    return dimensions


@st.dialog(t("save_standard_name_title"))
def _render_save_criteria_dialog(prefix: str, project_id: int, user_id: int, dimensions: list[dict[str, str]]) -> None:
    st.write(t("save_standard_name_body"))
    name = st.text_input(t("criteria_name"), key=f"{prefix}_save_criteria_name_dialog")
    cancel_col, confirm_col = st.columns(2)
    if cancel_col.button(t("cancel"), key=f"{prefix}_cancel_save_criteria", use_container_width=True):
        st.session_state[f"{prefix}_show_save_criteria_dialog"] = False
        st.rerun()
    if confirm_col.button(t("save_standard"), key=f"{prefix}_confirm_save_criteria", type="primary", use_container_width=True):
        cleaned_name = name.strip()
        if not cleaned_name:
            st.error(t("criteria_name_required"))
            return
        if not _criteria_has_content(prefix, dimensions):
            st.error(t("criteria_content_required"))
            return
        _save_snapshot(prefix, project_id, user_id, dimensions, cleaned_name)
        st.session_state[f"{prefix}_show_save_criteria_dialog"] = False
        st.session_state[f"{prefix}_save_criteria_name_dialog"] = ""
        st.success(t("criteria_saved"))
        st.rerun()


def _render_criteria_library(prefix: str, project_id: int, user_id: int) -> None:
    pending_delete_id = st.session_state.get(f"{prefix}_pending_delete_criteria_id")
    if pending_delete_id:
        ui.confirm_dialog(
            t("confirm_delete_title"),
            t("delete_criteria_confirm"),
            t("confirm_delete"),
            t("cancel"),
            lambda: delete_criteria_snapshot(project_id, user_id, int(pending_delete_id)),
            f"{prefix}_pending_delete_criteria_id",
        )

    ui.section_title(t("criteria_library"))
    snapshots = list_criteria_snapshots(project_id, user_id)
    if not snapshots:
        ui.empty_state(t("no_criteria_saved"))
        return

    with st.container(height=260, border=True):
        open_ids = set(st.session_state.get(f"{prefix}_criteria_library_open_ids", set()))
        for item in snapshots:
            item_id = int(item["id"])
            cols = st.columns([3.4, 1.1, 1.1, 1.1], vertical_alignment="center")
            cols[0].markdown(f"**{item.get('name') or item_id}**  ")
            cols[0].caption(item.get("created_at", ""))
            view_label = t("collapse") if item_id in open_ids else t("view")
            if cols[1].button(view_label, key=f"{prefix}_view_criteria_{item_id}", use_container_width=True):
                _toggle_open(prefix, "criteria_library", item_id)
                st.rerun()
            if cols[2].button(t("load"), key=f"{prefix}_load_criteria_{item_id}", use_container_width=True):
                st.session_state[f"{prefix}_pending_load_criteria_id"] = item_id
                st.rerun()
            if cols[3].button(t("delete"), key=f"{prefix}_delete_criteria_{item_id}", use_container_width=True):
                st.session_state[f"{prefix}_pending_delete_criteria_id"] = item_id
                st.rerun()
            if item_id in open_ids:
                st.caption(t("review_topic"))
                st.write(item.get("review_topic", ""))
                st.caption(t("inclusion_criteria"))
                st.write(item.get("inclusion_draft", ""))
                st.caption(t("exclusion_criteria"))
                st.write(item.get("exclusion_draft", ""))
            st.divider()


def _render_prompt_library(prefix: str, project_id: int, user_id: int) -> None:
    pending_delete_id = st.session_state.get(f"{prefix}_pending_delete_prompt_id")
    if pending_delete_id:
        ui.confirm_dialog(
            t("confirm_delete_title"),
            t("delete_prompt_confirm"),
            t("confirm_delete"),
            t("cancel"),
            lambda: delete_prompt_version(project_id, user_id, int(pending_delete_id)),
            f"{prefix}_pending_delete_prompt_id",
        )

    ui.section_title(t("prompt_versions"))
    versions = list_prompt_versions(project_id, user_id)
    if not versions:
        ui.empty_state(t("no_prompt_saved"))
        return

    with st.container(height=260, border=True):
        open_ids = set(st.session_state.get(f"{prefix}_prompt_library_open_ids", set()))
        for item in versions:
            item_id = int(item["id"])
            cols = st.columns([3.4, 1.1, 1.1, 1.1], vertical_alignment="center")
            cols[0].markdown(f"**{item.get('name') or item_id}**")
            cols[0].caption(item.get("created_at", ""))
            view_label = t("collapse") if item_id in open_ids else t("view")
            if cols[1].button(view_label, key=f"{prefix}_view_prompt_{item_id}", use_container_width=True):
                _toggle_open(prefix, "prompt_library", item_id)
                st.rerun()
            if cols[2].button(t("load"), key=f"{prefix}_load_prompt_{item_id}", use_container_width=True):
                st.session_state[f"{prefix}_pending_load_prompt_id"] = item_id
                st.rerun()
            if cols[3].button(t("delete"), key=f"{prefix}_delete_prompt_{item_id}", use_container_width=True):
                st.session_state[f"{prefix}_pending_delete_prompt_id"] = item_id
                st.rerun()
            if item_id in open_ids:
                ui.readonly_panel(t("prompt_text"), item.get("prompt_text", ""), height=220)
            st.divider()


def _render_results(prefix: str, project_id: int, user_id: int) -> None:
    runs = list_screening_runs(project_id, user_id)
    if not runs:
        return

    ui.section_title(t("screening_results"))
    selected_run = st.selectbox(
        t("screening_run"),
        runs,
        format_func=lambda item: f"#{item['id']} | {item['created_at']} | {item['status']}",
    )
    result_df = get_screening_results(int(selected_run["id"]))
    if not result_df.empty:
        dist = result_df["decision"].value_counts().reset_index()
        dist.columns = ["decision", "count"]
        fig = px.bar(dist, x="decision", y="count", color="decision", color_discrete_sequence=["#0f9f8a", "#b7791f", "#2f6fda"])
        fig.update_layout(height=260, margin=dict(l=12, r=12, t=32, b=24))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(result_df, use_container_width=True)
        if selected_run.get("export_path"):
            try:
                export_path = require_existing_path(selected_run["export_path"])
                with export_path.open("rb") as fh:
                    st.download_button(t("export_results"), data=fh.read(), file_name=export_path.name, mime="text/csv")
            except ManagedFileMissingError:
                logger.exception("Screening export file is missing for run_id=%s", selected_run["id"])
                st.warning(t("result_file_missing"))
    else:
        st.info(t("no_data"))

    pending_delete_id = st.session_state.get(f"{prefix}_pending_delete_screening_run_id")
    if pending_delete_id:
        ui.confirm_dialog(
            t("confirm_delete_title"),
            t("delete_screening_result_confirm"),
            t("confirm_delete"),
            t("cancel"),
            lambda: delete_screening_run(project_id, user_id, int(pending_delete_id)),
            f"{prefix}_pending_delete_screening_run_id",
        )
    if st.button(t("delete_screening_result"), key=f"delete_screening_run_{selected_run['id']}", use_container_width=True):
        st.session_state[f"{prefix}_pending_delete_screening_run_id"] = int(selected_run["id"])
        st.rerun()


def render(project: dict[str, object], user: dict[str, object]) -> None:
    project_id = int(project["id"])
    user_id = int(user["id"])
    prefix = _prefix(project_id)
    _ensure_state(prefix)
    _apply_pending_loads(prefix, project_id, user_id)
    _apply_pending_dimension_action(prefix)

    file_record = get_active_data_file(project_id, user_id)
    if not file_record:
        ui.empty_state(t("no_active_data_file"))
        return

    try:
        _, df = load_project_dataframe(project_id, user_id, int(file_record["id"]))
    except ManagedFileMissingError:
        logger.exception("Active data source is missing for project_id=%s user_id=%s", project_id, user_id)
        st.error(t("managed_file_missing"))
        return
    except Exception:
        logger.exception("Active data source loading failed for project_id=%s user_id=%s", project_id, user_id)
        st.error(t("data_preview_failed"))
        return

    if df is None or df.empty:
        ui.empty_state(t("no_data"))
        return

    st.text_area(t("review_topic"), key=f"{prefix}_review_topic", height=88)
    st.text_area(t("key_points"), key=f"{prefix}_key_points", height=88)
    st.text_area(t("inclusion_criteria"), key=f"{prefix}_inclusion", height=120)
    st.text_area(t("exclusion_criteria"), key=f"{prefix}_exclusion", height=120)

    dimensions = _render_dimensions(prefix)

    st.radio(
        t("workflow_mode"),
        ["use_ai", "skip_ai"],
        format_func=lambda value: t("use_ai_expansion") if value == "use_ai" else t("skip_ai_expansion"),
        key=f"{prefix}_workflow_mode",
        horizontal=True,
    )

    if st.session_state[f"{prefix}_workflow_mode"] == "use_ai":
        if st.button(t("expand_with_ai"), use_container_width=True):
            try:
                expanded = expand_criteria_with_ai(
                    user_id,
                    st.session_state[f"{prefix}_review_topic"],
                    st.session_state[f"{prefix}_key_points"],
                    st.session_state[f"{prefix}_inclusion"],
                    st.session_state[f"{prefix}_exclusion"],
                    dimensions,
                )
                _set_ai_expanded_state(prefix, expanded)
                st.session_state[f"{prefix}_last_saved_criteria_id"] = None
                st.rerun()
            except Exception:
                logger.exception("AI criteria expansion failed for project_id=%s user_id=%s", project_id, user_id)
                st.error(t("api_connection_failed"))

        if _current_ai_expanded(prefix):
            st.text_area(t("expanded_review_topic"), key=f"{prefix}_expanded_topic", height=88)
            st.text_area(t("expanded_inclusion_criteria"), key=f"{prefix}_expanded_include", height=120)
            st.text_area(t("expanded_exclusion_criteria"), key=f"{prefix}_expanded_exclude", height=120)
            st.text_area(t("expanded_dimension_rules"), key=f"{prefix}_expanded_dims", height=150)

    button_cols = st.columns(2)
    if button_cols[0].button(t("save_standard"), key=f"{prefix}_open_save_criteria", use_container_width=True):
        if not _criteria_has_content(prefix, dimensions):
            st.error(t("criteria_content_required"))
        else:
            st.session_state[f"{prefix}_show_save_criteria_dialog"] = True
    if st.session_state.get(f"{prefix}_show_save_criteria_dialog"):
        _render_save_criteria_dialog(prefix, project_id, user_id, dimensions)

    can_assemble = _criteria_saved(prefix, dimensions)
    if button_cols[1].button(t("assemble_prompt"), use_container_width=True, disabled=not can_assemble):
        _assemble_from_state(prefix, dimensions)
        st.rerun()
    if not can_assemble:
        st.info(t("criteria_unsaved_before_prompt"))

    st.divider()
    _render_criteria_library(prefix, project_id, user_id)

    st.divider()
    prompt_text = st.text_area(t("prompt_text"), key=f"{prefix}_prompt_editor", height=300)
    st.session_state[f"{prefix}_prompt"] = prompt_text

    if st.button(t("review_with_ai"), key=f"{prefix}_review_prompt_button", use_container_width=True, disabled=not prompt_text.strip()):
        try:
            bilingual = create_bilingual_review(user_id, prompt_text, st.session_state.get(f"{prefix}_prompt_components"))
            st.session_state[f"{prefix}_bilingual"] = bilingual
            st.rerun()
        except Exception:
            logger.exception("Bilingual prompt review failed for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("api_connection_failed"))

    bilingual = st.session_state.get(f"{prefix}_bilingual")
    if bilingual:
        ui.section_title(t("bilingual_review"))
        _render_bilingual_review(prefix, bilingual)

    prompt_name_col, save_prompt_col = st.columns([2.4, 1], vertical_alignment="bottom")
    prompt_name = prompt_name_col.text_input(t("prompt_name"), key=f"{prefix}_save_prompt_name", placeholder=t("prompt_name"))
    if save_prompt_col.button(t("save_prompt"), use_container_width=True, disabled=not prompt_text.strip()):
        cleaned_prompt_name = prompt_name.strip()
        if not cleaned_prompt_name:
            st.error(t("prompt_name_required"))
        else:
            version_id = save_prompt_version(project_id, user_id, prompt_text, st.session_state.get(f"{prefix}_bilingual"), name=cleaned_prompt_name)
            st.success(f"{t('prompt_saved')} #{version_id}")

    st.divider()
    _render_prompt_library(prefix, project_id, user_id)

    st.divider()
    ui.section_title(t("run_screening"))
    api_config = get_active_api_config(user_id)
    if not api_config:
        st.warning(t("api_missing"))

    completed_existing_runs = get_existing_screening_runs_for_file(project_id, user_id, int(file_record["id"]))
    if completed_existing_runs:
        st.warning(t("existing_screening_result_hint"))

    control_cols = st.columns(3)
    control_cols[0].number_input(t("batch_size"), min_value=1, max_value=100, step=1, key=f"{prefix}_batch_size")
    control_cols[1].number_input(t("rate_limit_per_min"), min_value=1, max_value=600, step=1, key=f"{prefix}_rate_limit")
    control_cols[2].number_input(t("temperature"), min_value=0.0, max_value=1.0, step=0.1, key=f"{prefix}_temperature")

    confirmed = st.checkbox(t("confirm_start_screening"), key=f"{prefix}_confirm_start_screening")
    if not confirmed:
        st.info(t("screening_disabled_no_confirm"))

    latest_versions = list_prompt_versions(project_id, user_id)
    latest_version_id = int(latest_versions[0]["id"]) if latest_versions else None
    run_disabled = api_config is None or not prompt_text.strip() or not confirmed

    def execute_screening_run() -> None:
        try:
            progress_bar = st.progress(0)
            progress_text = st.empty()

            def _progress(done: int, total: int) -> None:
                ratio = 0 if total <= 0 else min(1.0, done / total)
                progress_bar.progress(ratio)
                progress_text.caption(t("screening_progress_text").format(done=done, total=total))

            result = run_screening(
                project_id,
                user_id,
                int(file_record["id"]),
                df,
                prompt_text,
                dimensions,
                int(st.session_state[f"{prefix}_batch_size"]),
                int(st.session_state[f"{prefix}_rate_limit"]),
                float(st.session_state[f"{prefix}_temperature"]),
                latest_version_id,
                progress_callback=_progress,
            )
            st.success(f"{t('run_complete')} #{result['run_id']}")
            st.rerun()
        except ManagedFileMissingError:
            logger.exception("Screening source file is missing for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("managed_file_missing"))
        except Exception:
            logger.exception("Screening run failed for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("screening_run_failed"))

    if st.button(t("run_screening"), use_container_width=True, disabled=run_disabled):
        execute_screening_run()

    _render_results(prefix, project_id, user_id)
