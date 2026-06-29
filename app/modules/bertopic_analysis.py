from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import ui
from app.services.bertopic_service import (
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
from app.services.storage import load_project_dataframe, read_dataframe_bytes


def _ensure_state(project_id: int) -> None:
    prefix = f"bertopic_{project_id}"
    st.session_state.setdefault(f"{prefix}_random_state", 42)
    st.session_state.setdefault(f"{prefix}_n_neighbors", 15)
    st.session_state.setdefault(f"{prefix}_n_components", 5)
    st.session_state.setdefault(f"{prefix}_min_topic_size", 5)
    st.session_state.setdefault(f"{prefix}_nr_topics", 15)


def _chart_title(chart_key: str) -> str:
    return t(chart_key)


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


def _render_chart_card(column, chart_key: str, artifact_path: str, interpretation: str, run_id: int, topic_info_csv: str, user_id: int) -> None:
    with column:
        st.markdown(f"#### {_chart_title(chart_key)}")
        chart_payload = load_plotly_artifact(artifact_path)
        figure = go.Figure(chart_payload)
        figure.update_layout(height=360, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(figure, use_container_width=True, key=f"chart_{run_id}_{chart_key}")
        if st.button(t("generate_interpretation"), key=f"interpret_{run_id}_{chart_key}", disabled=get_active_api_config(user_id) is None, use_container_width=True):
            try:
                save_chart_interpretation(user_id, run_id, chart_key, _chart_context(chart_key, chart_payload, topic_info_csv), current_language())
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        st.session_state[f"interpretation_value_{run_id}_{chart_key}"] = interpretation
        st.text_area(t("chart_interpretation"), height=160, key=f"interpretation_value_{run_id}_{chart_key}")


def _render_topic_results(project_id: int, user_id: int) -> None:
    runs = list_topic_runs(project_id, user_id)
    if not runs:
        return
    ui.section_title(t("topic_overview"))
    selected_run = st.selectbox(t("bertopic_run"), runs, format_func=lambda item: f"#{item['id']} | {item['created_at']} | {item['status']}")
    topic_info = pd.DataFrame(selected_run.get("topic_info", []))
    if not topic_info.empty:
        st.dataframe(topic_info, use_container_width=True)
    if selected_run.get("output_path"):
        out_df = pd.read_csv(selected_run["output_path"])
        st.dataframe(out_df.head(50), use_container_width=True)
        with open(selected_run["output_path"], "rb") as fh:
            st.download_button(t("export_results"), data=fh.read(), file_name="bertopic_results.csv", mime="text/csv")

    interpretations = list_chart_interpretations(int(selected_run["id"]))
    topic_info_csv = topic_info.to_csv(index=False) if not topic_info.empty else "No topic overview available."
    llm_col1, llm_col2 = st.columns(2)
    if llm_col1.button(t("generate_topic_names"), key=f"topic_names_{selected_run['id']}", disabled=get_active_api_config(user_id) is None, use_container_width=True):
        try:
            save_topic_names(user_id, int(selected_run["id"]), topic_info_csv, current_language())
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if llm_col2.button(t("generate_topic_explanation"), key=f"topic_explain_{selected_run['id']}", disabled=get_active_api_config(user_id) is None, use_container_width=True):
        try:
            save_topic_explanation(user_id, int(selected_run["id"]), topic_info_csv, current_language())
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.session_state[f"topic_names_value_{selected_run['id']}"] = interpretations.get("topic_names", "")
    st.session_state[f"topic_expl_value_{selected_run['id']}"] = interpretations.get("topic_explanation", "")
    st.text_area(t("topic_name_suggestions"), height=160, key=f"topic_names_value_{selected_run['id']}")
    st.text_area(t("topic_explanation"), height=180, key=f"topic_expl_value_{selected_run['id']}")

    artifacts = selected_run.get("artifacts", {})
    chart_cols = st.columns(3)
    for index, chart_key in enumerate(["barchart", "topics", "hierarchy"]):
        if chart_key in artifacts:
            _render_chart_card(
                chart_cols[index],
                chart_key,
                artifacts[chart_key],
                interpretations.get(chart_key, ""),
                int(selected_run["id"]),
                topic_info_csv,
                user_id,
            )


def render(project: dict, user: dict) -> None:
    project_id = int(project["id"])
    user_id = int(user["id"])
    _ensure_state(project_id)
    prefix = f"bertopic_{project_id}"
    ui.section_title(t("run_bertopic"))
    source_mode = st.radio(
        t("source_selection"),
        ["inherit_screening_results", "upload_new_dataset"],
        format_func=t,
        horizontal=True,
    )
    working_df = None
    screening_run_id = None
    data_file_id = None

    if source_mode == "inherit_screening_results":
        screening_runs = list_screening_runs(project_id, user_id)
        completed_runs = [run for run in screening_runs if run["status"] == "completed"]
        if not completed_runs:
            st.info(t("no_screening_results"))
        else:
            chosen_run = st.selectbox(t("screening_run"), completed_runs, format_func=lambda item: f"#{item['id']} | {item['created_at']}")
            screening_run_id = int(chosen_run["id"])
            source_df = pd.read_csv(chosen_run["export_path"])
            if "decision" in source_df.columns:
                source_df = source_df[source_df["decision"].isin(["include", "maybe"])]
            file_record, base_df = load_project_dataframe(project_id, user_id, int(chosen_run["data_file_id"]))
            if base_df is not None:
                merged = base_df.merge(source_df[["record_id"]], left_on="Record-id", right_on="record_id", how="inner")
                working_df = merged.drop(columns=["record_id"])
                data_file_id = int(file_record["id"]) if file_record else None
                st.caption(f"{t('current_data_source')}: {file_record['filename']} | run #{chosen_run['id']}")
    else:
        upload = st.file_uploader(t("upload_new_dataset"), type=["csv", "xlsx"], key="topic_upload")
        if upload is not None:
            working_df = read_dataframe_bytes(upload.name, upload.getvalue())
            st.dataframe(working_df.head(10), use_container_width=True)

    if st.button(t("run_bertopic"), use_container_width=True, disabled=working_df is None):
        params = {
            "random_state": st.session_state[f"{prefix}_random_state"],
            "n_neighbors": st.session_state[f"{prefix}_n_neighbors"],
            "n_components": st.session_state[f"{prefix}_n_components"],
            "min_topic_size": st.session_state[f"{prefix}_min_topic_size"],
            "nr_topics": st.session_state[f"{prefix}_nr_topics"],
        }
        try:
            result = run_bertopic(
                project_id,
                user_id,
                working_df,
                "screening" if source_mode == "inherit_screening_results" else "upload",
                params,
                data_file_id=data_file_id,
                screening_run_id=screening_run_id,
            )
            st.success(f"{t('run_complete')} #{result['run_id']}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.number_input(t("random_state"), step=1, key=f"{prefix}_random_state")
    col2.number_input(t("n_neighbors"), step=1, key=f"{prefix}_n_neighbors")
    col3.number_input(t("n_components"), step=1, key=f"{prefix}_n_components")
    col4.number_input(t("min_topic_size"), step=1, key=f"{prefix}_min_topic_size")
    col5.number_input(t("nr_topics"), step=1, key=f"{prefix}_nr_topics")
    st.caption(t("bertopic_default_settings"))

    _render_topic_results(project_id, user_id)
