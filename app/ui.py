from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st
import streamlit.components.v1 as components


STATUS_VARIANTS = {
    "success": "status-success",
    "warning": "status-warning",
    "error": "status-error",
    "info": "status-info",
    "neutral": "status-neutral",
}


def page_header(title: str, subtitle: str = "") -> None:
    subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"""
        <section class="page-head">
          <div>
            <h1>{escape(title)}</h1>
            {subtitle_html}
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def page_title(title: str, subtitle: str = "") -> None:
    page_header(title, subtitle)


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


def surface(title: str = "", body: str = "", tone: str = "default") -> None:
    title_html = f"<h3>{escape(title)}</h3>" if title else ""
    escaped_body = escape(body).replace("\n", "<br>")
    body_html = f"<p>{escaped_body}</p>" if body else ""
    st.markdown(
        f"""
        <section class="ui-surface surface-{escape(tone)}">
          {title_html}
          {body_html}
        </section>
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


def status_pill(label: str, active: bool = True, variant: str | None = None) -> str:
    if variant:
        class_name = STATUS_VARIANTS.get(variant, STATUS_VARIANTS["neutral"])
    else:
        class_name = "status-success" if active else "status-neutral"
    return f"<span class='status-pill {class_name}'>{escape(label)}</span>"


def inline_status(label: str, variant: str = "neutral") -> None:
    st.markdown(status_pill(label, variant=variant), unsafe_allow_html=True)


def render_context_status(
    api_label: str,
    api_ready: bool,
    data_source_label: str,
    data_source_name: str,
    data_source_ready: bool,
    prompt_label: str = "",
    prompt_name: str = "",
    prompt_ready: bool = False,
) -> None:
    items = [
        (api_label, api_ready, "success" if api_ready else "warning"),
        (
            f"{data_source_label}: {data_source_name}",
            data_source_ready,
            "info" if data_source_ready else "warning",
        ),
    ]
    if prompt_label:
        items.append(
            (
                f"{prompt_label}: {prompt_name}",
                prompt_ready,
                "success" if prompt_ready else "warning",
            )
        )
    columns = st.columns(len(items))
    for column, (label, active, variant) in zip(columns, items):
        column.markdown(status_pill(label, active=active, variant=variant), unsafe_allow_html=True)


