from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

import pandas as pd

from . import db
from .llm import chat_text, parse_single_row_csv
from .prompting import (
    build_ai_expansion_prompt,
    build_bilingual_components_prompt,
    build_bilingual_review_prompt,
    build_chinese_screening_prompt,
    build_prompt_components,
    build_screening_prompt,
    normalize_dimensions,
)
from .storage import save_export_dataframe, source_export_path, unlink_managed_file
from .utils import json_dumps, json_loads, utc_now_iso

ProgressCallback = Callable[[int, int], None]


def _fallback_name(prefix: str, item_id: int) -> str:
    return f"{prefix} #{item_id}"


def save_criteria_snapshot(
    project_id: int,
    user_id: int,
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str = "",
    key_points: str = "",
    inclusion_draft: str = "",
    exclusion_draft: str = "",
    dimensions: list[dict[str, Any]] | None = None,
    ai_expanded: dict[str, Any] | None = None,
    name: str = "",
) -> int:
    return db.execute(
        """
        INSERT INTO criteria_snapshots (
            project_id, user_id, name, review_topic, review_type, review_objective,
            target_literature_type, key_points, inclusion_draft, exclusion_draft,
            dimensions_json, ai_expanded_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            user_id,
            name.strip(),
            review_topic,
            review_type,
            review_objective,
            target_literature_type,
            key_points,
            inclusion_draft,
            exclusion_draft,
            json_dumps(normalize_dimensions(dimensions or [])),
            json_dumps(ai_expanded) if ai_expanded else None,
            utc_now_iso(),
        ),
    )


def _format_snapshot(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["name"] = item.get("name") or _fallback_name("Unnamed criteria", int(item["id"]))
    item["review_type"] = item.get("review_type") or ""
    item["review_objective"] = item.get("review_objective") or ""
    item["target_literature_type"] = item.get("target_literature_type") or ""
    item["dimensions"] = normalize_dimensions(json_loads(item.get("dimensions_json"), []))
    item["ai_expanded"] = _normalize_expanded_payload(json_loads(item.get("ai_expanded_json"), None))
    return item


def list_criteria_snapshots(project_id: int, user_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        "SELECT * FROM criteria_snapshots WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC",
        (project_id, user_id),
    )
    return [_format_snapshot(row) for row in rows]


def get_criteria_snapshot(project_id: int, user_id: int, snapshot_id: int) -> dict[str, Any] | None:
    row = db.fetch_one(
        "SELECT * FROM criteria_snapshots WHERE id = ? AND project_id = ? AND user_id = ?",
        (snapshot_id, project_id, user_id),
    )
    return _format_snapshot(row) if row else None


def delete_criteria_snapshot(project_id: int, user_id: int, snapshot_id: int) -> None:
    db.execute(
        "DELETE FROM criteria_snapshots WHERE id = ? AND project_id = ? AND user_id = ?",
        (snapshot_id, project_id, user_id),
    )



def _normalize_expanded_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if any(key in payload for key in ("review_topic", "inclusion_criteria", "dimensions")):
        return {
            "review_topic": str(payload.get("review_topic") or payload.get("REVIEW_TOPIC") or "").strip(),
            "review_type": str(payload.get("review_type") or "").strip(),
            "review_objective": str(payload.get("review_objective") or "").strip(),
            "target_literature_type": str(payload.get("target_literature_type") or "").strip(),
            "inclusion_criteria": str(payload.get("inclusion_criteria") or payload.get("INCLUSION_CRITERIA") or "").strip(),
            "exclusion_criteria": str(payload.get("exclusion_criteria") or payload.get("EXCLUSION_CRITERIA") or "").strip(),
            "dimensions": normalize_dimensions(payload.get("dimensions") if isinstance(payload.get("dimensions"), list) else []),
            "raw": payload.get("raw"),
        }
    if any(key in payload for key in ("REVIEW_TOPIC", "INCLUSION_CRITERIA", "DIMENSION_RULES")):
        return {
            "review_topic": str(payload.get("REVIEW_TOPIC") or "").strip(),
            "review_type": "",
            "review_objective": "",
            "target_literature_type": "",
            "inclusion_criteria": str(payload.get("INCLUSION_CRITERIA") or "").strip(),
            "exclusion_criteria": str(payload.get("EXCLUSION_CRITERIA") or "").strip(),
            "dimensions": parse_dimension_rules(str(payload.get("DIMENSION_RULES") or ""), []),
            "raw": payload.get("raw"),
        }
    return None


def expand_criteria_with_ai(
    user_id: int,
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str = "",
    inclusion_draft: str = "",
    exclusion_draft: str = "",
    dimensions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = chat_text(
        user_id,
        "You improve literature screening criteria into structured academic English and return JSON only.",
        build_ai_expansion_prompt(
            review_topic,
            review_type,
            review_objective,
            target_literature_type,
            inclusion_draft,
            exclusion_draft,
            dimensions or [],
        ),
        temperature=0.2,
    )
    parsed = _extract_json_object(raw)
    normalized = _normalize_expanded_payload({**parsed, "raw": raw}) if parsed else None
    if not normalized:
        raise ValueError("AI expansion did not return valid structured JSON.")
    fallback_dims = normalize_dimensions(dimensions or [])
    if not normalized.get("dimensions") and fallback_dims:
        normalized["dimensions"] = fallback_dims
    return normalized


def parse_dimension_rules(dimension_rules: str, fallback_dimensions: list[dict[str, Any]]) -> list[dict[str, str]]:
    fallback = normalize_dimensions(fallback_dimensions)
    parsed_by_id: dict[str, dict[str, str]] = {}
    for line in (dimension_rules or "").splitlines():
        stripped = line.strip().lstrip("-*").strip()
        match = re.match(r"^(D\d+)\s*[:=]\s*(.+)$", stripped, flags=re.IGNORECASE)
        if not match:
            continue
        dim_id = match.group(1).upper()
        body = match.group(2).strip()
        if " - " in body:
            field_name, definition = body.split(" - ", 1)
        elif ": " in body:
            field_name, definition = body.split(": ", 1)
        else:
            field_name, definition = body, ""
        parsed_by_id[dim_id] = {"id": dim_id, "field_name": field_name.strip(), "definition": definition.strip()}
    if not parsed_by_id:
        return fallback
    results = []
    for idx, fallback_item in enumerate(fallback or parsed_by_id.values(), start=1):
        item = parsed_by_id.get(fallback_item.get("id", f"D{idx}"), fallback_item)
        merged = {**fallback_item, **item, "id": f"D{idx}"}
        results.append(merged)
    return normalize_dimensions(results)


def _is_old_prompt_call(target_literature_type: Any, dimensions: Any) -> bool:
    return isinstance(target_literature_type, list) and dimensions is None


def assemble_prompt(
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str | list[dict[str, Any]] = "",
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    dimensions: list[dict[str, Any]] | None = None,
) -> str:
    if _is_old_prompt_call(target_literature_type, dimensions):
        return build_screening_prompt(review_topic, review_type, review_objective, target_literature_type)
    return build_screening_prompt(review_topic, review_type, review_objective, target_literature_type, inclusion_criteria, exclusion_criteria, dimensions or [])


def assemble_prompt_components(
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str | list[dict[str, Any]] = "",
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    dimensions: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    if _is_old_prompt_call(target_literature_type, dimensions):
        return build_prompt_components(review_topic, review_type, review_objective, target_literature_type)
    return build_prompt_components(review_topic, review_type, review_objective, target_literature_type, inclusion_criteria, exclusion_criteria, dimensions or [])


def save_prompt_version(project_id: int, user_id: int, prompt_text: str, bilingual_json: dict[str, str] | None = None, name: str = "") -> int:
    return db.execute(
        "INSERT INTO prompt_versions (project_id, user_id, name, prompt_text, bilingual_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, user_id, name.strip(), prompt_text, json_dumps(bilingual_json) if bilingual_json else None, utc_now_iso()),
    )


def _format_prompt_version(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["name"] = item.get("name") or _fallback_name("未命名 Prompt", int(item["id"]))
    item["bilingual"] = json_loads(item["bilingual_json"], None)
    return item


def list_prompt_versions(project_id: int, user_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        "SELECT * FROM prompt_versions WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC",
        (project_id, user_id),
    )
    return [_format_prompt_version(row) for row in rows]


def get_prompt_version(project_id: int, user_id: int, prompt_id: int) -> dict[str, Any] | None:
    row = db.fetch_one(
        "SELECT * FROM prompt_versions WHERE id = ? AND project_id = ? AND user_id = ?",
        (prompt_id, project_id, user_id),
    )
    return _format_prompt_version(row) if row else None


def delete_prompt_version(project_id: int, user_id: int, prompt_id: int) -> None:
    db.execute(
        "DELETE FROM prompt_versions WHERE id = ? AND project_id = ? AND user_id = ?",
        (prompt_id, project_id, user_id),
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
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


def create_bilingual_review(user_id: int, prompt_text: str, components: dict[str, object] | None = None) -> dict[str, Any]:
    if components:
        raw = chat_text(
            user_id,
            "You translate structured literature-screening fields accurately and return JSON only.",
            build_bilingual_components_prompt(components),
            temperature=0.1,
        )
        translated = _extract_json_object(raw)
        if translated:
            return {
                "english": prompt_text,
                "chinese": build_chinese_screening_prompt(components, translated),
                "mode": "structured",
                "components": components,
                "translated_components": translated,
            }

    raw = chat_text(user_id, "You are a precise bilingual reviewer.", build_bilingual_review_prompt(prompt_text), temperature=0.1)
    return {"english": prompt_text, "chinese": raw, "mode": "full"}


def _format_records_for_prompt(batch: list[dict[str, Any]]) -> str:
    blocks = []
    for item in batch:
        blocks.append("\n".join([f"Record ID: {item['record_id']}", f"Title: {item['title']}", f"Abstract: {item['abstract']}"]))
    return "\n\n---\n\n".join(blocks)


def _allowed_reason_codes(normalized_dims: list[dict[str, str]]) -> set[str]:
    codes = {"NA", "E_SCOPE", "M_SCOPE"}
    for dim in normalized_dims:
        codes.add(f"E_{dim['id']}")
        codes.add(f"M_{dim['id']}")
    return codes


def _fallback_reason_code(decision: str, normalized_dims: list[dict[str, str]]) -> str:
    if decision == "include":
        return "NA"
    if normalized_dims:
        return f"{'E' if decision == 'exclude' else 'M'}_{normalized_dims[0]['id']}"
    return "E_SCOPE" if decision == "exclude" else "M_SCOPE"


def _clean_reason_code(value: Any, decision: str, normalized_dims: list[dict[str, str]]) -> str:
    code = str(value or "").strip().upper().replace(" ", "")
    code = re.sub(r"^([EM])_?D(\d+)$", r"\1_D\2", code)
    if decision == "include":
        return "NA"
    if code in _allowed_reason_codes(normalized_dims):
        if decision == "exclude" and code.startswith("E_"):
            return code
        if decision == "maybe" and code.startswith("M_"):
            return code
    return _fallback_reason_code(decision, normalized_dims)


def _coerce_dimension_value(value: Any) -> str:
    cleaned = str(value or "unclear").strip().lower()
    return cleaned if cleaned in {"yes", "no", "unclear"} else "unclear"


def _coerce_output(output: dict[str, str], source: dict[str, Any], normalized_dims: list[dict[str, str]]) -> dict[str, Any]:
    decision = (output.get("decision") or "maybe").strip().lower()
    if decision not in {"include", "exclude", "maybe"}:
        decision = "maybe"
    confidence = (output.get("confidence") or "low").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    rationale = str(output.get("rationale") or "The main unresolved domain remains unclear from the title and abstract.").strip()
    rationale = " ".join(rationale.split())
    return {
        "row_index": source["row_index"],
        "record_id": output.get("record_id", source["record_id"]),
        "title": output.get("title", source["title"]),
        "decision": decision,
        "confidence": confidence,
        "primary_reason_code": _clean_reason_code(output.get("primary_reason_code"), decision, normalized_dims),
        "rationale": rationale,
        "dimensions": {dim["id"]: _coerce_dimension_value(output.get(dim["id"])) for dim in normalized_dims},
    }


def _screen_single_record(user_id: int, prompt_text: str, source: dict[str, Any], csv_headers: list[str], normalized_dims: list[dict[str, str]], temperature: float) -> dict[str, Any]:
    user_prompt = (
        f"{prompt_text}\n\nSCREEN THIS SINGLE RECORD ONLY.\n"
        f"Title: {source['title']}\nAbstract: {source['abstract']}\nRecord ID: {source['record_id']}\n"
        f"Return CSV with exactly one data row and these headers: {', '.join(csv_headers)}"
    )
    raw = chat_text(user_id, "Return valid CSV for one record only.", user_prompt, temperature=temperature)
    parsed = parse_single_row_csv(raw)
    if not parsed:
        raise RuntimeError(f"Model did not return parseable CSV for row {source['row_index'] + 1}.")
    return _coerce_output(parsed[0], source, normalized_dims)


def _screen_batch_records(user_id: int, prompt_text: str, batch: list[dict[str, Any]], csv_headers: list[str], normalized_dims: list[dict[str, str]], temperature: float) -> list[dict[str, Any]]:
    if len(batch) == 1:
        return [_screen_single_record(user_id, prompt_text, batch[0], csv_headers, normalized_dims, temperature)]
    user_prompt = (
        f"{prompt_text}\n\nSCREEN THE FOLLOWING {len(batch)} RECORDS.\n"
        "Return one valid CSV table only, with exactly one data row per record. Do not add commentary.\n"
        f"Use exactly these headers: {', '.join(csv_headers)}\n\n{_format_records_for_prompt(batch)}"
    )
    raw = chat_text(user_id, "Return valid CSV for all supplied records only.", user_prompt, temperature=temperature)
    parsed = parse_single_row_csv(raw)
    if len(parsed) < len(batch):
        return [_screen_single_record(user_id, prompt_text, source, csv_headers, normalized_dims, temperature) for source in batch]
    parsed_by_id = {str(item.get("record_id", "")).strip(): item for item in parsed if item.get("record_id")}
    results = []
    for index, source in enumerate(batch):
        output = parsed_by_id.get(source["record_id"], parsed[index] if index < len(parsed) else {})
        if not output:
            results.append(_screen_single_record(user_id, prompt_text, source, csv_headers, normalized_dims, temperature))
            continue
        results.append(_coerce_output(output, source, normalized_dims))
    return results


def run_screening(
    project_id: int,
    user_id: int,
    data_file_id: int,
    df: pd.DataFrame,
    prompt_text: str,
    dimensions: list[dict[str, str]],
    batch_size: int,
    rate_limit_per_min: int,
    temperature: float,
    prompt_version_id: int | None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    normalized_dims = normalize_dimensions(dimensions)
    config = {"batch_size": batch_size, "rate_limit_per_min": rate_limit_per_min, "temperature": temperature, "dimensions": normalized_dims}
    run_id = db.execute(
        """
        INSERT INTO screening_runs (project_id, user_id, data_file_id, prompt_version_id, config_json, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'running', ?, ?)
        """,
        (project_id, user_id, data_file_id, prompt_version_id, json_dumps(config), utc_now_iso(), utc_now_iso()),
    )
    results: list[dict[str, Any]] = []
    delay = 60 / rate_limit_per_min if rate_limit_per_min > 0 else 0
    csv_headers = ["record_id", "title", "decision", "confidence", *[dim["id"] for dim in normalized_dims], "primary_reason_code", "rationale"]

    try:
        records = [
            {"row_index": int(row_index), "record_id": str(row.get("Record-id", "") or ""), "title": str(row.get("Title", "") or ""), "abstract": str(row.get("Abstract", "") or "")}
            for row_index, row in df.iterrows()
        ]
        total = len(records)
        if progress_callback:
            progress_callback(0, total)
        effective_batch_size = max(1, min(int(batch_size or 1), total if total else 1))
        batches = [records[index : index + effective_batch_size] for index in range(0, total, effective_batch_size)]
        completed = 0
        for batch_index, batch in enumerate(batches):
            batch_results = _screen_batch_records(user_id, prompt_text, batch, csv_headers, normalized_dims, temperature)
            results.extend(batch_results)
            completed += len(batch)
            if progress_callback:
                progress_callback(completed, total)
            if delay > 0 and batch_index < len(batches) - 1:
                time.sleep(delay)
    except Exception:
        db.execute("UPDATE screening_runs SET status = 'failed', updated_at = ? WHERE id = ?", (utc_now_iso(), run_id))
        raise

    include_count = sum(1 for item in results if item["decision"] == "include")
    exclude_count = sum(1 for item in results if item["decision"] == "exclude")
    maybe_count = sum(1 for item in results if item["decision"] == "maybe")

    export_rows = []
    for item in results:
        export_rows.append({"record_id": item["record_id"], "title": item["title"], "decision": item["decision"], "confidence": item["confidence"], **item["dimensions"], "primary_reason_code": item["primary_reason_code"], "rationale": item["rationale"]})

    export_df = pd.DataFrame(export_rows)
    source_row = db.fetch_one("SELECT filename FROM data_files WHERE id = ? AND project_id = ? AND user_id = ?", (data_file_id, project_id, user_id))
    source_filename = source_row["filename"] if source_row else f"screening_{run_id}.csv"
    export_path = source_export_path(user_id, project_id, source_filename, "\u7b5b\u9009")
    save_export_dataframe(export_df, export_path)

    db.executemany(
        """
        INSERT INTO screening_results (screening_run_id, row_index, record_id, title, decision, confidence, primary_reason_code, rationale, dimensions_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(run_id, item["row_index"], item["record_id"], item["title"], item["decision"], item["confidence"], item["primary_reason_code"], item["rationale"], json_dumps(item["dimensions"])) for item in results],
    )
    db.execute(
        """
        UPDATE screening_runs
        SET status = 'completed', total_records = ?, include_count = ?, exclude_count = ?, maybe_count = ?, export_path = ?, updated_at = ?
        WHERE id = ?
        """,
        (len(results), include_count, exclude_count, maybe_count, str(export_path), utc_now_iso(), run_id),
    )
    return {"run_id": run_id, "results_df": export_df}


