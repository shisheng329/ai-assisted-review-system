from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from app import ui
from app.services.i18n import t
from app.services.llm import get_active_api_config
from app.services.screening import (
    assemble_prompt,
    assemble_prompt_components,
    create_bilingual_review,
    expand_criteria_with_ai,
    get_screening_results,
    list_criteria_snapshots,
    list_prompt_versions,
    list_screening_runs,
    parse_dimension_rules,
    run_screening,
    save_criteria_snapshot,
    save_prompt_version,
)
from app.services.storage import get_active_data_file, load_project_dataframe


def _default_dimensions() -> list[dict[str, str]]:
    return [{"id": "D1", "name": "", "description": ""}]


def _ensure_state(project_id: int) -> None:
    prefix = f"screening_{project_id}"
    st.session_state.setdefault(f"{prefix}_review_topic", "")
    st.session_state.setdefault(f"{prefix}_key_points", "")
    st.session_state.setdefault(f"{prefix}_inclusion", "")
    st.session_state.setdefault(f"{prefix}_exclusion", "")
    st.session_state.setdefault(f"{prefix}_dimensions", _default_dimensions())
    st.session_state.setdefault(f"{prefix}_ai_expanded", None)
    st.session_state.setdefault(f"{prefix}_expanded_topic", "")
    st.session_state.setdefault(f"{prefix}_expanded_include", "")
    st.session_state.setdefault(f"{prefix}_expanded_exclude", "")
    st.session_state.setdefault(f"{prefix}_expanded_dims", "")
    st.session_state.setdefault(f"{prefix}_prompt", "")
    st.session_state.setdefault(f"{prefix}_prompt_editor", "")
    st.session_state.setdefault(f"{prefix}_assembled_prompt_text", "")
    st.session_state.setdefault(f"{prefix}_prompt_components", None)
    st.session_state.setdefault(f"{prefix}_bilingual", None)
    st.session_state.setdefault(f"{prefix}_workflow_mode", "use_ai")
    st.session_state.setdefault(f"{prefix}_batch_size", 10)
    st.session_state.setdefault(f"{prefix}_rate_limit", 60)
    st.session_state.setdefault(f"{prefix}_temperature", 0.2)
    st.session_state.setdefault(f"{prefix}_pending_snapshot_restore", None)
    st.session_state.setdefault(f"{prefix}_pending_prompt_restore", None)


def _sync_dimension_widget_state(prefix: str, dimensions: list[dict[str, str]]) -> None:
    for idx, dim in enumerate(dimensions):
        st.session_state[f"{prefix}_dim_name_{idx}"] = dim.get("name", "")
        st.session_state[f"{prefix}_dim_desc_{idx}"] = dim.get("description", "")


def _set_prompt_text(prefix: str, prompt: str, components: dict[str, object] | None = None) -> str:
    st.session_state[f"{prefix}_prompt"] = prompt
    st.session_state[f"{prefix}_prompt_editor"] = prompt
    st.session_state[f"{prefix}_assembled_prompt_text"] = prompt
    st.session_state[f"{prefix}_prompt_components"] = components
    st.session_state[f"{prefix}_bilingual"] = None
    return prompt


def _set_ai_expanded_state(prefix: str, ai_expanded: dict[str, str] | None) -> None:
    st.session_state[f"{prefix}_ai_expanded"] = ai_expanded
    st.session_state[f"{prefix}_expanded_topic"] = (ai_expanded or {}).get("REVIEW_TOPIC", "")
    st.session_state[f"{prefix}_expanded_include"] = (ai_expanded or {}).get("INCLUSION_CRITERIA", "")
    st.session_state[f"{prefix}_expanded_exclude"] = (ai_expanded or {}).get("EXCLUSION_CRITERIA", "")
    st.session_state[f"{prefix}_expanded_dims"] = (ai_expanded or {}).get("DIMENSION_RULES", "")


def _current_ai_expanded(prefix: str) -> dict[str, str] | None:
    if not st.session_state.get(f"{prefix}_ai_expanded") and not any(
        st.session_state.get(key)
        for key in (
            f"{prefix}_expanded_topic",
            f"{prefix}_expanded_include",
            f"{prefix}_expanded_exclude",
            f"{prefix}_expanded_dims",
        )
    ):
        return None
    return {
        "REVIEW_TOPIC": st.session_state.get(f"{prefix}_expanded_topic", "").strip(),
        "INCLUSION_CRITERIA": st.session_state.get(f"{prefix}_expanded_include", "").strip(),
        "EXCLUSION_CRITERIA": st.session_state.get(f"{prefix}_expanded_exclude", "").strip(),
        "DIMENSION_RULES": st.session_state.get(f"{prefix}_expanded_dims", "").strip(),
    }


