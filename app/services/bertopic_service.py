from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
import os
import subprocess
import sys
import traceback
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from . import db
from .llm import chat_text
from .storage import (
    project_exports_root,
    read_export_dataframe,
    require_existing_path,
    save_export_dataframe,
    save_json_artifact,
    source_export_path,
    unlink_managed_file,
)
from .utils import app_root, ensure_dir, json_dumps, json_loads, to_json_compatible, utc_now_iso


logger = logging.getLogger(__name__)
BERTOPIC_WORKER_TIMEOUT_SECONDS = 600


class BERTopicDependencyError(RuntimeError):
    pass


class BERTopicInputError(RuntimeError):
    pass


class BERTopicRuntimeError(RuntimeError):
    pass


class BERTopicTimeoutError(RuntimeError):
    pass


def _ensure_numba_cache_dir() -> Path:
    cache_dir = Path(tempfile.gettempdir()) / "literature_lab_numba_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_dir))
    return cache_dir


def check_bertopic_dependencies(timeout_seconds: int = 30) -> list[str]:
    cache_dir = _ensure_numba_cache_dir()
    modules = [
        ("streamlit", "streamlit"),
        ("scikit-learn", "sklearn"),
        ("umap-learn", "umap"),
        ("hdbscan", "hdbscan"),
        ("numba", "numba"),
        ("torch", "torch"),
        ("transformers", "transformers"),
        ("sentence-transformers", "sentence_transformers"),
        ("bertopic", "bertopic"),
    ]
    unavailable: list[str] = []
    env = os.environ.copy()
    env["NUMBA_CACHE_DIR"] = str(cache_dir)
    for package, module in modules:
        if importlib.util.find_spec(module) is None:
            unavailable.append(f"{package}: not installed")
            continue
        code = (
            "import importlib, importlib.metadata as md, time\n"
            "start=time.time()\n"
            f"importlib.import_module({module!r})\n"
            f"print({package!r}, md.version({package!r}), f'elapsed={{time.time()-start:.2f}}')\n"
        )
        try:
            subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=True,
                env=env,
                cwd=str(app_root()),
            )
        except subprocess.TimeoutExpired:
            unavailable.append(f"{package}: import timeout after {timeout_seconds}s")
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip().splitlines()
            suffix = f": {detail[-1]}" if detail else ""
            unavailable.append(f"{package}: import failed{suffix}")
    return unavailable


def _standardize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    lower_map = {str(column).strip().lower(): column for column in work.columns}
    rename_map = {}
    if "Title" not in work.columns and "title" in lower_map:
        rename_map[lower_map["title"]] = "Title"
    if "Abstract" not in work.columns and "abstract" in lower_map:
        rename_map[lower_map["abstract"]] = "Abstract"
    if rename_map:
        work = work.rename(columns=rename_map)
    return work


def _prepare_docs(df: pd.DataFrame) -> pd.DataFrame:
    work = _standardize_text_columns(df)
    required = {"Title", "Abstract"}
    missing = required - set(work.columns)
    if missing:
        raise BERTopicInputError(f"Missing columns: {', '.join(sorted(missing))}")
    work["Title"] = work["Title"].fillna("")
    work["Abstract"] = work["Abstract"].fillna("")
    work["text"] = (work["Title"].astype(str).str.strip() + ". " + work["Abstract"].astype(str).str.strip()).str.strip()
    work = work[work["text"].str.len() > 1].reset_index(drop=True)
    if len(work) < 3:
        raise BERTopicInputError("At least 3 valid records are required for BERTopic.")
    return work


def _normalize_params(params: dict[str, Any], doc_count: int) -> dict[str, Any]:
    defaults = {
        "random_state": 42,
        "n_neighbors": 15,
        "n_components": 5,
        "min_topic_size": 5,
        "nr_topics": 15,
    }
    config = {**defaults, **params}
    max_neighbors = max(2, doc_count - 1)
    config["n_neighbors"] = min(max(2, int(config.get("n_neighbors") or 2)), max_neighbors)
    config["n_components"] = min(max(2, int(config.get("n_components") or 2)), max(2, doc_count - 1))
    config["min_topic_size"] = min(max(2, int(config.get("min_topic_size") or 2)), max(2, doc_count))
    config["nr_topics"] = min(max(2, int(config.get("nr_topics") or 2)), max(2, doc_count))
    config["random_state"] = int(config.get("random_state") or 42)
    return config