def apply_page_width(mode: str = "standard") -> None:
    widths = {"compact": "1160px", "standard": "1320px", "wide": "1540px"}
    max_width = widths.get(mode, widths["standard"])
    st.markdown(
        f"""
        <style>
        .block-container {{
            max-width: {max_width} !important;
            width: min(100%, {max_width}) !important;
        }}
        @media (max-width: 760px) {{
            .block-container {{
                width: 100% !important;
                max-width: 100% !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str = "") -> None:
    body_html = f"<p>{escape(body)}</p>" if body else ""
    st.markdown(
        f"""
        <div class="empty-state">
          <div class="empty-mark">L</div>
          <h3>{escape(title)}</h3>
          {body_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def table_header(labels: Iterable[str]) -> None:
    cells = "".join(f"<span>{escape(label)}</span>" for label in labels)
    st.markdown(f"<div class='table-header'>{cells}</div>", unsafe_allow_html=True)


def row_separator() -> None:
    st.markdown("<div class='row-separator'></div>", unsafe_allow_html=True)


def fixed_list_container(height: int = 280):
    return st.container(height=height, border=True)


def upload_hint(title: str, body: str = "") -> None:
    body_html = f"<p>{escape(body)}</p>" if body else ""
    st.markdown(
        f"""
        <div class="upload-hint">
          <strong>{escape(title)}</strong>
          {body_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def readonly_panel(title: str, body: str, height: int = 320) -> None:
    escaped_body = escape(body or "")
    st.markdown(
        f"""
        <section class="readonly-panel" style="height: {int(height)}px;">
          <div class="readonly-title">{escape(title)}</div>
          <pre>{escaped_body}</pre>
        </section>
        """,
        unsafe_allow_html=True,
    )


def ai_result_panel(title: str, body: str, height: int = 220) -> None:
    escaped_title = escape(title)
    escaped_body = escape(body or "")
    components.html(
        f"""
        <section class="ai-result-panel">
          <div class="ai-result-title">{escaped_title}</div>
          <textarea readonly aria-label="{escaped_title}">{escaped_body}</textarea>
        </section>
        <style>
          html, body {{
            margin: 0;
            padding: 0;
            background: transparent;
            overflow: hidden;
            font-family: "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
          }}
          .ai-result-panel {{
            box-sizing: border-box;
            height: {int(height)}px;
            display: flex;
            flex-direction: column;
            border: 1px solid #d7e3df;
            background: #ffffff;
            border-radius: 10px;
            overflow: hidden;
          }}
          .ai-result-title {{
            flex: 0 0 auto;
            padding: 0.58rem 0.75rem;
            border-bottom: 1px solid #d7e3df;
            background: #eef8f4;
            color: #087b69;
            font-weight: 760;
            font-size: 0.86rem;
          }}
          textarea {{
            flex: 1 1 auto;
            width: 100%;
            min-height: 0;
            box-sizing: border-box;
            overflow-y: auto;
            overflow-x: auto;
            resize: none;
            margin: 0;
            padding: 0.85rem;
            border: 0;
            outline: 0;
            background: #ffffff;
            color: #17211f;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            user-select: text;
            cursor: text;
            font-family: Consolas, "Microsoft YaHei", monospace;
            font-size: 13.5px;
            line-height: 1.62;
          }}
          textarea:focus {{
            box-shadow: inset 0 0 0 1px rgba(16, 163, 127, 0.28);
          }}
        </style>
        """,
        height=int(height) + 4,
        scrolling=False,
    )

def info_row(label: str, value: object, status_html: str = "") -> None:
    value_text = "" if value is None else str(value)
    st.markdown(
        f"""
        <div class="info-row">
          <span>{escape(label)}</span>
          <strong>{escape(value_text)}</strong>
          {status_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def confirm_dialog(
    title: str,
    body: str,
    confirm_label: str,
    cancel_label: str,
    on_confirm,
    key: str,
) -> None:
    @st.dialog(title)
    def _dialog() -> None:
        st.write(body)
        cancel_col, confirm_col = st.columns(2)
        if cancel_col.button(cancel_label, key=f"{key}_cancel", use_container_width=True):
            st.session_state.pop(key, None)
            st.rerun()
        if confirm_col.button(confirm_label, key=f"{key}_confirm", type="primary", use_container_width=True):
            on_confirm()
            st.session_state.pop(key, None)
            st.rerun()

    _dialog()


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-accent: #0f9f8a;
            --app-accent-dark: #0b7568;
            --app-accent-soft: #dff7f0;
            --app-accent-wash: #f1fbf8;
            --app-info: #2f6fda;
            --app-warning: #b7791f;
            --app-warning-soft: #fff7df;
            --app-error: #c2413d;
            --app-error-soft: #fff0ef;
            --app-bg: #f5f7f6;
            --app-bg-pattern: rgba(15, 159, 138, 0.04);
            --app-surface: #ffffff;
            --app-surface-muted: #f8faf9;
            --app-text: #17211f;
            --app-subtle: #53635f;
            --app-muted: #71817c;
            --app-border: #dde6e2;
            --app-border-strong: #c8d5d0;
            --app-shadow: 0 18px 42px rgba(28, 64, 56, 0.08);
            --app-shadow-soft: 0 8px 22px rgba(28, 64, 56, 0.055);
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --font-sans: "Microsoft YaHei", "Source Han Sans SC", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: "Cascadia Mono", "SFMono-Regular", Consolas, ui-monospace, monospace;
        }
        html { scroll-behavior: smooth; }
        .stApp {
            color: var(--app-text);
            background:
                radial-gradient(circle at 12% 8%, rgba(15, 159, 138, 0.08), transparent 28rem),
                linear-gradient(180deg, #f8faf9 0%, var(--app-bg) 42%, #f2f5f3 100%);
            font-family: var(--font-sans);
            font-variant-numeric: tabular-nums;
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: 0.45;
            background-image:
                linear-gradient(var(--app-bg-pattern) 1px, transparent 1px),
                linear-gradient(90deg, var(--app-bg-pattern) 1px, transparent 1px);
            background-size: 28px 28px;
            z-index: 0;
        }
        header[data-testid="stHeader"] { background: transparent; height: 0; }
        .block-container {
            padding-top: 1rem !important;
            padding-left: 1.1rem !important;
            padding-right: 1.1rem !important;
            max-width: 1320px;
        }
        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.94);
            border-right: 1px solid var(--app-border);
            box-shadow: 12px 0 34px rgba(28, 64, 56, 0.055);
            min-width: 224px !important;
            width: 224px !important;
            max-width: 224px !important;
        }
        section[data-testid="stSidebar"] > div {
            padding: 1.05rem 0.72rem 1rem;
            width: 224px !important;
        }
        .brand-block {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            padding: 0.05rem 0.15rem 0.9rem;
            margin-bottom: 0.2rem;
        }
        .brand-mark,
        .empty-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.85rem;
            height: 1.85rem;
            border-radius: var(--radius-md);
            background: linear-gradient(145deg, var(--app-accent), #13b69d);
            color: #ffffff;
            font-weight: 800;
            box-shadow: 0 8px 18px rgba(15, 159, 138, 0.22);
        }
        .brand-title {
            color: var(--app-text);
            font-size: 1.02rem;
            font-weight: 800;
            letter-spacing: 0;
            white-space: nowrap;
        }
        .brand-compact { padding-bottom: 0; margin-bottom: 0; }
        .sidebar-caption {
            color: var(--app-muted);
            font-size: 0.72rem;
            line-height: 1.35;
            margin: 0 0 0.6rem;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button {
            width: 100%;
            justify-content: flex-start;
            border: 0;
            border-radius: var(--radius-md);
            color: #33423f;
            background: transparent;
            min-height: 2.08rem;
            padding: 0.38rem 0.62rem;
            font-weight: 600;
            box-shadow: none;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            transition: background 180ms ease, color 180ms ease, transform 180ms ease;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
            color: var(--app-accent-dark);
            background: var(--app-accent-wash);
            transform: translateX(1px);
        }
        .nav-active {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            min-height: 2.08rem;
            padding: 0 0.55rem;
            margin: 0.12rem 0;
            border-radius: var(--radius-md);
            background: var(--app-accent-soft);
            color: var(--app-accent-dark);
            border-left: 3px solid var(--app-accent);
            font-weight: 750;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .nav-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.12rem;
            height: 1.12rem;
            border-radius: var(--radius-sm);
            background: rgba(15, 159, 138, 0.13);
            font-size: 0.7rem;
            font-weight: 800;
            flex: 0 0 auto;
        }
        .shell-title h1,
        .page-head h1 {
            margin: 0;
            color: var(--app-text);
            font-size: clamp(1.35rem, 1.1rem + 0.7vw, 1.85rem);
            line-height: 1.18;
            font-weight: 820;
            letter-spacing: 0;
            text-wrap: balance;
        }
        .shell-title p,
        .page-head p {
            margin: 0.28rem 0 0;
            color: var(--app-muted);
            font-size: 0.9rem;
            line-height: 1.55;
            max-width: 68ch;
        }
        .page-head { margin: 0 0 1rem; }
        .section-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            margin: 1.15rem 0 0.5rem;
        }
        .section-head h2 {
            margin: 0;
            color: var(--app-text);
            font-size: 1.02rem;
            line-height: 1.25;
            font-weight: 760;
            letter-spacing: 0;
        }
        .section-head span {
            color: var(--app-muted);
            font-size: 0.82rem;
            line-height: 1.4;
        }
        .ui-surface,
        .hero-card,
        .stat-card,
        div[data-testid="stForm"],
        div[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid var(--app-border);
            border-radius: var(--radius-lg);
            box-shadow: var(--app-shadow-soft);
        }
        .ui-surface {
            padding: 1rem 1.05rem;
            margin: 0.55rem 0 0.85rem;
        }
        .ui-surface h3,
        .hero-card h2,
        .empty-state h3 {
            margin: 0 0 0.42rem;
            color: var(--app-text);
            font-size: 1.02rem;
            line-height: 1.35;
            font-weight: 760;
            letter-spacing: 0;
        }
        .ui-surface p,
        .hero-card p,
        .empty-state p {
            margin: 0;
            color: var(--app-subtle);
            line-height: 1.7;
            max-width: 72ch;
        }
        .surface-info { border-color: rgba(47, 111, 218, 0.22); background: #f5f8ff; }
        .surface-warning { border-color: rgba(183, 121, 31, 0.22); background: var(--app-warning-soft); }
        .hero-card {
            padding: 1.15rem 1.25rem;
            margin-bottom: 1rem;
        }
        .hero-card h2 { font-size: 1.08rem; }
        .app-hero {
            padding: clamp(1.5rem, 2.4vw, 2.25rem) clamp(1.25rem, 3vw, 2.4rem);
            border-radius: 14px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,251,248,0.94)),
                radial-gradient(circle at 86% 18%, rgba(15,159,138,0.16), transparent 18rem);
            border: 1px solid var(--app-border);
            box-shadow: var(--app-shadow);
            margin-top: 0.8rem;
            margin-bottom: 1rem;
        }
        .app-hero .kicker {
            margin: 0 0 0.6rem;
            color: var(--app-accent-dark);
            font-weight: 800;
            font-size: 0.86rem;
        }
        .app-hero h2 {
            max-width: min(100%, 24ch);
            margin: 0 0 0.82rem;
            color: var(--app-text);
            font-size: clamp(1.55rem, 2.4vw, 2.25rem);
            line-height: 1.15;
            font-weight: 850;
            letter-spacing: 0;
            text-wrap: balance;
        }
        .app-hero p {
            max-width: 68ch;
            color: var(--app-subtle);
            font-size: 1rem;
            line-height: 1.8;
            margin: 0;
        }
        .stat-card {
            padding: 1rem;
            min-height: 7rem;
        }
        .stat-label {
            color: var(--app-muted);
            font-size: 0.82rem;
            font-weight: 650;
        }
        .stat-value {
            margin-top: 0.36rem;
            color: var(--app-text);
            font-size: 1.72rem;
            line-height: 1.1;
            font-weight: 820;
            font-variant-numeric: tabular-nums;
        }
        .stat-note {
            margin-top: 0.45rem;
            color: var(--app-muted);
            font-size: 0.78rem;
            line-height: 1.45;
        }
        .empty-state {
            border: 1px dashed var(--app-border-strong);
            border-radius: var(--radius-lg);
            background: rgba(255, 255, 255, 0.72);
            padding: 1.2rem;
            margin: 0.7rem 0 1rem;
        }
        .empty-mark {
            width: 2rem;
            height: 2rem;
            margin-bottom: 0.68rem;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            min-height: 1.45rem;
            padding: 0 0.55rem;
            border-radius: var(--radius-sm);
            font-size: 0.78rem;
            font-weight: 720;
            border: 1px solid transparent;
        }
        .status-success { color: #087461; background: var(--app-accent-soft); border-color: rgba(15,159,138,0.18); }
        .status-info { color: #2459b8; background: #eaf1ff; border-color: rgba(47,111,218,0.18); }
        .status-warning { color: #915f17; background: var(--app-warning-soft); border-color: rgba(183,121,31,0.18); }
        .status-error { color: var(--app-error); background: var(--app-error-soft); border-color: rgba(194,65,61,0.18); }
        .status-neutral { color: #53635f; background: #edf2f0; border-color: var(--app-border); }
        .table-header {
            display: grid;
            grid-auto-flow: column;
            grid-auto-columns: minmax(0, 1fr);
            gap: 0.75rem;
            padding: 0.5rem 0.65rem;
            margin: 0.35rem 0 0.15rem;
            color: var(--app-muted);
            font-size: 0.78rem;
            font-weight: 720;
            border-bottom: 1px solid var(--app-border);
        }
        .row-separator {
            height: 1px;
            background: var(--app-border);
            margin: 0.42rem 0;
        }
        .info-row {
            display: grid;
            grid-template-columns: minmax(5.5rem, 0.34fr) minmax(0, 1fr) auto;
            align-items: center;
            gap: 0.55rem;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(221, 230, 226, 0.7);
        }
        .info-row:last-child { border-bottom: 0; }
        .info-row span {
            color: var(--app-muted);
            font-size: 0.84rem;
        }
        .info-row strong {
            color: var(--app-text);
            font-size: 0.92rem;
            font-weight: 680;
            overflow-wrap: anywhere;
        }
        .upload-hint {
            border: 1px solid rgba(15, 159, 138, 0.18);
            background: rgba(241, 251, 248, 0.82);
            border-radius: var(--radius-md);
            padding: 0.72rem 0.82rem;
            margin: 0.35rem 0 0.5rem;
            color: var(--app-text);
        }
        .upload-hint strong {
            display: block;
            font-size: 0.9rem;
            margin-bottom: 0.18rem;
        }
        .upload-hint p {
            margin: 0;
            color: var(--app-subtle);
            font-size: 0.82rem;
            line-height: 1.55;
        }
        div[data-testid="stFileUploader"] section {
            background: rgba(255, 255, 255, 0.68) !important;
            border-color: rgba(15, 159, 138, 0.22) !important;
        }
        div[data-testid="stFileUploader"] small,
        div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] span {
            color: var(--app-muted) !important;
            font-size: 0.74rem !important;
        }
        .readonly-panel {
            border: 1px solid var(--app-border);
            background: #ffffff;
            border-radius: var(--radius-lg);
            box-shadow: var(--app-shadow-soft);
            overflow: hidden;
            margin: 0.45rem 0 0.9rem;
        }
        .readonly-title {
            padding: 0.58rem 0.75rem;
            border-bottom: 1px solid var(--app-border);
            background: var(--app-accent-wash);
            color: var(--app-accent-dark);
            font-weight: 760;
            font-size: 0.86rem;
        }
        .readonly-panel pre {
            height: calc(100% - 2.45rem);
            overflow: auto;
            margin: 0;
            padding: 0.85rem;
            background: #ffffff;
            color: var(--app-text);
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            font-family: var(--font-mono);
            font-size: 0.82rem;
            line-height: 1.6;
        }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.94);
            border: 1px solid var(--app-border);
            border-radius: var(--radius-lg) !important;
            padding: 0.85rem 0.95rem;
            box-shadow: var(--app-shadow-soft);
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stPlotlyChart"],
        div[data-testid="stFileUploader"],
        div[data-testid="stAlert"] {
            border-radius: var(--radius-lg) !important;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stPlotlyChart"] {
            overflow: hidden;
            border: 1px solid var(--app-border);
            background: var(--app-surface);
            box-shadow: var(--app-shadow-soft);
        }
        div[data-testid="stForm"],
        div[data-testid="stExpander"] {
            overflow: hidden;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div,
        div[data-testid="stNumberInput"] input {
            border-radius: var(--radius-md) !important;
            border-color: var(--app-border) !important;
            background-color: #f9fbfa !important;
            transition: border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
        }
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stNumberInput"] input:focus {
            border-color: var(--app-accent) !important;
            box-shadow: 0 0 0 3px rgba(15, 159, 138, 0.14) !important;
            background-color: #ffffff !important;
        }
        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button,
        [data-testid="stFormSubmitButton"] button {
            border-radius: var(--radius-md);
            border: 1px solid var(--app-border);
            font-weight: 680;
            min-height: 2.42rem;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            transition: transform 160ms ease, background 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
            box-shadow: none;
        }
        [data-testid="stButton"] button:hover,
        [data-testid="stDownloadButton"] button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            border-color: rgba(15, 159, 138, 0.42);
            background: var(--app-accent-wash);
            transform: translateY(-1px);
            box-shadow: 0 7px 18px rgba(28, 64, 56, 0.07);
        }
        [data-testid="stButton"] button:active,
        [data-testid="stDownloadButton"] button:active,
        [data-testid="stFormSubmitButton"] button:active {
            transform: translateY(0) scale(0.99);
        }
        [data-testid="stButton"] button:focus,
        [data-testid="stDownloadButton"] button:focus,
        [data-testid="stFormSubmitButton"] button:focus {
            box-shadow: 0 0 0 3px rgba(15, 159, 138, 0.18) !important;
            border-color: var(--app-accent) !important;
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
        [data-testid="stFormSubmitButton"] button p { margin: 0; }
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {
            background: var(--app-accent);
            border-color: var(--app-accent);
            color: #ffffff;
        }
        [data-testid="stButton"] button[kind="primary"]:hover,
        [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
            background: var(--app-accent-dark);
            border-color: var(--app-accent-dark);
        }
        [data-testid="stAlert"] {
            border: 1px solid var(--app-border);
            box-shadow: none;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stCaptionContainer"] p {
            line-height: 1.65;
        }
        code, pre, textarea {
            font-family: var(--font-mono);
        }

        .dashboard-kpi {
            min-height: 9.4rem;
            padding: 0.95rem 1rem;
            border: 1px solid var(--app-border);
            border-radius: var(--radius-lg);
            background: rgba(255, 255, 255, 0.92);
            box-shadow: var(--app-shadow-soft);
        }
        .dashboard-kpi-label {
            color: var(--app-muted);
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .dashboard-kpi-value {
            color: var(--app-text);
            font-size: clamp(1.55rem, 1.1rem + 1vw, 2.15rem);
            line-height: 1.05;
            font-weight: 840;
            margin-bottom: 0.55rem;
        }
        .dashboard-kpi-note {
            color: var(--app-muted);
            font-size: 0.78rem;
            line-height: 1.45;
        }
        .dashboard-mini-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
            margin-top: 0.7rem;
        }
        .dashboard-mini-stat {
            padding: 0.62rem 0.7rem;
            border-radius: var(--radius-md);
            background: var(--app-surface-muted);
            border: 1px solid var(--app-border);
        }
        .dashboard-mini-stat span {
            display: block;
            color: var(--app-muted);
            font-size: 0.72rem;
            margin-bottom: 0.22rem;
        }
        .dashboard-mini-stat strong {
            display: block;
            color: var(--app-text);
            font-size: 1.1rem;
            line-height: 1.1;
        }
        .dashboard-card-title {
            margin: 0 0 0.35rem;
            color: var(--app-text);
            font-size: 0.95rem;
            font-weight: 780;
        }
        @media (max-width: 760px) {
            .block-container {
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
            }
            .section-head {
                display: block;
            }
            .section-head span {
                display: block;
                margin-top: 0.2rem;
            }
            .app-hero h2 {
                max-width: 100%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
