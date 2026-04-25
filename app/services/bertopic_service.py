from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from . import db
from .llm import chat_text
from .storage import project_exports_root, save_export_dataframe, save_json_artifact
from .utils import json_dumps, json_loads, short_uuid, to_json_compatible, utc_now_iso


def _prepare_docs(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["Title"] = work["Title"].fillna("")
    work["Abstract"] = work["Abstract"].fillna("")
    work["text"] = work["Title"].astype(str) + ". " + work["Abstract"].astype(str)
    return work


def _topic_info_records(topic_info: pd.DataFrame) -> list[dict[str, Any]]:
    return to_json_compatible(topic_info.fillna("").to_dict(orient="records"))


@lru_cache(maxsize=1)
def _load_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2", device="cpu")


def _language_instruction(language: str) -> str:
    return "Respond in Chinese." if language == "zh-CN" else "Respond in English."


def _save_text_result(topic_run_id: int, key: str, text: str) -> str:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO topic_interpretations (topic_run_id, chart_key, interpretation_text, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(topic_run_id, chart_key) DO UPDATE SET interpretation_text = excluded.interpretation_text, created_at = excluded.created_at
            """,
            (topic_run_id, key, text, utc_now_iso()),
        )
    return text


def run_bertopic(
    project_id: int,
    user_id: int,
    df: pd.DataFrame,
    source_type: str,
    params: dict[str, Any],
    data_file_id: int | None = None,
    screening_run_id: int | None = None,
) -> dict[str, Any]:
    from bertopic import BERTopic
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    defaults = {
        "random_state": 42,
        "n_neighbors": 15,
        "n_components": 5,
        "min_topic_size": 5,
        "nr_topics": 15,
    }
    config = {**defaults, **params}
    run_id = db.execute(
        """
        INSERT INTO topic_runs (project_id, user_id, source_type, data_file_id, screening_run_id, params_json, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
        """,
        (project_id, user_id, source_type, data_file_id, screening_run_id, json_dumps(config), utc_now_iso(), utc_now_iso()),
    )

    try:
        work = _prepare_docs(df)
        docs = work["text"].tolist()
        umap_model = UMAP(
            n_neighbors=int(config["n_neighbors"]),
            n_components=int(config["n_components"]),
            min_dist=0.0,
            metric="cosine",
            random_state=int(config["random_state"]),
        )
        vectorizer_model = CountVectorizer(stop_words="english")
        topic_model = BERTopic(
            language="multilingual",
            embedding_model=_load_embedding_model(),
            vectorizer_model=vectorizer_model,
            umap_model=umap_model,
            min_topic_size=int(config["min_topic_size"]),
            nr_topics=int(config["nr_topics"]),
        )
        topics, _probs = topic_model.fit_transform(docs)
        topic_info = topic_model.get_topic_info()
        work["Topic"] = topics
        topic_names = topic_info.set_index("Topic")["Name"].to_dict()
        work["Topic_Name"] = work["Topic"].map(topic_names)

        export_dir = project_exports_root(user_id, project_id)
        output_path = export_dir / f"topics_{short_uuid()}.csv"
        save_export_dataframe(work.drop(columns=["text"]), output_path)

        fig_barchart = topic_model.visualize_barchart(top_n_topics=int(config["nr_topics"]))
        fig_topics = topic_model.visualize_topics()
        fig_hierarchy = topic_model.visualize_hierarchy()
        artifacts = {
            "barchart": save_json_artifact(to_json_compatible(fig_barchart.to_plotly_json()), export_dir / f"barchart_{run_id}.json"),
            "topics": save_json_artifact(to_json_compatible(fig_topics.to_plotly_json()), export_dir / f"topics_{run_id}.json"),
            "hierarchy": save_json_artifact(to_json_compatible(fig_hierarchy.to_plotly_json()), export_dir / f"hierarchy_{run_id}.json"),
        }
        db.execute(
            """
            UPDATE topic_runs
            SET status = 'completed', topic_info_json = ?, artifacts_json = ?, output_path = ?, updated_at = ?
            WHERE id = ?
            """,
            (json_dumps(_topic_info_records(topic_info)), json_dumps(artifacts), str(output_path), utc_now_iso(), run_id),
        )
        return {"run_id": run_id, "output_df": work.drop(columns=["text"]), "topic_info": topic_info, "artifacts": artifacts}
    except Exception:
        db.execute(
            "UPDATE topic_runs SET status = 'failed', updated_at = ? WHERE id = ?",
            (utc_now_iso(), run_id),
        )
        raise


def list_topic_runs(project_id: int, user_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all("SELECT * FROM topic_runs WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))
    results = []
    for row in rows:
        item = dict(row)
        item["params"] = json_loads(item["params_json"], {})
        item["topic_info"] = json_loads(item["topic_info_json"], [])
        item["artifacts"] = json_loads(item["artifacts_json"], {})
        results.append(item)
    return results


def load_plotly_artifact(path: str) -> dict[str, Any]:
    return json_loads(Path(path).read_text(encoding="utf-8"), {})


def save_chart_interpretation(user_id: int, topic_run_id: int, chart_key: str, context_text: str, language: str) -> str:
    prompt = (
        f"Interpret the specific BERTopic chart '{chart_key}' generated from the user's dataset. "
        "Use only the provided topic overview and Plotly data summary. "
        "Do not explain what this chart type is for, do not explain the BERTopic algorithm, and do not give generic chart-reading guidance. "
        "Focus on what the user's clustered records appear to show: dominant topics, distribution patterns, notable separations, and uncertainty visible in this result.\n\n"
        f"{_language_instruction(language)}\n\n{context_text}"
    )
    interpretation = chat_text(user_id, "You explain BERTopic outputs clearly and concisely.", prompt, temperature=0.3)
    return _save_text_result(topic_run_id, chart_key, interpretation)


def save_topic_names(user_id: int, topic_run_id: int, context_text: str, language: str) -> str:
    prompt = (
        "Based on the BERTopic topic overview below, propose concise, user-friendly names for the main topics. "
        "Return a short numbered list with topic id and suggested name only.\n\n"
        f"{_language_instruction(language)}\n\n{context_text}"
    )
    text = chat_text(user_id, "You name BERTopic topics clearly and consistently.", prompt, temperature=0.2)
    return _save_text_result(topic_run_id, "topic_names", text)


def save_topic_explanation(user_id: int, topic_run_id: int, context_text: str, language: str) -> str:
    prompt = (
        "Explain the main BERTopic topics for a research user using only the topic overview below. "
        "Summarize what each major topic appears to represent.\n\n"
        f"{_language_instruction(language)}\n\n{context_text}"
    )
    text = chat_text(user_id, "You explain BERTopic topic summaries clearly and concisely.", prompt, temperature=0.3)
    return _save_text_result(topic_run_id, "topic_explanation", text)


def list_chart_interpretations(topic_run_id: int) -> dict[str, str]:
    rows = db.fetch_all("SELECT chart_key, interpretation_text FROM topic_interpretations WHERE topic_run_id = ?", (topic_run_id,))
    return {row["chart_key"]: row["interpretation_text"] for row in rows}