def _topic_info_records(topic_info: pd.DataFrame) -> list[dict[str, Any]]:
    return to_json_compatible(topic_info.fillna("").to_dict(orient="records"))


@lru_cache(maxsize=1)
def _load_local_embedding_model():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2", device="cpu", local_files_only=True)


def _build_offline_embeddings(docs: list[str], random_state: int) -> tuple[Any, dict[str, Any]]:
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform(docs)
    if matrix.shape[1] < 2:
        raise BERTopicInputError("Not enough vocabulary for offline topic embeddings.")
    n_components = min(100, max(2, len(docs) - 1), max(2, matrix.shape[1] - 1))
    embeddings = TruncatedSVD(n_components=n_components, random_state=random_state).fit_transform(matrix)
    return embeddings, {
        "embedding_mode": "tfidf_svd_offline",
        "embedding_model": "TfidfVectorizer + TruncatedSVD",
        "embedding_dimensions": int(n_components),
        "vocabulary_size": int(matrix.shape[1]),
    }


def _resolve_embeddings(docs: list[str], random_state: int) -> tuple[Any | None, Any | None, dict[str, Any]]:
    try:
        return _load_local_embedding_model(), None, {
            "embedding_mode": "sentence_transformer_local",
            "embedding_model": "all-MiniLM-L6-v2",
        }
    except Exception as exc:
        logger.exception("Local BERTopic embedding model could not be loaded; using offline TF-IDF/SVD fallback")
        embeddings, detail = _build_offline_embeddings(docs, random_state)
        detail["embedding_fallback_reason"] = str(exc)
        detail["embedding_fallback_type"] = type(exc).__name__
        return None, embeddings, detail


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




def _classify_error_type(message: str, default: str = "runtime") -> str:
    lowered = str(message or "").lower()
    if any(token in lowered for token in ["huggingface.co", "all-minilm-l6-v2", "sentence-transformer", "proxyerror", "hf_hub", "transformers_offline"]):
        return "embedding_model"
    if any(token in lowered for token in ["timed out", "timeoutexpired"]):
        return "timeout"
    return default


