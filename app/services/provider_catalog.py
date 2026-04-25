from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    provider_name: str
    transport: str
    base_url: str
    default_models: tuple[str, ...]
    headers_strategy: str = "bearer"
    extra_headers: dict[str, str] = field(default_factory=dict)


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        key="zhipu",
        provider_name="智谱 BigModel",
        transport="openai_compatible",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_models=("GLM-5.1", "GLM-4.5", "GLM-4-Flash"),
    ),
    ProviderSpec(
        key="longcat",
        provider_name="LongCat",
        transport="anthropic_compatible",
        base_url="https://api.longcat.chat/anthropic",
        default_models=("LongCat-Flash-Chat", "LongCat-Chat"),
        headers_strategy="anthropic_api_key",
        extra_headers={"anthropic-version": "2023-06-01"},
    ),
    ProviderSpec(
        key="openai",
        provider_name="OpenAI",
        transport="openai_compatible",
        base_url="https://api.openai.com/v1",
        default_models=("gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"),
    ),
    ProviderSpec(
        key="anthropic",
        provider_name="Anthropic",
        transport="anthropic_compatible",
        base_url="https://api.anthropic.com",
        default_models=("claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"),
        headers_strategy="anthropic_api_key",
        extra_headers={"anthropic-version": "2023-06-01"},
    ),
    ProviderSpec(
        key="deepseek",
        provider_name="DeepSeek",
        transport="openai_compatible",
        base_url="https://api.deepseek.com/v1",
        default_models=("deepseek-chat", "deepseek-reasoner"),
    ),
    ProviderSpec(
        key="qwen",
        provider_name="通义千问 DashScope",
        transport="openai_compatible",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_models=("qwen-max", "qwen-plus", "qwen-turbo"),
    ),
    ProviderSpec(
        key="moonshot",
        provider_name="Kimi Moonshot",
        transport="openai_compatible",
        base_url="https://api.moonshot.cn/v1",
        default_models=("moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"),
    ),
    ProviderSpec(
        key="doubao",
        provider_name="豆包 Volcano Ark",
        transport="openai_compatible",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_models=("doubao-seed-1-6-thinking", "doubao-seed-1-6-flash", "doubao-pro-32k"),
    ),
    ProviderSpec(
        key="baichuan",
        provider_name="百川",
        transport="openai_compatible",
        base_url="https://api.baichuan-ai.com/v1",
        default_models=("Baichuan4-Turbo", "Baichuan4-Air"),
    ),
    ProviderSpec(
        key="minimax",
        provider_name="MiniMax",
        transport="openai_compatible",
        base_url="https://api.minimax.chat/v1",
        default_models=("MiniMax-Text-01", "abab6.5s-chat"),
    ),
    ProviderSpec(
        key="gemini",
        provider_name="Gemini",
        transport="openai_compatible",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_models=("gemini-2.5-flash", "gemini-2.5-pro"),
    ),
    ProviderSpec(
        key="groq",
        provider_name="Groq",
        transport="openai_compatible",
        base_url="https://api.groq.com/openai/v1",
        default_models=("llama-3.3-70b-versatile", "qwen-qwq-32b", "deepseek-r1-distill-llama-70b"),
    ),
    ProviderSpec(
        key="siliconflow",
        provider_name="SiliconFlow",
        transport="openai_compatible",
        base_url="https://api.siliconflow.cn/v1",
        default_models=("Qwen/Qwen3-32B", "deepseek-ai/DeepSeek-V3", "THUDM/GLM-4-9B-Chat"),
    ),
)


def list_provider_specs() -> list[ProviderSpec]:
    return list(PROVIDER_SPECS)


def get_provider_spec(key_or_name: str | None = None, base_url: str | None = None) -> ProviderSpec | None:
    normalized_name = (key_or_name or "").strip().lower()
    normalized_base_url = (base_url or "").strip().lower()

    for spec in PROVIDER_SPECS:
        if normalized_name in {spec.key.lower(), spec.provider_name.lower()}:
            return spec

    if "bigmodel" in normalized_name or "zhipu" in normalized_name or "open.bigmodel.cn" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "zhipu")
    if "longcat" in normalized_name or "longcat.chat" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "longcat")
    if "anthropic" in normalized_name or "/anthropic" in normalized_base_url or "api.anthropic.com" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "anthropic")
    if "openai" in normalized_name or "api.openai.com" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "openai")
    if "deepseek" in normalized_name or "api.deepseek.com" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "deepseek")
    if "dashscope" in normalized_name or "aliyuncs.com/compatible-mode" in normalized_base_url or "qwen" in normalized_name:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "qwen")
    if "moonshot" in normalized_name or "kimi" in normalized_name or "moonshot.cn" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "moonshot")
    if "volc" in normalized_name or "doubao" in normalized_name or "ark.cn-beijing.volces.com" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "doubao")
    if "baichuan" in normalized_name or "baichuan-ai.com" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "baichuan")
    if "minimax" in normalized_name or "minimax.chat" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "minimax")
    if "gemini" in normalized_name or "generativelanguage.googleapis.com" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "gemini")
    if "groq" in normalized_name or "api.groq.com" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "groq")
    if "siliconflow" in normalized_name or "api.siliconflow.cn" in normalized_base_url:
        return next(spec for spec in PROVIDER_SPECS if spec.key == "siliconflow")
    return None
