from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from . import db
from .utils import ensure_dir, exports_root, json_dumps, json_loads, safe_filename, short_uuid, uploads_root, utc_now_iso


REQUIRED_COLUMNS = ["Record-id", "Title", "Abstract"]


def project_root(user_id: int, project_id: int) -> Path:
    return ensure_dir(uploads_root() / f"user_{user_id}" / f"project_{project_id}")


def project_exports_root(user_id: int, project_id: int) -> Path:
    return ensure_dir(exports_root() / f"user_{user_id}" / f"project_{project_id}")


def save_uploaded_file(uploaded_file: Any, destination: Path) -> Path:
    ensure_dir(destination.parent)
    destination.write_bytes(uploaded_file.getbuffer())
    return destination


def read_dataframe(file_path: str | Path) -> pd.DataFrame:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)
    raise ValueError(f"Unsupported file type: {suffix}")


def read_dataframe_bytes(filename: str, file_bytes: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(BytesIO(file_bytes))
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(BytesIO(file_bytes))
    raise ValueError(f"Unsupported file type: {suffix}")


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    return [column for column in REQUIRED_COLUMNS if column not in df.columns]


def save_data_file(user_id: int, project_id: int, uploaded_file: Any) -> dict[str, Any]:
    filename = safe_filename(uploaded_file.name)
    suffix = Path(filename).suffix.lower()
    stored_path = project_root(user_id, project_id) / f"{short_uuid()}_{filename}"
    save_uploaded_file(uploaded_file, stored_path)
    df = read_dataframe(stored_path)
    missing = validate_dataframe(df)
    if missing:
        stored_path.unlink(missing_ok=True)
        raise ValueError(", ".join(missing))
    row_count = int(len(df))
    abstract_count = int(df["Abstract"].fillna("").astype(str).str.strip().ne("").sum())
    created_at = utc_now_iso()
    file_id = db.execute(
        """
        INSERT INTO data_files (project_id, user_id, filename, stored_path, file_type, row_count, abstract_count, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (project_id, user_id, filename, str(stored_path), suffix.lstrip("."), row_count, abstract_count, created_at),
    )
    if not db.fetch_one("SELECT active_data_file_id FROM projects WHERE id = ? AND active_data_file_id IS NOT NULL", (project_id,)):
        set_active_data_file(project_id, user_id, file_id)
    return {"file_id": file_id, "dataframe": df, "row_count": row_count, "abstract_count": abstract_count}


def save_data_bytes(user_id: int, project_id: int, filename: str, file_bytes: bytes) -> dict[str, Any]:
    safe_name = safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    stored_path = project_root(user_id, project_id) / f"{short_uuid()}_{safe_name}"
    ensure_dir(stored_path.parent)
    stored_path.write_bytes(file_bytes)
    df = read_dataframe(stored_path)
    missing = validate_dataframe(df)
    if missing:
        stored_path.unlink(missing_ok=True)
        raise ValueError(", ".join(missing))
    row_count = int(len(df))
    abstract_count = int(df["Abstract"].fillna("").astype(str).str.strip().ne("").sum())
    file_id = db.execute(
        """
        INSERT INTO data_files (project_id, user_id, filename, stored_path, file_type, row_count, abstract_count, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (project_id, user_id, safe_name, str(stored_path), suffix.lstrip("."), row_count, abstract_count, utc_now_iso()),
    )
    if not db.fetch_one("SELECT active_data_file_id FROM projects WHERE id = ? AND active_data_file_id IS NOT NULL", (project_id,)):
        set_active_data_file(project_id, user_id, file_id)
    return {"file_id": file_id, "dataframe": df, "row_count": row_count, "abstract_count": abstract_count}


def set_active_data_file(project_id: int, user_id: int, file_id: int) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE data_files SET is_active = 0 WHERE project_id = ? AND user_id = ?", (project_id, user_id))
        conn.execute("UPDATE data_files SET is_active = 1 WHERE id = ? AND user_id = ?", (file_id, user_id))
        conn.execute(
            "UPDATE projects SET active_data_file_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (file_id, utc_now_iso(), project_id, user_id),
        )


def get_project_files(project_id: int, user_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetch_all("SELECT * FROM data_files WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))]


def get_active_data_file(project_id: int, user_id: int) -> dict[str, Any] | None:
    row = db.fetch_one(
        """
        SELECT data_files.*
        FROM projects
        LEFT JOIN data_files ON data_files.id = projects.active_data_file_id
        WHERE projects.id = ? AND projects.user_id = ?
        """,
        (project_id, user_id),
    )
    return dict(row) if row and row["id"] else None


def load_project_dataframe(project_id: int, user_id: int, data_file_id: int | None = None) -> tuple[dict[str, Any] | None, pd.DataFrame | None]:
    if data_file_id:
        row = db.fetch_one("SELECT * FROM data_files WHERE id = ? AND user_id = ? AND project_id = ?", (data_file_id, user_id, project_id))
    else:
        row = db.fetch_one(
            """
            SELECT data_files.*
            FROM projects
            JOIN data_files ON data_files.id = projects.active_data_file_id
            WHERE projects.id = ? AND projects.user_id = ?
            """,
            (project_id, user_id),
        )
    if not row:
        return None, None
    record = dict(row)
    return record, read_dataframe(record["stored_path"])


def _managed_export_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    try:
        candidate = Path(path_value).resolve()
        candidate.relative_to(exports_root().resolve())
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _collect_data_file_artifact_paths(file_id: int) -> list[Path]:
    paths: dict[str, Path] = {}
    screening_rows = db.fetch_all("SELECT export_path FROM screening_runs WHERE data_file_id = ?", (file_id,))
    topic_rows = db.fetch_all("SELECT output_path, artifacts_json FROM topic_runs WHERE data_file_id = ?", (file_id,))

    for row in screening_rows:
        path = _managed_export_path(row["export_path"])
        if path:
            paths[str(path)] = path

    for row in topic_rows:
        output_path = _managed_export_path(row["output_path"])
        if output_path:
            paths[str(output_path)] = output_path
        artifacts = json_loads(row["artifacts_json"], {})
        if isinstance(artifacts, dict):
            for artifact_path in artifacts.values():
                if isinstance(artifact_path, str):
                    path = _managed_export_path(artifact_path)
                    if path:
                        paths[str(path)] = path

    return list(paths.values())


def delete_data_file(project_id: int, user_id: int, file_id: int) -> None:
    file_row = db.fetch_one("SELECT * FROM data_files WHERE id = ? AND project_id = ? AND user_id = ?", (file_id, project_id, user_id))
    if not file_row:
        return
    artifact_paths = _collect_data_file_artifact_paths(file_id)
    with db.connect() as conn:
        conn.execute("DELETE FROM screening_runs WHERE data_file_id = ?", (file_id,))
        conn.execute("DELETE FROM topic_runs WHERE data_file_id = ?", (file_id,))
        conn.execute("DELETE FROM data_files WHERE id = ?", (file_id,))
        active_row = conn.execute("SELECT active_data_file_id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if active_row and active_row["active_data_file_id"] == file_id:
            replacement = conn.execute(
                "SELECT id FROM data_files WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id, user_id),
            ).fetchone()
            conn.execute(
                "UPDATE projects SET active_data_file_id = ?, updated_at = ? WHERE id = ?",
                (replacement["id"] if replacement else None, utc_now_iso(), project_id),
            )
            if replacement:
                conn.execute("UPDATE data_files SET is_active = 1 WHERE id = ?", (replacement["id"],))
    for path in artifact_paths:
        path.unlink(missing_ok=True)
    Path(file_row["stored_path"]).unlink(missing_ok=True)


def save_export_dataframe(df: pd.DataFrame, path: Path) -> str:
    ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def save_json_artifact(payload: dict[str, Any], path: Path) -> str:
    ensure_dir(path.parent)
    path.write_text(json_dumps(payload), encoding="utf-8")
    return str(path)


def save_template_file(user_id: int, project_id: int, uploaded_file: Any) -> dict[str, Any]:
    filename = safe_filename(uploaded_file.name)
    stored_path = project_root(user_id, project_id) / f"{short_uuid()}_{filename}"
    save_uploaded_file(uploaded_file, stored_path)
    df = read_dataframe(stored_path)
    preview = df.head(5).fillna("").to_dict(orient="records")
    template_id = db.execute(
        """
        INSERT INTO pdf_templates (project_id, user_id, filename, stored_path, columns_json, preview_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, user_id, filename, str(stored_path), json_dumps(list(df.columns)), json_dumps(preview), utc_now_iso()),
    )
    db.execute(
        "UPDATE projects SET active_pdf_template_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (template_id, utc_now_iso(), project_id, user_id),
    )
    return {"template_id": template_id, "preview": preview, "columns": list(df.columns)}


def save_template_bytes(user_id: int, project_id: int, filename: str, file_bytes: bytes) -> dict[str, Any]:
    safe_name = safe_filename(filename)
    stored_path = project_root(user_id, project_id) / f"{short_uuid()}_{safe_name}"
    ensure_dir(stored_path.parent)
    stored_path.write_bytes(file_bytes)
    df = read_dataframe(stored_path)
    preview = df.head(5).fillna("").to_dict(orient="records")
    template_id = db.execute(
        """
        INSERT INTO pdf_templates (project_id, user_id, filename, stored_path, columns_json, preview_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, user_id, safe_name, str(stored_path), json_dumps(list(df.columns)), json_dumps(preview), utc_now_iso()),
    )
    db.execute(
        "UPDATE projects SET active_pdf_template_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (template_id, utc_now_iso(), project_id, user_id),
    )
    return {"template_id": template_id, "preview": preview, "columns": list(df.columns)}


def get_active_template(project_id: int, user_id: int) -> dict[str, Any] | None:
    row = db.fetch_one(
        """
        SELECT pdf_templates.*
        FROM projects
        LEFT JOIN pdf_templates ON pdf_templates.id = projects.active_pdf_template_id
        WHERE projects.id = ? AND projects.user_id = ?
        """,
        (project_id, user_id),
    )
    return dict(row) if row and row["id"] else None


def list_pdf_templates(project_id: int, user_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetch_all("SELECT * FROM pdf_templates WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))]


def set_active_template(project_id: int, user_id: int, template_id: int | None) -> None:
    db.execute(
        "UPDATE projects SET active_pdf_template_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (template_id, utc_now_iso(), project_id, user_id),
    )


def delete_pdf_template(project_id: int, user_id: int, template_id: int) -> None:
    row = db.fetch_one("SELECT * FROM pdf_templates WHERE id = ? AND project_id = ? AND user_id = ?", (template_id, project_id, user_id))
    if not row:
        return
    with db.connect() as conn:
        conn.execute("DELETE FROM pdf_templates WHERE id = ?", (template_id,))
        active_row = conn.execute("SELECT active_pdf_template_id FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id)).fetchone()
        if active_row and active_row["active_pdf_template_id"] == template_id:
            replacement = conn.execute(
                "SELECT id FROM pdf_templates WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id, user_id),
            ).fetchone()
            conn.execute(
                "UPDATE projects SET active_pdf_template_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (replacement["id"] if replacement else None, utc_now_iso(), project_id, user_id),
            )
    Path(row["stored_path"]).unlink(missing_ok=True)


def save_pdf_files(user_id: int, project_id: int, uploaded_files: list[Any]) -> list[int]:
    ids: list[int] = []
    for uploaded_file in uploaded_files:
        filename = safe_filename(uploaded_file.name)
        if Path(filename).suffix.lower() != ".pdf":
            raise ValueError(f"Unsupported PDF file type: {Path(filename).suffix.lower()}")
        stored_path = project_root(user_id, project_id) / f"{short_uuid()}_{filename}"
        save_uploaded_file(uploaded_file, stored_path)
        file_id = db.execute(
            "INSERT INTO pdf_files (project_id, user_id, filename, stored_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, user_id, filename, str(stored_path), utc_now_iso()),
        )
        ids.append(file_id)
    return ids


def get_project_pdf_files(project_id: int, user_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetch_all("SELECT * FROM pdf_files WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))]


def get_pdf_files_by_ids(project_id: int, user_id: int, file_ids: list[int]) -> list[dict[str, Any]]:
    if not file_ids:
        return []
    placeholders = ",".join("?" for _ in file_ids)
    params: tuple[Any, ...] = (project_id, user_id, *file_ids)
    query = f"SELECT * FROM pdf_files WHERE project_id = ? AND user_id = ? AND id IN ({placeholders}) ORDER BY created_at DESC"
    return [dict(row) for row in db.fetch_all(query, params)]


def delete_pdf_file(project_id: int, user_id: int, file_id: int) -> None:
    row = db.fetch_one("SELECT * FROM pdf_files WHERE id = ? AND project_id = ? AND user_id = ?", (file_id, project_id, user_id))
    if not row:
        return
    db.execute("DELETE FROM pdf_files WHERE id = ? AND project_id = ? AND user_id = ?", (file_id, project_id, user_id))
    Path(row["stored_path"]).unlink(missing_ok=True)
