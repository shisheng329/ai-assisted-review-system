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
