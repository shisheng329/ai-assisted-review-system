from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from .utils import ensure_dir


def db_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if configured:
        path = Path(configured)
    else:
        path = Path(__file__).resolve().parents[2] / "data" / "app.db"
    ensure_dir(path.parent)
    return path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


@contextmanager
def connect() -> Iterable[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                preferred_language TEXT NOT NULL DEFAULT 'zh-CN',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS api_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider_name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model_name TEXT NOT NULL,
                language_pref TEXT NOT NULL DEFAULT 'zh-CN',
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                active_data_file_id INTEGER,
                active_pdf_template_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS data_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0,
                abstract_count INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS criteria_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                review_topic TEXT NOT NULL,
                key_points TEXT NOT NULL,
                inclusion_draft TEXT NOT NULL,
                exclusion_draft TEXT NOT NULL,
                dimensions_json TEXT NOT NULL,
                ai_expanded_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS prompt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                prompt_text TEXT NOT NULL,
                bilingual_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS screening_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                data_file_id INTEGER NOT NULL,
                prompt_version_id INTEGER,
                config_json TEXT NOT NULL,
                status TEXT NOT NULL,
                total_records INTEGER NOT NULL DEFAULT 0,
                include_count INTEGER NOT NULL DEFAULT 0,
                exclude_count INTEGER NOT NULL DEFAULT 0,
                maybe_count INTEGER NOT NULL DEFAULT 0,
                export_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(data_file_id) REFERENCES data_files(id) ON DELETE CASCADE,
                FOREIGN KEY(prompt_version_id) REFERENCES prompt_versions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS screening_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screening_run_id INTEGER NOT NULL,
                row_index INTEGER NOT NULL,
                record_id TEXT NOT NULL,
                title TEXT NOT NULL,
                decision TEXT NOT NULL,
                confidence TEXT NOT NULL,
                primary_reason_code TEXT NOT NULL,
                rationale TEXT NOT NULL,
                dimensions_json TEXT NOT NULL,
                FOREIGN KEY(screening_run_id) REFERENCES screening_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS topic_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                data_file_id INTEGER,
                screening_run_id INTEGER,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                topic_info_json TEXT,
                artifacts_json TEXT,
                output_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(data_file_id) REFERENCES data_files(id) ON DELETE SET NULL,
                FOREIGN KEY(screening_run_id) REFERENCES screening_runs(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS topic_interpretations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_run_id INTEGER NOT NULL,
                chart_key TEXT NOT NULL,
                interpretation_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(topic_run_id, chart_key),
                FOREIGN KEY(topic_run_id) REFERENCES topic_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pdf_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                columns_json TEXT NOT NULL,
                preview_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pdf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pdf_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                template_id INTEGER NOT NULL,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                output_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(template_id) REFERENCES pdf_templates(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pdf_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_run_id INTEGER NOT NULL,
                row_index INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                extracted_json TEXT NOT NULL,
                error_message TEXT,
                FOREIGN KEY(pdf_run_id) REFERENCES pdf_runs(id) ON DELETE CASCADE
            );
            """
        )


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(query, params).fetchone()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with connect() as conn:
        cur = conn.execute(query, params)
        return int(cur.lastrowid)


def executemany(query: str, params: list[tuple[Any, ...]]) -> None:
    with connect() as conn:
        conn.executemany(query, params)
