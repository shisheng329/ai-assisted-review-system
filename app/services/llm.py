from __future__ import annotations

import csv
import io
import random
import re
import time
from typing import Any

import httpx

from . import db
from .provider_catalog import ProviderSpec, get_provider_spec


class LLMRequestError(RuntimeError):
    """Readable provider request failure."""


class LLMRateLimitError(LLMRequestError):
    """Provider rate limit failure."""


def get_active_api_config(user_id: int) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM api_configs WHERE user_id = ? AND is_active = 1 ORDER BY updated_at DESC LIMIT 1", (user_id,))
    return dict(row) if row else None


def save_api_config(
    user_id: int,
    provider_name: str,
    base_url: str,
    api_key: str,
    model_name: str,
    language_pref: str,
    activate: bool,
) -> int:
    with db.connect() as conn:
        if activate:
            conn.execute("UPDATE api_configs SET is_active = 0 WHERE user_id = ?", (user_id,))
        cursor = conn.execute(
            """
            INSERT INTO api_configs (user_id, provider_name, base_url, api_key, model_name, language_pref, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (user_id, provider_name, base_url.rstrip("/"), api_key, model_name, language_pref, 1 if activate else 0),
        )
        return int(cursor.lastrowid)


def list_api_configs(user_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetch_all("SELECT * FROM api_configs WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))]


def activate_api_config(user_id: int, config_id: int) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE api_configs SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.execute("UPDATE api_configs SET is_active = 1, updated_at = datetime('now') WHERE user_id = ? AND id = ?", (user_id, config_id))


def delete_api_config(user_id: int, config_id: int) -> None:
    with db.connect() as conn:
        target = conn.execute("SELECT id, is_active FROM api_configs WHERE user_id = ? AND id = ?", (user_id, config_id)).fetchone()
        if not target:
            return
        was_active = int(target["is_active"]) == 1
        conn.execute("DELETE FROM api_configs WHERE user_id = ? AND id = ?", (user_id, config_id))
        if not was_active:
            return
        replacement = conn.execute(
            "SELECT id FROM api_configs WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if replacement:
            conn.execute("UPDATE api_configs SET is_active = 1, updated_at = datetime('now') WHERE id = ?", (int(replacement["id"]),))


def resolve_provider(config: dict[str, Any]) -> ProviderSpec:
    spec = get_provider_spec(config.get("provider_name"), config.get("base_url"))
    if spec:
        return spec
    return ProviderSpec(
        key="custom_openai",
        provider_name=config.get("provider_name") or "Custom",
        transport="openai_compatible",
        base_url=config["base_url"],
        default_models=(config.get("model_name") or "custom-model",),
    )


def _merge_headers(spec: ProviderSpec, api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", **spec.extra_headers}
    if spec.headers_strategy == "anthropic_api_key":
        headers["x-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _resolve_endpoint(spec: ProviderSpec, base_url: str) -> str:
    base = base_url.rstrip("/")
    if spec.transport == "anthropic_compatible":
        if base.endswith("/v1/messages"):
            return base
        return f"{base}/v1/messages"
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _build_payload(spec: ProviderSpec, config: dict[str, Any], messages: list[dict[str, str]], temperature: float) -> dict[str, Any]:
    if spec.transport == "anthropic_compatible":
        system_text = "\n\n".join(message["content"] for message in messages if message["role"] == "system").strip()
        conversational_messages = [
            {"role": message["role"] if message["role"] in {"user", "assistant"} else "user", "content": message["content"]}
            for message in messages
            if message["role"] != "system"
        ]
        return {
            "model": config["model_name"],
            "system": system_text,
            "messages": conversational_messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }
    return {
        "model": config["model_name"],
        "messages": messages,
        "temperature": temperature,
    }


def _parse_response_text(spec: ProviderSpec, data: dict[str, Any]) -> str:
    if spec.transport == "anthropic_compatible":
        blocks = data.get("content", [])
        texts = [block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text"]
        if texts:
            return "\n".join(texts).strip()
        if isinstance(blocks, str):
            return blocks.strip()
        raise LLMRequestError("Anthropic-compatible response does not contain text content.")

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif "content" in item:
                    parts.append(str(item.get("content", "")))
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def _extract_provider_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text.strip()[:300] or response.reason_phrase
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            return str(payload["error"].get("message") or payload["error"].get("code") or response.reason_phrase)
        if payload.get("error"):
            return str(payload["error"])
        if payload.get("message"):
            return str(payload["message"])
    return response.reason_phrase


def _retry_delay_seconds(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 20.0)
            except ValueError:
                pass
    return min((2 ** attempt) + random.uniform(0.2, 0.8), 20.0)


def _raise_provider_error(spec: ProviderSpec, config: dict[str, Any], response: httpx.Response) -> None:
    provider = spec.provider_name
    model = config["model_name"]
    status = response.status_code
    detail = _extract_provider_error(response)
    base_message = f"{provider} / {model} request failed with HTTP {status}: {detail}"
    if status == 429:
        raise LLMRateLimitError(f"{base_message}. 请求过快或额度受限，请稍后重试或切换配置。")
    raise LLMRequestError(base_message)


def _chat_completion(config: dict[str, Any], messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    spec = resolve_provider(config)
    endpoint = _resolve_endpoint(spec, config["base_url"])
    payload = _build_payload(spec, config, messages, temperature)
    headers = _merge_headers(spec, config["api_key"])
    retryable_statuses = {408, 429, 500, 502, 503, 504}

    with httpx.Client(timeout=120) as client:
        for attempt in range(3):
            try:
                response = client.post(endpoint, headers=headers, json=payload)
                if response.status_code < 400:
                    return _parse_response_text(spec, response.json())
                if response.status_code in retryable_statuses and attempt < 2:
                    time.sleep(_retry_delay_seconds(response, attempt))
                    continue
                _raise_provider_error(spec, config, response)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < 2:
                    time.sleep(_retry_delay_seconds(None, attempt))
                    continue
                raise LLMRequestError(
                    f"{spec.provider_name} / {config['model_name']} request failed due to network error: {exc}"
                ) from exc
    raise LLMRequestError(f"{spec.provider_name} / {config['model_name']} request failed after retries.")


def chat_text(user_id: int, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    config = get_active_api_config(user_id)
    if not config:
        raise RuntimeError("No active API configuration.")
    return _chat_completion(
        config,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )


def test_active_api_config(user_id: int) -> str:
    config = get_active_api_config(user_id)
    if not config:
        raise RuntimeError("No active API configuration.")
    spec = resolve_provider(config)
    endpoint = _resolve_endpoint(spec, config["base_url"])
    response = _chat_completion(
        config,
        [
            {"role": "system", "content": "Return exactly OK."},
            {"role": "user", "content": "Connectivity test. Return exactly OK."},
        ],
        temperature=0.0,
    )
    return f"{spec.provider_name} / {config['model_name']} via {endpoint}: {response[:120]}"


def _clean_csv_text(raw_csv: str) -> str:
    text = (raw_csv or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:csv)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    lines = [line.strip("\ufeff") for line in text.splitlines() if line.strip() and not line.strip().startswith("```")]
    header_index = 0
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "record_id" in lowered and "decision" in lowered:
            header_index = index
            break
    return "\n".join(lines[header_index:])


def parse_single_row_csv(raw_csv: str) -> list[dict[str, str]]:
    cleaned_csv = _clean_csv_text(raw_csv)
    if not cleaned_csv:
        return []
    lines = [line for line in cleaned_csv.splitlines() if line.strip()]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    parsed: list[dict[str, str]] = []
    for row in reader:
        cleaned: dict[str, str] = {}
        for key, value in row.items():
            normalized_key = (key or "").strip()
            if not normalized_key:
                continue
            cleaned[normalized_key] = str(value or "").strip()
        if cleaned:
            parsed.append(cleaned)
    return parsed
