
from __future__ import annotations

import pandas as pd

from app.services.prompting import (
    build_bilingual_components_prompt,
    build_chinese_screening_prompt,
    build_prompt_components,
    build_screening_prompt,
    normalize_dimensions,
)
from app.services.screening import _coerce_output
from app.services.storage import standardize_bibliographic_columns


def _dimensions() -> list[dict[str, str]]:
    return [
        {
            "field_name": "Population",
            "definition": "Studies about target populations.",
            "direct_positive_signals": "Names the target population.",
            "indirect_or_proxy_signals": "Mentions a proxy setting.",
            "yes_rule": "Title or abstract directly matches the target population.",
            "unclear_rule": "Population may match but is underspecified.",
            "no_rule": "Population is explicitly outside scope.",
            "do_not_exclude_cases": "Do not exclude when the setting is broad.",
            "fatal_mismatch_cases": "Animal-only or unrelated population.",
        },
        {
            "field_name": "Intervention",
            "definition": "Studies about the target intervention.",
            "direct_positive_signals": "Names the intervention.",
            "indirect_or_proxy_signals": "Mentions a related tool.",
            "yes_rule": "Intervention clearly appears.",
            "unclear_rule": "Intervention is plausible but not explicit.",
            "no_rule": "Intervention is explicitly absent.",
            "do_not_exclude_cases": "Do not exclude when only the method label is missing.",
            "fatal_mismatch_cases": "Clearly unrelated intervention.",
        },
    ]


def _prompt() -> str:
    return build_screening_prompt(
        "AI fairness in health",
        "scoping review",
        "Map how fairness-aware AI is used.",
        "primary empirical studies",
        "Include AI health fairness studies.",
        "Exclude non-health studies.",
        _dimensions(),
    )


def test_normalize_dimensions_maps_legacy_shape() -> None:
    dims = normalize_dimensions([{"name": "Legacy name", "description": "Legacy desc"}])
    assert dims[0]["id"] == "D1"
    assert dims[0]["field_name"] == "Legacy name"
    assert dims[0]["definition"] == "Legacy desc"
    assert dims[0]["name"] == "Legacy name"
    assert dims[0]["description"] == "Legacy desc"
    assert "fatal_mismatch_cases" in dims[0]


def test_structured_prompt_uses_dynamic_headers_and_clean_reason_codes() -> None:
    prompt = _prompt()
    assert "record_id,title,decision,confidence,D1,D2,primary_reason_code,rationale" in prompt
    assert "### MANDATORY SCREENING RULES" in prompt
    assert "### GENERAL DOMAIN CODING LOGIC" in prompt
    assert "### FINAL DECISION LOGIC" in prompt
    assert "### OUTPUT REQUIREMENTS" in prompt
    assert "### FINAL VALIDATION CHECK BEFORE OUTPUT" in prompt
    assert "Population" in prompt
    assert "Intervention" in prompt
    assert "{D" not in prompt
    assert "D5" not in prompt
    assert "E_D1" in prompt
    assert "M_D2" in prompt
    assert "E_D 1" not in prompt
    assert "M_D 2" not in prompt
    assert "Use only title and abstract" in prompt


def test_prompt_does_not_include_placeholders_or_tech_default_reason() -> None:
    prompt = _prompt()
    assert "Example:" not in prompt
    assert "scoping review / systematic review / mapping review / rapid review" not in prompt
    assert "primary empirical studies / intervention studies / qualitative studies / modelling studies" not in prompt
    assert "E_TECH" not in prompt
    assert "purely technical" not in prompt
    assert "benchmarking study" not in prompt


