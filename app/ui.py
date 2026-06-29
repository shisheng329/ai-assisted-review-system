from __future__ import annotations

from html import escape

import streamlit as st


def page_header(title: str, subtitle: str = "") -> None:
    subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="page-head">
          <div>
            <h1>{escape(title)}</h1>
            {subtitle_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, caption: str = "") -> None:
    caption_html = f"<span>{escape(caption)}</span>" if caption else ""
    st.markdown(
        f"""
        <div class="section-head">
          <h2>{escape(title)}</h2>
          {caption_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_card(label: str, value: object, note: str = "", accent: str = "green") -> None:
    note_html = f"<div class='stat-note'>{escape(str(note))}</div>" if note else ""
    st.markdown(
        f"""
        <div class="stat-card stat-{escape(accent)}">
          <div class="stat-label">{escape(label)}</div>
          <div class="stat-value">{escape(str(value))}</div>
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_pill(label: str, active: bool = True) -> str:
    class_name = "pill-on" if active else "pill-off"
    return f"<span class='status-pill {class_name}'>{escape(label)}</span>"


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-green: #10b981;
            --app-green-dark: #059669;
            --app-green-soft: #d1fae5;
            --app-bg: #f4f6f8;
            --app-card: #ffffff;
            --app-text: #111827;
            --app-muted: #6b7280;
            --app-border: #e5e7eb;
        }
        .stApp { background: var(--app-bg); color: var(--app-text); }
        header[data-testid="stHeader"] {
            background: transparent;
            height: 0;
        }
        .block-container {
            padding-top: 1.1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 1360px;
        }
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--app-border);
            box-shadow: 10px 0 30px rgba(15, 23, 42, 0.04);
            min-width: 220px !important;
            width: 220px !important;
            max-width: 220px !important;
        }
        section[data-testid="stSidebar"] > div {
            padding: 1.1rem 0.7rem 1rem;
            width: 220px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button {
            width: 100%;
            justify-content: flex-start;
            border: 0;
            border-radius: 8px;
            color: #334155;
            background: transparent;
            min-height: 2rem;
            padding: 0.35rem 0.6rem;
            font-weight: 500;
            box-shadow: none;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
            color: var(--app-green-dark);
            background: #ecfdf5;
        }
        .brand-block {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.05rem 0.1rem 0.9rem;
            margin-bottom: 0.2rem;
        }
        .brand-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.85rem;
            height: 1.85rem;
            border-radius: 8px;
            background: var(--app-green);
            color: #ffffff;
            font-weight: 800;
        }
        .brand-title {
            color: #111827;
            font-size: 1.05rem;
            font-weight: 800;
            letter-spacing: 0;
            white-space: nowrap;
        }
        .sidebar-caption {
            color: var(--app-muted);
            font-size: 0.7rem;
            line-height: 1.35;
            margin: 0 0 0.55rem;
        }
        .nav-active {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            min-height: 2rem;
            padding: 0 0.55rem;
            margin: 0.12rem 0;
            border-radius: 8px;
            background: var(--app-green-soft);
            color: var(--app-green-dark);
            border-left: 3px solid var(--app-green);
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .nav-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.1rem;
            height: 1.1rem;
            border-radius: 6px;
            background: rgba(16, 185, 129, 0.13);
            font-size: 0.7rem;
            font-weight: 800;
            flex: 0 0 auto;
        }
        .shell-header {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: center;
            margin-bottom: 1rem;
        }
        .shell-title h1 {
            margin: 0;
            font-size: 1.45rem;
            line-height: 1.2;
            font-weight: 800;
            letter-spacing: 0;
        }
        .shell-title p {
            margin: 0.22rem 0 0;
            color: var(--app-muted);
            font-size: 0.88rem;
        }
        .shell-user {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: var(--app-muted);
            font-size: 0.86rem;
            white-space: nowrap;
        }
        .avatar-dot {
            width: 2.25rem;
            height: 2.25rem;
            border-radius: 50%;
            background: #111827;
            color: #ffffff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
        }
        .page-head {
            margin: 0 0 1rem;
        }
        .page-head h1 {
            margin: 0;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: 0;
        }
        .page-head p {
            color: var(--app-muted);
            margin: 0.25rem 0 0;
        }
        .section-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            margin: 1.05rem 0 0.45rem;
        }
        .section-head h2 {
            margin: 0;
            font-size: 1rem;
            font-weight: 750;
            letter-spacing: 0;
        }
        .section-head span {
            color: var(--app-muted);
            font-size: 0.82rem;
        }
        div[data-testid="stForm"],
        div[data-testid="stExpander"],
        div[data-testid="stDataFrame"],
        div[data-testid="stPlotlyChart"],
        div[data-testid="stMetric"],
        div[data-testid="stFileUploader"],
        div[data-testid="stAlert"] {
            border-radius: 8px !important;
        }
        div[data-testid="stForm"],
        div[data-testid="stExpander"] {
            border: 1px solid var(--app-border);
            background: #ffffff;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--app-border);
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        .stat-card {
            background: #ffffff;
            border: 1px solid var(--app-border);
            border-radius: 8px;
            padding: 1rem;
            min-height: 7rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        .stat-label {
            color: var(--app-muted);
            font-size: 0.82rem;
            font-weight: 650;
        }
        .stat-value {
            margin-top: 0.35rem;
            color: var(--app-text);
            font-size: 1.75rem;
            line-height: 1.1;
            font-weight: 800;
        }
        .stat-note {
            margin-top: 0.45rem;
            color: var(--app-muted);
            font-size: 0.78rem;
        }
        .hero-card {
            padding: 1.15rem 1.25rem;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid var(--app-border);
            margin-bottom: 1rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.045);
        }
        .hero-card h2 {
            margin-top: 0;
            letter-spacing: 0;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            min-height: 1.45rem;
            padding: 0 0.55rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .pill-on {
            color: #047857;
            background: #d1fae5;
        }
        .pill-off {
            color: #64748b;
            background: #f1f5f9;
        }
        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button,
        [data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            border: 1px solid var(--app-border);
            font-weight: 650;
            min-height: 2.45rem;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        [data-testid="stButton"] button *,
        [data-testid="stDownloadButton"] button *,
        [data-testid="stFormSubmitButton"] button * {
            white-space: nowrap !important;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.15;
        }
        [data-testid="stButton"] button p,
        [data-testid="stDownloadButton"] button p,
        [data-testid="stFormSubmitButton"] button p {
            margin: 0;
        }
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {
            background: var(--app-green);
            border-color: var(--app-green);
        }
        @media (max-width: 760px) {
            .shell-header {
                display: block;
            }
            .shell-user {
                margin-top: 0.5rem;
                white-space: normal;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
