from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
                marker_colors=["#0f9f8a", "#dff7f0"],
                textinfo="none",
                hoverinfo="skip",
                showlegend=False,
            )
        ]
    )
    fig.update_layout(
        height=172,
        margin=dict(l=4, r=4, t=26, b=4),
        title=dict(text=title, x=0.02, y=0.98, font=dict(size=14, color="#17211f")),
        annotations=[
            dict(text=center, x=0.5, y=0.5, showarrow=False, font=dict(size=21, color="#17211f", family="Arial Black"))
        ],
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )
    return fig


def _bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> go.Figure:
    fig = px.bar(df, x=x_col, y=y_col, title=title, color_discrete_sequence=["#0f9f8a"])
    fig.update_traces(marker_line_width=0, marker_opacity=0.95)
    fig.update_layout(
        height=280,
        margin=dict(l=18, r=14, t=36, b=34),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        title=dict(font=dict(size=15, color="#17211f")),
        xaxis=dict(showgrid=False, tickfont=dict(size=11, color="#71817c")),
        yaxis=dict(gridcolor="#dde6e2", tickfont=dict(size=11, color="#71817c")),
        bargap=0.42,
    )
    return fig



def _kpi_card(label: str, value: object, note: str = "", mini_stats: list[tuple[str, object]] | None = None) -> None:
    mini_html = ""
    if mini_stats:
        mini_html = "<div class='dashboard-mini-grid'>" + "".join(
            f"<div class='dashboard-mini-stat'><span>{escape(str(name))}</span><strong>{escape(str(stat))}</strong></div>"
            for name, stat in mini_stats
        ) + "</div>"
    st.markdown(
        f"""
        <section class="dashboard-kpi">
          <div class="dashboard-kpi-label">{escape(str(label))}</div>
          <div class="dashboard-kpi-value">{escape(str(value))}</div>
          <div class="dashboard-kpi-note">{escape(str(note))}</div>
          {mini_html}
        </section>
        """,
        unsafe_allow_html=True,
    )

def render(project: dict, user: dict) -> None:
    metrics = get_project_metrics(int(project["id"]), int(user["id"]))
    runs = list_screening_runs(int(project["id"]), int(user["id"]))
    latest = runs[0] if runs else None
    screened_total = int(latest["total_records"]) if latest else int(metrics["total_records"] or 0)
    included = int(latest["include_count"]) if latest else int(metrics["included_count"] or 0)
    maybe = int(latest["maybe_count"]) if latest else 0
    excluded = int(latest["exclude_count"]) if latest else 0

    top_left, top_mid, top_right = st.columns([1.0, 1.15, 1.0], gap="small")
    with top_left:
        with st.container(border=True):
            st.plotly_chart(
                _donut(screened_total, max(screened_total, int(metrics["total_records"] or 0)), t("total_records"), f"{screened_total:,}"),
                use_container_width=True,
                key="dashboard_screened_donut",
            )
    with top_mid:
        _kpi_card(
            t("included_count"),
            f"{included:,}",
            f"{t('recent_activity')}: {metrics['recent_activity'] or t('no_data')}",
            [(t("topic_count"), metrics["topic_count"]), (t("pdf_result_count"), metrics["pdf_result_count"])],
        )
    with top_right:
        with st.container(border=True):
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
    chart_left, chart_right = st.columns(2, gap="small")
    with chart_left:
        with st.container(border=True):
            st.plotly_chart(_bar_chart(dist_df, t("decision"), t("count"), t("decision_distribution")), use_container_width=True)
    with chart_right:
        with st.container(border=True):
            st.plotly_chart(_bar_chart(history_df, "run", t("count"), t("screening_run")), use_container_width=True)