def test_bilingual_review_translates_only_dynamic_components() -> None:
    components = build_prompt_components(
        "AI fairness in health",
        "scoping review",
        "Map how fairness-aware AI is used.",
        "primary empirical studies",
        "Include AI health fairness studies.",
        "Exclude non-health studies.",
        _dimensions(),
    )
    translation_request = build_bilingual_components_prompt(components)
    assert "Translate only the user-filled JSON values" in translation_request
    assert "MANDATORY SCREENING RULES" not in translation_request
    assert "FINAL DECISION LOGIC" not in translation_request

    chinese = build_chinese_screening_prompt(
        components,
        {
            "review_topic": "医疗公平人工智能",
            "review_type": "范围综述",
            "review_objective": "梳理公平感知人工智能的使用方式。",
            "target_literature_type": "原始实证研究",
            "inclusion_criteria": "纳入医疗人工智能公平研究。",
            "exclusion_criteria": "排除非医疗研究。",
            "dimensions": [
                {
                    "id": "D1",
                    "field_name": "人群",
                    "definition": "关于目标人群的研究。",
                    "direct_positive_signals": "直接命名目标人群。",
                    "indirect_or_proxy_signals": "提到代理场景。",
                    "yes_rule": "题名或摘要直接匹配目标人群。",
                    "unclear_rule": "人群可能匹配但说明不足。",
                    "no_rule": "人群明确超出范围。",
                    "do_not_exclude_cases": "场景较宽泛时不要排除。",
                    "fatal_mismatch_cases": "仅动物或无关人群。",
                }
            ],
        },
    )
    assert "### 强制筛选规则" in chinese
    assert "医疗公平人工智能" in chinese
    assert "人群" in chinese
    assert "Intervention" in chinese  # Missing translated D2 falls back to source text.
    assert "record_id,title,decision,confidence,D1,D2,primary_reason_code,rationale" in chinese
    assert "MANDATORY SCREENING RULES" not in chinese
    assert "E_TECH" not in chinese
    assert "示例" not in chinese


def test_standardize_bibliographic_columns_accepts_aliases_and_generates_ids() -> None:
    df = pd.DataFrame({"title": ["A", "B"], "abstract": ["Alpha", "Beta"]})
    standardized = standardize_bibliographic_columns(df)
    assert list(standardized["Record-id"]) == ["row-1", "row-2"]
    assert list(standardized["Title"]) == ["A", "B"]
    assert list(standardized["Abstract"]) == ["Alpha", "Beta"]

    with_id = pd.DataFrame({"record_id": ["R1"], "Title": ["A"], "Abstract": ["Alpha"]})
    standardized_with_id = standardize_bibliographic_columns(with_id)
    assert list(standardized_with_id["Record-id"]) == ["R1"]


def test_coerce_output_enforces_allowed_values_and_reason_codes() -> None:
    source = {"row_index": 0, "record_id": "R1", "title": "Title", "abstract": "Abstract"}
    dims = normalize_dimensions(_dimensions())
    output = _coerce_output(
        {
            "record_id": "R1",
            "title": "Title",
            "decision": "uncertain",
            "confidence": "certain",
            "D1": "possibly",
            "D2": "YES",
            "primary_reason_code": "E_D 1",
            "rationale": "First sentence.\nSecond sentence.",
        },
        source,
        dims,
    )
    assert output["decision"] == "maybe"
    assert output["confidence"] == "low"
    assert output["dimensions"] == {"D1": "unclear", "D2": "yes"}
    assert output["primary_reason_code"] == "M_D1"
    assert "\n" not in output["rationale"]


def test_old_e_tech_reason_falls_back_to_current_exclusion_code() -> None:
    source = {"row_index": 0, "record_id": "R1", "title": "Title", "abstract": "Abstract"}
    dims = normalize_dimensions(_dimensions())
    output = _coerce_output(
        {
            "record_id": "R1",
            "title": "Title",
            "decision": "exclude",
            "confidence": "high",
            "D1": "no",
            "D2": "unclear",
            "primary_reason_code": "E_TECH",
            "rationale": "The population is explicitly outside scope.",
        },
        source,
        dims,
    )
    assert output["primary_reason_code"] == "E_D1"
