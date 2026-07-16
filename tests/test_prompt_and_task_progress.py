from __future__ import annotations

import importlib
import shutil
import sqlite3
import uuid
from pathlib import Path


def _make_workspace_tmp(label: str) -> Path:
    root = Path.cwd() / ".pytest_cache" / "literature_lab_tmp"
    root.mkdir(parents=True, exist_ok=True)
    tmp_root = root / f"{label}_{uuid.uuid4().hex[:12]}"
    tmp_root.mkdir(parents=True, exist_ok=False)
    return tmp_root


def _configure_temp_paths(monkeypatch, tmp_root: Path) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_root / "data" / "app.db"))
    monkeypatch.setenv("UPLOADS_PATH", str(tmp_root / "uploads"))
    monkeypatch.setenv("EXPORTS_PATH", str(tmp_root / "exports"))


def test_prompt_migration_active_switch_and_delete_fallback(monkeypatch) -> None:
    tmp_root = _make_workspace_tmp("prompt_versions")
    try:
        _configure_temp_paths(monkeypatch, tmp_root)
        database_path = tmp_root / "data" / "app.db"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as conn:
            conn.execute(
                """
                CREATE TABLE prompt_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    prompt_text TEXT NOT NULL,
                    bilingual_json TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO prompt_versions (project_id, user_id, prompt_text, created_at) VALUES (1, 1, 'old', '2026-01-01')"
            )
            conn.execute(
                "INSERT INTO prompt_versions (project_id, user_id, prompt_text, created_at) VALUES (1, 1, 'latest', '2026-01-02')"
            )

        db = importlib.import_module("app.services.db")
        screening = importlib.import_module("app.services.screening")
        db.init_db()

        active = screening.get_active_prompt_version(1, 1)
        assert active is not None
        assert active["prompt_text"] == "latest"

        first_id = screening.save_prompt_version(1, 1, "first saved", name="First")
        second_id = screening.save_prompt_version(1, 1, "second saved", name="Second")
        assert screening.get_active_prompt_version(1, 1)["id"] == second_id

        assert screening.set_active_prompt_version(1, 1, first_id) is True
        assert screening.get_active_prompt_version(1, 1)["id"] == first_id

        screening.delete_prompt_version(1, 1, first_id)
        assert screening.get_active_prompt_version(1, 1)["id"] == second_id
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_pdf_progress_continues_after_one_file_failure(monkeypatch) -> None:
    tmp_root = _make_workspace_tmp("pdf_progress")
    try:
        _configure_temp_paths(monkeypatch, tmp_root)
        db = importlib.import_module("app.services.db")
        auth = importlib.import_module("app.services.auth")
        projects = importlib.import_module("app.services.projects")
        pdf_service = importlib.import_module("app.services.pdf_service")
        db.init_db()

        user_id = auth.register_user("pdf-user", "pdf@example.com", "pass123456")
        project_id = projects.create_project(user_id, "PDF Project", "")
        template_id = db.execute(
            """
            INSERT INTO pdf_templates (
                project_id, user_id, filename, stored_path, columns_json, preview_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, user_id, "template.csv", str(tmp_root / "template.csv"), '["field"]', "[]", "2026-01-01"),
        )
        good_id = db.execute(
            "INSERT INTO pdf_files (project_id, user_id, filename, stored_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, user_id, "good.pdf", str(tmp_root / "good.pdf"), "2026-01-01"),
        )
        bad_id = db.execute(
            "INSERT INTO pdf_files (project_id, user_id, filename, stored_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, user_id, "bad.pdf", str(tmp_root / "bad.pdf"), "2026-01-02"),
        )

        def fake_extract(path: str) -> str:
            if path.endswith("bad.pdf"):
                raise RuntimeError("broken PDF")
            return "A valid research document."

        monkeypatch.setattr(pdf_service, "_extract_pdf_text", fake_extract)
        monkeypatch.setattr(pdf_service, "chat_text", lambda *args, **kwargs: '{"field": "value"}')
        events: list[tuple[int, int, str, str, str]] = []

        result = pdf_service.run_pdf_extraction(
            project_id,
            user_id,
            template_id,
            ["field"],
            [good_id, bad_id],
            progress_callback=lambda done, total, filename, stage, error: events.append(
                (done, total, filename, stage, error)
            ),
        )

        assert result["success_count"] == 1
        assert result["failed_count"] == 1
        assert {event[3] for event in events} >= {"preparing", "processing", "completed", "failed"}
        assert max(event[0] for event in events) == 2
        assert result["results_df"].shape[0] == 2
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_completed_topic_run_keeps_chart_diagnostics(monkeypatch) -> None:
    tmp_root = _make_workspace_tmp("topic_diagnostics")
    try:
        _configure_temp_paths(monkeypatch, tmp_root)
        db = importlib.import_module("app.services.db")
        auth = importlib.import_module("app.services.auth")
        projects = importlib.import_module("app.services.projects")
        bertopic_service = importlib.import_module("app.services.bertopic_service")
        db.init_db()

        user_id = auth.register_user("topic-user", "topic@example.com", "pass123456")
        project_id = projects.create_project(user_id, "Topic Project", "")
        detail = {
            "effective_topic_count": 1,
            "chart_diagnostics": {
                "topics": {
                    "generated": False,
                    "effective_topic_count": 1,
                    "error_type": "ValueError",
                    "error_message": "not enough topics",
                }
            },
        }
        db.execute(
            """
            INSERT INTO topic_runs (
                project_id, user_id, source_type, params_json, status,
                error_detail_json, created_at, updated_at
            ) VALUES (?, ?, 'upload', '{}', 'completed', ?, ?, ?)
            """,
            (project_id, user_id, bertopic_service.json_dumps(detail), "2026-01-01", "2026-01-01"),
        )

        run = bertopic_service.list_topic_runs(project_id, user_id)[0]
        assert run["status"] == "completed"
        assert run["error_detail"]["chart_diagnostics"]["topics"]["generated"] is False
        assert run["error_detail"]["effective_topic_count"] == 1
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