def _assemble_from_state(prefix: str, dimensions: list[dict[str, str]]) -> str:
    workflow_mode = st.session_state[f"{prefix}_workflow_mode"]
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


def _save_snapshot(prefix: str, project_id: int, user_id: int, dimensions: list[dict[str, str]], include_ai_expanded: bool = True) -> int:
    ai_expanded = _current_ai_expanded(prefix) if include_ai_expanded else None
    st.session_state[f"{prefix}_ai_expanded"] = ai_expanded
    return save_criteria_snapshot(
        project_id,
        user_id,
        st.session_state[f"{prefix}_review_topic"],
        st.session_state[f"{prefix}_key_points"],
        st.session_state[f"{prefix}_inclusion"],
        st.session_state[f"{prefix}_exclusion"],
        dimensions,
        ai_expanded,
    )


def _render_bilingual_review(prefix: str, bilingual: dict[str, str]) -> None:
    english = escape(bilingual.get("english", ""))
    chinese = escape(bilingual.get("chinese", ""))
    html = f"""
    <style>
      .bi-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }}
      .bi-card {{
        border: 1px solid rgba(16,185,129,0.18);
        border-radius: 8px;
        background: #ffffff;
        overflow: hidden;
      }}
      .bi-title {{
        padding: 10px 14px;
        font-weight: 600;
        border-bottom: 1px solid rgba(16,185,129,0.14);
        background: #ecfdf5;
      }}
      .bi-body {{
        height: 320px;
        overflow-y: auto;
        padding: 14px;
        white-space: pre-wrap;
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        line-height: 1.55;
      }}
    </style>
    <div class="bi-grid">
      <div class="bi-card">
        <div class="bi-title">{escape(t("english_version"))}</div>
        <div class="bi-body" id="en-{prefix}">{english}</div>
      </div>
      <div class="bi-card">
        <div class="bi-title">{escape(t("chinese_version"))}</div>
        <div class="bi-body" id="zh-{prefix}">{chinese}</div>
      </div>
    </div>
    <script>
      const left = document.getElementById("en-{prefix}");
      const right = document.getElementById("zh-{prefix}");
      let syncing = false;
      function sync(source, target) {{
        source.addEventListener("scroll", () => {{
          if (syncing) return;
          syncing = true;
          target.scrollTop = source.scrollTop;
          requestAnimationFrame(() => syncing = false);
        }});
      }}
      sync(left, right);
      sync(right, left);
    </script>
    """
    components.html(html, height=370)


def _apply_pending_restores(prefix: str, project_id: int, user_id: int) -> None:
    snapshot_id = st.session_state.get(f"{prefix}_pending_snapshot_restore")
    if snapshot_id:
        snapshot = next((item for item in list_criteria_snapshots(project_id, user_id) if int(item["id"]) == int(snapshot_id)), None)
        if snapshot:
            dimensions = snapshot["dimensions"] or _default_dimensions()
            st.session_state[f"{prefix}_review_topic"] = snapshot["review_topic"]
            st.session_state[f"{prefix}_key_points"] = snapshot["key_points"]
            st.session_state[f"{prefix}_inclusion"] = snapshot["inclusion_draft"]
            st.session_state[f"{prefix}_exclusion"] = snapshot["exclusion_draft"]
            st.session_state[f"{prefix}_dimensions"] = dimensions
            _sync_dimension_widget_state(prefix, dimensions)
            _set_ai_expanded_state(prefix, snapshot["ai_expanded"])
            st.session_state[f"{prefix}_workflow_mode"] = "use_ai" if snapshot["ai_expanded"] else "skip_ai"
        st.session_state[f"{prefix}_pending_snapshot_restore"] = None

    prompt_id = st.session_state.get(f"{prefix}_pending_prompt_restore")
    if prompt_id:
        version = next((item for item in list_prompt_versions(project_id, user_id) if int(item["id"]) == int(prompt_id)), None)
        if version:
            st.session_state[f"{prefix}_prompt"] = version["prompt_text"]
            st.session_state[f"{prefix}_prompt_editor"] = version["prompt_text"]
            st.session_state[f"{prefix}_assembled_prompt_text"] = version["prompt_text"]
            bilingual = version["bilingual"]
            st.session_state[f"{prefix}_bilingual"] = bilingual
            st.session_state[f"{prefix}_prompt_components"] = (bilingual or {}).get("components") if isinstance(bilingual, dict) else None
        st.session_state[f"{prefix}_pending_prompt_restore"] = None


