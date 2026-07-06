from __future__ import annotations

import shutil
from typing import Any

from . import db
from .storage import project_exports_root, project_root
from .utils import utc_now_iso


def create_project(user_id: int, name: str, description: str) -> int:
    return db.execute(
        """
        INSERT INTO projects (user_id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, name.strip(), description.strip(), utc_now_iso(), utc_now_iso()),
    )


def update_project(user_id: int, project_id: int, name: str, description: str) -> None:
    db.execute(
        """
        UPDATE projects
        SET name = ?, description = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (name.strip(), description.strip(), utc_now_iso(), project_id, user_id),
    )


def delete_project(user_id: int, project_id: int) -> None:
    project = get_project(project_id, user_id)
    if not project:
        return
    upload_root = project_root(user_id, project_id)
    export_root = project_exports_root(user_id, project_id)
    db.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    shutil.rmtree(upload_root, ignore_errors=True)
    shutil.rmtree(export_root, ignore_errors=True)


def list_projects(user_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetch_all("SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC", (user_id,))]


def get_project(project_id: int, user_id: int) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    return dict(row) if row else None


def get_project_metrics(project_id: int, user_id: int) -> dict[str, Any]:
    project = get_project(project_id, user_id)
    if not project:
        return {"total_records": 0, "included_count": 0, "topic_count": 0, "pdf_result_count": 0, "recent_activity": ""}
    total_records = db.fetch_one(
        "SELECT COALESCE(SUM(row_count), 0) AS value FROM data_files WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    )["value"]
    included_count = db.fetch_one(
        "SELECT COALESCE(SUM(include_count), 0) AS value FROM screening_runs WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    )["value"]
    topic_count = db.fetch_one(
        "SELECT COUNT(*) AS value FROM topic_runs WHERE project_id = ? AND user_id = ? AND status = 'completed'",
        (project_id, user_id),
    )["value"]
    pdf_result_count = db.fetch_one(
        """
        SELECT COUNT(*) AS value
        FROM pdf_results
        JOIN pdf_runs ON pdf_runs.id = pdf_results.pdf_run_id
        WHERE pdf_runs.project_id = ? AND pdf_runs.user_id = ?
        """,
        (project_id, user_id),
    )["value"]
    recent_activity = project["updated_at"]
    return {
        "total_records": total_records,
        "included_count": included_count,
        "topic_count": topic_count,
        "pdf_result_count": pdf_result_count,
        "recent_activity": recent_activity,
    }