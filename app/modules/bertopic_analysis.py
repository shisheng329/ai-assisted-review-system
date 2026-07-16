from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import session_state as ss
from app import ui
from app.services.bertopic_service import (
    BERTopicDependencyError,
    BERTopicInputError,
    BERTopicRuntimeError,
    BERTopicTimeoutError,
    delete_topic_run,
    get_existing_topic_runs_for_file,
    list_chart_interpretations,
    list_topic_runs,
    load_plotly_artifact,
    run_bertopic,
    save_chart_interpretation,
    save_topic_explanation,
    save_topic_names,
)
from app.services.i18n import current_language, t
from app.services.llm import get_active_api_config
from app.services.screening import list_screening_runs
from app.services.storage import (
    ManagedFileMissingError,
    get_project_files,
    load_project_dataframe,
    read_dataframe_bytes,
    read_export_dataframe,
    require_existing_path,
    save_data_bytes,
    validate_dataframe,
)


logger = logging.getLogger(__name__)


def _ensure_state(project_id: int) -> None:
    prefix = f"bertopic_{project_id}"
    st.session_state.setdefault(f"{prefix}_random_state", 42)
    st.session_state.setdefault(f"{prefix}_n_neighbors", 15)
    st.session_state.setdefault(f"{prefix}_n_components", 5)
    st.session_state.setdefault(f"{prefix}_min_topic_size", 5)
    st.session_state.setdefault(f"{prefix}_nr_topics", 15)
    st.session_state.setdefault(f"{prefix}_handled_topic_upload_token", "")
    st.session_state.setdefault(f"{prefix}_uploaded_data_file_id", None)


def _chart_title(chart_key: str) -> str:
    return t(chart_key)


def _normalize_topic_upload_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    lower_map = {str(column).strip().lower(): column for column in work.columns}
    rename_map = {}
    if "Title" not in work.columns and "title" in lower_map:
        rename_map[lower_map["title"]] = "Title"
    if "Abstract" not in work.columns and "abstract" in lower_map:
        rename_map[lower_map["abstract"]] = "Abstract"
    if rename_map:
        work = work.rename(columns=rename_map)
    if "Record-id" not in work.columns:
        work.insert(0, "Record-id", [f"topic-upload-{idx + 1}" for idx in range(len(work))])
    return work


def _short_values(values: Any, limit: int = 8) -> str:
    if values is None:
        return ""
    if not isinstance(values, list):
        values = [values]
    return ", ".join(str(item)[:80] for item in values[:limit])


def _chart_context(chart_key: str, chart_payload: dict[str, Any], topic_info_csv: str) -> str:
    traces = []
    for trace in chart_payload.get("data", [])[:6]:
        traces.append(
            "\n".join(
                part
                for part in [
                    f"trace_type: {trace.get('type', '')}",
                    f"name: {trace.get('name', '')}",
                    f"x_sample: {_short_values(trace.get('x'))}",
                    f"y_sample: {_short_values(trace.get('y'))}",
                    f"text_sample: {_short_values(trace.get('text'))}",
                ]
                if part.split(": ", 1)[1]
            )
        )
    return (
        f"Chart key: {chart_key}\n"
        "Interpret this specific chart generated from the user's uploaded or inherited dataset.\n\n"
        f"Topic overview CSV:\n{topic_info_csv}\n\n"
        f"Plotly chart data summary:\n{chr(10).join(traces) or 'No trace summary available.'}"
    )


def _topic_count(topic_info: pd.DataFrame) -> int:
    if topic_info.empty:
        return 0
    if "Topic" not in topic_info.columns:
        return int(len(topic_info))
    topics = pd.to_numeric(topic_info["Topic"], errors="coerce")
    return int(topics[topics != -1].dropna().nunique())


def _topic_chart_height(topic_count: int) -> int:
    topic_count = max(1, int(topic_count or 1))
    return min(560, max(300, 240 + min(topic_count, 12) * 24))


