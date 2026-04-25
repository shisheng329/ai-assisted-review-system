from __future__ import annotations

import json
import re
import time
from typing import Any

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
from .storage import project_exports_root, save_export_dataframe
from .utils import json_dumps, json_loads, short_uuid, utc_now_iso


def save_criteria_snapshot(
    project_id: int,
    user_id: int,
    review_topic: str,
    key_points: str,
    inclusion_draft: str,
    exclusion_draft: str,
    dimensions: list[dict[str, str]],
    ai_expanded: dict[str, Any] | None,
) -> int:
    return db.execute(
        """
        INSERT INTO criteria_snapshots (project_id, user_id, review_topic, key_points, inclusion_draft, exclusion_draft, dimensions_json, ai_expanded_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            user_id,
            review_topic,
            key_points,
            inclusion_draft,
            exclusion_draft,
            json_dumps(normalize_dimensions(dimensions)),
            json_dumps(ai_expanded) if ai_expanded else None,
            utc_now_iso(),
        ),
    )


def list_criteria_snapshots(project_id: int, user_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        "SELECT * FROM criteria_snapshots WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC",
        (project_id, user_id),
    )
    results = []
    for row in rows:
        item = dict(row)
        item["dimensions"] = json_loads(item["dimensions_json"], [])
        item["ai_expanded"] = json_loads(item["ai_expanded_json"], None)
        results.append(item)
    return results


def expand_criteria_with_ai(user_id: int, review_topic: str, key_points: str, inclusion_draft: str, exclusion_draft: str, dimensions: list[dict[str, str]]) -> dict[str, str]:
    raw = chat_text(
        user_id,
        "You improve literature screening criteria into clear academic English.",
        build_ai_expansion_prompt(review_topic, key_points, inclusion_draft, exclusion_draft, dimensions),
        temperature=0.2,
    )
    sections = {"raw": raw}
    current_key = None
    buffer: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped in {"REVIEW_TOPIC", "INCLUSION_CRITERIA", "EXCLUSION_CRITERIA", "DIMENSION_RULES"}:
            if current_key:
                sections[current_key] = "\n".join(buffer).strip()
            current_key = stripped
            buffer = []
            continue
        buffer.append(line)
    if current_key:
        sections[current_key] = "\n".join(buffer).strip()
    return sections


def parse_dimension_rules(dimension_rules: str, fallback_dimensions: list[dict[str, str]]) -> list[dict[str, str]]:
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
            name, description = body.split(" - ", 1)
        elif ": " in body:
            name, description = body.split(": ", 1)
        else:
            name, description = body, ""
        parsed_by_id[dim_id] = {"id": dim_id, "name": name.strip(), "description": description.strip()}
    if not parsed_by_id:
        return fallback
    results = []
    for fallback_item in fallback:
        item = parsed_by_id.get(fallback_item["id"], fallback_item)
        results.append({"id": fallback_item["id"], "name": item.get("name", ""), "description": item.get("description", "")})
    return results


def assemble_prompt(
    review_topic: str,
    inclusion_criteria: str,
    exclusion_criteria: str,
    dimensions: list[dict[str, str]],
) -> str:
    return build_screening_prompt(review_topic, inclusion_criteria, exclusion_criteria, dimensions)


def assemble_prompt_components(
    review_topic: str,
    inclusion_criteria: str,
    exclusion_criteria: str,
    dimensions: list[dict[str, str]],
) -> dict[str, object]:
    return build_prompt_components(review_topic, inclusion_criteria, exclusion_criteria, dimensions)


def save_prompt_version(project_id: int, user_id: int, prompt_text: str, bilingual_json: dict[str, str] | None = None) -> int:
    return db.execute(
        "INSERT INTO prompt_versions (project_id, user_id, prompt_text, bilingual_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (project_id, user_id, prompt_text, json_dumps(bilingual_json) if bilingual_json else None, utc_now_iso()),
    )


def list_prompt_versions(project_id: int, user_id: int) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        "SELECT * FROM prompt_versions WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC",
        (project_id, user_id),
    )
    results = []
    for row in rows:
        item = dict(row)
        item["bilingual"] = json_loads(item["bilingual_json"], None)
        results.append(item)
    return results


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

    raw = chat_text(
        user_id,
        "You are a precise bilingual reviewer.",
        build_bilingual_review_prompt(prompt_text),
        temperature=0.1,
    )
    return {"english": prompt_text, "chinese": raw, "mode": "full"}


def _format_records_for_prompt(batch: list[dict[str, Any]]) -> str:
    blocks = []
    for item in batch:
        blocks.append(
            "\n".join(
                [
                    f"Record ID: {item['record_id']}",
                    f"Title: {item['title']}",
                    f"Abstract: {item['abstract']}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def _coerce_output(
    output: dict[str, str],
    source: dict[str, Any],
    normalized_dims: list[dict[str, str]],
) -> dict[str, Any]:
    decision = (output.get("decision") or "maybe").strip().lower()
    if decision not in {"include", "exclude", "maybe"}:
        decision = "maybe"
    confidence = (output.get("confidence") or "low").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return {
        "row_index": source["row_index"],
        "record_id": output.get("record_id", source["record_id"]),
        "title": output.get("title", source["title"]),
        "decision": decision,
        "confidence": confidence,
        "primary_reason_code": output.get("primary_reason_code", "M2"),
        "rationale": output.get("rationale", "The main unresolved domain remains unclear from the title and abstract."),
        "dimensions": {dim["id"]: (output.get(dim["id"], "unclear") or "unclear").strip().lower() for dim in normalized_dims},
    }


def _screen_single_record(
    user_id: int,
    prompt_text: str,
    source: dict[str, Any],
    csv_headers: list[str],
    normalized_dims: list[dict[str, str]],
    temperature: float,
) -> dict[str, Any]:
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


def _screen_batch_records(
    user_id: int,
    prompt_text: str,
    batch: list[dict[str, Any]],
    csv_headers: list[str],
    normalized_dims: list[dict[str, str]],
    temperature: float,
) -> list[dict[str, Any]]:
    if len(batch) == 1:
        return [_screen_single_record(user_id, prompt_text, batch[0], csv_headers, normalized_dims, temperature)]
    user_prompt = (
        f"{prompt_text}\n\nSCREEN THE FOLLOWING {len(batch)} RECORDS.\n"
        "Return one valid CSV table only, with exactly one data row per record. Do not add commentary.\n"
        f"Use exactly these headers: {', '.join(csv_headers)}\n\n"
        f"{_format_records_for_prompt(batch)}"
    )
    raw = chat_text(user_id, "Return valid CSV for all supplied records only.", user_prompt, temperature=temperature)
    parsed = parse_single_row_csv(raw)
    if len(parsed) < len(batch):
        return [
            _screen_single_record(user_id, prompt_text, source, csv_headers, normalized_dims, temperature)
            for source in batch
        ]
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
) -> dict[str, Any]:
    normalized_dims = normalize_dimensions(dimensions)
    config = {
        "batch_size": batch_size,
        "rate_limit_per_min": rate_limit_per_min,
        "temperature": temperature,
        "dimensions": normalized_dims,
    }
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
            {
                "row_index": int(row_index),
                "record_id": str(row.get("Record-id", "") or ""),
                "title": str(row.get("Title", "") or ""),
                "abstract": str(row.get("Abstract", "") or ""),
            }
            for row_index, row in df.iterrows()
        ]
        effective_batch_size = max(1, min(int(batch_size or 1), len(records) if records else 1))
        batches = [records[index : index + effective_batch_size] for index in range(0, len(records), effective_batch_size)]
        for batch_index, batch in enumerate(batches):
            results.extend(_screen_batch_records(user_id, prompt_text, batch, csv_headers, normalized_dims, temperature))
            if delay > 0 and batch_index < len(batches) - 1:
                time.sleep(delay)
    except Exception:
        db.execute(
            "UPDATE screening_runs SET status = 'failed', updated_at = ? WHERE id = ?",
            (utc_now_iso(), run_id),
        )
        raise

    include_count = sum(1 for item in results if item["decision"] == "include")
    exclude_count = sum(1 for item in results if item["decision"] == "exclude")
    maybe_count = sum(1 for item in results if item["decision"] == "maybe")

    export_rows = []
    for item in results:
        row = {
            "record_id": item["record_id"],
            "title": item["title"],
            "decision": item["decision"],
            "confidence": item["confidence"],
            **item["dimensions"],
            "primary_reason_code": item["primary_reason_code"],
            "rationale": item["rationale"],
        }
        export_rows.append(row)

    export_df = pd.DataFrame(export_rows)
    export_path = project_exports_root(user_id, project_id) / f"screening_{short_uuid()}.csv"
    save_export_dataframe(export_df, export_path)

    db.executemany(
        """
        INSERT INTO screening_results (screening_run_id, row_index, record_id, title, decision, confidence, primary_reason_code, rationale, dimensions_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_id,
                item["row_index"],
                item["record_id"],
                item["title"],
                item["decision"],
                item["confidence"],
                item["primary_reason_code"],
                item["rationale"],
                json_dumps(item["dimensions"]),
            )
            for item in results
        ],
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


def list_screening_runs(project_id: int, user_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetch_all("SELECT * FROM screening_runs WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC", (project_id, user_id))]


def get_screening_results(run_id: int) -> pd.DataFrame:
    rows = db.fetch_all("SELECT * FROM screening_results WHERE screening_run_id = ? ORDER BY row_index", (run_id,))
    formatted: list[dict[str, Any]] = []
    for row in rows:
        dimensions = json_loads(row["dimensions_json"], {})
        item = {
            "record_id": row["record_id"],
            "title": row["title"],
            "decision": row["decision"],
            "confidence": row["confidence"],
            **dimensions,
            "primary_reason_code": row["primary_reason_code"],
            "rationale": row["rationale"],
        }
        formatted.append(item)
    return pd.DataFrame(formatted)
