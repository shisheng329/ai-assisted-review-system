from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

from . import db
from .llm import chat_text
from .storage import get_pdf_files_by_ids, project_exports_root, save_export_dataframe
from .utils import json_dumps, json_loads, short_uuid, utc_now_iso


def _extract_pdf_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    chunks = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()


def _detect_document_language(text: str) -> str:
    sample = text[:4000]
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", sample))
    alpha_count = len(re.findall(r"[A-Za-z]", sample))
    if cjk_count > alpha_count / 3:
        return "Chinese"
    return "English"


def _extract_json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _normalize_payload(payload: dict[str, Any], template_columns: list[str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for column in template_columns:
        value = payload.get(column, "")
        if isinstance(value, list):
            normalized[column] = "; ".join(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, dict):
            normalized[column] = json.dumps(value, ensure_ascii=False)
        else:
            normalized[column] = str(value or "").strip()
    return normalized


def run_pdf_extraction(project_id: int, user_id: int, template_id: int, template_columns: list[str], pdf_file_ids: list[int]) -> dict[str, Any]:
    pdf_files = get_pdf_files_by_ids(project_id, user_id, pdf_file_ids)
    if not pdf_files:
        raise RuntimeError("No PDF files selected for extraction.")
    run_id = db.execute(
        """
        INSERT INTO pdf_runs (project_id, user_id, template_id, params_json, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'running', ?, ?)
        """,
        (project_id, user_id, template_id, json_dumps({"columns": template_columns, "pdf_file_ids": pdf_file_ids}), utc_now_iso(), utc_now_iso()),
    )
    rows = []
    try:
        for index, pdf_file in enumerate(pdf_files):
            try:
                extracted_text = _extract_pdf_text(pdf_file["stored_path"])[:20000]
                language = _detect_document_language(extracted_text)
                user_prompt = f"""
                Extract structured values from the following PDF text according to these target fields:
                {", ".join(template_columns)}

                Return JSON only. Use exactly the same field names as listed above.
                Keep the extracted values in the same language as the PDF content. The detected document language is {language}.
                Use empty string when a field cannot be found.
                Do not translate values into another language.

                PDF text:
                {extracted_text}
                """.strip()
                raw = chat_text(
                    user_id,
                    "You extract structured values from research PDFs and return valid JSON only.",
                    user_prompt,
                    temperature=0.1,
                )
                payload = _normalize_payload(_extract_json_object(raw), template_columns)
                error_message = ""
            except Exception as exc:
                payload = {column: "" for column in template_columns}
                error_message = str(exc)
            row = {"file_name": pdf_file["filename"], **payload, "error_message": error_message}
            rows.append(row)
            db.execute(
                """
                INSERT INTO pdf_results (pdf_run_id, row_index, file_name, extracted_json, error_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, index, pdf_file["filename"], json_dumps(payload), error_message),
            )
        df = pd.DataFrame(rows)
        export_path = project_exports_root(user_id, project_id) / f"pdf_extract_{short_uuid()}.csv"
        save_export_dataframe(df, export_path)
        db.execute(
            "UPDATE pdf_runs SET status = 'completed', output_path = ?, updated_at = ? WHERE id = ?",
            (str(export_path), utc_now_iso(), run_id),
        )
        return {"run_id": run_id, "results_df": df}
    except Exception:
        db.execute(
            "UPDATE pdf_runs SET status = 'failed', updated_at = ? WHERE id = ?",
            (utc_now_iso(), run_id),
        )
        raise


def list_pdf_runs(project_id: int, user_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all("SELECT * FROM pdf_runs WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))
    results = []
    for row in rows:
        item = dict(row)
        item["params"] = json_loads(item["params_json"], {})
        results.append(item)
    return results


def get_pdf_results(run_id: int) -> pd.DataFrame:
    rows = db.fetch_all("SELECT * FROM pdf_results WHERE pdf_run_id = ? ORDER BY row_index", (run_id,))
    formatted: list[dict[str, Any]] = []
    for row in rows:
        payload = json_loads(row["extracted_json"], {})
        formatted.append({"file_name": row["file_name"], **payload, "error_message": row["error_message"] or ""})
    return pd.DataFrame(formatted)