def _apply_chart_layout(figure: go.Figure, chart_key: str, topic_count: int) -> go.Figure:
    height = _topic_chart_height(topic_count)
    figure.update_layout(
        height=height,
        margin=dict(l=24, r=20, t=42, b=32),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#17211f", size=11),
        autosize=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    figure.update_xaxes(automargin=True)
    figure.update_yaxes(automargin=True, tickfont=dict(size=10 if topic_count > 8 else 11))
    if chart_key == "hierarchy":
        figure.update_layout(margin=dict(l=36, r=20, t=42, b=32))
    if chart_key == "topics":
        figure.update_traces(marker=dict(line=dict(width=1, color="#ffffff")), selector=dict(mode="markers"))
    return figure


def _format_created_at(value: object) -> str:
    return str(value or "").replace("T", " ")[:16]


def _format_topic_run_label(item: dict[str, Any]) -> str:
    filename = item.get("data_filename") or t("unknown_data_source")
    if item.get("screening_run_id"):
        source = f"{t('screening_run_short')} #{item['screening_run_id']}"
    elif item.get("source_type") == "upload":
        source = t("direct_topic_source")
    else:
        source = str(item.get("source_type") or t("direct_topic_source"))
    return f"{filename} | {source} | {t('topic_run_short')} #{item['id']} | {item.get('status', '')} | {_format_created_at(item.get('created_at'))}"


def _format_screening_run_label(item: dict[str, Any], file_names: dict[int, str]) -> str:
    filename = file_names.get(int(item.get("data_file_id") or 0), t("unknown_data_source"))
    return f"{filename} | {t('screening_run_short')} #{item['id']} | {item.get('status', '')} | {_format_created_at(item.get('created_at'))}"


def _render_ai_text_result(
    run_id: int,
    result_key: str,
    title_key: str,
    button_key: str,
    current_text: str,
    disabled: bool,
    generate_fn,
    result_height: int = 220,
) -> None:
    open_key = f"bertopic_ai_result_open_{run_id}_{result_key}"

    def generate_result() -> None:
        try:
            with st.status(t("ai_generating"), expanded=False):
                generate_fn()
            st.session_state[open_key] = True
            st.rerun()
        except Exception:
            logger.exception("BERTopic AI text generation failed for run_id=%s key=%s", run_id, result_key)
            st.error(t("ai_operation_failed"))

    if current_text:
        if open_key not in st.session_state:
            st.session_state[open_key] = True
        is_open = bool(st.session_state.get(open_key, True))
        if is_open:
            ui.ai_result_panel(t(title_key), current_text, height=result_height)

        action_cols = st.columns(2)
        if action_cols[0].button(f"{t('regenerate')} {t(button_key)}", key=f"{result_key}_{run_id}_regenerate", disabled=disabled, use_container_width=True):
            generate_result()
        toggle_label = t("collapse") if is_open else t("view")
        if action_cols[1].button(toggle_label, key=f"{result_key}_{run_id}_toggle", use_container_width=True):
            st.session_state[open_key] = not is_open
            st.rerun()
        return

    if st.button(t(button_key), key=f"{result_key}_{run_id}_generate", disabled=disabled, use_container_width=True):
        generate_result()

def _render_chart_card(
    column,
    chart_key: str,
    artifact_path: str | None,
    diagnostic: dict[str, Any],
    interpretation: str,
    run_id: int,
    topic_info_csv: str,
    user_id: int,
    topic_count: int,
) -> None:
    with column:
        st.markdown(f"#### {_chart_title(chart_key)}")
        chart_payload: dict[str, Any] | None = None
        if artifact_path:
            try:
                chart_payload = load_plotly_artifact(artifact_path)
                figure = _apply_chart_layout(go.Figure(chart_payload), chart_key, topic_count)
                st.plotly_chart(figure, use_container_width=True, key=f"chart_{run_id}_{chart_key}")
            except ManagedFileMissingError:
                logger.exception("BERTopic chart artifact is missing for run_id=%s chart=%s", run_id, chart_key)
                st.warning(t("chart_artifact_missing"))
            except Exception as exc:
                logger.exception("BERTopic chart rendering failed for run_id=%s chart=%s", run_id, chart_key)
                st.warning(f"{t('chart_unavailable')}: {str(exc)[:180]}")
        else:
            effective_topic_count = int(diagnostic.get("effective_topic_count") or topic_count or 0)
            error_message = str(diagnostic.get("error_message") or "").strip()
            if effective_topic_count < 2 and chart_key in {"topics", "hierarchy"}:
                st.info(t("chart_effective_topics_insufficient"))
            elif error_message:
                st.warning(f"{t('chart_unavailable')}: {error_message}")
            else:
                st.warning(t("chart_unavailable"))

        if chart_payload is None:
            if interpretation:
                _render_ai_text_result(
                    run_id,
                    f"interpret_{chart_key}",
                    "chart_interpretation",
                    "generate_interpretation",
                    interpretation,
                    True,
                    lambda: None,
                    result_height=220,
                )
            return

        _render_ai_text_result(
            run_id,
            f"interpret_{chart_key}",
            "chart_interpretation",
            "generate_interpretation",
            interpretation,
            get_active_api_config(user_id) is None,
            lambda: save_chart_interpretation(
                user_id,
                run_id,
                chart_key,
                _chart_context(chart_key, chart_payload or {}, topic_info_csv),
                current_language(),
            ),
            result_height=220,
        )

def _render_topic_results(project_id: int, user_id: int) -> None:
    runs = list_topic_runs(project_id, user_id)
    if not runs:
        return
    ui.section_title(t("topic_overview"))
    selected_run = st.selectbox(t("bertopic_run"), runs, format_func=_format_topic_run_label)
    if selected_run.get("status") == "failed":
        message = selected_run.get("error_message") or t("bertopic_failed_unknown")
        st.warning(f"{t('bertopic_failed_reason')}: {message}")
        detail = dict(selected_run.get("error_detail") or {})
        if detail:
            visible_detail = {key: value for key, value in detail.items() if key != "traceback"}
            with st.expander(t("bertopic_error_details"), expanded=False):
                st.json(visible_detail)
    topic_info = pd.DataFrame(selected_run.get("topic_info", []))
    topic_count = _topic_count(topic_info)
    if not topic_info.empty:
        st.dataframe(topic_info, use_container_width=True)
    if selected_run.get("output_path"):
        try:
            output_path = require_existing_path(selected_run["output_path"])
            out_df = read_export_dataframe(output_path)
            st.dataframe(out_df.head(50), use_container_width=True)
            with output_path.open("rb") as fh:
                st.download_button(t("export_results"), data=fh.read(), file_name=output_path.name, mime="text/csv")
        except ManagedFileMissingError:
            logger.exception("BERTopic output file is missing for run_id=%s", selected_run["id"])
            st.warning(t("result_file_missing"))
        except Exception:
            logger.exception("BERTopic output file could not be displayed for run_id=%s", selected_run["id"])
            st.warning(t("result_file_missing"))

    run_id = int(selected_run["id"])
    interpretations = list_chart_interpretations(run_id)
    topic_info_csv = topic_info.to_csv(index=False) if not topic_info.empty else "No topic overview available."
    llm_col1, llm_col2 = st.columns(2)
    with llm_col1:
        _render_ai_text_result(
            run_id,
            "topic_names",
            "topic_name_suggestions",
            "generate_topic_names",
            interpretations.get("topic_names", ""),
            get_active_api_config(user_id) is None,
            lambda: save_topic_names(user_id, run_id, topic_info_csv, current_language()),
        )
    with llm_col2:
        _render_ai_text_result(
            run_id,
            "topic_explain",
            "topic_explanation",
            "generate_topic_explanation",
            interpretations.get("topic_explanation", ""),
            get_active_api_config(user_id) is None,
            lambda: save_topic_explanation(user_id, run_id, topic_info_csv, current_language()),
        )

    artifacts = selected_run.get("artifacts", {})
    diagnostics = dict((selected_run.get("error_detail") or {}).get("chart_diagnostics") or {})
    chart_cols = st.columns(3)
    for index, chart_key in enumerate(["barchart", "topics", "hierarchy"]):
        _render_chart_card(
            chart_cols[index],
            chart_key,
            artifacts.get(chart_key),
            dict(diagnostics.get(chart_key) or {}),
            interpretations.get(chart_key, ""),
            run_id,
            topic_info_csv,
            user_id,
            topic_count,
        )

    pending_delete_id = ss.get(ss.PENDING_DELETE_TOPIC_RUN_ID)
    if pending_delete_id:
        ui.confirm_dialog(
            t("confirm_delete_title"),
            t("delete_topic_result_confirm"),
            t("confirm_delete"),
            t("cancel"),
            lambda: delete_topic_run(project_id, user_id, int(pending_delete_id)),
            ss.PENDING_DELETE_TOPIC_RUN_ID,
        )
    if st.button(t("delete_topic_result"), key=f"delete_topic_run_{selected_run['id']}", use_container_width=True):
        ss.set_value(ss.PENDING_DELETE_TOPIC_RUN_ID, int(selected_run["id"]))
        st.rerun()


def render(project: dict, user: dict) -> None:
    project_id = int(project["id"])
    user_id = int(user["id"])
    _ensure_state(project_id)
    prefix = f"bertopic_{project_id}"
    ui.section_title(t("run_bertopic"))
    source_mode = st.radio(t("source_selection"), ["inherit_screening_results", "upload_new_dataset"], format_func=t, horizontal=True)
    working_df = None
    screening_run_id = None
    data_file_id = None

    if source_mode == "inherit_screening_results":
        screening_runs = list_screening_runs(project_id, user_id)
        file_names = {int(item["id"]): item["filename"] for item in get_project_files(project_id, user_id)}
        completed_runs = []
        for run in screening_runs:
            if run["status"] != "completed" or not run.get("export_path"):
                continue
            try:
                require_existing_path(run["export_path"])
                completed_runs.append(run)
            except ManagedFileMissingError:
                logger.exception("Screening export file is missing for run_id=%s", run["id"])
        if not completed_runs:
            ui.empty_state(t("no_screening_results"), t("source_selection"))
        else:
            chosen_run = st.selectbox(t("screening_run"), completed_runs, format_func=lambda item: _format_screening_run_label(item, file_names))
            screening_run_id = int(chosen_run["id"])
            try:
                source_df = read_export_dataframe(chosen_run["export_path"])
                if "decision" in source_df.columns:
                    source_df = source_df[source_df["decision"] == "include"]
                if source_df.empty:
                    st.info(t("bertopic_no_include_records"))
                else:
                    file_record, base_df = load_project_dataframe(project_id, user_id, int(chosen_run["data_file_id"]))
                    if base_df is not None and file_record is not None:
                        merged = base_df.merge(source_df[["record_id"]], left_on="Record-id", right_on="record_id", how="inner")
                        working_df = merged.drop(columns=["record_id"])
                        data_file_id = int(file_record["id"])
                        st.caption(f"{t('current_data_source')}: {file_record['filename']} | run #{chosen_run['id']}")
            except ManagedFileMissingError:
                logger.exception("Inherited BERTopic source file is missing for screening_run_id=%s", screening_run_id)
                st.warning(t("result_file_missing"))
            except Exception:
                logger.exception("Preparing inherited BERTopic source failed for project_id=%s", project_id)
                st.error(t("bertopic_source_failed"))
    else:
        ui.upload_hint(t("upload_drag_hint"), t("upload_csv_hint"))
        upload = st.file_uploader(t("upload_new_dataset"), type=["csv", "xlsx", "xls"], key="topic_upload", label_visibility="collapsed")
        if upload is not None:
            try:
                upload_bytes = upload.getvalue()
                upload_token = f"{upload.name}:{len(upload_bytes)}"
                preview_df = _normalize_topic_upload_dataframe(read_dataframe_bytes(upload.name, upload_bytes))
                missing = validate_dataframe(preview_df)
                if missing:
                    st.error(f"{t('required_columns_missing')}: {', '.join(missing)}")
                else:
                    save_name = f"{Path(upload.name).stem or 'topic_dataset'}.csv"
                    save_bytes = preview_df.to_csv(index=False).encode("utf-8-sig")
                    if upload_token != st.session_state[f"{prefix}_handled_topic_upload_token"]:
                        saved = save_data_bytes(user_id, project_id, save_name, save_bytes)
                        st.session_state[f"{prefix}_handled_topic_upload_token"] = upload_token
                        st.session_state[f"{prefix}_uploaded_data_file_id"] = int(saved["file_id"])
                    data_file_id = int(st.session_state[f"{prefix}_uploaded_data_file_id"])
                    file_record, working_df = load_project_dataframe(project_id, user_id, data_file_id)
                    st.caption(f"{t('current_data_source')}: {file_record['filename'] if file_record else upload.name}")
                    st.dataframe((working_df if working_df is not None else preview_df).head(10), use_container_width=True)
            except ValueError as exc:
                logger.exception("BERTopic upload validation failed for project_id=%s filename=%s", project_id, upload.name)
                st.error(f"{t('upload_failed')}: {exc}")
            except Exception:
                logger.exception("BERTopic upload failed for project_id=%s filename=%s", project_id, upload.name)
                st.error(t("upload_failed_generic"))

    existing_topic_runs = get_existing_topic_runs_for_file(project_id, user_id, int(data_file_id)) if data_file_id else []
    completed_topic_runs = [run for run in existing_topic_runs if run["status"] == "completed"]
    confirm_overwrite_key = f"{prefix}_confirm_topic_overwrite"
    if completed_topic_runs:
        st.info(t("existing_topic_result_hint"))

    def execute_topic_run() -> None:
        params = {
            "random_state": st.session_state[f"{prefix}_random_state"],
            "n_neighbors": st.session_state[f"{prefix}_n_neighbors"],
            "n_components": st.session_state[f"{prefix}_n_components"],
            "min_topic_size": st.session_state[f"{prefix}_min_topic_size"],
            "nr_topics": st.session_state[f"{prefix}_nr_topics"],
        }
        try:
            with st.status(t("bertopic_running"), expanded=True) as status:
                def update_stage(stage: str) -> None:
                    status.update(label=t(f"bertopic_stage_{stage}"), state="running", expanded=True)

                result = run_bertopic(
                    project_id,
                    user_id,
                    working_df,
                    "screening" if source_mode == "inherit_screening_results" else "upload",
                    params,
                    data_file_id=data_file_id,
                    screening_run_id=screening_run_id,
                    progress_callback=update_stage,
                )
                status.update(label=f"{t('run_complete')} #{result['run_id']}", state="complete", expanded=False)
            st.session_state.pop(confirm_overwrite_key, None)
            st.success(f"{t('run_complete')} #{result['run_id']}")
            st.rerun()
        except BERTopicDependencyError:
            logger.exception("BERTopic dependencies are missing for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("bertopic_dependencies_missing"))
        except BERTopicInputError:
            logger.exception("BERTopic input is too small or invalid for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("bertopic_input_too_small"))
        except BERTopicTimeoutError:
            logger.exception("BERTopic worker timed out for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("bertopic_timeout"))
        except BERTopicRuntimeError as exc:
            logger.exception("BERTopic run failed for project_id=%s user_id=%s", project_id, user_id)
            st.error(f"{t('bertopic_run_failed')}: {str(exc)[:240]}")
        except Exception:
            logger.exception("BERTopic run failed for project_id=%s user_id=%s", project_id, user_id)
            st.error(t("bertopic_run_failed"))

    if st.button(t("run_bertopic"), use_container_width=True, disabled=working_df is None):
        if completed_topic_runs and not st.session_state.get(confirm_overwrite_key):
            st.session_state[confirm_overwrite_key] = True
            st.rerun()
        else:
            execute_topic_run()

    if st.session_state.get(confirm_overwrite_key):
        st.warning(t("overwrite_topic_confirm"))
        confirm_col, cancel_col, _ = st.columns([1.2, 1.2, 4])
        if confirm_col.button(t("confirm_run"), key=f"{prefix}_confirm_topic_run", use_container_width=True):
            execute_topic_run()
        if cancel_col.button(t("cancel"), key=f"{prefix}_cancel_topic_run", use_container_width=True):
            st.session_state.pop(confirm_overwrite_key, None)
            st.rerun()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.number_input(t("random_state"), step=1, key=f"{prefix}_random_state", help=t("random_state_help"))
    col2.number_input(t("n_neighbors"), step=1, key=f"{prefix}_n_neighbors", help=t("n_neighbors_help"))
    col3.number_input(t("n_components"), step=1, key=f"{prefix}_n_components", help=t("n_components_help"))
    col4.number_input(t("min_topic_size"), step=1, key=f"{prefix}_min_topic_size", help=t("min_topic_size_help"))
    col5.number_input(t("nr_topics"), step=1, key=f"{prefix}_nr_topics", help=t("nr_topics_help"))
    st.caption(t("bertopic_default_settings"))

    _render_topic_results(project_id, user_id)
