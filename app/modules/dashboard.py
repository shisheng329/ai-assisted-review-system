from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app import ui
from app.services.i18n import t
from app.services.projects import get_project_metrics
from app.services.screening import list_screening_runs


def _donut(value: int, total: int, title: str, center: str) -> go.Figure:
    safe_total = max(int(total or 0), int(value or 0), 1)
    safe_value = max(int(value or 0), 0)
    fig = go.Figure(
        data=[
            go.Pie(
                values=[safe_value, max(safe_total - safe_value, 0)],
                hole=0.72,
                sort=False,
                direction="clockwise",
                marker_colors=["#10b981", "#d1fae5"],
                textinfo="none",
                hoverinfo="skip",
                showlegend=False,
            )
        ]
    )
    fig.update_layout(
        height=230,
        margin=dict(l=8, r=8, t=28, b=8),
        title=dict(text=title, x=0.02, y=0.98, font=dict(size=14, color="#111827")),
        annotations=[
            dict(text=center, x=0.5, y=0.5, showarrow=False, font=dict(size=26, color="#111827", family="Arial Black"))
        ],
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


def _bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> go.Figure:
    fig = px.bar(df, x=x_col, y=y_col, title=title, color_discrete_sequence=["#10b981"])
    fig.update_traces(marker_line_width=0, marker_opacity=0.95)
    fig.update_layout(
        height=320,
        margin=dict(l=18, r=18, t=52, b=32),
        paper_bgcolor="white",
        plot_bgcolor="white",
        title=dict(font=dict(size=15, color="#111827")),
        xaxis=dict(showgrid=False, tickfont=dict(size=11, color="#6b7280")),
        yaxis=dict(gridcolor="#eef2f7", tickfont=dict(size=11, color="#6b7280")),
        bargap=0.42,
    )
    return fig


def render(project: dict, user: dict) -> None:
    metrics = get_project_metrics(int(project["id"]), int(user["id"]))
    runs = list_screening_runs(int(project["id"]), int(user["id"]))
    latest = runs[0] if runs else None
    screened_total = int(latest["total_records"]) if latest else int(metrics["total_records"] or 0)
    included = int(latest["include_count"]) if latest else int(metrics["included_count"] or 0)
    maybe = int(latest["maybe_count"]) if latest else 0
    excluded = int(latest["exclude_count"]) if latest else 0

    top_left, top_mid, top_right = st.columns([1.2, 1.1, 1.2], gap="medium")
    with top_left:
        st.plotly_chart(
            _donut(screened_total, max(screened_total, int(metrics["total_records"] or 0)), t("total_records"), f"{screened_total:,}"),
            use_container_width=True,
            key="dashboard_screened_donut",
        )
    with top_mid:
        ui.stat_card(t("included_count"), f"{included:,}", f"{t('recent_activity')}: {metrics['recent_activity'] or t('no_data')}")
        small1, small2 = st.columns(2)
        small1.metric(t("topic_count"), metrics["topic_count"])
        small2.metric(t("pdf_result_count"), metrics["pdf_result_count"])
    with top_right:
        st.plotly_chart(
            _donut(included + maybe, max(screened_total, included + maybe), t("screening_results"), f"{included + maybe:,}"),
            use_container_width=True,
            key="dashboard_progress_donut",
        )

    if not runs:
        st.info(t("no_data"))
        return

    dist_df = pd.DataFrame(
        [
            {t("decision"): t("include"), t("count"): latest["include_count"]},
            {t("decision"): t("exclude"), t("count"): latest["exclude_count"]},
            {t("decision"): t("maybe"), t("count"): latest["maybe_count"]},
        ]
    )
    history_df = pd.DataFrame(
        [
            {"run": f"#{run['id']}", t("count"): run["total_records"]}
            for run in list(reversed(runs[:12]))
        ]
    )
    chart_left, chart_right = st.columns(2, gap="medium")
    with chart_left:
        st.plotly_chart(_bar_chart(dist_df, t("decision"), t("count"), t("decision_distribution")), use_container_width=True)
    with chart_right:
        st.plotly_chart(_bar_chart(history_df, "run", t("count"), t("screening_run")), use_container_width=True)