def render(project: dict, user: dict) -> None:
    project_id = int(project["id"])
    user_id = int(user["id"])
    _ensure_state(project_id)
    prefix = f"screening_{project_id}"
    _apply_pending_restores(prefix, project_id, user_id)
    api_config = get_active_api_config(user_id)
    active_file = get_active_data_file(project_id, user_id)
    if not active_file:
        st.warning(t("screening_source_hint"))
        return
    st.caption(f"{t('current_data_source')}: {active_file['filename']} ({active_file['row_count']})")

    ui.section_title(t("criteria_draft"))
    st.session_state[f"{prefix}_review_topic"] = st.text_area(t("review_topic"), value=st.session_state[f"{prefix}_review_topic"])
    st.session_state[f"{prefix}_key_points"] = st.text_area(t("key_points"), value=st.session_state[f"{prefix}_key_points"])
    st.session_state[f"{prefix}_inclusion"] = st.text_area(t("inclusion_criteria"), value=st.session_state[f"{prefix}_inclusion"])
    st.session_state[f"{prefix}_exclusion"] = st.text_area(t("exclusion_criteria"), value=st.session_state[f"{prefix}_exclusion"])

    dimensions = st.session_state[f"{prefix}_dimensions"]
    ui.section_title(t("dimensions"))
    header = st.columns([1, 3, 4, 0.7, 0.7])
    header[1].caption(t("dimension_name"))
    header[2].caption(t("dimension_description"))
    for idx, dim in enumerate(dimensions):
        cols = st.columns([1, 3, 4, 0.7, 0.7], vertical_alignment="center")
        cols[0].markdown(f"**D{idx + 1}**")
        dim["name"] = cols[1].text_input(
            t("dimension_name"),
            value=dim.get("name", ""),
            key=f"{prefix}_dim_name_{idx}",
            label_visibility="collapsed",
            placeholder=t("dimension_name"),
        )
        dim["description"] = cols[2].text_input(
            t("dimension_description"),
            value=dim.get("description", ""),
            key=f"{prefix}_dim_desc_{idx}",
            label_visibility="collapsed",
            placeholder=t("dimension_description"),
        )
        if cols[3].button("+", key=f"{prefix}_add_dim_{idx}", use_container_width=True):
            dimensions.insert(idx + 1, {"id": "", "name": "", "description": ""})
            st.rerun()
        if cols[4].button("-", key=f"{prefix}_remove_dim_{idx}", use_container_width=True, disabled=len(dimensions) == 1):
            dimensions.pop(idx)
            st.rerun()
    st.session_state[f"{prefix}_dimensions"] = dimensions

    workflow_mode = st.radio(
        t("workflow_mode"),
        ["use_ai", "skip_ai"],
        horizontal=True,
        key=f"{prefix}_workflow_mode",
        format_func=lambda item: t("use_ai_expansion") if item == "use_ai" else t("skip_ai_expansion"),
    )

    if workflow_mode == "skip_ai":
        skip_col1, skip_col2 = st.columns(2)
        if skip_col1.button(t("save_standard"), use_container_width=True, key=f"{prefix}_save_standard_skip"):
            snapshot_id = _save_snapshot(prefix, project_id, user_id, dimensions, include_ai_expanded=False)
            _assemble_from_state(prefix, dimensions)
            st.success(f"{t('success_saved')} #{snapshot_id}")
            st.rerun()
        if skip_col2.button(t("skip_and_assemble_prompt"), use_container_width=True, key=f"{prefix}_skip_and_assemble"):
            _save_snapshot(prefix, project_id, user_id, dimensions, include_ai_expanded=False)
            _assemble_from_state(prefix, dimensions)
            st.success(t("run_complete"))
            st.rerun()
    else:
        if st.button(t("expand_with_ai"), use_container_width=True, key=f"{prefix}_expand_ai", disabled=api_config is None):
            try:
                ai_expanded = expand_criteria_with_ai(
                    user_id,
                    st.session_state[f"{prefix}_review_topic"],
                    st.session_state[f"{prefix}_key_points"],
                    st.session_state[f"{prefix}_inclusion"],
                    st.session_state[f"{prefix}_exclusion"],
                    dimensions,
                )
                _set_ai_expanded_state(prefix, ai_expanded)
                st.success(t("run_complete"))
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        if st.session_state.get(f"{prefix}_ai_expanded") or st.session_state.get(f"{prefix}_expanded_topic"):
            ui.section_title(t("ai_expansion"))
            st.text_area(t("expanded_review_topic"), height=120, key=f"{prefix}_expanded_topic")
            st.text_area(t("expanded_inclusion_criteria"), height=120, key=f"{prefix}_expanded_include")
            st.text_area(t("expanded_exclusion_criteria"), height=120, key=f"{prefix}_expanded_exclude")
            st.text_area(t("expanded_dimension_rules"), height=150, key=f"{prefix}_expanded_dims")

        ai_col1, ai_col2 = st.columns(2)
        if ai_col1.button(t("save_standard"), use_container_width=True, key=f"{prefix}_save_standard_ai"):
            snapshot_id = _save_snapshot(prefix, project_id, user_id, dimensions, include_ai_expanded=True)
            st.success(f"{t('success_saved')} #{snapshot_id}")
        if ai_col2.button(t("assemble_prompt"), use_container_width=True, key=f"{prefix}_assemble_ai"):
            _assemble_from_state(prefix, dimensions)
            st.success(t("run_complete"))
            st.rerun()

    with st.expander(t("history_records")):
        snapshots = list_criteria_snapshots(project_id, user_id)
        for snapshot in snapshots[:10]:
            if st.button(f"{t('screening_standard')} #{snapshot['id']} | {snapshot['created_at']}", key=f"restore_snapshot_{snapshot['id']}"):
                st.session_state[f"{prefix}_pending_snapshot_restore"] = int(snapshot["id"])
                st.rerun()

    ui.section_title(t("final_prompt"))
    st.text_area(t("prompt_text"), height=450, key=f"{prefix}_prompt_editor")
    st.session_state[f"{prefix}_prompt"] = st.session_state.get(f"{prefix}_prompt_editor", "")
    prompt_text = st.session_state[f"{prefix}_prompt"]
    existing_bilingual = st.session_state.get(f"{prefix}_bilingual")
    if isinstance(existing_bilingual, dict) and existing_bilingual.get("english") != prompt_text:
        st.session_state[f"{prefix}_bilingual"] = None

    review_col, version_col = st.columns(2)
    if review_col.button(t("bilingual_review"), use_container_width=True, disabled=(api_config is None or not prompt_text.strip())):
        try:
            components = st.session_state.get(f"{prefix}_prompt_components")
            if prompt_text != st.session_state.get(f"{prefix}_assembled_prompt_text"):
                components = None
            st.session_state[f"{prefix}_bilingual"] = create_bilingual_review(user_id, prompt_text, components)
            st.success(t("run_complete"))
        except Exception as exc:
            st.error(str(exc))
    if version_col.button(t("save_as_new_version"), use_container_width=True, disabled=not prompt_text.strip()):
        version_id = save_prompt_version(project_id, user_id, prompt_text, st.session_state[f"{prefix}_bilingual"])
        st.success(f"{t('success_saved')} #{version_id}")

    bilingual = st.session_state.get(f"{prefix}_bilingual")
    if bilingual:
        _render_bilingual_review(prefix, bilingual)

    prompt_versions = list_prompt_versions(project_id, user_id)
    with st.expander(t("prompt_versions")):
        for version in prompt_versions[:10]:
            if st.button(f"{t('prompt_versions')} #{version['id']} | {version['created_at']}", key=f"restore_prompt_{version['id']}"):
                st.session_state[f"{prefix}_pending_prompt_restore"] = int(version["id"])
                st.rerun()

    ui.section_title(t("start_screening"))
    if st.button(t("run_screening"), use_container_width=True, disabled=(api_config is None or not prompt_text.strip())):
        file_record, df = load_project_dataframe(project_id, user_id)
        if df is None:
            st.warning(t("screening_source_hint"))
        else:
            latest_version_id = prompt_versions[0]["id"] if prompt_versions else None
            try:
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
                )
                st.success(f"{t('run_complete')} #{result['run_id']}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    params1, params2, params3 = st.columns(3)
    params1.number_input(t("batch_size"), min_value=1, max_value=100, key=f"{prefix}_batch_size")
    params2.number_input(t("rate_limit_per_min"), min_value=0, max_value=600, key=f"{prefix}_rate_limit")
    params3.slider(t("temperature"), min_value=0.0, max_value=1.0, step=0.1, key=f"{prefix}_temperature")

    runs = list_screening_runs(project_id, user_id)
    if runs:
        ui.section_title(t("screening_results"))
        selected_run = st.selectbox(t("screening_run"), runs, format_func=lambda item: f"#{item['id']} | {item['created_at']} | {item['status']}")
        result_df = get_screening_results(int(selected_run["id"]))
        if not result_df.empty:
            dist = result_df["decision"].value_counts().reset_index()
            dist.columns = ["decision", "count"]
            fig = px.bar(dist, x="decision", y="count", color="decision")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(result_df, use_container_width=True)
            if selected_run.get("export_path"):
                with open(selected_run["export_path"], "rb") as fh:
                    st.download_button(t("export_results"), data=fh.read(), file_name="screening_results.csv", mime="text/csv")
