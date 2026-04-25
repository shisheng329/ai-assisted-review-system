from __future__ import annotations

import json
from textwrap import dedent


def normalize_dimensions(dimensions: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for idx, dimension in enumerate(dimensions, start=1):
        normalized.append(
            {
                "id": f"D{idx}",
                "name": dimension.get("name", "").strip(),
                "description": dimension.get("description", "").strip(),
            }
        )
    return normalized


def build_prompt_components(
    review_topic: str,
    inclusion_criteria: str,
    exclusion_criteria: str,
    dimensions: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "review_topic": review_topic.strip(),
        "inclusion_criteria": inclusion_criteria.strip(),
        "exclusion_criteria": exclusion_criteria.strip(),
        "dimensions": normalize_dimensions(dimensions),
    }


def build_screening_prompt(
    review_topic: str,
    inclusion_criteria: str,
    exclusion_criteria: str,
    dimensions: list[dict[str, str]],
) -> str:
    components = build_prompt_components(review_topic, inclusion_criteria, exclusion_criteria, dimensions)
    dims = components["dimensions"]
    dim_lines = "\n".join(f"{item['id']} = {item['name']}: {item['description']}" for item in dims)
    exclude_codes = ["NA = no exclusion reason because included", "E1 = not a primary empirical eligible study", "E2 = wrong thematic scope"]
    maybe_codes = ["M1 = unclear study type", "M2 = multiple critical domains unclear"]
    for idx, item in enumerate(dims, start=1):
        exclude_codes.append(f"E{idx + 2} = Inconsistent with the requirements of screening dimension {item['id']}.")
        maybe_codes.append(f"M{idx + 2} = The relevance to the requirements of screening dimension {item['id']} is unclear.")
    csv_headers = ["record_id", "title", "decision", "confidence", *[item["id"] for item in dims], "primary_reason_code", "rationale"]
    allowed_dimension_values = "\n".join(f"{item['id']}: yes / no / unclear" for item in dims)
    maybe_domain_hint = ", ".join(item["id"] for item in dims) if dims else "D1"
    decision_dimension_list = ", ".join(item["id"] for item in dims) if dims else "D1"
    prompt = f"""
    ROLE SETTING
    You are a researcher conducting rigorous title-and-abstract screening for a scoping review. Your task is to screen each record row by row and return one structured screening decision per record.

    CORE SCREENING PRINCIPLE
    This is a recall-oriented title-and-abstract pre-screening task. The goal is to avoid false exclusion of potentially relevant studies. Exclude only when the title and/or abstract provides explicit evidence of a fatal mismatch. Do not exclude merely because a criterion is not fully specified. Absence of evidence is not sufficient for exclusion. If a record appears plausibly relevant but one or more critical domains remain unclear from the title/abstract alone, assign "maybe" rather than "exclude". Use "include" only when the core criteria are clearly or mostly satisfied and there is no explicit fatal mismatch.

    NON-NEGOTIABLE RULES
    1. Use only the title and abstract for screening decisions.
    2. Do not infer unsupported information beyond the title or abstract.
    3. Screen every row. Do not skip any record.
    4. If the abstract is missing or empty, screen conservatively based on the title only.
    5. If information is insufficient to make a clear exclusion, use "maybe" rather than "exclude".
    6. Evaluate each screening domain independently before making the final decision.
    7. A single positive signal in one domain does not override a clear mismatch in another critical domain.
    8. Use "exclude" only when the title and/or abstract clearly indicates that at least one critical criterion is not satisfied.
    9. Use "include" only when the title/abstract provides enough evidence to justify likely relevance.
    10. Use "maybe" whenever the study appears plausibly relevant but one or more critical domains remain unresolved.
    11. Do not treat missing detail as evidence of exclusion.
    12. Do not use metadata outside title/abstract.

    REVIEW TOPIC
    Inclusion criteria: {components["inclusion_criteria"]}
    {components["review_topic"]}
    Exclusion criteria: {components["exclusion_criteria"]}

    IMPORTANT INTERPRETATION RULES FOR PRE-SCREENING
    {dim_lines}

    DECISION LOGIC
    Apply the decision logic in this order:
    Step 1. Code every screening domain independently: {decision_dimension_list}
    Step 2. Check for explicit fatal mismatches only.
    Step 3. Assign "maybe" when there is no explicit fatal mismatch, the study is plausibly relevant, but one or more critical domains remain unclear from title/abstract alone.
    Step 4. Assign "include" only when the core criteria are clearly or mostly satisfied, there is no explicit fatal mismatch, and the title/abstract provides enough information to justify likely relevance.

    PRIMARY REASON CODE RULE
    Use the following primary reason codes:
    {chr(10).join(exclude_codes)}
    {chr(10).join(maybe_codes)}
    If decision = include, use NA.
    If decision = maybe, use the most important unresolved domain code.
    If decision = exclude, select the one most core exclusion reason code.

    CONFIDENCE GUIDANCE
    high = title/abstract gives clear evidence for the decision with little or no ambiguity
    medium = decision is reasonably supported but one critical aspect remains somewhat ambiguous
    low = decision depends on sparse, incomplete, or weak title/abstract information

    OUTPUT REQUIREMENTS
    Return the results as CSV only. Do not add any commentary before or after the CSV.
    For records labelled "maybe", the rationale should explicitly name the main unresolved domain ({maybe_domain_hint}).
    Use exactly this column order:
    {", ".join(csv_headers)}

    Allowed values:
    decision: include / exclude / maybe
    confidence: high / medium / low
    {allowed_dimension_values}

    Rationale rule:
    rationale must be one concise sentence stating the strongest inclusion signal or the key exclusion/uncertainty reason, using only information from the title and abstract.
    Do not mention metadata outside title/abstract.
    Do not use multiple sentences.
    Do not mention the screening prompt or codebook.
    State the most important reason supporting the decision.

    FINAL VALIDATION CHECK BEFORE OUTPUT
    Before producing the final CSV, ensure that:
    1. every row has been screened
    2. no row is skipped
    3. all output values follow the allowed labels exactly
    4. the title is kept unchanged
    5. the output is valid CSV
    6. exclude is used only when there is explicit evidence of a fatal mismatch in the title/abstract
    7. records with plausible relevance but unresolved information are labelled maybe, not exclude
    """.strip()
    return dedent(prompt)


def build_ai_expansion_prompt(review_topic: str, key_points: str, inclusion_criteria: str, exclusion_criteria: str, dimensions: list[dict[str, str]]) -> str:
    dim_lines = "\n".join(f"{item['id']}: {item['name']} - {item['description']}" for item in normalize_dimensions(dimensions))
    return dedent(
        f"""
        Expand the following screening draft into polished academic English for title-and-abstract screening.
        Translate every user-provided item into English before polishing it. This includes the review topic, research key points, inclusion criteria, exclusion criteria, screening dimension names, and screening dimension descriptions.
        The output must contain English only, except for unavoidable proper nouns. Do not leave Chinese phrases in DIMENSION_RULES.
        Return plain text with these headings exactly:
        REVIEW_TOPIC
        INCLUSION_CRITERIA
        EXCLUSION_CRITERIA
        DIMENSION_RULES
        Under DIMENSION_RULES, return one line per dimension using this exact format:
        D1: English dimension name - English dimension description

        Review topic:
        {review_topic}

        Research key points:
        {key_points}

        Inclusion criteria draft:
        {inclusion_criteria}

        Exclusion criteria draft:
        {exclusion_criteria}

        Screening dimensions:
        {dim_lines}
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
        Translate only the JSON values below into Chinese for a literature-screening prompt.
        Return valid JSON only, with exactly these keys:
        review_topic, inclusion_criteria, exclusion_criteria, dimensions.
        dimensions must be an array of objects with id, name, and description. Keep each id unchanged.
        Do not translate the keys. Do not add markdown fences or commentary.

        Source JSON:
        {json.dumps(components, ensure_ascii=False)}
        """
    ).strip()


def build_chinese_screening_prompt(components: dict[str, object], translated: dict[str, object]) -> str:
    dims = translated.get("dimensions") if isinstance(translated, dict) else None
    if not isinstance(dims, list):
        dims = components.get("dimensions", [])
    normalized_dims = []
    for idx, item in enumerate(dims if isinstance(dims, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        normalized_dims.append(
            {
                "id": str(item.get("id") or f"D{idx}").strip(),
                "name": str(item.get("name") or "").strip(),
                "description": str(item.get("description") or "").strip(),
            }
        )
    if not normalized_dims:
        normalized_dims = normalize_dimensions(components.get("dimensions", []))  # type: ignore[arg-type]

    dim_lines = "\n".join(f"{item['id']} = {item['name']}: {item['description']}" for item in normalized_dims)
    decision_dimension_list = ", ".join(item["id"] for item in normalized_dims) if normalized_dims else "D1"
    maybe_domain_hint = decision_dimension_list
    exclude_codes = ["NA = 纳入文献无排除原因", "E1 = 不是符合条件的原始实证研究", "E2 = 主题范围不匹配"]
    maybe_codes = ["M1 = 研究类型不明确", "M2 = 多个关键领域不明确"]
    for idx, item in enumerate(normalized_dims, start=1):
        exclude_codes.append(f"E{idx + 2} = 不符合筛选维度 {item['id']} 的要求。")
        maybe_codes.append(f"M{idx + 2} = 与筛选维度 {item['id']} 要求的相关性不明确。")
    headers = ["record_id", "title", "decision", "confidence", *[item["id"] for item in normalized_dims], "primary_reason_code", "rationale"]
    allowed_dimension_values = "\n".join(f"{item['id']}: yes / no / unclear" for item in normalized_dims)

    review_topic = str(translated.get("review_topic") or components.get("review_topic") or "").strip()
    inclusion = str(translated.get("inclusion_criteria") or components.get("inclusion_criteria") or "").strip()
    exclusion = str(translated.get("exclusion_criteria") or components.get("exclusion_criteria") or "").strip()

    prompt = f"""
    角色设定
    你是一名研究者，正在为范围综述进行严格的题名与摘要筛选。你的任务是逐行筛选每条记录，并为每条记录返回一个结构化筛选决策。

    核心筛选原则
    这是一个以召回率为导向的题名与摘要预筛选任务。目标是避免错误排除潜在相关研究。只有当题名和/或摘要提供明确证据表明存在致命不匹配时，才排除文献。不要仅因为某项标准未被完整说明而排除。缺少证据本身不足以作为排除依据。如果记录看起来可能相关，但一个或多个关键领域仅凭题名/摘要仍不清楚，应标记为 "maybe"，而不是 "exclude"。只有当核心标准明确或基本满足，且不存在明确致命不匹配时，才使用 "include"。

    不可协商规则
    1. 仅使用题名和摘要做出筛选决策。
    2. 不要推断题名或摘要之外没有支持的信息。
    3. 筛选每一行，不得跳过任何记录。
    4. 如果摘要缺失或为空，仅基于题名保守筛选。
    5. 如果信息不足以明确排除，使用 "maybe" 而不是 "exclude"。
    6. 在做出最终决策前，独立评估每个筛选领域。
    7. 某一领域的单个积极信号不能抵消另一关键领域的明确不匹配。
    8. 只有当题名和/或摘要清楚表明至少一个关键标准未被满足时，才使用 "exclude"。
    9. 只有当题名/摘要提供足够证据支持可能相关时，才使用 "include"。
    10. 当研究看起来可能相关但一个或多个关键领域仍未解决时，使用 "maybe"。
    11. 不要把细节缺失视为排除证据。
    12. 不要使用题名/摘要之外的元数据。

    综述主题
    纳入标准：{inclusion}
    {review_topic}
    排除标准：{exclusion}

    预筛选重要解释规则
    {dim_lines}

    决策逻辑
    按以下顺序应用决策逻辑：
    步骤 1. 独立编码每个筛选领域：{decision_dimension_list}
    步骤 2. 仅检查明确的致命不匹配。
    步骤 3. 当不存在明确致命不匹配、研究可能相关，但一个或多个关键领域仅凭题名/摘要仍不清楚时，标记为 "maybe"。
    步骤 4. 只有当核心标准明确或基本满足、不存在明确致命不匹配，且题名/摘要提供足够信息支持可能相关时，才标记为 "include"。

    主要原因代码规则
    使用以下主要原因代码：
    {chr(10).join(exclude_codes)}
    {chr(10).join(maybe_codes)}
    如果 decision = include，使用 NA。
    如果 decision = maybe，使用最重要的未解决领域代码。
    如果 decision = exclude，选择一个最核心的排除原因代码。

    置信度说明
    high = 题名/摘要为该决策提供清晰证据，几乎没有歧义
    medium = 决策有合理支持，但一个关键方面仍有一定歧义
    low = 决策依赖稀疏、不完整或较弱的题名/摘要信息

    输出要求
    仅返回 CSV 结果。不要在 CSV 前后添加任何评论。
    对于标记为 "maybe" 的记录，rationale 应明确指出主要未解决领域（{maybe_domain_hint}）。
    严格使用以下列顺序：
    {", ".join(headers)}

    允许值：
    decision: include / exclude / maybe
    confidence: high / medium / low
    {allowed_dimension_values}

    理由规则：
    rationale 必须是一个简洁句子，仅基于题名和摘要说明最强的纳入信号或关键排除/不确定原因。
    不要提及题名/摘要之外的元数据。
    不要使用多个句子。
    不要提及筛选 prompt 或代码本。
    说明支持该决策的最重要原因。

    输出前最终验证
    在生成最终 CSV 前，确保：
    1. 每一行都已筛选
    2. 没有跳过任何行
    3. 所有输出值严格遵循允许标签
    4. title 保持不变
    5. 输出是有效 CSV
    6. 仅当题名/摘要中有明确致命不匹配证据时才使用 exclude
    7. 对于可能相关但信息未解决的记录，标记为 maybe，而不是 exclude
    """.strip()
    return dedent(prompt)
