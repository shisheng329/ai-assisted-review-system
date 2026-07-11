
from __future__ import annotations

import json
from textwrap import dedent
from typing import Any


DIMENSION_FIELDS = [
    "field_name",
    "definition",
    "direct_positive_signals",
    "indirect_or_proxy_signals",
    "yes_rule",
    "unclear_rule",
    "no_rule",
    "do_not_exclude_cases",
    "fatal_mismatch_cases",
]


_FIELD_ALIASES = {
    "field_name": ("field_name", "name"),
    "definition": ("definition", "description"),
    "direct_positive_signals": ("direct_positive_signals",),
    "indirect_or_proxy_signals": ("indirect_or_proxy_signals",),
    "yes_rule": ("yes_rule",),
    "unclear_rule": ("unclear_rule",),
    "no_rule": ("no_rule",),
    "do_not_exclude_cases": ("do_not_exclude_cases",),
    "fatal_mismatch_cases": ("fatal_mismatch_cases",),
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def normalize_dimensions(dimensions: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for idx, dimension in enumerate(dimensions or [], start=1):
        item: dict[str, str] = {"id": f"D{idx}"}
        for field, aliases in _FIELD_ALIASES.items():
            value = ""
            for alias in aliases:
                if alias in dimension and _clean(dimension.get(alias)):
                    value = _clean(dimension.get(alias))
                    break
            item[field] = value
        item["name"] = item["field_name"]
        item["description"] = item["definition"]
        normalized.append(item)
    return normalized


def _coerce_prompt_args(
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str | list[dict[str, Any]] = "",
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    dimensions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Backward compatibility for the old positional form:
    # (review_topic, inclusion_criteria, exclusion_criteria, dimensions).
    if isinstance(target_literature_type, list) and dimensions is None:
        dimensions = target_literature_type
        inclusion_criteria = review_type
        exclusion_criteria = review_objective
        review_type = ""
        review_objective = ""
        target_literature_type = ""
    return {
        "review_topic": _clean(review_topic),
        "review_type": _clean(review_type),
        "review_objective": _clean(review_objective),
        "target_literature_type": _clean(target_literature_type),
        "inclusion_criteria": _clean(inclusion_criteria),
        "exclusion_criteria": _clean(exclusion_criteria),
        "dimensions": normalize_dimensions(dimensions),
    }


def build_prompt_components(
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str | list[dict[str, Any]] = "",
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    dimensions: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    return _coerce_prompt_args(
        review_topic,
        review_type,
        review_objective,
        target_literature_type,
        inclusion_criteria,
        exclusion_criteria,
        dimensions,
    )


def _csv_headers(dimensions: list[dict[str, str]]) -> list[str]:
    return [
        "record_id",
        "title",
        "decision",
        "confidence",
        *[item["id"] for item in dimensions],
        "primary_reason_code",
        "rationale",
    ]


def _dimension_names(dimensions: list[dict[str, str]], language: str = "en") -> str:
    if not dimensions:
        return "- no user-filled screening domains" if language == "en" else "- 未提供用户填写的筛选领域"
    fallback = "Unnamed domain" if language == "en" else "未命名领域"
    return "\n".join(f"- {item['id']}: {item['field_name'] or fallback}" for item in dimensions)


def _domain_lines(dimensions: list[dict[str, str]], language: str = "en") -> str:
    blocks = []
    if language == "zh":
        for item in dimensions:
            blocks.append(
                dedent(
                    f"""
                    #### {item['id']}: {item['field_name'] or '未命名领域'}
                    概念定义:
                    {item['definition']}
                    直接正向信号:
                    {item['direct_positive_signals']}
                    间接或代理信号:
                    {item['indirect_or_proxy_signals']}
                    编码为 "yes" 的条件:
                    {item['yes_rule']}
                    编码为 "unclear" 的条件:
                    {item['unclear_rule']}
                    编码为 "no" 的条件:
                    {item['no_rule']}
                    不要仅因为以下情况排除:
                    {item['do_not_exclude_cases']}
                    明确致命不匹配:
                    {item['fatal_mismatch_cases']}
                    """
                ).strip()
            )
        return "\n\n".join(blocks) if blocks else "未提供额外筛选领域。"

    for item in dimensions:
        blocks.append(
            dedent(
                f"""
                #### {item['id']}: {item['field_name'] or 'Unnamed domain'}
                Concept definition:
                {item['definition']}
                Direct positive signals:
                {item['direct_positive_signals']}
                Indirect or proxy signals:
                {item['indirect_or_proxy_signals']}
                Code as "yes" when:
                {item['yes_rule']}
                Code as "unclear" when:
                {item['unclear_rule']}
                Code as "no" when:
                {item['no_rule']}
                Do not exclude solely because:
                {item['do_not_exclude_cases']}
                Clear fatal mismatch:
                {item['fatal_mismatch_cases']}
                """
            ).strip()
        )
    return "\n\n".join(blocks) if blocks else "No additional screening domains were provided."


def _reason_code_lines(dimensions: list[dict[str, str]], language: str = "en") -> str:
    if language == "zh":
        lines = [
            "- NA = 没有排除或不确定原因，因为该记录被纳入",
            "- E_SCOPE = 明确超出综述主题范围",
        ]
        for item in dimensions:
            lines.append(f"- E_{item['id']} = 明确不符合 {item['field_name'] or item['id']}")
        lines.append("- M_MULTIPLE = 多个关键领域不明确")
        for item in dimensions:
            lines.append(f"- M_{item['id']} = 与 {item['field_name'] or item['id']} 的相关性不明确")
        return "\n".join(lines)

    lines = [
        "- NA = no exclusion or uncertainty reason because the record is included",
        "- E_SCOPE = clearly outside the thematic scope of the review",
    ]
    for item in dimensions:
        lines.append(f"- E_{item['id']} = clearly inconsistent with {item['field_name'] or item['id']}")
    lines.append("- M_MULTIPLE = multiple critical domains are unclear")
    for item in dimensions:
        lines.append(f"- M_{item['id']} = unclear relevance to {item['field_name'] or item['id']}")
    return "\n".join(lines)


def _allowed_values_lines(dimensions: list[dict[str, str]]) -> str:
    dim_lines = "\n".join(f"- {item['id']}: yes / no / unclear" for item in dimensions)
    reason_codes = ["NA", "E_SCOPE", "M_MULTIPLE"]
    for item in dimensions:
        reason_codes.append(f"E_{item['id']}")
    for item in dimensions:
        reason_codes.append(f"M_{item['id']}")
    return dedent(
        f"""
        - decision: include / exclude / maybe
        - confidence: high / medium / low
        {dim_lines}
        - primary_reason_code: {' / '.join(reason_codes)}
        """
    ).strip()


def _merge_translated_dimensions(
    source_dimensions: list[dict[str, Any]], translated_dimensions: Any
) -> list[dict[str, str]]:
    source = normalize_dimensions(source_dimensions)
    translated = normalize_dimensions(translated_dimensions if isinstance(translated_dimensions, list) else [])
    translated_by_id = {item["id"]: item for item in translated}
    merged: list[dict[str, str]] = []
    for source_item in source:
        translated_item = translated_by_id.get(source_item["id"], {})
        merged_item = {"id": source_item["id"]}
        for field in DIMENSION_FIELDS:
            merged_item[field] = _clean(translated_item.get(field)) or source_item[field]
        merged_item["name"] = merged_item["field_name"]
        merged_item["description"] = merged_item["definition"]
        merged.append(merged_item)
    return merged


def build_screening_prompt(
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str | list[dict[str, Any]] = "",
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    dimensions: list[dict[str, Any]] | None = None,
) -> str:
    components = build_prompt_components(
        review_topic,
        review_type,
        review_objective,
        target_literature_type,
        inclusion_criteria,
        exclusion_criteria,
        dimensions,
    )
    dims = components["dimensions"]
    headers = _csv_headers(dims)
    domain_names = _dimension_names(dims)
    domain_no_checks = "\n".join(f"- {item['id']} = no" for item in dims) or "- any critical domain = no"

    prompt = f"""
    You are a researcher conducting rigorous title-and-abstract screening for a literature review.
    Your task is to screen every record in the uploaded CSV file, one row at a time, and return a structured screening decision for each record.
    You must screen every row. Do not skip any record.
    Use only the Title and Abstract to make screening decisions.
    Assume the uploaded CSV contains at least the following fields:
    - record_id
    - title
    - abstract
    If column names differ but clearly correspond to record ID, title, and abstract, use the corresponding fields.
    Do not use journal name, authors, affiliation, year, publication type labels, database source, citation count, keywords, or any metadata outside the title and abstract unless explicitly permitted by the user.

    ### MANDATORY SCREENING RULES
    1. This is a recall-oriented title-and-abstract pre-screening task for identifying studies that may be relevant to a literature review.
    2. Use only title and abstract to make screening decisions. Do not use journal name, authors, affiliation, year, publication type labels, database source, citation count, keywords, or other metadata unless explicitly allowed.
    3. The goal is to avoid falsely excluding potentially relevant studies. Both "include" and "maybe" mean the record should be retained for further review.
    4. Use "exclude" only when the title and/or abstract provide explicit evidence of a fatal mismatch with at least one critical screening domain.
    5. Do not exclude a record merely because a criterion is not fully stated. Absence of evidence is not evidence of absence.
    6. Do not rely only on exact keywords. Judge conceptual relevance, methodological relevance, population relevance, setting relevance, spatial relevance, and issue relevance in relation to the review topic.
    7. Evaluate each screening domain independently before assigning the final decision.
    8. If the title or abstract suggests possible relevance but does not explicitly confirm it, code the relevant domain as "unclear", not "no".
    9. If the abstract is missing, empty, sparse, or vague, screen conservatively using the title only and use "maybe" when the exclusion reason is not explicit.
    10. A single positive signal in one domain cannot override an explicit fatal mismatch in another critical domain.
    11. A single unclear domain is not, by itself, a reason for exclusion.
    12. Use "maybe" when a record appears potentially relevant but one or more critical domains remain unresolved from title/abstract alone.
    13. Use "include" only when the core criteria are clearly or mostly satisfied, no critical domain shows a fatal mismatch, and title/abstract provide enough evidence for likely relevance.
    14. Title-and-abstract screening is not final eligibility determination. When a decision would require information that can only be confirmed in the full text, choose "maybe".
    15. When uncertain between "exclude" and "maybe", choose "maybe".
    16. When uncertain between "maybe" and "include", choose "maybe" unless relevance is strong.
    17. Do not apply exclusion criteria based on missing, incomplete, indirect, implicit, or ambiguous information.

    ### USER-FILLED REVIEW CONFIGURATION
    #### REVIEW TOPIC
    {components['review_topic']}
    #### REVIEW TYPE
    {components['review_type']}
    #### REVIEW OBJECTIVE
    {components['review_objective']}
    #### TARGET LITERATURE TYPE
    {components['target_literature_type']}

    ### INCLUSION CRITERIA
    {components['inclusion_criteria']}

    ### EXCLUSION CRITERIA
    The following exclusion criteria should be applied only when title and/or abstract provide explicit fatal mismatch evidence.
    Do not apply exclusion criteria based on missing, incomplete, indirect, or ambiguous information.
    {components['exclusion_criteria']}

    ### USER-FILLED SCREENING DOMAINS AND CONCEPT DEFINITIONS
    Define each screening domain used in this review.
    Each domain should represent one core eligibility concept.
    For each domain, use the concept definition and title/abstract coding rules below.
    Each domain must be coded independently as:
    - yes
    - no
    - unclear
    Use "no" only when title and/or abstract explicitly show that the domain is not satisfied.
    Use "unclear" when the domain may be satisfied but title/abstract do not provide enough information for a confident "yes".
    Do not use "no" because information is missing.

    {_domain_lines(dims)}

    ### GENERAL DOMAIN CODING LOGIC
    For each screening domain, assign one of the following labels:
    - yes = the title/abstract provides clear or strong evidence that the domain is satisfied.
    - unclear = the title/abstract suggests possible relevance, but evidence is incomplete, indirect, implicit, or insufficient for a confident "yes".
    - no = the title/abstract provides explicit evidence that the domain is not satisfied.
    Important:
    Use "no" only for explicit fatal mismatch.
    Do not use "no" because information is missing.
    If a domain is not mentioned but could still be satisfied, code it as "unclear".
    If no domain is clearly coded as "no" and at least one domain is coded "unclear", the final decision must be "maybe", not "exclude".
    Exclusion requires at least one domain to be clearly coded as "no" based on title/abstract evidence.

    ### FINAL DECISION LOGIC
    Apply the decision logic in this order.
    #### Step 1. Code all screening domains independently
    Independently code the following domains as yes, no, or unclear:
    {domain_names}
    Do not assign a final include/maybe/exclude decision before coding all domains.

    #### Step 2. Check for explicit fatal mismatch
    Assign "exclude" only if the title or abstract explicitly shows one of the following:
    {domain_no_checks}
    - the paper is clearly outside the thematic scope of the review
    Do not assign "exclude" merely because evidence is absent, incomplete, indirect, implicit, or not fully specific.

    #### Step 3. Check for unresolved but plausible relevance
    Assign "maybe" when:
    - no explicit fatal mismatch is present;
    - one or more critical domains remain unclear from the title/abstract alone;
    - the record is otherwise plausibly relevant to the review topic.
    Use "maybe" especially when:
    - the abstract is missing, sparse, or vague;
    - study type cannot be confidently determined from the title/abstract;
    - a domain appears conceptually relevant but is not explicitly stated;
    - the study may satisfy one or more screening domains but confirmation likely requires full-text screening.
    Do not use "maybe" when the title or abstract clearly provides sufficient evidence for inclusion or exclusion.

    #### Step 4. Assign "include"
    Assign "include" only when:
    - all or most critical domains are coded as "yes";
    - no critical domain is coded as "no";
    - the title/abstract provides enough information to justify likely relevance;
    - there is no explicit fatal mismatch.

    #### Step 5. Resolve uncertainty conservatively
    When uncertain between "exclude" and "maybe", choose "maybe".
    When uncertain between "maybe" and "include", choose "maybe" unless the relevance is strong.

    ### PRIMARY REASON CODE RULE
    Use the following primary reason codes:
    {_reason_code_lines(dims)}
    Coding rule for primary_reason_code:
    - If decision = include, use NA.
    - If decision = maybe, use the most important unresolved domain code.
    - If decision = maybe and more than one critical domain is unclear, use M_MULTIPLE only when no single unresolved domain is clearly most important.
    - If decision = exclude, choose the single most important explicit exclusion reason.
    - For exclude decisions, the primary reason must be based on explicit evidence from the title/abstract, not on missing information.

    ### CONFIDENCE GUIDANCE
    Use:
    - high = title/abstract gives clear evidence for the decision with little or no ambiguity.
    - medium = decision is reasonably supported but one critical aspect remains somewhat ambiguous.
    - low = decision depends on sparse, incomplete, indirect, or weak title/abstract information.

    ### OUTPUT REQUIREMENTS
    Return the results as CSV only.
    Do not add any commentary before or after the CSV.
    Do not wrap the CSV in markdown code fences.
    Do not return a markdown table.
    Use exactly this column order:
    {','.join(headers)}

    ### Allowed values:
    {_allowed_values_lines(dims)}
    CSV formatting rules:
    - Return a valid CSV.
    - Quote fields when needed.
    - Keep the title unchanged.
    - Do not add line breaks inside any field.
    - Do not leave required fields blank unless the corresponding input value is genuinely missing.
    - The rationale must be one concise sentence.

    ### FIELD RULES
    - record_id must be copied exactly from the input record.
    - title must be copied exactly from the input record.
    - decision must use only one of the allowed values.
    - confidence must use only one of the allowed values.
    - All D columns must each use only yes, no, or unclear.
    - primary_reason_code must follow the PRIMARY REASON CODE RULE.
    - rationale must be one concise sentence.
    - Do not leave any required field blank unless the corresponding input value is genuinely missing.

    ### RATIONALE RULE
    The rationale must:
    - be one concise sentence;
    - state the strongest inclusion signal or the key exclusion/uncertainty reason;
    - rely only on title and abstract;
    - not mention metadata outside title/abstract;
    - not mention the screening prompt or codebook;
    - not use multiple sentences;
    - explicitly name the main unresolved domain when decision = maybe;
    - explicitly name the fatal mismatch when decision = exclude.

    ### FINAL VALIDATION CHECK BEFORE OUTPUT
    Before producing the final CSV, ensure that:
    1. every row has been screened;
    2. no row is skipped;
    3. all output values follow the allowed labels exactly;
    4. the title is kept unchanged;
    5. the output is valid CSV;
    6. the output is not a markdown table;
    7. the output is not wrapped in code fences;
    8. "exclude" is used only when there is explicit evidence of a fatal mismatch in the title/abstract;
    9. records with plausible relevance but unresolved information are labelled "maybe", not "exclude";
    10. missing, incomplete, indirect, or ambiguous information is never used as the sole basis for exclusion.
    """.strip()
    return dedent(prompt)


def build_ai_expansion_prompt(
    review_topic: str,
    review_type: str = "",
    review_objective: str = "",
    target_literature_type: str | list[dict[str, Any]] = "",
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    dimensions: list[dict[str, Any]] | None = None,
) -> str:
    components = build_prompt_components(
        review_topic,
        review_type,
        review_objective,
        target_literature_type,
        inclusion_criteria,
        exclusion_criteria,
        dimensions,
    )
    return dedent(
        f"""
        Expand the following draft into a structured title-and-abstract screening standard for a rigorous, recall-oriented review.
        Translate user-provided content into academic English where needed.
        Return valid JSON only. Do not add markdown fences or commentary.

        Required JSON shape:
        {{
          "review_topic": "...",
          "review_type": "...",
          "review_objective": "...",
          "target_literature_type": "...",
          "inclusion_criteria": "...",
          "exclusion_criteria": "...",
          "dimensions": [
            {{
              "id": "D1",
              "field_name": "...",
              "definition": "...",
              "direct_positive_signals": "...",
              "indirect_or_proxy_signals": "...",
              "yes_rule": "...",
              "unclear_rule": "...",
              "no_rule": "...",
              "do_not_exclude_cases": "...",
              "fatal_mismatch_cases": "..."
            }}
          ]
        }}

        Preserve the number and order of dimensions. Use D1..Dn ids. Keep the screening principle conservative: include/maybe unless Title/Abstract explicitly shows a fatal mismatch.

        Source JSON:
        {json.dumps(components, ensure_ascii=False)}
        """
    ).strip()


def build_bilingual_review_prompt(prompt_text: str) -> str:
    return dedent(
        f"""
        Translate the following screening prompt into Chinese while preserving the original structure and all section headings.
        Return the Chinese translation only. Do not repeat the English source text. Do not add commentary.

        Prompt:
        {prompt_text}
        """
    ).strip()


def build_bilingual_components_prompt(components: dict[str, object]) -> str:
    return dedent(
        f"""
        Translate only the user-filled JSON values below into Chinese for a literature-screening prompt.
        Do not translate or rewrite fixed screening rules, output rules, decision logic, or any prompt template text.
        Return valid JSON only, with exactly these top-level keys:
        review_topic, review_type, review_objective, target_literature_type, inclusion_criteria, exclusion_criteria, dimensions.
        dimensions must keep id unchanged and translate values for: {', '.join(DIMENSION_FIELDS)}.
        Do not translate keys. Do not add markdown fences or commentary.

        Source JSON:
        {json.dumps(components, ensure_ascii=False)}
        """
    ).strip()


def build_chinese_screening_prompt(components: dict[str, object], translated: dict[str, object]) -> str:
    source_dims = components.get("dimensions", []) if isinstance(components, dict) else []
    translated_dims = translated.get("dimensions") if isinstance(translated, dict) else None
    dims = _merge_translated_dimensions(source_dims if isinstance(source_dims, list) else [], translated_dims)
    headers = _csv_headers(dims)
    domain_names = _dimension_names(dims, language="zh")
    domain_no_checks = "\n".join(f"- {item['id']} = no" for item in dims) or "- 某个关键领域 = no"

    def value(key: str) -> str:
        if isinstance(translated, dict) and translated.get(key):
            return _clean(translated.get(key))
        return _clean(components.get(key))

    prompt = f"""
    你是一名研究者，正在进行严格的题名和摘要筛选，以识别可能与文献综述相关的研究。
    你的任务是逐行筛选上传 CSV 文件中的每条题录，并为每条记录返回一个结构化筛选决定。
    必须筛选每一行，不得跳过任何记录。
    只能使用题名和摘要做出筛选决定。
    假定上传的 CSV 至少包含以下列：
    - record_id
    - title
    - abstract
    如果列名略有不同，但 clearly correspond to record ID, title, and abstract，请使用对应列。
    除非用户明确允许，否则不要使用期刊名、作者、机构、发表年份、文献类型标签、数据库来源、引用次数、关键词或题名和摘要以外的任何元数据。

    ### 强制筛选规则
    1. 这是一个以召回为导向的题名和摘要预筛选任务，用于识别可能与文献综述相关的研究。
    2. 只能使用题名和摘要进行筛选决定。除非明确允许，不要使用期刊名、作者、机构、发表年份、文献类型标签、数据库来源、引用次数、关键词或其他元数据。
    3. 目标是避免错误排除潜在相关研究。"include" 和 "maybe" 都表示该记录应保留进入后续审查。
    4. 只有当题名和/或摘要提供了与至少一个关键筛选领域存在致命不匹配的明确证据时，才使用 "exclude"。
    5. 不要仅因为某项标准没有被完整说明而排除。缺少证据并不等于不存在。
    6. 不要只依赖精确关键词。应根据综述主题判断概念相关性、方法相关性、人群相关性、场景相关性、空间相关性和问题相关性。
    7. 在做出最终决定之前，必须独立评估每个筛选领域。
    8. 如果题名或摘要暗示可能相关但没有明确说明，应将相关领域编码为 "unclear"，而不是 "no"。
    9. 如果摘要缺失、为空、信息稀少或含糊，应仅基于题名保守筛选；当排除理由不明确时使用 "maybe"。
    10. 一个领域中的单个正向信号不能覆盖另一个关键领域中的明确致命不匹配。
    11. 单个不明确领域本身不构成排除理由。
    12. 当记录看起来可能相关，但一个或多个关键领域仅凭题名/摘要仍未解决时，使用 "maybe"。
    13. 只有当核心标准明确或基本满足、没有关键领域显示致命不匹配，且题名/摘要提供了足够证据支持可能相关时，才使用 "include"。
    14. 题名和摘要筛选不是最终纳排判断。当决定需要全文中才可能获得的信息时，选择 "maybe"。
    15. 当在 "exclude" 和 "maybe" 之间不确定时，选择 "maybe"。
    16. 当在 "maybe" 和 "include" 之间不确定时，选择 "maybe"，除非相关性很强。
    17. 不要基于缺失、不完整、间接、隐含或模糊的信息应用排除标准。

    ### 用户填写的综述配置
    #### 综述主题
    {value('review_topic')}
    #### 综述类型
    {value('review_type')}
    #### 综述目标
    {value('review_objective')}
    #### 目标文献类型
    {value('target_literature_type')}

    ### 纳入标准
    {value('inclusion_criteria')}

    ### 排除标准
    以下排除标准只有在题名和/或摘要提供明确致命不匹配证据时才应适用。
    不要基于缺失、不完整、间接或模糊的信息应用排除标准。
    {value('exclusion_criteria')}

    ### 用户填写的筛选领域和概念定义
    定义本综述使用的每个筛选领域。
    每个领域应代表一个核心资格概念。
    对每个领域，使用下面的概念定义以及题名和摘要编码规则。
    必须将每个领域独立编码为：
    - yes
    - no
    - unclear
    只有当题名和/或摘要明确显示该领域不满足时，才使用 "no"。
    当该领域可能满足，但题名/摘要没有提供足够信息支持 confident "yes" 时，使用 "unclear"。
    不要因为信息缺失而使用 "no"。

    {_domain_lines(dims, language='zh')}

    ### 一般领域编码逻辑
    对每个筛选领域，分配以下标签之一：
    - yes = 题名/摘要提供了清楚或强有力的证据，说明该领域满足。
    - unclear = 题名/摘要提示可能相关，但证据不完整、间接、隐含或不足以做出 confident "yes"。
    - no = 题名/摘要提供了明确证据，说明该领域不满足。
    重要：
    仅将 "no" 用于明确致命不匹配。
    不要因信息缺失而使用 "no"。
    当某个领域未被提及但仍可能满足时，将其编码为 "unclear"。
    如果没有领域被明确编码为 "no"，且至少一个领域被编码为 "unclear"，最终决定必须是 "maybe"，不是 "exclude"。
    只有当至少一个领域基于题名/摘要证据被明确编码为 "no" 时，才排除。

    ### 最终决策逻辑
    按以下顺序应用决策逻辑。
    #### 第 1 步：独立编码所有筛选领域
    将以下领域独立编码为 yes、no 或 unclear：
    {domain_names}
    在编码所有领域之前，不要做出最终 include/maybe/exclude 决定。

    #### 第 2 步：只检查明确致命不匹配
    只有当题名或摘要明确显示以下情况之一时，才赋值 "exclude"：
    {domain_no_checks}
    - 论文明确超出综述主题范围
    不要仅因为证据缺失、不完整、间接、隐含或不够具体而赋值 "exclude"。

    #### 第 3 步：检查未解决但可能相关的情况
    当以下情况出现时赋值 "maybe"：
    - 没有明确致命不匹配；
    - 一个或多个关键领域仅凭题名/摘要仍不明确；
    - 记录在其他方面与综述主题可能相关。
    尤其在以下情况下使用 "maybe"：
    - 摘要缺失、稀少或模糊；
    - 研究类型无法凭题名/摘要自信判断；
    - 某个领域在概念上相关但未被明确陈述；
    - 研究可能满足一个或多个筛选领域，但确认可能需要全文筛选。
    当题名或摘要已经为纳入或排除提供清晰证据时，不要使用 "maybe"。

    #### 第 4 步：赋值 "include"
    只有在以下情况下赋值 "include"：
    - 所有或大多数关键领域编码为 "yes"；
    - 没有关键领域编码为 "no"；
    - 题名/摘要提供了足够信息支持可能相关；
    - 没有明确致命不匹配。

    #### 第 5 步：保守处理不确定性
    当在 "exclude" 和 "maybe" 之间不确定时，选择 "maybe"。
    当在 "maybe" 和 "include" 之间不确定时，选择 "maybe"，除非相关性很强。

    ### 主要原因代码规则
    使用以下 primary reason codes：
    {_reason_code_lines(dims, language='zh')}
    primary_reason_code 编码规则：
    - 如果 decision = include，使用 NA。
    - 如果 decision = maybe，使用最重要的未解决领域代码。
    - 如果 decision = maybe 且多个关键领域不明确，仅当没有一个未解决领域明显最重要时，使用 M_MULTIPLE。
    - 如果 decision = exclude，选择最重要的单一明确排除理由。
    - 对于 exclude 决定，primary reason 必须基于题名/摘要中的明确证据，而不是基于信息缺失。

    ### 置信度指引
    使用：
    - high = 题名/摘要为该决定提供清晰证据，几乎没有歧义。
    - medium = 决定有合理支持，但一个关键方面仍有一定歧义。
    - low = 决定依赖稀少、不完整、间接或较弱的题名/摘要信息。

    ### 输出要求
    只以 CSV 返回结果。
    不要在 CSV 前后添加任何说明。
    不要将 CSV 包裹在 markdown code fences 中。
    不要返回 markdown table。
    严格使用以下列顺序：
    {','.join(headers)}

    ### 允许值：
    {_allowed_values_lines(dims)}
    CSV 格式规则：
    - 返回有效 CSV。
    - 必要时为字段加引号。
    - 保持 title 不变。
    - 不要在任何字段内部添加换行。
    - 除非对应输入值确实缺失，否则不要留空必填字段。
    - rationale 必须是一句简短句子。

    ### 字段规则
    - record_id 必须从输入记录中精确复制。
    - title 必须从输入记录中精确复制。
    - decision 只能使用允许值之一。
    - confidence 只能使用允许值之一。
    - 所有 D 列都只能使用 yes、no 或 unclear。
    - primary_reason_code 必须遵循 PRIMARY REASON CODE RULE。
    - rationale 必须是一句简短句子。
    - 除非对应输入值确实缺失，否则不要留空任何必填字段。

    ### RATIONALE 规则
    rationale 必须：
    - 是一句简短句子；
    - 说明最强纳入信号，或关键排除/不确定原因；
    - 只依赖题名和摘要；
    - 不提及题名/摘要以外的元数据；
    - 不提及筛选 prompt 或 codebook；
    - 不使用多个句子；
    - 当 decision = maybe 时，明确命名主要未解决领域；
    - 当 decision = exclude 时，明确命名致命不匹配。

    ### 输出前最终检查
    生成最终 CSV 前，确保：
    1. 每一行都已被筛选；
    2. 没有跳过任何行；
    3. 所有输出值都严格遵循允许标签；
    4. title 保持不变；
    5. 输出是有效 CSV；
    6. 输出不是 markdown table；
    7. 输出没有被包裹在 code fences 中；
    8. 只有当题名/摘要中存在明确致命不匹配证据时才使用 "exclude"；
    9. 具有可能相关性但信息未解决的记录标记为 "maybe"，而不是 "exclude"；
    10. 缺失、不完整、间接或模糊的信息绝不作为排除的唯一依据。
    """.strip()
    return dedent(prompt)
