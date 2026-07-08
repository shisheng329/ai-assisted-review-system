from __future__ import annotations

import importlib
import shutil
import uuid
from pathlib import Path

import pandas as pd


def _make_workspace_tmp() -> Path:
    root = Path.cwd() / ".pytest_cache" / "literature_lab_tmp"
    root.mkdir(parents=True, exist_ok=True)
    tmp_root = root / f"auth_storage_{uuid.uuid4().hex[:12]}"
    tmp_root.mkdir(parents=True, exist_ok=False)
    return tmp_root


def _configure_temp_paths(monkeypatch, tmp_root: Path) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_root / "data" / "app.db"))
    monkeypatch.setenv("UPLOADS_PATH", str(tmp_root / "uploads"))
    monkeypatch.setenv("EXPORTS_PATH", str(tmp_root / "exports"))


def test_auth_project_and_data_file_smoke(monkeypatch) -> None:
    tmp_root = _make_workspace_tmp()
    try:
        _configure_temp_paths(monkeypatch, tmp_root)

        db = importlib.import_module("app.services.db")
        auth = importlib.import_module("app.services.auth")
        projects = importlib.import_module("app.services.projects")
        storage = importlib.import_module("app.services.storage")

        db.init_db()
        user_id = auth.register_user("tester", "tester@example.com", "pass123456")
        user = auth.authenticate_user("tester@example.com", "pass123456")
        assert user is not None
        assert int(user["id"]) == user_id
        assert auth.authenticate_user("tester", "pass123456") is None

        project_id = projects.create_project(user_id, "Smoke Project", "Temporary test project")
        df = pd.DataFrame(
            {
                "Record-id": ["R1", "R2", "R3"],
                "Title": ["One", "Two", "Three"],
                "Abstract": ["Alpha", "Beta", "Gamma"],
            }
        )
        saved = storage.save_data_bytes(user_id, project_id, "records.csv", df.to_csv(index=False).encode("utf-8"))
        assert saved["row_count"] == 3

        active_file = storage.get_active_data_file(project_id, user_id)
        assert active_file is not None
        assert active_file["filename"] == "records.csv"

        file_record, loaded_df = storage.load_project_dataframe(project_id, user_id)
        assert file_record is not None
        assert loaded_df is not None
        assert list(loaded_df["Record-id"]) == ["R1", "R2", "R3"]
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