def _short_error_message(message: str, limit: int = 360) -> str:
    cleaned = " ".join(str(message or "").split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def _base_error_detail(payload: dict[str, Any] | None = None, work: pd.DataFrame | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    params = dict(payload.get("params") or {})
    detail: dict[str, Any] = {
        "run_id": payload.get("run_id"),
        "project_id": payload.get("project_id"),
        "user_id": payload.get("user_id"),
        "source_type": payload.get("source_type"),
        "data_file_id": payload.get("data_file_id"),
        "screening_run_id": payload.get("screening_run_id"),
        "params": params,
        "text_fields": ["Title", "Abstract"],
        "embedding_model": "all-MiniLM-L6-v2",
        "input_path": payload.get("input_path"),
    }
    if work is not None:
        detail.update(
            {
                "input_rows": int(len(work)),
                "title_nonempty": int(work["Title"].fillna("").astype(str).str.strip().ne("").sum()) if "Title" in work else None,
                "abstract_nonempty": int(work["Abstract"].fillna("").astype(str).str.strip().ne("").sum()) if "Abstract" in work else None,
            }
        )
    if extra:
        detail.update(extra)
    return detail


def _update_topic_run_failure(run_id: int, error_type: str, message: str, detail: dict[str, Any] | None = None) -> None:
    db.execute(
        """
        UPDATE topic_runs
        SET status = 'failed', error_type = ?, error_message = ?, error_detail_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (error_type, _short_error_message(message), json_dumps(detail or {}), utc_now_iso(), run_id),
    )


def _job_result_path(user_id: int, project_id: int, run_id: int) -> Path:
    return project_exports_root(user_id, project_id) / "_jobs" / f"bertopic_{run_id}_result.json"


def _legacy_error_from_job(item: dict[str, Any]) -> tuple[str | None, str | None, dict[str, Any]]:
    try:
        result_path = _job_result_path(int(item["user_id"]), int(item["project_id"]), int(item["id"]))
        if not result_path.exists():
            return None, None, {}
        result = json_loads(result_path.read_text(encoding="utf-8"), {})
        if result.get("status") == "completed":
            return None, None, {}
        message = result.get("message") or "BERTopic worker failed."
        error_type = _classify_error_type(str(message), str(result.get("error_type") or "runtime"))
        detail = dict(result.get("detail") or {})
        detail.setdefault("legacy_result_path", str(result_path))
        return str(error_type), _short_error_message(str(message)), detail
    except Exception:
        logger.exception("Failed to read legacy BERTopic error detail for run_id=%s", item.get("id"))
        return None, None, {}

def _worker_payload_dir(user_id: int, project_id: int) -> Path:
    return ensure_dir(project_exports_root(user_id, project_id) / "_jobs")


def _write_worker_payload(
    run_id: int,
    project_id: int,
    user_id: int,
    work: pd.DataFrame,
    source_type: str,
    config: dict[str, Any],
    data_file_id: int | None,
    screening_run_id: int | None,
) -> Path:
    payload_dir = _worker_payload_dir(user_id, project_id)
    input_path = payload_dir / f"bertopic_{run_id}_input.csv"
    result_path = payload_dir / f"bertopic_{run_id}_result.json"
    payload_path = payload_dir / f"bertopic_{run_id}_payload.json"
    work.drop(columns=["text"], errors="ignore").to_csv(input_path, index=False, encoding="utf-8-sig")
    payload = {
        "run_id": run_id,
        "project_id": project_id,
        "user_id": user_id,
        "source_type": source_type,
        "data_file_id": data_file_id,
        "screening_run_id": screening_run_id,
        "params": config,
        "input_path": str(input_path),
        "result_path": str(result_path),
    }
    payload_path.write_text(json_dumps(payload), encoding="utf-8")
    return payload_path


def _read_worker_result(payload_path: Path) -> dict[str, Any]:
    payload = json_loads(payload_path.read_text(encoding="utf-8"), {})
    result_path = Path(payload.get("result_path", ""))
    if not result_path.exists():
        return {"status": "failed", "error_type": "runtime", "message": "BERTopic worker did not write a result file."}
    return json_loads(result_path.read_text(encoding="utf-8"), {})


def _cleanup_worker_files(payload_path: Path) -> None:
    payload = json_loads(payload_path.read_text(encoding="utf-8"), {}) if payload_path.exists() else {}
    for key in ("input_path", "result_path"):
        value = payload.get(key)
        if value:
            unlink_managed_file(value)
    unlink_managed_file(payload_path)


def _raise_worker_error(result: dict[str, Any]) -> None:
    message = str(result.get("message") or "BERTopic worker failed.")
    error_type = result.get("error_type")
    if error_type == "dependency":
        raise BERTopicDependencyError(message)
    if error_type == "input":
        raise BERTopicInputError(message)
    if error_type == "timeout":
        raise BERTopicTimeoutError(message)
    raise BERTopicRuntimeError(message)


def run_bertopic(
    project_id: int,
    user_id: int,
    df: pd.DataFrame,
    source_type: str,
    params: dict[str, Any],
    data_file_id: int | None = None,
    screening_run_id: int | None = None,
    timeout_seconds: int = BERTOPIC_WORKER_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    work = _prepare_docs(df)
    config = _normalize_params(params, len(work))
    run_id = db.execute(
        """
        INSERT INTO topic_runs (project_id, user_id, source_type, data_file_id, screening_run_id, params_json, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
        """,
        (project_id, user_id, source_type, data_file_id, screening_run_id, json_dumps(config), utc_now_iso(), utc_now_iso()),
    )
    payload_path = _write_worker_payload(run_id, project_id, user_id, work, source_type, config, data_file_id, screening_run_id)
    env = os.environ.copy()
    env["NUMBA_CACHE_DIR"] = str(_ensure_numba_cache_dir())
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "app.services.bertopic_worker", str(payload_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(app_root()),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        detail = _base_error_detail(
            json_loads(payload_path.read_text(encoding="utf-8"), {}),
            work,
            {
                "timeout_seconds": int(timeout_seconds),
                "stdout": exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout,
                "stderr": exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr,
            },
        )
        _update_topic_run_failure(run_id, "timeout", f"BERTopic worker timed out after {timeout_seconds}s.", detail)
        logger.exception("BERTopic worker timed out for run_id=%s", run_id)
        raise BERTopicTimeoutError(f"BERTopic worker timed out after {timeout_seconds}s.") from exc

    result = _read_worker_result(payload_path)
    if completed.returncode != 0 and result.get("status") != "completed":
        detail = dict(result.get("detail") or {})
        detail.setdefault("stdout", completed.stdout)
        detail.setdefault("stderr", completed.stderr)
        result["detail"] = detail
        logger.error("BERTopic worker failed for run_id=%s stdout=%s stderr=%s result=%s", run_id, completed.stdout, completed.stderr, result)
        _update_topic_run_failure(run_id, str(result.get("error_type") or "runtime"), str(result.get("message") or "BERTopic worker failed."), detail)
        _raise_worker_error(result)
    if result.get("status") != "completed":
        _update_topic_run_failure(run_id, str(result.get("error_type") or "runtime"), str(result.get("message") or "BERTopic worker failed."), dict(result.get("detail") or {}))
        _raise_worker_error(result)

    output_path = result.get("output_path")
    output_df = read_export_dataframe(output_path)
    topic_info = pd.DataFrame(result.get("topic_info", []))
    return {"run_id": run_id, "output_df": output_df, "topic_info": topic_info, "artifacts": result.get("artifacts", {})}


def _run_bertopic_in_worker(payload: dict[str, Any]) -> dict[str, Any]:
    from bertopic import BERTopic
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    run_id = int(payload["run_id"])
    project_id = int(payload["project_id"])
    user_id = int(payload["user_id"])
    data_file_id = payload.get("data_file_id")
    config = dict(payload.get("params") or {})
    input_path = Path(payload["input_path"])
    work = _prepare_docs(pd.read_csv(input_path))
    docs = work["text"].tolist()
    detail = _base_error_detail(payload, work)

    try:
        embedding_model, embeddings, embedding_detail = _resolve_embeddings(docs, int(config["random_state"]))
        detail.update(embedding_detail)
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
            embedding_model=embedding_model,
            vectorizer_model=vectorizer_model,
            umap_model=umap_model,
            min_topic_size=int(config["min_topic_size"]),
            nr_topics=int(config["nr_topics"]),
        )
        if embeddings is None:
            topics, _probs = topic_model.fit_transform(docs)
        else:
            topics, _probs = topic_model.fit_transform(docs, embeddings=embeddings)
        topic_info = topic_model.get_topic_info()
        work["Topic"] = topics
        topic_names = topic_info.set_index("Topic")["Name"].to_dict()
        work["Topic_Name"] = work["Topic"].map(topic_names)

        export_dir = project_exports_root(user_id, project_id)
        source_row = db.fetch_one("SELECT filename FROM data_files WHERE id = ? AND project_id = ? AND user_id = ?", (data_file_id, project_id, user_id)) if data_file_id else None
        source_filename = source_row["filename"] if source_row else f"topics_{run_id}.csv"
        output_path = source_export_path(user_id, project_id, source_filename, "聚类")
        save_export_dataframe(work.drop(columns=["text"], errors="ignore"), output_path)

        artifacts = {}
        chart_builders = {
            "barchart": lambda: topic_model.visualize_barchart(top_n_topics=int(config["nr_topics"])),
            "topics": topic_model.visualize_topics,
            "hierarchy": topic_model.visualize_hierarchy,
        }
        for chart_key, build_chart in chart_builders.items():
            try:
                chart = build_chart()
                artifacts[chart_key] = save_json_artifact(
                    to_json_compatible(chart.to_plotly_json()),
                    export_dir / f"{chart_key}_{run_id}.json",
                )
            except Exception:
                logger.exception("BERTopic chart generation failed for run_id=%s chart=%s", run_id, chart_key)
        topic_info_records = _topic_info_records(topic_info)
        db.execute(
            """
            UPDATE topic_runs
            SET status = 'completed', topic_info_json = ?, artifacts_json = ?, output_path = ?, error_type = NULL, error_message = NULL, error_detail_json = NULL, updated_at = ?
            WHERE id = ?
            """,
            (json_dumps(topic_info_records), json_dumps(artifacts), str(output_path), utc_now_iso(), run_id),
        )
        return {"status": "completed", "run_id": run_id, "output_path": str(output_path), "topic_info": topic_info_records, "artifacts": artifacts, "detail": detail}
    except Exception as exc:
        detail.update({"traceback": traceback.format_exc(), "exception_type": type(exc).__name__})
        _update_topic_run_failure(run_id, _classify_error_type(str(exc), "runtime"), str(exc), detail)
        raise


def worker_main(payload_path_value: str) -> int:
    payload_path = Path(payload_path_value)
    payload = json_loads(payload_path.read_text(encoding="utf-8"), {})
    result_path = Path(payload.get("result_path", payload_path.with_suffix(".result.json")))
    try:
        result = _run_bertopic_in_worker(payload)
        result_path.write_text(json_dumps(result), encoding="utf-8")
        return 0
    except BERTopicInputError as exc:
        detail = _base_error_detail(payload, extra={"traceback": traceback.format_exc(), "exception_type": type(exc).__name__})
        result = {"status": "failed", "error_type": "input", "message": str(exc), "detail": detail}
    except (ImportError, ModuleNotFoundError) as exc:
        detail = _base_error_detail(payload, extra={"traceback": traceback.format_exc(), "exception_type": type(exc).__name__})
        result = {"status": "failed", "error_type": "dependency", "message": str(exc), "detail": detail}
    except Exception as exc:
        logger.exception("BERTopic worker failed")
        detail = _base_error_detail(payload, extra={"traceback": traceback.format_exc(), "exception_type": type(exc).__name__})
        result = {"status": "failed", "error_type": _classify_error_type(str(exc), "runtime"), "message": str(exc), "detail": detail}
    run_id = payload.get("run_id")
    if run_id:
        try:
            _update_topic_run_failure(int(run_id), str(result["error_type"]), str(result["message"]), dict(result.get("detail") or {}))
        except Exception:
            logger.exception("Failed to mark BERTopic run failed from worker_main")
    result_path.write_text(json_dumps(result), encoding="utf-8")
    return 1


def get_existing_topic_runs_for_file(project_id: int, user_id: int, data_file_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        """
        SELECT * FROM topic_runs
        WHERE project_id = ? AND user_id = ? AND data_file_id = ?
        ORDER BY created_at DESC
        """,
        (project_id, user_id, data_file_id),
    )
    return [dict(row) for row in rows]


def delete_topic_run(project_id: int, user_id: int, run_id: int) -> None:
    row = db.fetch_one(
        "SELECT * FROM topic_runs WHERE id = ? AND project_id = ? AND user_id = ?",
        (run_id, project_id, user_id),
    )
    if not row:
        return
    paths = []
    if row["output_path"]:
        paths.append(row["output_path"])
    artifacts = json_loads(row["artifacts_json"], {})
    if isinstance(artifacts, dict):
        paths.extend(path for path in artifacts.values() if isinstance(path, str))
    db.execute("DELETE FROM topic_runs WHERE id = ? AND project_id = ? AND user_id = ?", (run_id, project_id, user_id))
    for path_value in paths:
        unlink_managed_file(path_value)


def list_topic_runs(project_id: int, user_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all("SELECT * FROM topic_runs WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))
    results = []
    for row in rows:
        item = dict(row)
        item["params"] = json_loads(item.get("params_json"), {})
        item["topic_info"] = json_loads(item.get("topic_info_json"), [])
        item["artifacts"] = json_loads(item.get("artifacts_json"), {})
        item["error_detail"] = json_loads(item.get("error_detail_json"), {})
        if item.get("status") == "failed" and not item.get("error_message"):
            error_type, message, detail = _legacy_error_from_job(item)
            if message:
                item["error_type"] = error_type
                item["error_message"] = message
                item["error_detail"] = detail
        results.append(item)
    return results


def load_plotly_artifact(path: str) -> dict[str, Any]:
    return json_loads(require_existing_path(path).read_text(encoding="utf-8"), {})


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
