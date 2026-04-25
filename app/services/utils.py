from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    base = os.getenv("DATABASE_PATH", str(app_root() / "data" / "app.db"))
    db_path = Path(base)
    return db_path.parent


def uploads_root() -> Path:
    return app_root() / "uploads"


def exports_root() -> Path:
    return app_root() / "exports"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name.strip())
    return cleaned or f"file_{uuid.uuid4().hex[:8]}"


def to_json_compatible(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_compatible(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_compatible(item) for item in value]
    if isinstance(value, set):
        return [to_json_compatible(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return to_json_compatible(value.item())
        except Exception:
            pass
    if hasattr(value, "tolist") and callable(getattr(value, "tolist")):
        try:
            return to_json_compatible(value.tolist())
        except Exception:
            pass
    return value


def json_dumps(value: Any) -> str:
    return json.dumps(to_json_compatible(value), ensure_ascii=False)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def short_uuid() -> str:
    return uuid.uuid4().hex[:12]
