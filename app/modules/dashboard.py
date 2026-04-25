from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.services.i18n import t
from app.services.projects import get_project_metrics
from app.services.screening import list_screening_runs


def render(project: dict, user: dict) -> None:
    st.subheader(t("project_dashboard"))
    metrics = get_project_metrics(int(project["id"]), int(user["id"]))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("total_records"), metrics["total_records"])
    col2.metric(t("included_count"), metrics["included_count"])
    col3.metric(t("topic_count"), metrics["topic_count"])
    col4.metric(t("pdf_result_count"), metrics["pdf_result_count"])
    st.caption(f"{t('recent_activity')}: {metrics['recent_activity'] or t('no_data')}")

    runs = list_screening_runs(int(project["id"]), int(user["id"]))
    if not runs:
        st.info(t("no_data"))
        return
    latest = runs[0]
    dist_df = pd.DataFrame(
        [
            {t("decision"): t("include"), t("count"): latest["include_count"]},
            {t("decision"): t("exclude"), t("count"): latest["exclude_count"]},
            {t("decision"): t("maybe"), t("count"): latest["maybe_count"]},
        ]
    )
    fig = px.bar(dist_df, x=t("decision"), y=t("count"), title=t("decision_distribution"), color=t("decision"))
    st.plotly_chart(fig, use_container_width=True)
