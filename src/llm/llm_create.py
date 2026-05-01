from .llm_configurations import (
    LLM,
    MODEL_REGISTRY,
    LLM_COST_STUB_RESPONSE_IS_PROMPT,
    LLM_COST_STUB_RESPONSE_IS_LIKE_DAFNYBENCH,
    LLM_YIELD_RESULT_WITHOUT_API,
)
from .llm_open_ai import OpenAI_LLM
from .llm_amazon_bedrock import AmazonBedrock_LLM
from .llm_openrounter import OpenRouter_LLM


def create_llm(name: str, model: str, **kwargs) -> LLM:
    if model not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model}")

    info = MODEL_REGISTRY[model]

    if info.provider.name == "openai":
        return OpenAI_LLM(name, info, **kwargs)

    if info.provider.name == "bedrock":
        return AmazonBedrock_LLM(name, info, **kwargs)

    if info.provider.name == "openrouter":
        return OpenRouter_LLM(name, info, **kwargs)

    if info.provider.name == "debug":
        if info.model_id == "cost_stub_almost_real":
            return LLM_COST_STUB_RESPONSE_IS_PROMPT(name, info)
        elif info.model_id == "cost_stub_response_dafnybench":
            return LLM_COST_STUB_RESPONSE_IS_LIKE_DAFNYBENCH(name, info)
        elif info.model_id == "without_api":
            return LLM_YIELD_RESULT_WITHOUT_API(name, info)
        else:
            raise RuntimeError("Invalid Options for debug provider")
    raise RuntimeError("No valid option provided")
