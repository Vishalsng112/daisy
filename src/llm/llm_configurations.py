"""
Legacy module for backward compatibility.
Configuration moved to llm_model_registry.py, base models moved to llm_base_models.py.
"""

from src.llm_model_registry import (
    ProviderInfo,
    PROVIDER_BEDROCK,
    PROVIDER_OPENAI,
    PROVIDER_OPENROUTER,
    PROVIDER_DEBUG,
    ModelInfo,
    MODEL_REGISTRY,
)

from .llm_base_models import (
    LLMCostSnapshot,
    LLM,
    LLM_EMPTY_RESPONSE_STUB,
    LLM_COST_STUB_RESPONSE_IS_LIKE_DAFNYBENCH,
    LLM_COST_STUB_RESPONSE_IS_PROMPT,
    LLM_YIELD_RESULT_WITHOUT_API,
)

__all__ = [
    "ProviderInfo",
    "PROVIDER_BEDROCK",
    "PROVIDER_OPENAI",
    "PROVIDER_OPENROUTER",
    "PROVIDER_DEBUG",
    "ModelInfo",
    "MODEL_REGISTRY",
    "LLMCostSnapshot",
    "LLM",
    "LLM_EMPTY_RESPONSE_STUB",
    "LLM_COST_STUB_RESPONSE_IS_LIKE_DAFNYBENCH",
    "LLM_COST_STUB_RESPONSE_IS_PROMPT",
    "LLM_YIELD_RESULT_WITHOUT_API",
]