def get_existing_screening_runs_for_file(project_id: int, user_id: int, data_file_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        """
        SELECT * FROM screening_runs
        WHERE project_id = ? AND user_id = ? AND data_file_id = ?
        ORDER BY created_at DESC
        """,
        (project_id, user_id, data_file_id),
    )
    return [dict(row) for row in rows]


def delete_screening_run(project_id: int, user_id: int, run_id: int) -> None:
    row = db.fetch_one("SELECT * FROM screening_runs WHERE id = ? AND project_id = ? AND user_id = ?", (run_id, project_id, user_id))
    if not row:
        return
    export_path = row["export_path"]
    with db.connect() as conn:
        conn.execute("UPDATE topic_runs SET screening_run_id = NULL WHERE screening_run_id = ? AND project_id = ? AND user_id = ?", (run_id, project_id, user_id))
        conn.execute("DELETE FROM screening_runs WHERE id = ? AND project_id = ? AND user_id = ?", (run_id, project_id, user_id))
    unlink_managed_file(export_path)


def list_screening_runs(project_id: int, user_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetch_all("SELECT * FROM screening_runs WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))]


def get_screening_results(run_id: int) -> pd.DataFrame:
    rows = db.fetch_all("SELECT * FROM screening_results WHERE screening_run_id = ? ORDER BY row_index", (run_id,))
    formatted: list[dict[str, Any]] = []
    for row in rows:
        dimensions = json_loads(row["dimensions_json"], {})
        formatted.append({"record_id": row["record_id"], "title": row["title"], "decision": row["decision"], "confidence": row["confidence"], **dimensions, "primary_reason_code": row["primary_reason_code"], "rationale": row["rationale"]})
    return pd.DataFrame(formatted)
